"""Funnel and A/B read-out for a checkout revamp, on synthetic session data.

Illustrates the method used to evaluate the revamp: stage-by-stage funnel for
control vs variant, two-proportion z-tests with 95% CIs, the sample path as its own
funnel, and an operational guardrail (address errors -> failed freight deliveries).
The numbers here are simulated; the production revamp delivered +15% revenue.

    python analysis/funnel_ab.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
NAVY, TEAL, GREY = "#0B1F3A", "#0E8C8C", "#9AA5B1"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13})
rng = np.random.default_rng(42)

STAGES = ["Checkout start", "Identified", "Address", "Delivery", "Payment", "Order"]
# step-through probabilities (each stage given the previous one)
CONTROL = [1.00, 0.71, 0.86, 0.90, 0.88, 0.93]   # account wall, manual address, assigned date
VARIANT = [1.00, 0.79, 0.88, 0.91, 0.885, 0.93]   # guest-first, autocomplete, chosen date
SAMPLE_CONTROL = [1.00, 0.72, 0.85, 0.92, 0.95]  # sample through full checkout
SAMPLE_VARIANT = [1.00, 0.97]                    # one click
ADDR_ERR = {"control": 0.031, "variant": 0.009}  # orders shipped to a wrong/incomplete address


def run_funnel(p, n):
    alive, counts = n, []
    for step in p:
        alive = rng.binomial(alive, step)
        counts.append(alive)
    return np.array(counts)


def ztest(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    se_d = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return p1, p2, (p2 - p1) / p1, 2 * (1 - norm.cdf(abs(z))), (p2 - p1 - 1.96 * se_d, p2 - p1 + 1.96 * se_d)


def main():
    n = 20_000
    c, v = run_funnel(CONTROL, n), run_funnel(VARIANT, n)
    p1, p2, lift, pval, ci = ztest(c[-1], n, v[-1], n)
    print(f"Checkout completion: control {p1:.1%}  variant {p2:.1%}  lift {lift:+.1%}  p={'<0.001' if pval < 1e-3 else f'{pval:.3f}'}  95% CI of diff [{ci[0]:+.2%}, {ci[1]:+.2%}]")
    print("Stage-to-stage (control -> variant):")
    for i in range(1, len(STAGES)):
        print(f"  {STAGES[i]:<12} {c[i]/c[i-1]:.1%} -> {v[i]/v[i-1]:.1%}")

    ns = 8_000
    sc, sv = run_funnel(SAMPLE_CONTROL, ns), run_funnel(SAMPLE_VARIANT, ns)
    s1, s2, slift, sp, _ = ztest(sc[-1], ns, sv[-1], ns)
    print(f"Sample orders: control {s1:.1%}  variant {s2:.1%}  lift {slift:+.1%}  p={'<0.001' if sp < 1e-3 else f'{sp:.3f}'}")

    err = {k: rng.binomial(int(x), ADDR_ERR[k]) for k, x in [("control", c[-1]), ("variant", v[-1])]}
    print(f"Address errors per 1,000 orders: control {1000*err['control']/c[-1]:.1f}  variant {1000*err['variant']/v[-1]:.1f}")

    out = ROOT / "figures"; out.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    x = np.arange(len(STAGES))
    ax.plot(x, c / n * 100, marker="o", color=GREY, lw=2.5, label="Before (control)")
    ax.plot(x, v / n * 100, marker="o", color=TEAL, lw=2.5, label="After (variant)")
    for i in (1, len(STAGES) - 1):
        ax.annotate(f"{c[i]/n:.0%}", (i, c[i] / n * 100), textcoords="offset points", xytext=(0, -16), ha="center", color=GREY, fontsize=10)
        ax.annotate(f"{v[i]/n:.0%}", (i, v[i] / n * 100), textcoords="offset points", xytext=(0, 8), ha="center", color=TEAL, fontsize=10, fontweight="bold")
    ax.set_xticks(x, STAGES); ax.set_ylabel("% of checkout starts"); ax.set_ylim(0, 105)
    ax.set_title(f"Checkout funnel: completion {lift:+.0%} (p<0.001), synthetic")
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(out / "01_funnel.png", dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    axes[0].bar(["Before", "After"], [s1 * 100, s2 * 100], color=[GREY, TEAL])
    axes[0].set_title("Sample checkout completion (%)", fontsize=12)
    axes[1].bar(["Before", "After"], [1000 * err["control"] / c[-1], 1000 * err["variant"] / v[-1]], color=[GREY, TEAL])
    axes[1].set_title("Address errors per 1,000 orders", fontsize=12)
    for ax in axes:
        for r in ax.patches:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height(), f"{r.get_height():.1f}", ha="center", va="bottom", fontweight="bold")
        ax.set_yticks([])
    fig.suptitle("Samples feed orders; address quality protects freight (synthetic)", fontweight="bold")
    fig.tight_layout(); fig.savefig(out / "02_samples_and_addresses.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    main()
