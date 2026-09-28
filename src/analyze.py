"""Rebuild the retail portfolio from the original workbook. Python 3.11+."""
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def prepare(raw):
    required = ['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country']
    if list(raw.columns) != required:
        raise ValueError(f'Expected columns {required}; got {list(raw.columns)}')
    duplicate = raw.duplicated()
    d = raw.loc[~duplicate].copy()
    for col in ['InvoiceNo', 'StockCode', 'Country']:
        d[col] = d[col].astype('string').str.strip()
    d['Description'] = d.Description.astype('string').str.strip().fillna('Unknown description')
    d['CustomerID'] = d.CustomerID.astype('Int64').astype('string')
    d['InvoiceDate'] = pd.to_datetime(d.InvoiceDate, errors='coerce')
    cancel = d.InvoiceNo.str.upper().str.startswith('C')
    d['ExclusionReason'] = np.select([
        d.InvoiceDate.isna(), d.UnitPrice.isna() | (d.UnitPrice <= 0),
        d.Quantity.isna() | (d.Quantity == 0), cancel & (d.Quantity > 0)
    ], ['Invalid date', 'Nonpositive or missing price', 'Zero or missing quantity', 'Cancellation with positive quantity'], default='')
    excluded = d[d.ExclusionReason != ''].copy()
    d = d[d.ExclusionReason == ''].drop(columns='ExclusionReason').copy()
    d['LineValue'] = d.Quantity * d.UnitPrice
    d['GrossSales'] = d.LineValue.clip(lower=0)
    d['Credits'] = -d.LineValue.clip(upper=0)
    d['NetSales'] = d.LineValue
    d['Month'] = d.InvoiceDate.dt.strftime('%Y-%m')
    d['IsSale'] = d.Quantity > 0
    d['IsMerchandise'] = d.StockCode.str.fullmatch(r'\d{5}[A-Za-z]*').fillna(False)
    audit = {
        'raw_rows': len(raw), 'duplicate_rows_removed': int(duplicate.sum()),
        'excluded_rows_after_dedup': len(excluded), 'included_rows': len(d),
        'missing_customer_rows_raw': int(raw.CustomerID.isna().sum()),
        'raw_signed_value': float((raw.Quantity * raw.UnitPrice).sum()),
        'duplicate_signed_value': float((raw.loc[duplicate, 'Quantity'] * raw.loc[duplicate, 'UnitPrice']).sum()),
        'excluded_signed_value': float((excluded.Quantity * excluded.UnitPrice).sum()),
        'exclusions': {str(k): int(v) for k, v in excluded.ExclusionReason.value_counts().items()},
    }
    return d, excluded, audit


def aggregate(d, keys):
    totals = d.groupby(keys, dropna=False).agg(GrossSales=('GrossSales', 'sum'), Credits=('Credits', 'sum'), NetSales=('NetSales', 'sum')).reset_index()
    orders = d[d.IsSale].groupby(keys).InvoiceNo.nunique().rename('Orders').reset_index()
    return totals.merge(orders, on=keys, how='left').fillna({'Orders': 0})


def customers(d):
    s = d[d.IsSale & d.CustomerID.notna()].copy()
    snapshot = d.InvoiceDate.max().normalize() + pd.Timedelta(days=1)
    rfm = s.groupby('CustomerID').agg(LastPurchase=('InvoiceDate', 'max'), Frequency=('InvoiceNo', 'nunique'), Monetary=('GrossSales', 'sum')).reset_index()
    rfm['Recency'] = (snapshot - rfm.LastPurchase.dt.normalize()).dt.days
    # Fixed, explainable thresholds; no arbitrary tie-breaking in quantile bins.
    rfm['Segment'] = np.select([
        (rfm.Recency <= 30) & (rfm.Frequency >= 5),
        (rfm.Recency <= 90) & (rfm.Frequency >= 2),
        (rfm.Recency <= 30) & (rfm.Frequency == 1),
        (rfm.Recency > 90) & (rfm.Frequency >= 2)
    ], ['Active frequent', 'Active repeat', 'Recent one-time', 'Lapsed repeat'], default='Other customers')
    first = s.groupby('CustomerID').InvoiceDate.min().dt.to_period('M')
    s['Cohort'] = s.CustomerID.map(first)
    s['ActivityMonth'] = s.InvoiceDate.dt.to_period('M')
    s['MonthIndex'] = (s.ActivityMonth.dt.year - s.Cohort.dt.year) * 12 + s.ActivityMonth.dt.month - s.Cohort.dt.month
    counts = s.groupby(['Cohort', 'MonthIndex']).CustomerID.nunique()
    sizes = counts.xs(0, level='MonthIndex')
    last_full = d.InvoiceDate.max().to_period('M') - 1
    rows = []
    for cohort, size in sizes.items():
        for age in range(13):
            observed = cohort + age <= last_full
            n = int(counts.get((cohort, age), 0)) if observed else None
            rows.append({'Cohort': str(cohort), 'MonthIndex': age, 'CohortSize': int(size), 'Customers': n, 'Retention': n / size if observed else None})
    return rfm, pd.DataFrame(rows), str(snapshot.date())


def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso'))


def run(source, output=ROOT):
    for folder in ['data/processed', 'reports', 'dashboard']:
        (output / folder).mkdir(parents=True, exist_ok=True)
    print('Reading workbook...', flush=True)
    raw = pd.read_excel(source)
    d, excluded, audit = prepare(raw)
    print('Building customer and sales models...', flush=True)
    monthly = aggregate(d, ['Month'])
    country = aggregate(d, ['Country']).sort_values('NetSales', ascending=False)
    rfm, cohort, snapshot = customers(d)
    segments = rfm.groupby('Segment').agg(Customers=('CustomerID', 'size'), GrossSales=('Monetary', 'sum')).reset_index()
    products = aggregate(d[d.IsMerchandise], ['StockCode']).sort_values('NetSales', ascending=False)
    labels = d[d.IsMerchandise].groupby('StockCode').Description.agg(lambda x: x.mode().iloc[0])
    products['Description'] = products.StockCode.map(labels)
    monthly_country = aggregate(d, ['Month', 'Country'])
    product_slices = aggregate(d[d.IsMerchandise], ['Month', 'Country', 'StockCode'])
    gross, credits, net = [float(d[c].sum()) for c in ['GrossSales', 'Credits', 'NetSales']]
    orders = int(d.loc[d.IsSale, 'InvoiceNo'].nunique())
    kpi = {'gross_sales': gross, 'credits': credits, 'net_sales': net, 'orders': orders,
           'gross_aov': gross / orders, 'credit_value_ratio': credits / gross,
           'known_customers': len(rfm), 'repeat_customer_share': float((rfm.Frequency >= 2).mean()),
           'identified_sales_share': float(d.loc[d.IsSale & d.CustomerID.notna(), 'GrossSales'].sum() / gross),
           'uk_net_share': float(country.loc[country.Country == 'United Kingdom', 'NetSales'].sum() / net),
           'top10_customer_gross_share': float(rfm.nlargest(10, 'Monetary').Monetary.sum() / rfm.Monetary.sum()),
           'start': str(d.InvoiceDate.min().date()), 'end': str(d.InvoiceDate.max().date()), 'rfm_snapshot': snapshot}
    audit['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    audit['net_sales_without_dedup'] = net + audit['duplicate_signed_value']
    assert len(raw) == audit['duplicate_rows_removed'] + len(excluded) + len(d)
    assert abs(audit['raw_signed_value'] - audit['duplicate_signed_value'] - audit['excluded_signed_value'] - net) < .01
    assert abs(gross - credits - net) < .01
    # Required for summing distinct invoice counts across dashboard month/country groups.
    assert d[d.IsSale].groupby('InvoiceNo').Month.nunique().max() == 1
    assert d[d.IsSale].groupby('InvoiceNo').Country.nunique().max() == 1
    for name, frame in [('transactions', d), ('excluded_records', excluded), ('monthly_sales', monthly), ('country_sales', country), ('products', products), ('customer_segments', rfm), ('cohort_retention', cohort), ('segment_summary', segments)]:
        frame.to_csv(output / 'data/processed' / f'{name}.csv', index=False)
    with sqlite3.connect(output / 'data/retail.sqlite') as con:
        d.to_sql('transactions', con, if_exists='replace', index=False)
        rfm.to_sql('customer_segments', con, if_exists='replace', index=False)
        cohort.to_sql('cohort_retention', con, if_exists='replace', index=False)
        con.execute('CREATE INDEX IF NOT EXISTS idx_invoice ON transactions(InvoiceNo)')
        con.execute('CREATE INDEX IF NOT EXISTS idx_month_country ON transactions(Month, Country)')
        sql_checks = pd.read_sql_query('SELECT SUM(GrossSales) gross, SUM(Credits) credits, SUM(NetSales) net, COUNT(DISTINCT CASE WHEN IsSale=1 THEN InvoiceNo END) orders FROM transactions', con).iloc[0]
        assert abs(sql_checks['net'] - net) < .01 and sql_checks['orders'] == orders
        sql_text = '\n'.join(line for line in (ROOT / 'sql/analysis.sql').read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('--'))
        for index, statement in enumerate(sql_text.split(';')):
            if statement.strip():
                pd.read_sql_query(statement, con).to_csv(output / 'reports' / f'sql_result_{index+1:02}.csv', index=False)
    audit['validation'] = 'Passed: row accounting, monetary bridge, gross less credits, invoice grain, SQL/Python KPI agreement'
    (output / 'reports/metrics.json').write_text(json.dumps(kpi, indent=2), encoding='utf-8')
    (output / 'reports/data_quality.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    payload = {'kpi': kpi, 'audit': audit, 'sales': records(monthly_country), 'products': records(product_slices),
               'labels': labels.to_dict(), 'segments': records(segments), 'cohorts': records(cohort)}
    template = (ROOT / 'dashboard/template.html').read_text(encoding='utf-8')
    html = template.replace('__DATA__', json.dumps(payload, separators=(',', ':')).replace('</', '<\\/'))
    (output / 'dashboard/index.html').write_text(html, encoding='utf-8')
    write_report(output, kpi, audit, monthly, country, products, rfm)
    print(json.dumps(kpi, indent=2), flush=True)
    print(audit['validation'], flush=True)
    return kpi


def write_report(output, k, a, monthly, country, products, rfm):
    full = monthly[monthly.Month < k['end'][:7]]
    peak = full.loc[full.NetSales.idxmax()]
    top = products.iloc[0]
    lapsed = int((rfm.Segment == 'Lapsed repeat').sum())
    report = f'''# Online Retail: revenue, customers and credit activity

Independent portfolio case study. Historical transactions, {k['start']} to {k['end']}. All monetary values are GBP. This is a demonstration, not paid client work.

## Business question
Where should an ecommerce operator focus stock planning, customer retention and credit investigation?

## Findings
- Net sales were **£{k['net_sales']:,.0f}**, comprising £{k['gross_sales']:,.0f} in positive sales less £{k['credits']:,.0f} in negative-quantity credits. Gross order value averaged **£{k['gross_aov']:,.2f}** across {k['orders']:,} purchase invoices.
- The UK contributed **{k['uk_net_share']:.1%}** of net sales. Protecting the core market should be considered before broad international expansion.
- **{peak.Month}** was the highest observed complete month, at **£{peak.NetSales:,.0f}** net sales. Use this historical pattern to plan peak-period stock and fulfilment. One year cannot establish recurring seasonality.
- **{k['repeat_customer_share']:.1%}** of {k['known_customers']:,} identified purchasing customers placed at least two orders. The ten largest identified customers represented **{k['top10_customer_gross_share']:.1%}** of identified gross sales. Review account concentration and service needs.
- There are **{lapsed:,} lapsed repeat customers** under the stated rules. Test a small reactivation campaign and compare incremental orders against a holdout group.
- The leading merchandise code by net sales is **{top.StockCode}**, {top.Description}, at **£{top.NetSales:,.0f}**. Review credits and stock availability alongside sales before prioritising replenishment.
- Credits represent **{k['credit_value_ratio']:.1%}** of positive sales value. Investigate the largest credit invoices. This ratio is not a matched return rate and includes corrections and cancellations.

## Decisions and measurement
| Proposed action | Evidence | How to evaluate |
|---|---|---|
| Prepare peak-period inventory | Monthly sales pattern | Stockout frequency and fulfilment time, requiring new operational data |
| Contact lapsed repeat accounts | More than 90 days since purchase and at least two historical orders | Incremental purchase rate versus a random holdout |
| Review large credit events | Negative-quantity transaction values | Classify causes and monitor credit value by cause |
| Improve customer identification | Only {k['identified_sales_share']:.1%} of gross sales has a CustomerID | Share of future sales tied to a valid customer ID |

These are proposed actions. No revenue uplift, savings or causal impact has been measured.

## Data quality and reconciliation
{a['raw_rows']:,} source rows = {a['duplicate_rows_removed']:,} exact duplicate rows removed + {a['excluded_rows_after_dedup']:,} excluded rows + {a['included_rows']:,} analytical rows.

Signed raw value £{a['raw_signed_value']:,.2f} − duplicate value £{a['duplicate_signed_value']:,.2f} − excluded value £{a['excluded_signed_value']:,.2f} = analytical net sales £{k['net_sales']:,.2f}.

Exact duplicates are assumed to be repeated ingestion records. The file has no unique line identifier, so this cannot be proven. Keeping duplicates would produce net sales of £{a['net_sales_without_dedup']:,.2f}. No outliers are trimmed. Missing customer IDs remain in sales metrics but are excluded from customer analysis.

## Metric definitions and limits
- Sales include positive-price, nonzero-quantity lines with valid dates. Positive-quantity C-prefixed cancellations are excluded if present. Negative quantities are credits irrespective of invoice prefix.
- Net sales = signed quantity × unit price. Gross sales = positive line values. Credits = absolute negative line values. These are analytical transaction values, not audited accounting revenue or profit.
- Orders count distinct invoices with a positive sale. Gross AOV = gross sales / those orders. Customer repeat share = customers with two or more purchase invoices / all identified purchasing customers in this observation window.
- Overall metrics include postage and other positive-price non-product lines. Product rankings restrict StockCode to five digits with optional letter suffixes. This operational heuristic can omit legitimate special-code items.
- RFM snapshot is {k['rfm_snapshot']}. Recency uses calendar days. Frequency counts purchase invoices. Monetary is gross purchase value before credits. Segments use recency and frequency; monetary is retained for value prioritisation.
- Segment rule order: Active frequent (recency ≤30, frequency ≥5), Active repeat (recency ≤90, frequency ≥2), Recent one-time (recency ≤30, frequency =1), Lapsed repeat (recency >90, frequency ≥2), otherwise Other customers.
- Cohorts use first **observed** purchase, not verified acquisition. Retention is the share returning in each specific later month. Not-yet-observed cells and all December 2011 activity are blank. Month zero is 100% for complete cohorts. Early cohorts can include existing customers.
- December 2011 ends on December 9. Do not interpret its fall against November as a full-month decline. Customer metrics use the full observed period and are not lifetime value or churn estimates.
- No product cost, advertising spend, traffic, stock or delivery data is supplied. Profit, ROAS, conversion rate and stockout impact cannot be calculated.

## Reproduction and evidence
Run `python src/analyze.py --input "data/Online Retail.xlsx"`. See `README.md`, `sql/analysis.sql`, `reports/data_quality.json`, and the executed notebook. The offline dashboard can be opened directly from `dashboard/index.html`.

## Source
Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Source information: https://archive.ics.uci.edu/dataset/352/online-retail. CC BY 4.0. Changes: duplicates removed, eligibility rules applied, and derived analysis added. Local source SHA-256: `{a['source_sha256']}`.
'''
    (output / 'reports/CASE_STUDY.md').write_text(report, encoding='utf-8')
    copy = f'''# Upwork portfolio text

## Title
Ecommerce Sales Analysis, SQL & Customer Retention Dashboard

## Role
Data Analyst

## Description
I analysed 541,909 historical retail transaction rows to understand sales, credit activity and repeat purchasing. I built a reproducible Python cleaning pipeline, a SQLite database, SQL analyses and an interactive dashboard. The analysis identified £{k['net_sales']/1e6:.2f}M in net sales and a {k['repeat_customer_share']:.1%} repeat-purchase share among identified customers. Deliverables include customer segments, cohort retention, product rankings and practical recommendations. Independent portfolio project using the public UCI Online Retail dataset.

## Skills
Python, SQL, Data Cleaning, Data Visualization, Customer Segmentation

## Attachments
1. `reports/portfolio_cover.png` as the cover image.
2. `reports/dashboard_preview.png` as a dashboard example.
3. `reports/CASE_STUDY.md` for the full reasoning and limitations.
4. A repository link if you choose to publish the project. No public link has been created.

## Short walkthrough
Start with the business question. Show the data-quality bridge, then use the country and month filters. Explain gross sales versus net sales and credits. Show the customer segments and cohort matrix, including unavailable future periods. Finish with one recommended retention experiment and how its outcome would be measured.
'''
    (output / 'reports/UPWORK_PORTFOLIO.md').write_text(copy, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'data/Online Retail.xlsx')
    args = parser.parse_args()
    run(args.input)
