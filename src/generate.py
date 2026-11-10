from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20261110


def generate(n=8000, seed=SEED):
    """One randomized customer and one checkout per row. No real payment data."""
    rng = np.random.default_rng(seed)
    customers, events = [], []
    for i in range(n):
        customer = f"customer_{i:05d}"
        checkout = f"checkout_{i:05d}"
        variant = "treatment" if rng.random() < .5 else "control"
        returning = int(rng.random() < .6)
        merchant = str(rng.choice(["retail", "digital", "services"]))
        prior = float(rng.beta(4, 2))
        start = pd.Timestamp("2026-10-01", tz="UTC") + pd.Timedelta(seconds=int(rng.integers(28 * 86400)))
        customers.append((customer, checkout, variant, "returning" if returning else "new",
                          merchant, round(prior, 6), start.isoformat()))

        def event(kind, seconds, attempt=0):
            events.append((f"event_{len(events):06d}", checkout, kind,
                           (start + pd.Timedelta(seconds=seconds)).isoformat(), attempt))

        event("checkout_started", 0)
        if rng.random() > .88 + .06 * returning:
            continue
        event("payment_submitted", 12)
        approval = .51 + .39 * prior + .05 * returning + (.035 if merchant == "digital" else 0)
        authorized = rng.random() < approval
        event("authorization_succeeded" if authorized else "authorization_failed", 14, 1)
        if not authorized and rng.random() < (.65 if variant == "treatment" else .30):
            event("payment_retried", 25, 2)
            authorized = rng.random() < .48
            event("authorization_succeeded" if authorized else "authorization_failed", 27, 2)
        if authorized:
            event("payment_captured", 30)
            if rng.random() < .025:
                event("refund_issued", 5 * 86400)
    columns = ["customer_id", "checkout_id", "variant", "customer_segment", "merchant_segment",
               "prior_conversion", "assigned_at"]
    return (pd.DataFrame(customers, columns=columns),
            pd.DataFrame(events, columns=["event_id", "checkout_id", "event_type", "event_at", "attempt"]))


def main():
    Path("data").mkdir(exist_ok=True)
    customers, events = generate()
    customers.to_csv("data/customers.csv", index=False)
    events.to_csv("data/events.csv", index=False)
    print(f"Generated {len(customers):,} customers and {len(events):,} events (seed {SEED}).")


if __name__ == "__main__":
    main()
