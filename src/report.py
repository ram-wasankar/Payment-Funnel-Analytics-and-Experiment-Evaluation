import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main():
    m = json.loads(Path("results/metrics.json").read_text())
    facts = pd.read_csv("results/checkout_facts.csv")
    segments = pd.read_csv("results/segments.csv")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "svg.hashsalt": "payment-funnel"})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), facecolor="#fbfbf8")
    colors = ["#8897a6", "#1d615b"]
    for ax in axes:
        ax.set_facecolor("#fbfbf8")
    stages = ["Started", "Submitted", "Captured"]
    for i, variant in enumerate(["control", "treatment"]):
        group = facts[facts.variant == variant]
        counts = [len(group), group.payment_submitted.sum(), group.payment_captured.sum()]
        axes[0].barh([j+i*.32 for j in range(3)], [100*x/len(group) for x in counts],
                     height=.28, label=variant.title(), color=colors[i])
    axes[0].set_yticks([j+.16 for j in range(3)], stages)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 110)
    axes[0].set_xlabel("% of randomized customers")
    axes[0].set_title("01 / Checkout funnel", loc="left", pad=18)
    axes[0].legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -.25), ncol=2)
    axes[1].errorbar(segments.lift_pp, range(len(segments)),
                     xerr=[segments.lift_pp-segments.lower_pp, segments.upper_pp-segments.lift_pp],
                     fmt="o", color=colors[1], capsize=4)
    axes[1].set_yticks(range(len(segments)), segments.segment.str.title())
    axes[1].invert_yaxis()
    axes[1].axvline(0, color="#b3b3b3", linewidth=1, linestyle="--")
    axes[1].set_xlabel("Conversion lift, pp · 95% CI")
    axes[1].set_title("02 / Exploratory segments", loc="left", pad=18)
    names = ["Raw conversion", "Adjusted conversion", "Refunds / exposed"]
    rows = [m["conversion"], m["adjusted_conversion"], m["refunds_per_exposed_customer"]]
    for i, row in enumerate(rows):
        d, (lo, hi) = row["difference"]*100, [x*100 for x in row["ci95"]]
        axes[2].errorbar(d, i, xerr=[[d-lo], [hi-d]], fmt="o", capsize=4,
                         color=colors[1] if i < 2 else "#ab653d")
    axes[2].axvline(0, color="#b3b3b3", linewidth=1, linestyle="--")
    axes[2].set_yticks(range(3), names)
    axes[2].invert_yaxis()
    axes[2].set_xlabel("Treatment − control, pp · 95% CI")
    axes[2].set_title("03 / Lift and guardrail", loc="left", pad=18)
    fig.suptitle("PAYMENT FUNNEL / EXPERIMENT REVIEW", x=.02, ha="left", fontsize=18, fontweight="bold")
    fig.text(.02, .87, "8,000 synthetic customers · Fixed-horizon analysis · Seed 20261110", color="#666")
    fig.tight_layout(rect=[0, .02, 1, .83], w_pad=3)
    fig.savefig("results/dashboard.svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    conv, adjusted, refund = rows
    p = m["power_plan"]
    out = f"""# Experiment results

**Decision: retain control.** Conversion improves in this synthetic run, but the refund guardrail does not establish non-inferiority. A positive conversion result alone is not enough to recommend rollout.

![Payment funnel experiment review](dashboard.svg)

## Scorecard

| Metric | Result |
| --- | ---: |
| Randomized customers | {m['customers']:,} |
| Control / treatment | {m['arms']['control']:,} / {m['arms']['treatment']:,} |
| Control conversion | {conv['control']:.2%} |
| Treatment conversion | {conv['treatment']:.2%} |
| Absolute conversion lift | +{conv['difference']*100:.2f} pp |
| Conversion 95% CI | [{conv['ci95'][0]*100:.2f}, {conv['ci95'][1]*100:.2f}] pp |
| Two-sided conversion p-value | {conv['p_value']:.6f} |
| Adjusted conversion lift | +{adjusted['difference']*100:.2f} pp |
| Adjusted 95% CI | [{adjusted['ci95'][0]*100:.2f}, {adjusted['ci95'][1]*100:.2f}] pp |
| Sample-ratio mismatch p-value | {m['sample_ratio']['p_value']:.4f} |
| Refunds / exposed, control | {refund['control']:.2%} |
| Refunds / exposed, treatment | {refund['treatment']:.2%} |
| Refund lift 95% CI | [{refund['ci95'][0]*100:.2f}, {refund['ci95'][1]*100:.2f}] pp |
| Refund non-inferiority margin | +0.50 pp |

## Interpretation

The primary intention-to-treat outcome is capture per randomized customer. All assigned customers remain in the denominator, including those who never submit payment. Treatment changes retry uptake from 30% to 65% after an initial decline in the generator. No other direct treatment effect is encoded.

Regression adjustment uses prior conversion propensity and customer/merchant segments. The treatment coefficient is an adjusted risk difference from an OLS linear probability model with HC1 robust standard errors. It supports the primary unadjusted analysis; it does not establish which segment caused the effect. Segment intervals in the chart are exploratory, unadjusted for multiplicity, and not interaction tests.

SRM passes the predeclared 0.001 threshold. Planning assumed 70% baseline conversion, a 3 pp absolute minimum detectable effect, 80% power, two-sided alpha 0.05, and equal allocation: **{p['required_per_arm']:,} customers per arm**. Both arms exceed that target. This is prospective planning under the stated assumptions, not observed post-hoc power; refund safety may require a larger sample.

The upper bound on refund deterioration is {refund['ci95'][1]*100:.2f} pp, above the 0.50 pp margin. Refund non-inferiority therefore remains inconclusive. This does not prove treatment is harmful. The rule uses the upper endpoint of a two-sided 95% interval, a conservative one-sided 97.5% bound.

## Data and measurement

- Seed: 20261110; 8,000 customers; one checkout per randomized customer; 28 days of assignments.
- All data is generated. Results demonstrate the analysis, not a production payment improvement.
- Every captured payment has complete simulated follow-up: refunds occur five days later or never. No right censoring is introduced.
- Abandonment means started without capture, including terminal authorization failures. It is not an inferred browser exit.
- Authorization failure is a checkout-level flag. Retry rate uses checkouts with a failure as denominator, not all event rows.
- Prior conversion is a synthetic pre-treatment propensity feature, not an observed historical conversion rate from a separate dataset.
- Randomization is independent by customer. Real repeated checkouts would need customer-level aggregation or clustered inference.

## Evidence and reproduction

Run `python -m src.generate`, `python -m src.analyze`, then `python -m src.report` from the repository root. Regenerated CSVs feed Tableau and are ignored by Git to keep the repository small.

See [machine-readable results](metrics.json), [test verification](verification.json), [methodology](../METHODS.md), and [Tableau setup](../tableau/SETUP.md). Input SHA-256 digests in metrics.json identify the exact generated CSVs.

The shared SQL aggregation and window queries are executed against SQLite for parity checks. PostgreSQL schema/cohort SQL is supplied for deployment; a native PostgreSQL server and Tableau Desktop were not available in this verification environment.
"""
    Path("results/RESULTS.md").write_text(out)


if __name__ == "__main__":
    main()
