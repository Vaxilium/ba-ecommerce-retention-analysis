-- Business question: What is the 12-month CLV (revenue and margin) by acquisition channel,
-- first-order discount band and repeat status? (Customers with a full 365-day window.)
SELECT d.customer_id,
       d.acquisition_channel,
       d.country,
       d.first_order_discount_band,
       d.is_repeat_ever,
       CAST(strftime('%Y', d.first_order_date) AS INTEGER) AS cohort_year,
       ROUND(SUM(i.line_revenue), 2) AS revenue_12m,
       ROUND(SUM(i.line_margin), 2) AS margin_12m
FROM dim_customer d
JOIN fct_orders o ON o.customer_id = d.customer_id AND o.order_status <> 'cancelled'
JOIN fct_order_items i ON i.order_id = o.order_id
WHERE d.first_order_date IS NOT NULL
  AND date_diff('day', d.first_order_date, DATE '2025-12-31') >= 365
  AND date_diff('day', d.first_order_date, o.order_date) <= 365
GROUP BY d.customer_id, d.acquisition_channel, d.country, d.first_order_discount_band,
         d.is_repeat_ever, cohort_year;
