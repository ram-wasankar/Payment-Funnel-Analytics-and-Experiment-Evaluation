# Metric contract and experiment design

## Unit and horizon

The experiment randomizes customers 50/50 before checkout, with one checkout per customer. All 8,000 assigned customers are included. The generator is frozen at seed 20261110; there is one fixed-horizon analysis and no sequential peeking. Assignments span 28 days, with complete five-day refund follow-up for every capture. Synthetic arm labels are stored once in the customer table.

## Metric definitions

| Metric | Numerator | Denominator |
| --- | --- | --- |
| Conversion, primary | Customers with capture | All assigned customers |
| Submission | Customers submitting payment | All assigned customers |
| Authorization failure | Checkouts with at least one decline | Submitted checkouts |
| Retry uptake | Checkouts with a retry | Checkouts with at least one decline |
| Abandonment | Started checkouts without capture | All assigned customers |
| Refund guardrail, ITT | Customers with refund | All assigned customers |
| Conditional refund rate, descriptive | Captured checkouts refunded | Captured checkouts |

Retries can produce multiple authorization events. All outcome flags are collapsed to one row per checkout before joining dimensions. Never compute checkout conversion by dividing captures by total event count. Weekly cohorts use Monday starts in UTC; export additive counts and calculate ratios after aggregation.

## Statistical plan

- Primary estimator: treatment minus control conversion, intention to treat.
- Interval: normal approximation with unpooled sample variances; two-sided 95%. This is appropriate for the large arm counts here; sparse outcomes need a more suitable interval.
- Power: normal approximation for two independent proportions; baseline 0.70, absolute MDE 0.03, alpha 0.05, power 0.80, equal allocation; 3,554 per arm. The baseline is a planning assumption, not the observed control rate.
- SRM: chi-square goodness-of-fit against equal allocation; fail at p < 0.001. Passing does not prove assignment integrity.
- Guardrail: upper endpoint of the two-sided 95% interval for refunds per exposed customer must be below +0.005. This is a conservative non-inferiority rule. A nonsignificant refund difference is not a safety pass.
- Adjustment: OLS linear probability regression on treatment, centered pre-treatment conversion propensity, customer segment, and merchant-segment dummies. HC1 heteroskedasticity-robust covariance; no post-treatment variables. Supporting estimate only.
- Segments: exploratory risk differences and 95% intervals; no multiplicity adjustment or confirmatory subgroup claims. Regression controls for mix but does not prove heterogeneous treatment effects.
- Decision: raw conversion lower bound above zero, SRM pass, conversion planning target reached, and refund non-inferiority established. Every condition must pass.

## Scope

The generator changes retry uptake after decline from 30% to 65%; merchant/customer characteristics and a synthetic pre-treatment propensity affect approval. Refund probability conditional on capture is 2.5% in both arms. More captures can still increase refunds per exposed customer, which is why the guardrail has a different denominator from the conditional refund rate.

This is an offline portfolio study with synthetic data. It has no payment gateway, live experiment, real PII, revenue attribution model, sequential testing service, or operational deployment. PostgreSQL queries and Tableau-ready exports are included; SQLite verifies the common SQL logic locally. Tableau worksheet setup is supplied separately, without claiming an authored Tableau workbook.
