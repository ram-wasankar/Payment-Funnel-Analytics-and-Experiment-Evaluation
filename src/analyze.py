import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare, norm


ALPHA = .05
REFUND_MARGIN = .005  # absolute refunds / randomized customer


def checkout_facts(customers, events):
    flags = pd.crosstab(events.checkout_id, events.event_type)
    facts = customers.merge(flags, left_on="checkout_id", right_index=True, how="left", validate="one_to_one")
    for name in ["payment_submitted", "authorization_failed", "payment_retried", "payment_captured", "refund_issued"]:
        facts[name] = (facts.get(name, pd.Series(0, index=facts.index)).fillna(0) > 0).astype(int)
    facts["cohort_week"] = pd.to_datetime(facts.assigned_at, utc=True).dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    facts["abandoned"] = 1 - facts.payment_captured
    return facts


def difference(control, treatment):
    a, b = np.asarray(control, dtype=float), np.asarray(treatment, dtype=float)
    if min(len(a), len(b)) < 2:
        raise ValueError("At least two observations per arm required")
    delta = float(b.mean() - a.mean())
    se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
    z = norm.ppf(.975)
    return {"control": float(a.mean()), "treatment": float(b.mean()), "difference": delta,
            "ci95": [float(delta - z * se), float(delta + z * se)],
            "p_value": float(2 * norm.sf(abs(delta / se))) if se else (1.0 if delta == 0 else 0.0)}


def sample_size(baseline=.70, mde=.03, power=.80, alpha=.05):
    if not (0 < baseline < baseline + mde < 1 and 0 < power < 1 and 0 < alpha < 1):
        raise ValueError("Invalid planning assumptions")
    p1, p2 = baseline, baseline + mde
    pooled = (p1 + p2) / 2
    top = norm.ppf(1-alpha/2)*math.sqrt(2*pooled*(1-pooled)) + norm.ppf(power)*math.sqrt(p1*(1-p1)+p2*(1-p2))
    return math.ceil(top**2 / mde**2)


def adjusted_effect(facts):
    # Pre-treatment covariates only. No retries/authorization/refunds as predictors.
    treatment = (facts.variant == "treatment").astype(float).to_numpy()
    prior = facts.prior_conversion.to_numpy()
    merchant = pd.get_dummies(facts.merchant_segment, drop_first=True, dtype=float).to_numpy()
    x = np.column_stack([np.ones(len(facts)), treatment, prior-prior.mean(),
                         (facts.customer_segment == "returning").astype(float), merchant])
    if len(facts) <= x.shape[1] or np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError("Adjustment design must have full rank and residual degrees of freedom")
    y = facts.payment_captured.to_numpy(dtype=float)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    bread = np.linalg.inv(x.T @ x)
    meat = x.T @ ((residual**2)[:, None] * x)
    cov = bread @ meat @ bread * len(y)/(len(y)-x.shape[1])
    se = float(np.sqrt(cov[1, 1]))
    effect = float(beta[1])
    return {"difference": effect, "standard_error": se,
            "ci95": [effect-1.95996398454*se, effect+1.95996398454*se],
            "method": "OLS linear probability model, HC1 robust covariance",
            "covariates": ["prior_conversion", "customer_segment", "merchant_segment"]}


def allocation_check(control, treatment):
    if min(control, treatment) <= 0:
        return {"p_value": 0.0, "pass": False}
    p = float(chisquare([control, treatment]).pvalue)
    return {"p_value": p, "pass": p >= .001, "threshold": .001}


def summary(facts):
    control, treatment = [facts[facts.variant == arm] for arm in ["control", "treatment"]]
    conversion = difference(control.payment_captured, treatment.payment_captured)
    refunds = difference(control.refund_issued, treatment.refund_issued)
    allocation = allocation_check(len(control), len(treatment))
    planned = sample_size()
    guardrail = refunds["ci95"][1] < REFUND_MARGIN
    ready = allocation["pass"] and min(len(control), len(treatment)) >= planned
    return {"data": "seeded synthetic checkout events", "unit": "randomized customer; one checkout each",
            "customers": len(facts), "arms": {"control": len(control), "treatment": len(treatment)},
            "conversion": conversion, "adjusted_conversion": adjusted_effect(facts),
            "refunds_per_exposed_customer": {**refunds, "noninferiority_margin": REFUND_MARGIN,
                                             "upper_bound_below_margin": guardrail},
            "sample_ratio": allocation,
            "power_plan": {"baseline": .70, "absolute_mde": .03, "power": .80, "alpha": .05,
                           "required_per_arm": planned, "met": min(len(control), len(treatment)) >= planned},
            "decision": "candidate for a live experiment" if ready and guardrail and conversion["ci95"][0] > 0 else "inconclusive; retain control",
            "decision_scope": "Offline demonstration only; raw ITT conversion is primary, adjusted effect is supporting evidence."}


def export_cohorts(facts):
    keys = ["cohort_week", "variant", "customer_segment", "merchant_segment"]
    out = facts.groupby(keys).agg(customers=("customer_id", "size"), submitted=("payment_submitted", "sum"),
        converted=("payment_captured", "sum"), auth_failed=("authorization_failed", "sum"),
        retried=("payment_retried", "sum"), refunds=("refund_issued", "sum")).reset_index()
    out["abandoned"] = out.customers - out.converted
    return out


def main():
    customers, events = [pd.read_csv(f"data/{name}.csv") for name in ["customers", "events"]]
    facts = checkout_facts(customers, events)
    result = summary(facts)
    result["input_sha256"] = {name: hashlib.sha256(Path(f"data/{name}.csv").read_bytes()).hexdigest() for name in ["customers", "events"]}
    Path("results").mkdir(exist_ok=True)
    Path("results/metrics.json").write_text(json.dumps(result, indent=2)+"\n")
    facts.to_csv("results/checkout_facts.csv", index=False)
    export_cohorts(facts).to_csv("results/cohorts.csv", index=False)
    segments = []
    for dimension in ["customer_segment", "merchant_segment"]:
        for value, group in facts.groupby(dimension):
            a, b = [group[group.variant == arm] for arm in ["control", "treatment"]]
            d = difference(a.payment_captured, b.payment_captured)
            segments.append({"dimension": dimension, "segment": value, "control_n": len(a), "treatment_n": len(b),
                             "lift_pp": d["difference"]*100, "lower_pp": d["ci95"][0]*100, "upper_pp": d["ci95"][1]*100})
    pd.DataFrame(segments).to_csv("results/segments.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
