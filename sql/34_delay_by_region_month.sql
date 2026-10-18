-- Business question: Where and when did deliveries degrade? (logistics diagnostics)
SELECT ship_country,
       order_month,
       COUNT(*) AS orders,
       ROUND(AVG(delivery_delay_days), 2) AS avg_delay_days,
       ROUND(AVG(is_delayed), 4) AS pct_delayed_over_5d
FROM fct_orders
WHERE order_status <> 'cancelled'
GROUP BY ship_country, order_month
ORDER BY ship_country, order_month;
