"""Simulated A/B test of a win-back email on lapsed customers + full test math.

Control conversion is anchored to the EMPIRICAL natural reactivation rate measured
from order history (not assumed). Treatment lift is an explicit scenario input.
Includes two-proportion z-test, 95% CI, MDE and required sample size.
Outputs: outputs/analysis/ab_test.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from build_warehouse import open_engine

SEED = 42
ALPHA = 0.05
POWER = 0.80
TREATMENT_REL_LIFT = 0.35   # scenario input: win-back email lifts 60-day reactivation by 35% relative
COST_PER_EMAIL = 0.05       # USD per send (platform + ops)
INACTIVITY_WINDOW = (120, 540)  # days since last order ("lapsed, not dead")
MIN_ORDERS = 1


def z_two_sided(alpha: float) -> float:
    # inverse normal via bisection on the CDF (no scipy dependency)
    lo, hi = 0.0, 10.0
    target = 1 - alpha / 2
    for _ in range(80):
        mid = (lo + hi) / 2
        cdf = 0.5 * (1 + math.erf(mid / math.sqrt(2)))
        if cdf < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def normal_p_value(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


SNAPSHOT = pd.Timestamp("2025-12-31")
INACTIVITY_THRESHOLD = 180  # "lapsed" = no order for 180+ days
OUTCOME_WINDOW = 60         # natural reactivation measured over the next 60 days (matches test window)


def empirical_reactivation_rate(engine) -> tuple[float, int]:
    """Empirical P(reactivate within 30 days | inactive 180+ days so far), from order history.

    Episodes = every 180+ day inactivity spell (closed by the next order, or still open
    at the snapshot). Reactivation = next order arrives within 30 days of crossing 180d.
    """
    orders = engine.query_df("""
        SELECT customer_id, order_date FROM fct_orders
        WHERE order_status <> 'cancelled' ORDER BY customer_id, order_date
    """)
    episodes, reactivations = 0, 0
    for _, grp in orders.groupby("customer_id"):
        dates = pd.to_datetime(grp["order_date"]).sort_values().tolist()
        for prev, nxt in zip(dates[:-1], dates[1:]):
            threshold = prev + pd.Timedelta(days=INACTIVITY_THRESHOLD)
            if nxt > threshold:
                episodes += 1
                if nxt <= threshold + pd.Timedelta(days=OUTCOME_WINDOW):
                    reactivations += 1
        last = dates[-1]
        if last + pd.Timedelta(days=INACTIVITY_THRESHOLD + OUTCOME_WINDOW) <= SNAPSHOT:
            episodes += 1  # spell open at snapshot -> counted as non-reactivation
    return (reactivations / episodes if episodes else float("nan")), episodes


def main() -> None:
    engine = open_engine(Path("outputs/warehouse.duckdb"))
    natural_rate, episodes = empirical_reactivation_rate(engine)
    population = engine.query_df(f"""
        SELECT r.customer_id, r.recency_days, r.frequency, r.monetary,
               d.marketing_consent
        FROM mart_rfm r JOIN dim_customer d USING (customer_id)
        WHERE r.recency_days BETWEEN {INACTIVITY_WINDOW[0]} AND {INACTIVITY_WINDOW[1]}
          AND r.frequency >= {MIN_ORDERS} AND d.marketing_consent = TRUE
        ORDER BY r.customer_id
    """)
    avg_margin_per_order = engine.query_df("""
        SELECT AVG(order_margin) AS m FROM (
            SELECT o.order_id, SUM(i.line_margin) AS order_margin
            FROM fct_orders o JOIN fct_order_items i USING (order_id)
            WHERE o.order_status <> 'cancelled'
            GROUP BY o.order_id
        )
    """)["m"][0]
    engine.close()

    rng = np.random.default_rng(SEED)
    n = len(population)
    n_control = n // 2
    n_treat = n - n_control
    p_control = natural_rate
    p_treat = natural_rate * (1 + TREATMENT_REL_LIFT)

    conv_control = int(rng.binomial(n_control, p_control))
    conv_treat = int(rng.binomial(n_treat, p_treat))
    rate_control = conv_control / n_control
    rate_treat = conv_treat / n_treat
    abs_lift = rate_treat - rate_control
    rel_lift = abs_lift / rate_control

    p_pool = (conv_control + conv_treat) / n
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_treat))
    z = abs_lift / se_pool if se_pool > 0 else 0.0
    p_value = normal_p_value(z)
    se_diff = math.sqrt(rate_control * (1 - rate_control) / n_control + rate_treat * (1 - rate_treat) / n_treat)
    z_crit = z_two_sided(ALPHA)
    ci_abs = (abs_lift - z_crit * se_diff, abs_lift + z_crit * se_diff)
    ci_rel = (ci_abs[0] / rate_control, ci_abs[1] / rate_control)

    mde_abs = (z_crit + 0.84) * math.sqrt(2 * p_control * (1 - p_control) / (n / 2))
    mde_rel = mde_abs / p_control
    target_rel = 0.25
    delta = p_control * target_rel
    n_required = math.ceil(2 * (z_crit + 0.84) ** 2 * p_control * (1 - p_control) / delta ** 2)

    incremental_conversions = rel_lift * n_treat * rate_control if rate_control > 0 else 0
    incremental_margin = incremental_conversions * float(avg_margin_per_order)
    program_cost = n_treat * COST_PER_EMAIL
    roi = (incremental_margin - program_cost) / program_cost if program_cost else float("nan")
    conservative_conversions = max(0.0, ci_rel[0]) * n_treat * rate_control
    conservative_margin = conservative_conversions * float(avg_margin_per_order)

    significant = p_value < ALPHA
    decision = ("ROLL OUT" if significant and conservative_margin > program_cost
                else "TEST LONGER" if not significant else "ROLL OUT ONLY IF COST <= CONSERVATIVE MARGIN")

    result = {
        "design": {
            "population_filter": f"last order {INACTIVITY_WINDOW[0]}-{INACTIVITY_WINDOW[1]} days ago, opted-in",
            "population": int(n), "n_control": int(n_control), "n_treatment": int(n_treat),
            "seed": SEED, "alpha": ALPHA, "power": POWER,
            "outcome_window_days": OUTCOME_WINDOW,
            "treatment_rel_lift_assumption": TREATMENT_REL_LIFT,
            "natural_reactivation_basis": {"rate": round(natural_rate, 4), "episodes_observed": int(episodes)},
        },
        "observed": {
            "control_rate": round(rate_control, 4), "treatment_rate": round(rate_treat, 4),
            "conversions_control": conv_control, "conversions_treatment": conv_treat,
            "abs_lift": round(abs_lift, 4), "rel_lift": round(rel_lift, 4),
            "z": round(z, 3), "p_value": round(p_value, 6),
            "ci95_abs": [round(ci_abs[0], 4), round(ci_abs[1], 4)],
            "ci95_rel": [round(ci_rel[0], 4), round(ci_rel[1], 4)],
        },
        "power_analysis": {
            "mde_abs": round(mde_abs, 4), "mde_rel": round(mde_rel, 4),
            "sample_size_per_arm_for_25pct_rel_mde": int(n_required),
            "note": "MDE at 80% power / 5% two-sided alpha for the achieved sample size",
        },
        "economics": {
            "avg_margin_per_order": round(float(avg_margin_per_order), 2),
            "cost_per_email": COST_PER_EMAIL,
            "incremental_conversions": round(incremental_conversions, 1),
            "incremental_margin": round(incremental_margin, 2),
            "program_cost": round(program_cost, 2),
            "roi": round(roi, 2),
            "conservative_incremental_margin_ci_low": round(conservative_margin, 2),
        },
        "decision": decision,
    }
    Path("outputs/analysis/ab_test.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
