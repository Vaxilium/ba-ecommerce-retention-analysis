# Executive summary — Altiplano Goods retention diagnostic

> 🌐 _Versión en español: [executive-summary.es.md](executive-summary.es.md)_

**Prepared from:** synthetic order-level dataset, Jan 2024 – Dec 2025 (79k orders, 20k customers).
All figures below are computed by the repo's pipeline and reproduced by `make all`.

## The problem

90-day repeat purchase rate fell from **35.3%** (H1 2024) to
**26.8%** (Q3 2025) — **-8.5 pp** (-24% relative).
Because repeat customers drive **83%** of revenue, this is a revenue problem,
not a vanity metric: the top revenue decile alone carries **53%** of sales.

## What is driving it

1. **Mix shift to low-repeat acquisition.** Paid social (repeat 22.7%) and
   influencer grew while referral/organic/email (repeat 44.0%–38.6%)
   shrank. Decomposition: **7.1 pp of the 8.5 pp decline is mix**,
   1.3 pp within-segment behaviour.
2. **Deep discounting poisons retention.** Heavy-discount first orders repeat at
   **22.4%** vs **37.4%** full-price, and their
   12-month margin is **$126 vs $248**.
3. **Fulfilment failures are concentrated.** Colombia: first-delivery delay
   1.7 → 6.4 days,
   repeat rate 31.1% → 19.1%.
4. **A model can triage customers.** Logistic model (test AUC 0.64); top predicted decile
   repeats at 1.5× base rate — buyers worth white-glove treatment are identifiable at day 0.
5. **A win-back motion demonstrably works.** On 5,057 opted-in lapsed customers the email lifted
   60-day reactivation 5.1% → 7.5%
   (p=0.0003); economics: **19× ROI, payback inside the first wave**.

## Recommendations (prioritised in docs/07-roadmap.md)

1. **Launch the quarterly win-back program** (base case net benefit ≈ $19k/yr at current pool size; scale with pool).
2. **Fix the Colombia courier and pause paid-social scale-up there** until delay < 3 days.
3. **Cap acquisition discounts at light/medium bands**; replace depth with referral and email incentives.
4. **Protect champions (21% of customers, 71% of revenue)** with
   VIP service levels, not discounts.
5. **Deploy the churn-score triage** to route at-risk first orders to support before they silently churn.

## Caveats

Synthetic data; the pipeline, method and decision logic are the deliverable. Effects are directional,
estimated with CIs where it matters, and every number regenerates via `make all`.
