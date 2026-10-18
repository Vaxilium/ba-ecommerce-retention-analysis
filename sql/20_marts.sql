-- ============================================================================
-- 20_marts.sql — analysis-ready marts (staging -> marts)
-- ============================================================================

-- Dimension: one row per customer, with first-order context + retention flags.
CREATE OR REPLACE TABLE dim_customer AS
WITH first_orders AS (
    SELECT customer_id, MIN(order_date) AS first_order_date
    FROM stg_orders WHERE order_status <> 'cancelled'
    GROUP BY customer_id
),
first_order_row AS (
    SELECT * FROM (
        SELECT f.customer_id, o.order_id AS first_order_id, o.order_date,
               o.discount_rate, o.ship_country, o.promised_delivery_days, o.actual_delivery_days,
               ROW_NUMBER() OVER (PARTITION BY f.customer_id ORDER BY o.order_id) AS rn
        FROM first_orders f
        JOIN stg_orders o ON o.customer_id = f.customer_id AND o.order_date = f.first_order_date
    ) WHERE rn = 1
),
first_order_value AS (
    SELECT r.customer_id,
           SUM(i.quantity * i.unit_price) AS first_order_value
    FROM first_order_row r JOIN stg_order_items i ON i.order_id = r.first_order_id
    GROUP BY r.customer_id
),
first_ticket AS (
    SELECT r.customer_id, MAX(t.resolution_hours) AS first_order_ticket_hours
    FROM first_order_row r JOIN stg_support_tickets t ON t.order_id = r.first_order_id
    GROUP BY r.customer_id
),
first_return AS (
    SELECT r.customer_id, 1 AS first_order_returned
    FROM first_order_row r JOIN stg_returns ret ON ret.order_id = r.first_order_id
    GROUP BY r.customer_id
),
second_orders AS (
    SELECT o.customer_id, MIN(o.order_date) AS second_order_date
    FROM stg_orders o JOIN first_orders f ON f.customer_id = o.customer_id
    WHERE o.order_status <> 'cancelled' AND o.order_date > f.first_order_date
    GROUP BY o.customer_id
)
SELECT c.customer_id, c.signup_date, c.acquisition_channel, c.country, c.city, c.age_band,
       c.preferred_device, c.marketing_consent,
       f.order_date AS first_order_date,
       strftime('%Y-%m', f.order_date) AS cohort_month,
       COALESCE(v.first_order_value, 0.0) AS first_order_value,
       CASE WHEN f.discount_rate = 0 THEN 'none'
            WHEN f.discount_rate <= 0.15 THEN 'light'
            WHEN f.discount_rate <= 0.30 THEN 'medium'
            ELSE 'heavy' END AS first_order_discount_band,
       (f.actual_delivery_days - f.promised_delivery_days) AS first_order_delay_days,
       CASE WHEN (f.actual_delivery_days - f.promised_delivery_days) > 5 THEN 1 ELSE 0 END AS first_order_delayed,
       t.first_order_ticket_hours,
       CASE WHEN t.first_order_ticket_hours > 72 THEN 1 ELSE 0 END AS first_order_long_ticket,
       COALESCE(r.first_order_returned, 0) AS first_order_returned,
       date_diff('day', f.order_date, s.second_order_date) AS days_to_second_order,
       CASE WHEN date_diff('day', f.order_date, s.second_order_date) <= 90 THEN 1 ELSE 0 END AS is_repeat_90d,
       CASE WHEN s.second_order_date IS NOT NULL THEN 1 ELSE 0 END AS is_repeat_ever,
       CASE WHEN date_diff('day', f.order_date, DATE '2025-12-31') >= 90 THEN 1 ELSE 0 END AS has_full_90d_window,
       date_diff('day', c.signup_date, DATE '2025-12-31') AS tenure_days
FROM stg_customers c
LEFT JOIN first_order_row f USING (customer_id)
LEFT JOIN first_order_value v USING (customer_id)
LEFT JOIN first_ticket t USING (customer_id)
LEFT JOIN first_return r USING (customer_id)
LEFT JOIN second_orders s USING (customer_id);

-- Fact: orders enriched with basket totals + delivery diagnostics.
CREATE OR REPLACE TABLE fct_orders AS
WITH basket AS (
    SELECT order_id,
           SUM(quantity * unit_price) AS order_total,
           SUM(quantity) AS units,
           COUNT(*) AS order_lines
    FROM stg_order_items GROUP BY order_id
)
SELECT o.order_id, o.customer_id, o.order_date, o.order_status, o.ship_country,
       strftime('%Y-%m', o.order_date) AS order_month,
       o.discount_rate,
       CASE WHEN o.discount_rate = 0 THEN 'none'
            WHEN o.discount_rate <= 0.15 THEN 'light'
            WHEN o.discount_rate <= 0.30 THEN 'medium'
            ELSE 'heavy' END AS discount_band,
       (o.actual_delivery_days - o.promised_delivery_days) AS delivery_delay_days,
       CASE WHEN (o.actual_delivery_days - o.promised_delivery_days) > 5 THEN 1 ELSE 0 END AS is_delayed,
       o.shipping_cost, o.payment_method, o.device,
       COALESCE(b.order_total, 0.0) AS order_total,
       COALESCE(b.units, 0) AS units,
       COALESCE(b.order_lines, 0) AS order_lines
FROM stg_orders o LEFT JOIN basket b USING (order_id);

-- Fact: order lines with product economics.
CREATE OR REPLACE TABLE fct_order_items AS
SELECT i.order_item_id, i.order_id, i.product_id, p.category,
       i.quantity, i.unit_price, p.cost AS unit_cost,
       i.quantity * i.unit_price AS line_revenue,
       i.quantity * (i.unit_price - p.cost) AS line_margin
FROM stg_order_items i JOIN stg_products p USING (product_id);

-- Customer purchase sequence (window functions: ROW_NUMBER + LAG).
CREATE OR REPLACE TABLE mart_customer_orders AS
SELECT order_id, customer_id, order_date, order_status,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS order_seq,
       date_diff('day', LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id), order_date) AS days_since_prev_order
FROM stg_orders;

-- Cohort table: 90-day repeat rate per first-order month (censoring flagged).
CREATE OR REPLACE TABLE mart_cohort_retention AS
WITH base AS (
    SELECT cohort_month, is_repeat_90d, has_full_90d_window
    FROM dim_customer WHERE first_order_date IS NOT NULL
)
SELECT cohort_month,
       COUNT(*) AS customers,
       SUM(is_repeat_90d) AS repeaters_90d,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d,
       CASE WHEN MAX(has_full_90d_window) = 0 THEN 1 ELSE 0 END AS censored
FROM base GROUP BY cohort_month ORDER BY cohort_month;

-- RFM scores (window function showcase: NTILE).
CREATE OR REPLACE TABLE mart_rfm AS
WITH agg AS (
    SELECT o.customer_id,
           date_diff('day', MAX(o.order_date), DATE '2025-12-31') AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(i.line_revenue) AS monetary
    FROM fct_orders o
    JOIN fct_order_items i USING (order_id)
    WHERE o.order_status <> 'cancelled'
    GROUP BY o.customer_id
)
-- r/m use NTILE (continuous distributions). f uses explicit thresholds because
-- ~2/3 of customers sit on frequency = 1 (NTILE would split ties arbitrarily).
SELECT customer_id, recency_days, frequency, ROUND(monetary, 2) AS monetary,
       NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
       CASE WHEN frequency >= 6 THEN 5 WHEN frequency >= 4 THEN 4
            WHEN frequency = 3 THEN 3 WHEN frequency = 2 THEN 2
            ELSE 1 END AS f_score,
       NTILE(5) OVER (ORDER BY monetary) AS m_score
FROM agg;
