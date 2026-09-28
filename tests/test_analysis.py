import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze import prepare, customers


class AnalysisTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame([
            ['1','12345','Item',2,'2011-01-01',10,1,'UK'],
            ['1','12345','Item',2,'2011-01-01',10,1,'UK'],
            ['C2','12345','Item',-1,'2011-01-02',10,1,'UK'],
            ['3','12345','Item',1,'2011-02-01',5,None,'UK'],
            ['4','12345','Item',1,'2011-02-02',0,1,'UK'],
            ['C5','12345','Item',1,'2011-02-03',5,1,'UK'],
            ['6','12345','Item',1,'2011-03-09',10,2,'UK'],
        ], columns=['InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country'])

    def test_credits_duplicates_and_anonymous_sales(self):
        d, excluded, a = prepare(self.sample())
        self.assertEqual(len(d), 4)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(a['duplicate_rows_removed'], 1)
        self.assertEqual(d.GrossSales.sum(), 35)
        self.assertEqual(d.Credits.sum(), 10)
        self.assertEqual(d.NetSales.sum(), 25)
        self.assertEqual(d[d.CustomerID.isna()].GrossSales.sum(), 5)
        self.assertEqual(a['raw_signed_value']-a['duplicate_signed_value']-a['excluded_signed_value'], 25)

    def test_cohort_zero_vs_unobserved(self):
        d, _, _ = prepare(self.sample())
        rfm, c, snapshot = customers(d)
        self.assertEqual(len(rfm), 2)
        self.assertEqual(snapshot, '2011-03-10')
        jan = c[c.Cohort == '2011-01'].set_index('MonthIndex')
        self.assertEqual(jan.loc[0, 'Retention'], 1)
        self.assertEqual(jan.loc[1, 'Retention'], 0)
        self.assertTrue(pd.isna(jan.loc[2, 'Retention']))
        self.assertEqual(int(rfm.loc[rfm.CustomerID == '1', 'Frequency'].iloc[0]), 1)

    def test_segment_boundaries(self):
        rows = []
        snapshot = pd.Timestamp('2011-12-10')
        for customer, recency, frequency in [(1,30,5),(2,31,5),(3,90,2),(4,91,2),(5,30,1),(6,31,1),(7,1,1)]:
            for order in range(frequency):
                rows.append([f'{customer}-{order}', '12345', 'Item', 1, snapshot-pd.Timedelta(days=recency), 10, customer, 'UK'])
        raw = pd.DataFrame(rows, columns=self.sample().columns)
        d, _, _ = prepare(raw)
        rfm, _, _ = customers(d)
        actual = rfm.set_index('CustomerID').Segment.to_dict()
        self.assertEqual(actual, {'1':'Active frequent','2':'Active repeat','3':'Active repeat','4':'Lapsed repeat','5':'Recent one-time','6':'Other customers','7':'Recent one-time'})


if __name__ == '__main__':
    unittest.main()
