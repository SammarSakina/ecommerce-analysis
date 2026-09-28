"""Cross-check exported outputs and a dashboard filter against SQLite."""
import json
import sqlite3
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
k = json.loads((root / 'reports/metrics.json').read_text())
with sqlite3.connect(root / 'data/retail.sqlite') as con:
    filtered = con.execute("SELECT SUM(NetSales),COUNT(DISTINCT CASE WHEN IsSale=1 THEN InvoiceNo END) FROM transactions WHERE Country='Germany' AND Month<='2011-11'").fetchone()
    assert round(filtered[0]) == 213705 and filtered[1] == 440
    integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
    assert integrity == 'ok'
for table in ['monthly_sales', 'country_sales']:
    frame = pd.read_csv(root / f'data/processed/{table}.csv')
    assert abs(frame.NetSales.sum()-k['net_sales']) < .01
cohort = pd.read_csv(root / 'data/processed/cohort_retention.csv')
assert cohort.Retention.dropna().between(0,1).all()
assert cohort.loc[cohort.Cohort=='2011-12', 'Retention'].isna().all()
assert len(list((root / 'reports').glob('sql_result_*.csv'))) == 8
print('Export checks passed: SQLite integrity, monthly/country reconciliation, cohort bounds/censoring, 8 SQL results, Germany dashboard filter.')
