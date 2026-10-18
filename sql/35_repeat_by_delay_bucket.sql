-- Business question: Does a slow first delivery predict lower repeat purchase?
SELECT CASE WHEN first_order_delay_days <= 0 THEN '1_zero_or_early'
            WHEN first_order_delay_days <= 3 THEN '2_one_to_3d'
            WHEN first_order_delay_days <= 5 THEN '3_four_to_5d'
            WHEN first_order_delay_days <= 10 THEN '4_six_to_10d'
            ELSE '5_over_10d' END AS delay_bucket,
       COUNT(*) AS customers,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d
FROM dim_customer
WHERE has_full_90d_window = 1 AND first_order_delay_days IS NOT NULL
GROUP BY delay_bucket
ORDER BY delay_bucket;
