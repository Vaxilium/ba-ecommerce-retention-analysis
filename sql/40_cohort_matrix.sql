-- Business question: Repeat-purchase triangle — what share of each cohort is active N months later?
-- month_idx: 0 = first order; portable month arithmetic via strftime.
WITH first_orders AS (
    SELECT customer_id, MIN(order_date) AS first_order_date
    FROM fct_orders WHERE order_status <> 'cancelled'
    GROUP BY customer_id
),
activity AS (
    SELECT f.customer_id,
           strftime('%Y-%m', f.first_order_date) AS cohort_month,
           (CAST(strftime('%Y', o.order_date) AS INTEGER) * 12 + CAST(strftime('%m', o.order_date) AS INTEGER))
             - (CAST(strftime('%Y', f.first_order_date) AS INTEGER) * 12 + CAST(strftime('%m', f.first_order_date) AS INTEGER)) AS month_idx
    FROM first_orders f
    JOIN fct_orders o ON o.customer_id = f.customer_id AND o.order_status <> 'cancelled'
    GROUP BY f.customer_id, cohort_month, month_idx
)
SELECT cohort_month, month_idx, COUNT(DISTINCT customer_id) AS active_customers
FROM activity
GROUP BY cohort_month, month_idx
ORDER BY cohort_month, month_idx;
