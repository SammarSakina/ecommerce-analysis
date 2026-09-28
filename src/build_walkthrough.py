"""Create an executed, standard-library-only notebook and portfolio cover."""
from pathlib import Path
import contextlib
import io
import json
import os

ROOT = Path(__file__).resolve().parents[1]


def build_notebook():
    blocks = [
        ('markdown', '# Online Retail: from raw transactions to business decisions\n\nIndependent portfolio analysis using Chen (2015), UCI Online Retail, CC BY 4.0. Currency: GBP. See the case study for source citation, assumptions and limitations.\n\n**Objective:** quantify sales, credit exposure and repeat purchasing, then propose measurable business actions.'),
        ('code', "from pathlib import Path\nimport json, sqlite3\nimport pandas as pd\nROOT = Path.cwd() if (Path.cwd() / 'reports/metrics.json').exists() else Path.cwd().parent\nk = json.loads((ROOT / 'reports/metrics.json').read_text())\naudit = json.loads((ROOT / 'reports/data_quality.json').read_text())\nprint('Observation window:', k['start'], 'to', k['end'])\nprint('Source SHA-256:', audit['source_sha256'])"),
        ('markdown', '## 1. Audit the cleaning decisions\n\nThe pipeline removes exact duplicates as an assumption, excludes nonpositive prices and invalid transactional records, and retains negative quantities as credits. Anonymous purchases remain in sales totals. No outliers are trimmed. The source workbook is not modified.'),
        ('code', "print(json.dumps(audit, indent=2))\nassert audit['raw_rows'] == audit['duplicate_rows_removed'] + audit['excluded_rows_after_dedup'] + audit['included_rows']\nassert abs(audit['raw_signed_value'] - audit['duplicate_signed_value'] - audit['excluded_signed_value'] - k['net_sales']) < .01\nprint('Row and monetary reconciliation passed.')"),
        ('markdown', '## 2. Reconcile the headline metrics in SQL\n\nNet sales is signed transaction value, not profit. Gross AOV divides positive sales by distinct purchase invoices. A credit-value ratio does not establish a matched product-return rate.'),
        ('code', "con = sqlite3.connect(ROOT / 'data/retail.sqlite')\nquery = '''SELECT SUM(GrossSales) AS GrossSales, SUM(Credits) AS Credits, SUM(NetSales) AS NetSales, COUNT(DISTINCT CASE WHEN IsSale=1 THEN InvoiceNo END) AS Orders FROM transactions'''\nheadline = pd.read_sql_query(query, con)\nprint(headline.round(2).to_string(index=False))\nassert abs(headline.NetSales.iloc[0] - k['net_sales']) < .01\nprint('SQL agrees with Python.')"),
        ('markdown', '## 3. Compare complete months\n\nThe last month ends on 9 December 2011 and is excluded from the growth comparison. One year of activity is insufficient to establish a recurring seasonal effect.'),
        ('code', "monthly = pd.read_csv(ROOT / 'data/processed/monthly_sales.csv')\ncomplete = monthly[monthly.Month < k['end'][:7]].copy()\ncomplete['MoMPercent'] = complete.NetSales.pct_change() * 100\nprint(complete[['Month','NetSales','MoMPercent']].round(2).to_string(index=False))"),
        ('markdown', '## 4. Identify market and product concentration\n\nOverall sales include postage and special codes. Product rankings apply the five-digit stock-code heuristic, so the two totals have different scopes.'),
        ('code', "markets = pd.read_csv(ROOT / 'data/processed/country_sales.csv')\nproducts = pd.read_csv(ROOT / 'data/processed/products.csv')\nprint(markets.head(8).round(2).to_string(index=False))\nprint(products[['StockCode','Description','NetSales']].head(8).round(2).to_string(index=False))"),
        ('markdown', '## 5. Understand repeat purchasing and target groups\n\nCustomer analysis excludes anonymous transactions. Frequency counts distinct purchase invoices, monetary value is gross spend, and recency is measured at 10 December 2011. Fixed thresholds create explainable groups; they are not a predictive churn model.'),
        ('code', "rfm = pd.read_csv(ROOT / 'data/processed/customer_segments.csv')\nsummary = rfm.groupby('Segment').agg(Customers=('CustomerID','size'), GrossSales=('Monetary','sum'))\nprint(summary.round(2).to_string())\nprint('Repeat buyer share:', f\"{(rfm.Frequency >= 2).mean():.1%}\")\nprint('Top 10 share of identified gross sales:', f\"{rfm.nlargest(10, 'Monetary').Monetary.sum()/rfm.Monetary.sum():.1%}\")"),
        ('markdown', '## 6. Distinguish zero retention from unobserved time\n\nCohorts start at first observed purchase. Missing cells are future or partial periods, not zero. December 2011 is excluded from retention follow-up. Existing customers at the beginning of the dataset may appear in the first cohort.'),
        ('code', "cohort = pd.read_csv(ROOT / 'data/processed/cohort_retention.csv')\nheatmap = cohort.pivot(index='Cohort',columns='MonthIndex',values='Retention')\nprint((heatmap*100).round(1).to_string(na_rep='not observed'))\nassert cohort.Retention.dropna().between(0,1).all()\ncon.close()"),
        ('markdown', '## 7. Business recommendations\n\n- Plan inventory around the observed peak period, then validate against stockout and fulfilment data.\n- Test reactivation of lapsed repeat customers using a holdout group.\n- Review large credit invoices and collect a reason code before changing return policies.\n- Improve CustomerID capture to increase the coverage of customer analysis.\n\nNo uplift has been measured. Cost, web traffic and advertising data are absent, so profit, conversion and ROAS cannot be inferred. Open `dashboard/index.html` for the interactive views and read `reports/CASE_STUDY.md` for numerical findings.'),
    ]
    namespace = {}
    cells = []
    count = 0
    os.chdir(ROOT)
    for kind, source in blocks:
        cell = {'cell_type': kind, 'metadata': {}, 'source': source.splitlines(keepends=True), 'id': f'cell-{len(cells):02}'}
        if kind == 'code':
            count += 1
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                exec(compile(source, f'notebook-cell-{count}', 'exec'), namespace)
            cell.update(execution_count=count, outputs=[{'output_type': 'stream', 'name': 'stdout', 'text': stream.getvalue().splitlines(keepends=True)}])
        cells.append(cell)
    notebook = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python', 'version': '3.11'}}, 'nbformat': 4, 'nbformat_minor': 5}
    (ROOT / 'notebooks/02_portfolio_analysis.ipynb').write_text(json.dumps(notebook, indent=1), encoding='utf-8')
    print(f'Notebook: {count} code cells executed successfully')


def build_cover():
    from PIL import Image, ImageDraw, ImageFont
    k = json.loads((ROOT / 'reports/metrics.json').read_text())
    monthly = __import__('pandas').read_csv(ROOT / 'data/processed/monthly_sales.csv')
    image = Image.new('RGB', (1600, 1200), '#102d3a')
    draw = ImageDraw.Draw(image)
    fonts = Path('C:/Windows/Fonts')
    def font(size, bold=False):
        return ImageFont.truetype(str(fonts / ('segoeuib.ttf' if bold else 'segoeui.ttf')), size)
    draw.rectangle((80, 90, 145, 99), fill='#6ed3c9')
    draw.text((80, 120), 'ECOMMERCE ANALYTICS', font=font(25, True), fill='#6ed3c9')
    draw.text((76, 180), 'From transactions', font=font(78, True), fill='white')
    draw.text((76, 275), 'to business decisions.', font=font(78, True), fill='white')
    draw.text((80, 390), 'Python  /  SQL  /  Customer retention  /  Interactive dashboard', font=font(27), fill='#c1d1d9')
    cards = [('NET SALES', f"£{k['net_sales']/1e6:.2f}M"), ('PURCHASE ORDERS', f"{k['orders']:,}"), ('IDENTIFIED REPEAT BUYERS', f"{k['repeat_customer_share']:.1%}")]
    for i, (label, value) in enumerate(cards):
        x = 80+i*490
        draw.rounded_rectangle((x, 470, x+460, 665), radius=18, fill='#1c3e4c')
        draw.text((x+30, 497), label, font=font(21), fill='#b9ced5')
        draw.text((x+30, 537), value, font=font(62, True), fill='white')
    draw.text((80, 725), 'MONTHLY NET SALES', font=font(24, True), fill='white')
    draw.text((80, 767), 'December 2010–November 2011 · complete months · GBP', font=font(21), fill='#b9ced5')
    full = monthly[monthly.Month < '2011-12']
    maximum = full.NetSales.max()
    for i, row in enumerate(full.itertuples()):
        x = 90+i*119
        height = int(row.NetSales / maximum*210)
        draw.rounded_rectangle((x, 1040-height, x+75, 1040), radius=6, fill='#66cfc6' if row.Month != '2011-11' else '#e7b568')
        draw.text((x+4, 1052), row.Month[5:], font=font(18), fill='#b9ced5')
    draw.text((80, 1125), 'Independent portfolio project · UCI Online Retail · Historical data', font=font(22), fill='#b9ced5')
    image.save(ROOT / 'reports/portfolio_cover.png')
    print('Portfolio cover generated')


if __name__ == '__main__':
    build_notebook()
    build_cover()
