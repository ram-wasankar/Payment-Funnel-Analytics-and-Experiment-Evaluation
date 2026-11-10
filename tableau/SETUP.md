# Tableau dashboard setup

Run the three Python modules in the README first. Connect Tableau Desktop or Public to `results/cohorts.csv` as a text file. Set `cohort_week` to Date and all counts to Number (whole). One row is week × arm × customer segment × merchant segment. Keep those dimensions available as filters.

## Calculated fields

```text
Conversion = SUM([converted]) / SUM([customers])
Submission = SUM([submitted]) / SUM([customers])
Abandonment = SUM([abandoned]) / SUM([customers])
Authorization Failure = IF SUM([submitted]) > 0 THEN SUM([auth_failed]) / SUM([submitted]) END
Retry Uptake = IF SUM([auth_failed]) > 0 THEN SUM([retried]) / SUM([auth_failed]) END
Refunds per Exposed = SUM([refunds]) / SUM([customers])
Conditional Refund Rate = IF SUM([converted]) > 0 THEN SUM([refunds]) / SUM([converted]) END
```

Use aggregate ratios rather than averaging cohort percentages. Format as percentages with two decimal places.

## Minimal dashboard

Use a 1200 × 760 dashboard, white background, charcoal text, muted gray for control, teal for treatment, and amber for guardrail uncertainty.

1. **KPI row:** conversion, authorization failure, retry uptake, abandonment, refunds per exposed. Show arm labels and denominator definitions.
2. **Cohort trend:** week on Columns, Conversion on Rows, variant on Color. Include customer and merchant segment filters.
3. **Failure/retry breakdown:** merchant segment on Rows; Authorization Failure and Retry Uptake as separate measures. Do not imply mutually exclusive stages: a retried checkout can also convert.
4. **Experiment detail:** connect `results/segments.csv` for exploratory segment lift with lower/upper CI fields. Label it exploratory. Keep global SRM/guardrail results from metrics.json visible as a text note; filtering descriptive charts must not silently recalculate the global experiment decision.

The checked-in [dashboard preview](../results/dashboard.svg) is generated with Matplotlib. The CSVs are ready for Tableau, and this file specifies the worksheets; no `.twb` or published Tableau dashboard is included.
