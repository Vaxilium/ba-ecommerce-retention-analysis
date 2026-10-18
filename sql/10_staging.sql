-- ============================================================================
-- 10_staging.sql — cleaned, deduplicated, canonical tables (raw -> staging)
-- Engine: DuckDB (fallback: SQLite via build_warehouse.py translation)
-- One comment line per cleaning rule so the log in 15_quality.sql is auditable.
-- ============================================================================

-- Products: dedupe product_id; null category -> 'Uncategorized';
-- cost > list_price -> clamp cost to 90% of price (unit-economics error).
CREATE OR REPLACE TABLE stg_products AS
WITH dedup AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY product_name) AS rn
    FROM raw_products
)
SELECT product_id, product_name,
       COALESCE(category, 'Uncategorized') AS category,
       CAST(list_price AS DOUBLE) AS list_price,
       CASE WHEN CAST(cost AS DOUBLE) > CAST(list_price AS DOUBLE)
            THEN ROUND(CAST(list_price AS DOUBLE) * 0.9, 2)
            ELSE CAST(cost AS DOUBLE) END AS cost,
       CAST(launched_date AS DATE) AS launched_date,
       CAST(active AS BOOLEAN) AS active
FROM dedup WHERE rn = 1;

-- Customers: drop null id/signup_date; dedupe customer_id; canonicalize country
-- (trim, case, accents); null country -> 'Unknown'.
CREATE OR REPLACE TABLE stg_customers AS
WITH dedup AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY signup_date, email) AS rn
    FROM raw_customers
    WHERE customer_id IS NOT NULL AND signup_date IS NOT NULL
)
SELECT customer_id,
       CAST(signup_date AS DATE) AS signup_date,
       acquisition_channel,
       CASE LOWER(TRIM(country))
            WHEN 'mexico' THEN 'Mexico'
            WHEN 'brasil' THEN 'Brazil'
            WHEN 'brazil' THEN 'Brazil'
            WHEN 'perú' THEN 'Peru'
            WHEN 'peru' THEN 'Peru'
            WHEN 'chile' THEN 'Chile'
            WHEN 'colombia' THEN 'Colombia'
            WHEN 'argentina' THEN 'Argentina'
            ELSE 'Unknown' END AS country,
       city, email, age_band,
       CAST(marketing_consent AS BOOLEAN) AS marketing_consent,
       preferred_device
FROM dedup WHERE rn = 1;

-- Orders: dedupe order_id; drop future-dated rows (> snapshot 2025-12-31);
-- drop orders of invalid/dropped customers; canonicalize ship_country;
-- negative shipping_cost -> 0; null discount_rate -> 0.
CREATE OR REPLACE TABLE stg_orders AS
WITH dedup AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) AS rn
    FROM raw_orders
)
SELECT d.order_id,
       d.customer_id,
       CAST(d.order_date AS DATE) AS order_date,
       d.order_status,
       CASE LOWER(TRIM(d.ship_country))
            WHEN 'mexico' THEN 'Mexico'
            WHEN 'brasil' THEN 'Brazil'
            WHEN 'brazil' THEN 'Brazil'
            WHEN 'perú' THEN 'Peru'
            WHEN 'peru' THEN 'Peru'
            WHEN 'chile' THEN 'Chile'
            WHEN 'colombia' THEN 'Colombia'
            WHEN 'argentina' THEN 'Argentina'
            ELSE 'Unknown' END AS ship_country,
       COALESCE(CAST(d.discount_rate AS DOUBLE), 0.0) AS discount_rate,
       CAST(d.promised_delivery_days AS INTEGER) AS promised_delivery_days,
       CAST(d.actual_delivery_days AS INTEGER) AS actual_delivery_days,
       CASE WHEN CAST(d.shipping_cost AS DOUBLE) < 0 THEN 0.0
            ELSE CAST(d.shipping_cost AS DOUBLE) END AS shipping_cost,
       d.payment_method, d.device
FROM dedup d
WHERE d.rn = 1
  AND CAST(d.order_date AS DATE) <= DATE '2025-12-31'
  AND d.customer_id IN (SELECT customer_id FROM stg_customers);

-- Order items: drop non-positive quantity / unit_price; drop rows pointing to
-- dropped orders or unknown products.
CREATE OR REPLACE TABLE stg_order_items AS
SELECT i.order_item_id, i.order_id, i.product_id,
       CAST(i.quantity AS INTEGER) AS quantity,
       CAST(i.unit_price AS DOUBLE) AS unit_price
FROM raw_order_items i
WHERE CAST(i.quantity AS INTEGER) > 0
  AND CAST(i.unit_price AS DOUBLE) > 0
  AND i.order_id IN (SELECT order_id FROM stg_orders)
  AND i.product_id IN (SELECT product_id FROM stg_products);

-- Marketing touches: dedupe touch_id; drop future dates; canonical channel
-- casing; null channel -> 'unknown'; drop touches of dropped customers.
CREATE OR REPLACE TABLE stg_marketing_touches AS
WITH dedup AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY touch_id ORDER BY touch_date) AS rn
    FROM raw_marketing_touches
)
SELECT touch_id, customer_id,
       CAST(touch_date AS DATE) AS touch_date,
       COALESCE(NULLIF(LOWER(TRIM(channel)), ''), 'unknown') AS channel,
       campaign
FROM dedup
WHERE rn = 1
  AND CAST(touch_date AS DATE) <= DATE '2025-12-31'
  AND customer_id IN (SELECT customer_id FROM stg_customers);

-- Support tickets: drop resolved < opened (invalid timestamps); recompute
-- resolution_hours from timestamps; null topic -> 'unknown'; null order link
-- when the referenced order did not survive cleaning.
CREATE OR REPLACE TABLE stg_support_tickets AS
SELECT t.ticket_id, t.customer_id,
       CASE WHEN t.order_id IN (SELECT order_id FROM stg_orders) THEN t.order_id ELSE NULL END AS order_id,
       CAST(t.opened_at AS TIMESTAMP) AS opened_at,
       CAST(t.resolved_at AS TIMESTAMP) AS resolved_at,
       COALESCE(t.topic, 'unknown') AS topic,
       t.contact_channel, t.status,
       ROUND(date_diff('second', CAST(t.opened_at AS TIMESTAMP), CAST(t.resolved_at AS TIMESTAMP)) / 3600.0, 2) AS resolution_hours,
       CAST(t.satisfaction_score AS INTEGER) AS satisfaction_score
FROM raw_support_tickets t
WHERE t.resolved_at IS NOT NULL
  AND CAST(t.resolved_at AS TIMESTAMP) >= CAST(t.opened_at AS TIMESTAMP)
  AND t.customer_id IN (SELECT customer_id FROM stg_customers);

-- Returns: drop negative refunds and future request dates; null reason ->
-- 'unknown'; drop returns whose order did not survive cleaning.
CREATE OR REPLACE TABLE stg_returns AS
SELECT r.return_id, r.order_id,
       CAST(r.requested_date AS DATE) AS requested_date,
       COALESCE(r.reason, 'unknown') AS reason,
       r.status,
       CAST(r.refund_amount AS DOUBLE) AS refund_amount
FROM raw_returns r
WHERE CAST(r.refund_amount AS DOUBLE) >= 0
  AND CAST(r.requested_date AS DATE) <= DATE '2025-12-31'
  AND r.order_id IN (SELECT order_id FROM stg_orders);
