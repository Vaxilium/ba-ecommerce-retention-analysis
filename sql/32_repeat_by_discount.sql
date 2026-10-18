-- Business question: Do deeper first-order discounts attract customers who do not come back?
SELECT first_order_discount_band,
       COUNT(*) AS customers,
       SUM(is_repeat_90d) AS repeaters,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d,
       ROUND(AVG(first_order_value), 2) AS avg_first_order_value,
       ROUND(AVG(discount_rate_implied), 4) AS avg_discount
FROM (
    SELECT d.*,
           CASE first_order_discount_band WHEN 'none' THEN 0.0 WHEN 'light' THEN 0.10
                WHEN 'medium' THEN 0.23 ELSE 0.40 END AS discount_rate_implied
    FROM dim_customer d WHERE has_full_90d_window = 1
) t
GROUP BY first_order_discount_band
ORDER BY avg_discount;
