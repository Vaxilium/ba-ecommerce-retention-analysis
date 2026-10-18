"""Build docs/07-roadmap.md (RICE, computed) and docs/08-user-stories.md.
Dollar impacts are estimated from measured outputs; confidence and effort are explicit
assumptions shown in the table (documented as such)."""
from __future__ import annotations

import json
from pathlib import Path

SUM = json.loads(Path("outputs/analysis/summary.json").read_text())
RFM = json.loads(Path("outputs/analysis/rfm_segments.json").read_text())
AB = json.loads(Path("outputs/analysis/ab_test.json").read_text())
BC_CASES = {"base_annual_gm": 0.0}  # filled below from A/B (no dependency on workbook)

pool = AB["design"]["population"]
control = AB["observed"]["control_rate"]
lift = AB["observed"]["rel_lift"]
margin = AB["economics"]["avg_margin_per_order"]
waves = 4

winback_gm_yr = pool * control * lift * margin * waves
winback_cost_yr = pool * AB["economics"]["cost_per_email"] * waves

col = next(r for r in SUM["region_period"] if r["country"] == "Colombia" and r["period"] == "from_2025H2")
col_pre = next(r for r in SUM["region_period"] if r["country"] == "Colombia" and r["period"] == "pre_2025H2")
col_gap = col_pre["repeat_rate_90d"] - col["repeat_rate_90d"]

heavy = next(r for r in SUM["clv"]["by_band"] if r["first_order_discount_band"] == "heavy")
light = next(r for r in SUM["clv"]["by_band"] if r["first_order_discount_band"] == "light")
ps = next(r for r in SUM["clv"]["by_channel"] if r["acquisition_channel"] == "paid_social")
ref = next(r for r in SUM["clv"]["by_channel"] if r["acquisition_channel"] == "referral")
heavy_count = next(r for r in SUM["discount"] if r["first_order_discount_band"] == "heavy")["customers"]

delay_bad = sum(r["customers"] for r in SUM["delay_bucket"] if r["delay_bucket"] in ("4_six_to_10d", "5_over_10d"))
delay_gap = next(r for r in SUM["delay_bucket"] if r["delay_bucket"] == "2_one_to_3d")["repeat_rate_90d"] - \
            next(r for r in SUM["delay_bucket"] if r["delay_bucket"] == "4_six_to_10d")["repeat_rate_90d"]

needs_att = next(r for r in RFM["profiles"] if r["segment"] == "needs_attention")

INITIATIVES = [
    dict(
        name="Win-back program (quarterly waves)",
        story="US-1", owner="CRM / Lifecycle",
        reach=pool * waves,
        impact=winback_gm_yr - winback_cost_yr,
        confidence=0.80, effort=3,
        basis=f"A/B-validated: {lift:.0%} rel lift, p={AB['observed']['p_value']:.4f}",
        risk="Pool assumed constant/quarter; cool-down rules needed to avoid over-mailing",
    ),
    dict(
        name="Cap first-order discounts (no 'heavy' tier)",
        story="US-2", owner="Growth / Pricing",
        reach=heavy_count,
        impact=heavy_count * 0.2 * (light["avg_margin_12m"] - heavy["avg_margin_12m"]),
        confidence=0.30, effort=4,
        basis=f"12-mo margin gap light vs heavy band: ${light['avg_margin_12m']:.0f} vs ${heavy['avg_margin_12m']:.0f}; assume 20% of heavy recruits shift to light",
        risk="Volume loss from removing deep discounts is NOT modelled — directional estimate only",
    ),
    dict(
        name="Fix Colombia courier delays",
        story="US-3", owner="Operations",
        reach=col["customers"] * 4,
        impact=col["customers"] * col_gap * margin * 4,
        confidence=0.55, effort=6,
        basis=f"Colombia repeat fell {col_pre['repeat_rate_90d']:.1%} -> {col['repeat_rate_90d']:.1%} while delay hit {SUM['delay_colombia']['from_2025h2']:.1f} days",
        risk="Observational link; seasonal/postal factors could share the blame",
    ),
    dict(
        name="Delay-aware send suppression",
        story="US-4", owner="CRM / Ops integration",
        reach=delay_bad * 4,
        impact=delay_bad * delay_gap * margin * 4,
        confidence=0.45, effort=2,
        basis=f"Customers with 6+ day delays repeat {delay_gap:.1%} below the 1-3d baseline ({delay_bad} customers/yr)",
        risk="Suppression costs some short-term email revenue; retention gain is the bet",
    ),
    dict(
        name="Shift paid-social budget to referral / email",
        story="US-5", owner="Growth",
        reach=ps["customers"],
        impact=ps["customers"] * 0.15 * (ref["avg_margin_12m"] - ps["avg_margin_12m"]),
        confidence=0.35, effort=8,
        basis=f"12-mo margin per customer: referral ${ref['avg_margin_12m']:.0f} vs paid social ${ps['avg_margin_12m']:.0f}; assume 15% volume shift",
        risk="Channel capacity is not infinite; CAC differences not modelled here",
    ),
    dict(
        name="RFM-triggered lifecycle nudges (needs_attention)",
        story="US-1", owner="CRM / Lifecycle",
        reach=needs_att["customers"],
        impact=needs_att["customers"] * control * lift * margin,
        confidence=0.35, effort=3,
        basis=f"{needs_att['customers']:,} customers, {needs_att['avg_frequency']:.1f} orders avg, {needs_att['avg_monetary']:.0f} USD spend; assume half the win-back lift applies",
        risk="Segment overlaps win-back pool — count once to avoid double-dipping",
    ),
]

for i in INITIATIVES:
    if i["name"].startswith("RFM-triggered"):
        i["impact"] *= 0.5
    i["score"] = i["impact"] * i["confidence"] / i["effort"]

ranked = sorted(INITIATIVES, key=lambda i: -i["score"])
now = ranked[:2]
next_ = ranked[2:4]
later = ranked[4:]


def table(items) -> str:
    rows = "\n".join(
        f"| {i['name']} | {i['story']} | {i['owner']} | {i['reach']:,} | {i['impact']:,.0f} | "
        f"{i['confidence']:.2f} | {i['effort']} | **{i['score']:,.0f}** |" for i in items)
    return ("| Initiative | Story | Owner | Reach/yr | Impact (USD/yr) | Conf. | Effort (wks) | Score (USD/wk) |\n"
            "|---|---|---|---:|---:|---:|---:|---:|\n" + rows)


def basis_list(items) -> str:
    return "\n".join(f"- **{i['name']}** — basis: {i['basis']}. Risk: {i['risk']}." for i in items)


md7 = f"""# 07 — Prioritised Roadmap (RICE)

> Generated by `src/build_roadmap.py`. **Score = Impact × Confidence ÷ Effort** — risk-adjusted USD of
> annual margin per week of effort, so scores read directly in business terms (plain RICE would double-count
> reach right back into the score because Impact is already a total in USD). Confidence and Effort are
> explicit analyst assumptions; reach and impact derive from measured outputs.

## Ranked initiatives

{table(ranked)}

## Sequencing

- **Now (this quarter):** {", ".join(i['name'] for i in now)} — within Now, ship the **win-back program first**:
  it is the only initiative validated with an experiment, so it is the safest immediate win.
- **Next (next quarter):** {", ".join(i['name'] for i in next_)}.
- **Later (when capacity allows):** {", ".join(i['name'] for i in later)}.

## Evidence behind the estimates

{basis_list(ranked)}

## How these scores can move

RICE is a conversation tool: if operations commits to the Colombia fix, confidence rises and it jumps the
queue; if a discount A/B shows no volume loss, the discount-cap estimate firms up. Re-run `make all`
after new data to refresh every figure.
"""

md8 = f"""# 08 — User Stories and Acceptance Criteria

> Generated by `src/build_roadmap.py` from the same computed outputs as docs/07.
> Stories follow the analytics-to-delivery handoff pattern: data contract → trigger → acceptance test.

## US-1 — Win-back campaign to lapsed customers
*As a CRM manager, I want a quarterly win-back send to opted-in customers lapsed 120–540 days, so that
dormant revenue is recovered at low cost.*

- Story points: 5 · Linked initiative: win-back program / lifecycle nudges
- **Given** a customer's last order was 120–540 days ago **and** they are marketing opted-in
  **and** they received no win-back email in the last 90 days (cool-down),
  **when** the quarterly wave runs, **then** they receive exactly one win-back email and are tracked
  in the campaign table with a randomized control holdout.
- **Given** a customer purchased in the last 90 days, **when** the wave runs, **then** they are excluded.
- Metric guardrails: 60-day reactivation rate per arm, unsubscribe rate < 1%, send cost per reactivation
  (${AB['economics']['program_cost'] / max(AB['economics']['incremental_conversions'], 1):.2f} target at base case).

## US-2 — Discount depth caps in acquisition
*As a growth lead, I want first-order discount depth capped at the light tier for self-serve channels, so
that we stop buying retention-negative volume.*

- Story points: 8 · Linked initiative: discount cap
- **Given** a new customer at checkout on paid social/paid search,
  **when** cart value is below the qualification threshold, **then** the maximum offered discount is the
  light band (≤15%) and the offer shown is logged for audit.
- **Given** the cap is live, **when** the monthly readout runs, **then** conversion rate, AOV, and 90-day
  repeat rate by band are reported vs. the pre-cap baseline.

## US-3 — Colombia delivery SLA
*As an operations manager, I want a courier SLA dashboard for Colombia with a 3-day p90 target, so delays
stop destroying repeat rates.*

- Story points: 8 · Linked initiative: fix Colombia courier
- **Given** daily order data, **when** first-delivery delay exceeds 3 days for a Colombian order,
  **then** the order is flagged in the Ops queue and included in the weekly SLA report.
- **Given** the fix is live for 90 days, **when** the cohort readout runs, **then** Colombia 90-day repeat
  rate recovers toward the {col_pre['repeat_rate_90d']:.1%} pre-incident baseline.

## US-4 — Delay-aware send suppression
*As a CRM manager, I want promotional sends suppressed for customers with an open delayed delivery, so that
we don't ask for another order while the first one is late.*

- Story points: 3 · Linked initiative: delay-aware suppression
- **Given** a customer has an in-transit order past its promised date, **when** a promotional campaign
  executes, **then** the customer is suppressed until delivery (or resolution) plus 2 days.
- **Given** suppression is active, **when** the monthly report runs, **then** suppressed volume and the
  repeat-rate delta for suppressed vs. matched control are reported.

## US-5 — Churn-risk scoring batch + CRM routing
*As a lifecycle analyst, I want weekly churn scores for new customers so the first 90 days get the right
level of care.*

- Story points: 5 · Linked initiative: churn-score triage (feeds US-1 audience selection)
- **Given** the model artifact (test AUC {json.loads(Path('outputs/analysis/churn_model.json').read_text())['auc_test']:.2f}),
  **when** the weekly batch runs, **then** every customer with a first order in the last 30 days receives a
  score and a decile, written to the CRM with run timestamp and model version.
- **Given** scores are in the CRM, **when** a customer lands in the bottom decile, **then** they are queued
  for a service touch (not a discount) within 7 days.

## Definition of Done (all stories)

- Metric movement measured against a holdout or pre-period baseline, documented in `outputs/analysis/`.
- Pipeline artifacts regenerate via `make all`; no manual spreadsheet leaves the building.
- Privacy: processing limited to opted-in customers; suppression lists honoured before every send.
"""

Path("docs/07-roadmap.md").write_text(md7)
Path("docs/08-user-stories.md").write_text(md8)
print("wrote docs/07-roadmap.md and docs/08-user-stories.md")
