import sqlite3
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.generate import generate
from src.analyze import (allocation_check, adjusted_effect, checkout_facts, difference,
                         export_cohorts, sample_size, summary)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.customers, cls.events = generate()
        cls.facts = checkout_facts(cls.customers, cls.events)

    def test_seed_reproduces(self):
        a, b = generate(30, 7)
        c, d = generate(30, 7)
        pd.testing.assert_frame_equal(a, c)
        pd.testing.assert_frame_equal(b, d)

    def test_unique_assignment_and_event_keys(self):
        self.assertTrue(self.customers.customer_id.is_unique)
        self.assertTrue(self.customers.checkout_id.is_unique)
        self.assertTrue(self.events.event_id.is_unique)
        self.assertTrue(set(self.events.checkout_id) <= set(self.customers.checkout_id))

    def test_funnel_and_refund_invariants(self):
        f = self.facts
        self.assertTrue((f.payment_captured <= f.payment_submitted).all())
        self.assertTrue((f.payment_retried <= f.authorization_failed).all())
        self.assertTrue((f.refund_issued <= f.payment_captured).all())
        self.assertTrue((f.payment_captured + f.abandoned == 1).all())

    def test_event_times_follow_assignment(self):
        joined = self.events.merge(self.customers[["checkout_id", "assigned_at"]], on="checkout_id")
        self.assertTrue((pd.to_datetime(joined.event_at) >= pd.to_datetime(joined.assigned_at)).all())

    def test_sql_aggregation_matches_python_and_retry_order(self):
        with sqlite3.connect(":memory:") as db:
            self.customers.to_sql("customers", db, index=False)
            self.events.to_sql("events", db, index=False)
            db.executescript(Path("sql/funnel.sql").read_text())
            rows = pd.read_sql("SELECT * FROM checkout_facts ORDER BY checkout_id", db)
            expected = self.facts.sort_values("checkout_id")
            for sql, python in [("converted", "payment_captured"), ("submitted", "payment_submitted"),
                                ("auth_failed", "authorization_failed"), ("retried", "payment_retried"), ("refunded", "refund_issued")]:
                np.testing.assert_array_equal(rows[sql], expected[python])
            invalid = db.execute("SELECT COUNT(*) FROM authorization_sequence WHERE authorization_number=2 AND previous_result<>'authorization_failed'").fetchone()[0]
            self.assertEqual(invalid, 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checkout_facts").fetchone()[0], len(self.customers))

    def test_duplicate_events_do_not_inflate_conversion(self):
        facts = checkout_facts(self.customers, pd.concat([self.events, self.events], ignore_index=True))
        np.testing.assert_array_equal(facts.payment_captured, self.facts.payment_captured)

    def test_cohort_totals_reconcile(self):
        c = export_cohorts(self.facts)
        self.assertEqual(c.customers.sum(), len(self.facts))
        self.assertEqual(c.converted.sum(), self.facts.payment_captured.sum())
        self.assertTrue((c.converted + c.abandoned == c.customers).all())

    def test_difference_matches_hand_calculation(self):
        out = difference([0, 0, 1, 1], [0, 1, 1, 1])
        self.assertAlmostEqual(out["difference"], .25)
        se = np.sqrt((1/3 + .25)/4)
        self.assertAlmostEqual(out["ci95"][0], .25-norm.ppf(.975)*se)

    def test_allocation_check_catches_mismatch(self):
        self.assertTrue(allocation_check(100, 100)["pass"])
        self.assertFalse(allocation_check(900, 100)["pass"])

    def test_power_plan_and_invalid_inputs(self):
        self.assertEqual(sample_size(), 3554)
        self.assertGreater(sample_size(mde=.01), sample_size(mde=.03))
        with self.assertRaises(ValueError):
            sample_size(mde=-.01)

    def test_adjustment_recovers_known_linear_effect(self):
        f = self.facts.copy()
        f["payment_captured"] = .2 + .04*(f.variant=="treatment").astype(float) + .3*f.prior_conversion
        self.assertAlmostEqual(adjusted_effect(f)["difference"], .04, places=10)

    def test_refund_uncertainty_blocks_positive_conversion_rollout(self):
        out = summary(self.facts)
        self.assertGreater(out["conversion"]["ci95"][0], 0)
        self.assertFalse(out["refunds_per_exposed_customer"]["upper_bound_below_margin"])
        self.assertEqual(out["decision"], "inconclusive; retain control")


if __name__ == "__main__":
    unittest.main()
