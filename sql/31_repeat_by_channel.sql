-- Business question: Do customers acquired via some channels repeat less?
-- Population: customers with a fully observed 90-day window.
SELECT acquisition_channel,
       COUNT(*) AS customers,
       SUM(is_repeat_90d) AS repeaters,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d,
       ROUND(AVG(first_order_value), 2) AS avg_first_order_value
FROM dim_customer
WHERE has_full_90d_window = 1
GROUP BY acquisition_channel
ORDER BY repeat_rate_90d DESC;
