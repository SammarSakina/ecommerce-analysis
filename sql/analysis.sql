-- SQLite. Values are GBP. Analytical eligibility is applied by src/analyze.py.
-- 1. Reconcile sales and credits without discarding cancellations.
SELECT ROUND(SUM(GrossSales),2) AS GrossSales,
       ROUND(SUM(Credits),2) AS Credits,
       ROUND(SUM(NetSales),2) AS NetSales,
       COUNT(DISTINCT CASE WHEN IsSale=1 THEN InvoiceNo END) AS Orders,
       ROUND(SUM(GrossSales)/NULLIF(COUNT(DISTINCT CASE WHEN IsSale=1 THEN InvoiceNo END),0),2) AS GrossAOV
FROM transactions;

-- 2. Compare complete months only. Latest calendar month is conservatively excluded.
WITH monthly AS (
 SELECT Month, SUM(NetSales) AS NetSales FROM transactions
 WHERE Month < (SELECT MAX(Month) FROM transactions) GROUP BY Month
), changes AS (
 SELECT *, LAG(NetSales) OVER (ORDER BY Month) AS PriorMonthSales FROM monthly
)
SELECT Month, ROUND(NetSales,2) AS NetSales,
       ROUND(100.0*(NetSales-PriorMonthSales)/NULLIF(PriorMonthSales,0),2) AS MoMPercent
FROM changes ORDER BY Month;

-- 3. Markets ranked by net value; value ratio is not a matched return rate.
SELECT Country, ROUND(SUM(NetSales),2) AS NetSales,
       ROUND(100.0*SUM(NetSales)/(SELECT SUM(NetSales) FROM transactions),2) AS NetSalesSharePercent,
       ROUND(100.0*SUM(Credits)/NULLIF(SUM(GrossSales),0),2) AS CreditValuePercent
FROM transactions GROUP BY Country ORDER BY NetSales DESC;

-- 4. Product ranking uses the documented merchandise-code heuristic.
SELECT StockCode, ROUND(SUM(GrossSales),2) AS GrossSales,
       ROUND(SUM(Credits),2) AS Credits, ROUND(SUM(NetSales),2) AS NetSales
FROM transactions WHERE IsMerchandise=1 GROUP BY StockCode ORDER BY NetSales DESC LIMIT 15;

-- 5. Repeat purchasing from invoice grain (not number of line items).
WITH customers AS (
 SELECT CustomerID, COUNT(DISTINCT InvoiceNo) AS Orders
 FROM transactions WHERE IsSale=1 AND CustomerID IS NOT NULL GROUP BY CustomerID
)
SELECT COUNT(*) AS IdentifiedCustomers, SUM(CASE WHEN Orders>=2 THEN 1 ELSE 0 END) AS RepeatCustomers,
       ROUND(100.0*SUM(CASE WHEN Orders>=2 THEN 1 ELSE 0 END)/COUNT(*),2) AS RepeatSharePercent
FROM customers;

-- 6. Segment size and historical gross value.
SELECT Segment, COUNT(*) AS Customers, ROUND(SUM(Monetary),2) AS GrossSales,
       ROUND(AVG(Recency),1) AS AverageRecencyDays
FROM customer_segments GROUP BY Segment ORDER BY GrossSales DESC;

-- 7. Largest negative events for investigation; do not silently trim them.
SELECT InvoiceNo, Country, MIN(InvoiceDate) AS InvoiceDate,
       ROUND(SUM(Credits),2) AS CreditValue
FROM transactions WHERE Credits>0 GROUP BY InvoiceNo, Country ORDER BY CreditValue DESC LIMIT 20;

-- 8. Month-one retention for cohorts with a complete observed follow-up month.
SELECT Cohort, CohortSize, Customers AS MonthOneCustomers, ROUND(100.0*Retention,2) AS RetentionPercent
FROM cohort_retention WHERE MonthIndex=1 AND Retention IS NOT NULL ORDER BY Cohort;
