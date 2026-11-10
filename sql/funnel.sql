-- Shared relational logic: PostgreSQL production target; SQLite parity tested locally.
-- Count at checkout grain first: retries must not inflate conversion denominators.
CREATE VIEW checkout_facts AS
SELECT c.customer_id, c.checkout_id, c.variant, c.customer_segment,
       c.merchant_segment, c.prior_conversion, c.assigned_at,
       MAX(CASE WHEN e.event_type='payment_submitted' THEN 1 ELSE 0 END) AS submitted,
       MAX(CASE WHEN e.event_type='payment_captured' THEN 1 ELSE 0 END) AS converted,
       MAX(CASE WHEN e.event_type='authorization_failed' THEN 1 ELSE 0 END) AS auth_failed,
       MAX(CASE WHEN e.event_type='payment_retried' THEN 1 ELSE 0 END) AS retried,
       MAX(CASE WHEN e.event_type='refund_issued' THEN 1 ELSE 0 END) AS refunded
FROM customers c LEFT JOIN events e ON c.checkout_id=e.checkout_id
GROUP BY c.customer_id, c.checkout_id, c.variant, c.customer_segment,
         c.merchant_segment, c.prior_conversion, c.assigned_at;

CREATE VIEW authorization_sequence AS
SELECT checkout_id, event_at, event_type, attempt,
       ROW_NUMBER() OVER (PARTITION BY checkout_id ORDER BY event_at, event_id) AS authorization_number,
       LAG(event_type) OVER (PARTITION BY checkout_id ORDER BY event_at, event_id) AS previous_result
FROM events
WHERE event_type IN ('authorization_failed','authorization_succeeded');

SELECT variant, customer_segment, merchant_segment,
       COUNT(*) AS customers, SUM(converted) AS captured,
       1.0*SUM(converted)/COUNT(*) AS conversion,
       1.0*SUM(auth_failed)/NULLIF(SUM(submitted),0) AS checkout_auth_failure_rate,
       1.0*SUM(retried)/NULLIF(SUM(auth_failed),0) AS retry_after_failure_rate,
       1.0*SUM(refunded)/COUNT(*) AS refunds_per_exposed,
       1.0*SUM(1-converted)/COUNT(*) AS abandonment
FROM checkout_facts GROUP BY variant, customer_segment, merchant_segment;
