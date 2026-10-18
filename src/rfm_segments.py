"""RFM segmentation with profiles and recommended actions per segment.

Reads mart_rfm (NTILE scores computed in SQL) + dim_customer attributes.
Outputs: outputs/analysis/rfm_segments.json, rfm_segment_profiles.csv, rfm_customers.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from build_warehouse import open_engine

ACTIONS = {
    "champions": "Reward & referral: early access, loyalty perks, ask for reviews.",
    "loyal": "Upsell & cross-sell: bundles, category expansion, VIP tier invite.",
    "potential_loyalist": "Nurture: personalised recommendations, second-purchase nudge.",
    "new": "Onboard: welcome series, first-repeat incentive within 30 days.",
    "needs_attention": "Reactivate gently: win-back email with best-seller picks.",
    "about_to_sleep": "Win-back candidate: time-limited offer, low-cost channel first.",
    "at_risk": "Priority win-back: high-value lapsed — personal outreach / stronger offer.",
    "hibernating": "Low-cost reactivation only: newsletter + seasonal campaigns.",
    "lost": "Do not spend: suppress from paid audiences, keep email only.",
}


def segment(row) -> str:
    """Classic RFM mapping, adapted to the store's bimodal frequency distribution
    (many frequent buyers + many one-timers, little middle)."""
    r, f, m = row["r_score"], row["f_score"], row["m_score"]
    if r >= 4 and f >= 4:
        return "champions"
    if r >= 4 and f == 3:
        return "loyal"
    if r >= 4 and f == 2:
        return "potential_loyalist"
    if r >= 4:
        return "new"
    if r == 3 and (f >= 2 or m >= 3):
        return "needs_attention"
    if r == 3:
        return "about_to_sleep"
    if f >= 3 or m >= 4:
        return "at_risk"
    if m == 3:
        return "hibernating"
    return "lost"


def main() -> None:
    engine = open_engine(Path("outputs/warehouse.duckdb"))
    df = engine.query_df("""
        SELECT r.customer_id, r.recency_days, r.frequency, r.monetary,
               r.r_score, r.f_score, r.m_score,
               d.acquisition_channel, d.country, d.first_order_discount_band
        FROM mart_rfm r JOIN dim_customer d USING (customer_id)
    """)
    engine.close()

    df["segment"] = df.apply(segment, axis=1)
    total_revenue = df["monetary"].sum()
    profiles = (df.groupby("segment")
                .agg(customers=("customer_id", "count"),
                     avg_recency_days=("recency_days", "mean"),
                     avg_frequency=("frequency", "mean"),
                     avg_monetary=("monetary", "mean"),
                     revenue=("monetary", "sum"),
                     avg_r_score=("r_score", "mean"))
                .round(2).reset_index())
    profiles["pct_customers"] = (profiles["customers"] / len(df) * 100).round(1)
    profiles["pct_revenue"] = (profiles["revenue"] / total_revenue * 100).round(1)
    profiles["recommended_action"] = profiles["segment"].map(ACTIONS)
    profiles = profiles.sort_values("revenue", ascending=False).reset_index(drop=True)

    mix = (df.groupby(["segment", "acquisition_channel"]).size().unstack(fill_value=0))
    mix_share = (mix.div(mix.sum(axis=1), axis=0) * 100).round(1)
    lapsed = df[df["recency_days"].between(120, 540)]
    winback_population = int(len(lapsed[lapsed["segment"].isin(
        ["at_risk", "needs_attention", "about_to_sleep", "hibernating"])]))

    Path("outputs/analysis").mkdir(parents=True, exist_ok=True)
    profiles.to_csv("outputs/analysis/rfm_segment_profiles.csv", index=False)
    df[["customer_id", "segment", "r_score", "f_score", "m_score", "recency_days", "frequency", "monetary"]].to_csv(
        "outputs/analysis/rfm_customers.csv", index=False)
    result = {
        "total_customers": int(len(df)),
        "total_revenue": round(float(total_revenue), 2),
        "profiles": profiles.drop(columns=["revenue"]).to_dict("records"),
        "channel_mix_by_segment_pct": mix_share.to_dict("index"),
        "winback_population_120_540d": winback_population,
    }
    Path("outputs/analysis/rfm_segments.json").write_text(json.dumps(result, indent=2))
    print(profiles[["segment", "customers", "pct_customers", "avg_recency_days", "avg_frequency",
                    "avg_monetary", "pct_revenue"]].to_string(index=False))
    print("win-back population (120-540d inactive):", winback_population)


if __name__ == "__main__":
    main()
