-- Business question: How concentrated is revenue? (Pareto check by customer decile.)
WITH revenue AS (
    SELECT o.customer_id, SUM(i.line_revenue) AS revenue
    FROM fct_orders o
    JOIN fct_order_items i ON i.order_id = o.order_id
    WHERE o.order_status <> 'cancelled'
    GROUP BY o.customer_id
),
ranked AS (
    SELECT customer_id, revenue,
           NTILE(10) OVER (ORDER BY revenue DESC) AS revenue_decile,
           SUM(revenue) OVER () AS total_revenue
    FROM revenue
)
SELECT revenue_decile,
       COUNT(*) AS customers,
       ROUND(SUM(revenue), 2) AS revenue,
       ROUND(SUM(revenue) / MAX(total_revenue), 4) AS revenue_share
FROM ranked
GROUP BY revenue_decile
ORDER BY revenue_decile;
