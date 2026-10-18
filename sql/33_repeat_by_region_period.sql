-- Business question: Did regional retention change after mid-2025? (delivery-delay hypothesis)
-- Compares first-order cohorts before vs from July 2025 per country.
SELECT country,
       CASE WHEN first_order_date < DATE '2025-07-01' THEN 'pre_2025H2' ELSE 'from_2025H2' END AS period,
       COUNT(*) AS customers,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d,
       ROUND(AVG(first_order_delay_days), 2) AS avg_delay_days
FROM dim_customer
WHERE has_full_90d_window = 1
GROUP BY country, period
ORDER BY country, period;
