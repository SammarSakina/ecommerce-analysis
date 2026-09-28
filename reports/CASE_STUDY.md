# Online Retail: revenue, customers and credit activity

Independent portfolio case study. Historical transactions, 2010-12-01 to 2011-12-09. All monetary values are GBP. This is a demonstration, not paid client work.

## Business question
Where should an ecommerce operator focus stock planning, customer retention and credit investigation?

## Findings
- Net sales were **£9,748,131**, comprising £10,642,111 in positive sales less £893,980 in negative-quantity credits. Gross order value averaged **£533.17** across 19,960 purchase invoices.
- The UK contributed **84.0%** of net sales. Protecting the core market should be considered before broad international expansion.
- **2011-11** was the highest observed complete month, at **£1,456,146** net sales. Use this historical pattern to plan peak-period stock and fulfilment. One year cannot establish recurring seasonality.
- **65.6%** of 4,338 identified purchasing customers placed at least two orders. The ten largest identified customers represented **17.3%** of identified gross sales. Review account concentration and service needs.
- There are **602 lapsed repeat customers** under the stated rules. Test a small reactivation campaign and compare incremental orders against a holdout group.
- The leading merchandise code by net sales is **22423**, REGENCY CAKESTAND 3 TIER, at **£164,459**. Review credits and stock availability alongside sales before prioritising replenishment.
- Credits represent **8.4%** of positive sales value. Investigate the largest credit invoices. This ratio is not a matched return rate and includes corrections and cancellations.

## Decisions and measurement
| Proposed action | Evidence | How to evaluate |
|---|---|---|
| Prepare peak-period inventory | Monthly sales pattern | Stockout frequency and fulfilment time, requiring new operational data |
| Contact lapsed repeat accounts | More than 90 days since purchase and at least two historical orders | Incremental purchase rate versus a random holdout |
| Review large credit events | Negative-quantity transaction values | Classify causes and monitor credit value by cause |
| Improve customer identification | Only 83.5% of gross sales has a CustomerID | Share of future sales tied to a valid customer ID |

These are proposed actions. No revenue uplift, savings or causal impact has been measured.

## Data quality and reconciliation
541,909 source rows = 5,268 exact duplicate rows removed + 2,512 excluded rows + 534,129 analytical rows.

Signed raw value £9,747,747.93 − duplicate value £21,740.98 − excluded value £-22,124.12 = analytical net sales £9,748,131.07.

Exact duplicates are assumed to be repeated ingestion records. The file has no unique line identifier, so this cannot be proven. Keeping duplicates would produce net sales of £9,769,872.05. No outliers are trimmed. Missing customer IDs remain in sales metrics but are excluded from customer analysis.

## Metric definitions and limits
- Sales include positive-price, nonzero-quantity lines with valid dates. Positive-quantity C-prefixed cancellations are excluded if present. Negative quantities are credits irrespective of invoice prefix.
- Net sales = signed quantity × unit price. Gross sales = positive line values. Credits = absolute negative line values. These are analytical transaction values, not audited accounting revenue or profit.
- Orders count distinct invoices with a positive sale. Gross AOV = gross sales / those orders. Customer repeat share = customers with two or more purchase invoices / all identified purchasing customers in this observation window.
- Overall metrics include postage and other positive-price non-product lines. Product rankings restrict StockCode to five digits with optional letter suffixes. This operational heuristic can omit legitimate special-code items.
- RFM snapshot is 2011-12-10. Recency uses calendar days. Frequency counts purchase invoices. Monetary is gross purchase value before credits. Segments use recency and frequency; monetary is retained for value prioritisation.
- Segment rule order: Active frequent (recency ≤30, frequency ≥5), Active repeat (recency ≤90, frequency ≥2), Recent one-time (recency ≤30, frequency =1), Lapsed repeat (recency >90, frequency ≥2), otherwise Other customers.
- Cohorts use first **observed** purchase, not verified acquisition. Retention is the share returning in each specific later month. Not-yet-observed cells and all December 2011 activity are blank. Month zero is 100% for complete cohorts. Early cohorts can include existing customers.
- December 2011 ends on December 9. Do not interpret its fall against November as a full-month decline. Customer metrics use the full observed period and are not lifetime value or churn estimates.
- No product cost, advertising spend, traffic, stock or delivery data is supplied. Profit, ROAS, conversion rate and stockout impact cannot be calculated.

## Reproduction and evidence
Run `python src/analyze.py --input "data/Online Retail.xlsx"`. See `README.md`, `sql/analysis.sql`, `reports/data_quality.json`, and the executed notebook. The offline dashboard can be opened directly from `dashboard/index.html`.

## Source
Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Source information: https://archive.ics.uci.edu/dataset/352/online-retail. CC BY 4.0. Changes: duplicates removed, eligibility rules applied, and derived analysis added. Local source SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
