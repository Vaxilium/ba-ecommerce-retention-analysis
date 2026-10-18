-- Business question: How long do customers take to place their second order, and did that change?
-- Shares by bucket per cohort year (window function: share of cohort year total).
WITH buckets AS (
    SELECT CAST(strftime('%Y', first_order_date) AS INTEGER) AS cohort_year,
           CASE WHEN days_to_second_order IS NULL THEN 'never_in_window'
                WHEN days_to_second_order <= 30 THEN '1_within_30d'
                WHEN days_to_second_order <= 60 THEN '2_31_to_60d'
                WHEN days_to_second_order <= 90 THEN '3_61_to_90d'
                ELSE '4_over_90d' END AS time_bucket,
           customer_id
    FROM dim_customer
    WHERE first_order_date IS NOT NULL AND has_full_90d_window = 1
)
SELECT cohort_year, time_bucket, COUNT(*) AS customers,
       ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY cohort_year), 4) AS share_of_cohort
FROM buckets
GROUP BY cohort_year, time_bucket
ORDER BY cohort_year, time_bucket;
