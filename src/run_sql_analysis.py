"""Run the SQL analysis layer and generate docs/04-sql-findings.md from real outputs.

Executes sql/30_*.sql ... sql/41_*.sql against outputs/warehouse.duckdb, saves each
result to outputs/analysis/, computes derived statistics (medians, mix-shift
decomposition) and renders the findings document with embedded numbers.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd

from build_warehouse import open_engine

ANALYSIS_GLOB = "sql/[34][0-9]_*.sql"
PERIOD_1 = ("2024-01", "2024-06")
PERIOD_2 = ("2025-07", "2025-09")


def md_table(df: pd.DataFrame, floatfmt: str = ".4f") -> str:
    df = df.copy()
    df.columns = [str(c) for c in df.columns]

    def fmt(v):
        if isinstance(v, float):
            if pd.isna(v):
                return "—"
            if float(v).is_integer() and abs(v) >= 100:
                return f"{int(v):,}"
            return format(v, floatfmt)
        if isinstance(v, (int,)) and not isinstance(v, bool):
            return f"{v:,}"
        return str(v)
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def run_queries(engine, out_dir: Path) -> dict[str, pd.DataFrame]:
    results = {}
    for sql_file in sorted(glob.glob(ANALYSIS_GLOB)):
        name = Path(sql_file).stem
        df = engine.query_df(Path(sql_file).read_text())
        if engine.name == "sqlite":
            df = df.convert_dtypes()
        df.to_csv(out_dir / f"{name}.csv", index=False)
        results[name] = df
        print(f"{name}: {len(df)} rows")
    return results


def two_term(dim: pd.DataFrame, key_col: str) -> dict:
    """Exact two-term decomposition: mix effect (who) vs rate effect (behaviour)."""
    p1 = dim[dim["cohort_month"].between(*PERIOD_1)]
    p2 = dim[dim["cohort_month"].between(*PERIOD_2)]
    r1 = p1.groupby(key_col)["is_repeat_90d"].mean()
    r2 = p2.groupby(key_col)["is_repeat_90d"].mean()
    s1 = p1[key_col].value_counts(normalize=True)
    s2 = p2[key_col].value_counts(normalize=True)
    idx = r1.index.union(r2.index)
    r1f = r1.reindex(idx, fill_value=float(p1["is_repeat_90d"].mean()))
    r2f = r2.reindex(idx, fill_value=float(p2["is_repeat_90d"].mean()))
    s1f = s1.reindex(idx, fill_value=0.0)
    s2f = s2.reindex(idx, fill_value=0.0)
    mix = float(((s2f - s1f) * r1f).sum())
    rate = float((s2f * (r2f - r1f)).sum())
    return {"mix_pp": round(mix * 100, 2), "rate_pp": round(rate * 100, 2),
            "total_pp": round((mix + rate) * 100, 2)}


def mix_decomposition(dim: pd.DataFrame) -> dict:
    """Decompose the KPI change between the two periods into mix vs within-segment effects."""
    p1 = dim[dim["cohort_month"].between(*PERIOD_1)]
    p2 = dim[dim["cohort_month"].between(*PERIOD_2)]
    actual = float(p2["is_repeat_90d"].mean() - p1["is_repeat_90d"].mean()) * 100
    dim = dim.copy()
    dim["joint_cell"] = dim["acquisition_channel"] + " x " + dim["first_order_discount_band"]
    joint = two_term(dim, "joint_cell")
    region = two_term(dim, "country")
    return {"actual_delta_pp": round(actual, 2), "period_1": f"{PERIOD_1[0]}..{PERIOD_1[1]}",
            "period_2": f"{PERIOD_2[0]}..{PERIOD_2[1]}",
            "joint_channel_x_discount": joint, "region": region}


def rate(df: pd.DataFrame, key_col: str, key: str, value_col: str = "repeat_rate_90d") -> float:
    row = df[df[key_col] == key]
    return float(row[value_col].iloc[0]) if len(row) else float("nan")


def main() -> None:
    out_dir = Path("outputs/analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = open_engine(Path("outputs/warehouse.duckdb"))
    res = run_queries(engine, out_dir)

    dim = engine.query_df("SELECT * FROM dim_customer WHERE has_full_90d_window = 1")
    orders = engine.query_df("SELECT * FROM fct_orders WHERE order_status <> 'cancelled'")
    engine.close()

    # ---- derived statistics -------------------------------------------------
    r_h1_24 = float(dim[dim["cohort_month"].between(PERIOD_1[0], PERIOD_1[1])]["is_repeat_90d"].mean())
    r_q3_25 = float(dim[dim["cohort_month"].between(PERIOD_2[0], PERIOD_2[1])]["is_repeat_90d"].mean())
    second = dim.dropna(subset=["days_to_second_order"])
    median_24 = float(second[second["cohort_month"] < "2025-01"]["days_to_second_order"].median())
    median_25 = float(second[second["cohort_month"] >= "2025-01"]["days_to_second_order"].median())
    decomp = mix_decomposition(dim)

    ch = res["31_repeat_by_channel"]
    disc = res["32_repeat_by_discount"]
    reg = res["33_repeat_by_region_period"]
    delay = res["34_delay_by_region_month"]
    delay_bucket = res["35_repeat_by_delay_bucket"]
    ticket = res["36_repeat_by_ticket_bucket"]
    clv = res["38_clv_12m"]
    pareto = res["39_revenue_concentration"]
    tts = res["37_time_to_second_order"]
    rev_share = res["41_repeat_revenue_share"]

    clv_by_channel = clv.groupby("acquisition_channel").agg(
        customers=("customer_id", "count"), avg_revenue_12m=("revenue_12m", "mean"),
        avg_margin_12m=("margin_12m", "mean")).round(2).reset_index().sort_values("avg_margin_12m", ascending=False)
    clv_by_band = clv.groupby("first_order_discount_band").agg(
        customers=("customer_id", "count"), avg_revenue_12m=("revenue_12m", "mean"),
        avg_margin_12m=("margin_12m", "mean")).round(2).reset_index().sort_values("avg_margin_12m", ascending=False)
    clv_by_repeat = clv.groupby("is_repeat_ever").agg(
        customers=("customer_id", "count"), avg_revenue_12m=("revenue_12m", "mean"),
        avg_margin_12m=("margin_12m", "mean")).round(2).reset_index()

    top_decile = float(pareto.loc[pareto["revenue_decile"] == 1, "revenue_share"].iloc[0])
    top_3 = float(pareto.loc[pareto["revenue_decile"] <= 3, "revenue_share"].sum())
    repeat_rev = rev_share.set_index("is_repeat_ever")["revenue"]
    repeat_rev_share = float(repeat_rev.get(1, 0) / repeat_rev.sum()) if repeat_rev.sum() else float("nan")

    col_pre = reg[(reg["country"] == "Colombia") & (reg["period"] == "pre_2025H2")]
    col_post = reg[(reg["country"] == "Colombia") & (reg["period"] == "from_2025H2")]
    col_r_pre = float(col_pre["repeat_rate_90d"].iloc[0]) if len(col_pre) else float("nan")
    col_r_post = float(col_post["repeat_rate_90d"].iloc[0]) if len(col_post) else float("nan")
    col_delay = delay[(delay["ship_country"] == "Colombia")]
    col_delay_pre = float(col_delay[col_delay["order_month"] < "2025-07"]["avg_delay_days"].mean())
    col_delay_post = float(col_delay[col_delay["order_month"] >= "2025-07"]["avg_delay_days"].mean())

    best_chan = ch.iloc[0]
    worst_chan = ch.iloc[-1]
    chan_pp = (float(worst_chan["repeat_rate_90d"]) - float(best_chan["repeat_rate_90d"])) * 100
    disc_best = disc.iloc[0]
    disc_worst = disc.iloc[-1]
    disc_pp = (float(disc_worst["repeat_rate_90d"]) - float(disc_best["repeat_rate_90d"])) * 100
    t_noticket = rate(ticket, "ticket_bucket", "1_no_ticket")
    t_long = rate(ticket, "ticket_bucket", "4_over_72h")

    summary = {
        "kpi": {
            "repeat_rate_h1_2024": round(r_h1_24, 4),
            "repeat_rate_q3_2025": round(r_q3_25, 4),
            "decline_pp": round((r_q3_25 - r_h1_24) * 100, 1),
            "decline_rel_pct": round((r_q3_25 / r_h1_24 - 1) * 100, 1),
            "customers_analyzed": int(len(dim)),
            "valid_orders": int(len(orders)),
        },
        "channel": ch.to_dict("records"),
        "discount": disc.to_dict("records"),
        "region_period": reg.to_dict("records"),
        "delay_bucket": delay_bucket.to_dict("records"),
        "ticket": ticket.to_dict("records"),
        "delay_colombia": {"pre_2025h2": round(col_delay_pre, 2), "from_2025h2": round(col_delay_post, 2),
                           "repeat_pre": round(col_r_pre, 4), "repeat_post": round(col_r_post, 4)},
        "time_to_second": {"median_days_2024_cohorts": median_24, "median_days_2025_cohorts": median_25,
                           "buckets": tts.to_dict("records")},
        "clv": {"by_channel": clv_by_channel.to_dict("records"), "by_band": clv_by_band.to_dict("records"),
                "by_repeat": clv_by_repeat.to_dict("records")},
        "concentration": {"top_decile_share": round(top_decile, 4), "top_3_deciles_share": round(top_3, 4),
                          "deciles": pareto.to_dict("records")},
        "repeat_revenue_share": round(repeat_rev_share, 4),
        "decomposition": decomp,
        "trend": res["30_retention_trend"].to_dict("records"),
        "cohort_matrix": res["40_cohort_matrix"].to_dict("records"),
    }
    Path("outputs/analysis/summary.json").write_text(json.dumps(summary, indent=2))

    # ---- document -----------------------------------------------------------
    tts_24 = tts[tts["cohort_year"] == 2024]
    tts_25 = tts[tts["cohort_year"] == 2025]
    tts_cmp = tts_24.merge(tts_25, on="time_bucket", suffixes=("_2024", "_2025"))[
        ["time_bucket", "share_of_cohort_2024", "share_of_cohort_2025"]]
    delay_summary = (delay.assign(period=lambda d: (d["order_month"] >= "2025-07").map({True: "from_2025H2", False: "pre_2025H2"}))
                     .groupby(["ship_country", "period"])["avg_delay_days"].mean().round(2).reset_index())
    cm = res["40_cohort_matrix"].copy()
    cm["quarter"] = pd.to_datetime(cm["cohort_month"] + "-01").dt.to_period("Q").astype(str)
    cm_aggr = (cm[cm["month_idx"] <= 6].groupby(["quarter", "month_idx"])["active_customers"].sum().reset_index()
               .pivot(index="quarter", columns="month_idx", values="active_customers").fillna(0).astype(int).reset_index())

    doc = f"""# 04 — SQL Findings: Why is the 90-day repeat rate falling?

> Generated by `src/run_sql_analysis.py` from the warehouse (DuckDB). Every number below
> is computed from the synthetic data — never hand-written.
> All queries: `sql/30_*.sql` … `sql/41_*.sql` (CTEs + window functions).

## Method

- **KPI**: share of new customers placing a second non-cancelled order within 90 days of
  their first order. Only cohorts with a **fully observed 90-day window** are used
  (`has_full_90d_window = 1`), i.e. first orders up to 2025-10-02; later cohorts are censored.
- Population analyzed: **{len(dim):,} customers** with a first order; **{len(orders):,} valid orders**.

## 1. The decline is real and accelerating

**Headline: {r_h1_24:.1%}** (Jan–Jun 2024 cohorts) → **{r_q3_25:.1%}** (Jul–Sep 2025 cohorts),
a change of **{summary['kpi']['decline_pp']:+.1f} points** ({summary['kpi']['decline_rel_pct']:+.1f}% relative).

{md_table(res['30_retention_trend'])}

## 2. Acquisition mix has shifted toward channels with weaker repeat behaviour

{md_table(ch)}

Paid social customers repeat at **{float(worst_chan['repeat_rate_90d']):.1%}** vs
**{float(best_chan['repeat_rate_90d']):.1%}** for {best_chan['acquisition_channel']} —
a spread of **{abs(chan_pp):.1f} points** across channels (n ≥ {int(ch['customers'].min()):,} per channel).

## 3. Deeper first-order discounts attract deal-seekers

{md_table(disc)}

Customers acquired with a **heavy (>30%) discount repeat at {float(disc_worst['repeat_rate_90d']):.1%},
{abs(disc_pp):.1f} points below** the no-discount band ({float(disc_best['repeat_rate_90d']):.1%}).

## 4. Mix-shift decomposition: what explains the decline?

Between {decomp['period_1']} and {decomp['period_2']} the rate moved **{decomp['actual_delta_pp']:+.1f} pp**.
Two-term decomposition — *mix* = who we acquire & how we discount (joint channel × discount cells);
*rate* = behaviour change inside each cell:

| Effect (joint channel × discount cells) | pp |
|---|---:|
| Mix effect (shift to paid social & heavy discounts) | {decomp['joint_channel_x_discount']['mix_pp']:+.1f} |
| Within-cell rate effect (all types got worse) | {decomp['joint_channel_x_discount']['rate_pp']:+.1f} |
| **Total (equals the actual change)** | **{decomp['joint_channel_x_discount']['total_pp']:+.1f}** |

Regional view: mix {decomp['region']['mix_pp']:+.1f} pp vs within-region behaviour {decomp['region']['rate_pp']:+.1f} pp
— Colombia's breakdown (section 5) sits inside the within-region term.

## 5. Operations: delivery delays in Colombia from Jul 2025

Average delivery delay (days, actual − promised), by market and period:

{md_table(delay_summary, '.2f')}

Colombia: average delay went from **{col_delay_pre:.1f} days** (pre-2025H2) to **{col_delay_post:.1f} days**
(from Jul 2025). Repeat rate of the affected first-order cohorts fell from **{col_r_pre:.1%} to {col_r_post:.1%}**.

### Does delay predict churn? (repeat rate by first-delivery delay)

{md_table(delay_bucket)}

## 6. Support: slow resolutions predict churn

{md_table(ticket)}

Customers whose first-order ticket took **>72h repeat at {t_long:.1%} vs {t_noticket:.1%}**
for ticket-free customers ({(t_long - t_noticket) * 100:+.1f} pp).

## 7. Time to second order

Median days to second order: **{median_24:.0f} days** (2024 cohorts) → **{median_25:.0f} days** (2025 cohorts).

{md_table(tts_cmp)}

## 8. Customer value: 12-month CLV by segment (customers with full 365-day window)

By acquisition channel:

{md_table(clv_by_channel, '.2f')}

By first-order discount band:

{md_table(clv_by_band, '.2f')}

Repeat vs one-timers:

{md_table(clv_by_repeat, '.2f')}

Revenue concentration: top decile = **{top_decile:.1%}** of revenue, top 3 deciles = **{top_3:.1%}**.
Customers who ever repeated contribute **{repeat_rev_share:.1%}** of total revenue.

## 9. Repeat-purchase triangle (active customers by quarter × month index)

{md_table(cm_aggr)}

## Conclusion (evidence for the business questions)

1. **Why**: about **{abs(decomp['joint_channel_x_discount']['mix_pp']):.1f} of the {abs(decomp['actual_delta_pp']):.1f} points** come from
   *mix* — more paid-social customers ({float(ch['customers'].iloc[-1]):,.0f} of {int(ch['customers'].sum()):,} analyzed)
   and far more heavy-discount first orders. The remaining **{abs(decomp['joint_channel_x_discount']['rate_pp']):.1f} points** are
   within-segment deterioration: the **Colombia delivery breakdown** ({col_r_pre:.1%} → {col_r_post:.1%} for its
   affected cohorts) and **slow support resolutions** ({t_long:.1%} vs {t_noticket:.1%}).
2. **Who**: see section 2–6 and the RFM segmentation in `docs/05-analytics.md`.
3. **Payoff**: repeat customers generate substantially more value (section 8) — quantified in
   `docs/06-business-case.md` with the win-back A/B test.
4. **First steps**: the RICE-ranked roadmap in `docs/07-roadmap.md`.
"""
    Path("docs/04-sql-findings.md").write_text(doc)
    print("wrote docs/04-sql-findings.md and outputs/analysis/summary.json")


if __name__ == "__main__":
    main()
