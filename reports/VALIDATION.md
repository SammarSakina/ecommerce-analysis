# Validation record

- Full pipeline completed successfully on the supplied 541,909-row workbook.
- 534,129 analytical rows, 5,268 duplicate rows and 2,512 excluded rows reconcile to the input.
- Signed source value reconciles to analytical net sales through duplicate and exclusion adjustments.
- Python and SQLite agree on £9,748,131.074 net sales and 19,960 purchase invoices. Presentation uses rounded GBP values; calculations retain source precision.
- Monthly and country exports reconcile to total net sales.
- SQLite integrity check returned `ok`.
- All eight statements in `sql/analysis.sql` executed and exported result tables.
- Three synthetic tests passed: duplicate/credit/anonymous handling, observed-zero versus censored cohort periods, and segment threshold boundaries.
- Seven notebook code cells executed successfully with saved outputs.
- Browser checks passed for market filtering, complete-month selection, invalid date-range messaging, reset, customer view and methodology view. No browser console errors were observed during the market-filter check.
- Germany through November 2011 displayed £213,705 and 440 orders; independently checked against SQLite.
- Sales dashboard, cohort matrix and portfolio cover were visually reviewed. December 2011 is explicitly marked partial. Customer metrics explicitly use the full observation window.

No native Power BI report is included. The interactive dashboard is a self-contained HTML file. The source workbook, prior empty notebook and existing virtual environments are preserved.
