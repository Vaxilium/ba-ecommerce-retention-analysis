-- Business question: How much revenue comes from customers who ever repeated vs one-timers?
SELECT is_repeat_ever,
       COUNT(DISTINCT o.customer_id) AS customers,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(i.line_revenue), 2) AS revenue,
       ROUND(SUM(i.line_revenue) / COUNT(DISTINCT o.customer_id), 2) AS revenue_per_customer
FROM dim_customer d
JOIN fct_orders o ON o.customer_id = d.customer_id AND o.order_status <> 'cancelled'
JOIN fct_order_items i ON i.order_id = o.order_id
GROUP BY is_repeat_ever
ORDER BY is_repeat_ever DESC;
