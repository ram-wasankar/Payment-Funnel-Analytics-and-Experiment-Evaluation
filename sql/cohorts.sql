-- Explicit Monday weeks and UTC avoid session-timezone changes in cohort definitions.
CREATE VIEW weekly_cohorts AS
SELECT DATE_TRUNC('week', assigned_at AT TIME ZONE 'UTC')::date AS cohort_week,
       variant, customer_segment, merchant_segment,
       COUNT(*) AS customers, SUM(submitted) AS submitted, SUM(converted) AS converted,
       SUM(auth_failed) AS auth_failed, SUM(retried) AS retried, SUM(refunded) AS refunds,
       SUM(1-converted) AS abandoned
FROM checkout_facts
GROUP BY 1,2,3,4;
