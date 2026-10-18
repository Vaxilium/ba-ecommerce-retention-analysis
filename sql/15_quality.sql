-- ============================================================================
-- 15_quality.sql — data-quality evidence
--   cleaning_log : issues FOUND in raw + rule applied + rows affected
--   dq_findings  : post-clean validation (observed should equal expected)
-- One INSERT ... SELECT per rule so the counts come straight from the data.
-- ============================================================================

CREATE OR REPLACE TABLE cleaning_log (
    step_order INTEGER, table_name VARCHAR, issue VARCHAR,
    rows_found BIGINT, action VARCHAR, rule_applied VARCHAR);

INSERT INTO cleaning_log SELECT 1, 'products', 'cost above list price',
  (SELECT COUNT(*) FROM raw_products WHERE CAST(cost AS DOUBLE) > CAST(list_price AS DOUBLE)),
  'fixed', 'clamp cost to 90 percent of list_price';
INSERT INTO cleaning_log SELECT 2, 'products', 'null category',
  (SELECT COUNT(*) FROM raw_products WHERE category IS NULL), 'fixed', 'set to Uncategorized';
INSERT INTO cleaning_log SELECT 3, 'products', 'duplicate product_id',
  (SELECT COUNT(*) - COUNT(DISTINCT product_id) FROM raw_products), 'dropped', 'keep first row per product_id';
INSERT INTO cleaning_log SELECT 4, 'customers', 'null signup_date',
  (SELECT COUNT(*) FROM raw_customers WHERE signup_date IS NULL), 'dropped', 'row cannot be dated; drop';
INSERT INTO cleaning_log SELECT 5, 'customers', 'duplicate customer_id',
  (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM raw_customers), 'dropped', 'keep first row per customer_id';
INSERT INTO cleaning_log SELECT 6, 'customers', 'null / non-canonical country',
  (SELECT COUNT(*) FROM raw_customers WHERE country IS NULL OR LOWER(TRIM(country)) NOT IN
    ('mexico','brasil','brazil','perú','peru','chile','colombia','argentina')),
  'fixed', 'trim/lower/accents to canonical name; null to Unknown';
INSERT INTO cleaning_log SELECT 7, 'customers', 'duplicate emails across customers',
  (SELECT COUNT(*) - COUNT(DISTINCT email) FROM raw_customers), 'flagged', 'kept (email is not a primary key)';
INSERT INTO cleaning_log SELECT 8, 'orders', 'future order dates (after 2025-12-31)',
  (SELECT COUNT(*) FROM raw_orders WHERE CAST(order_date AS DATE) > DATE '2025-12-31'),
  'dropped', 'beyond data snapshot';
INSERT INTO cleaning_log SELECT 9, 'orders', 'duplicate order_id',
  (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM raw_orders), 'dropped', 'keep first row per order_id';
INSERT INTO cleaning_log SELECT 10, 'orders', 'orders of invalid/dropped customers',
  (SELECT COUNT(*) FROM raw_orders WHERE customer_id NOT IN (SELECT customer_id FROM stg_customers)),
  'dropped', 'no valid customer reference';
INSERT INTO cleaning_log SELECT 11, 'orders', 'null / non-canonical ship_country',
  (SELECT COUNT(*) FROM raw_orders WHERE ship_country IS NULL OR LOWER(TRIM(ship_country)) NOT IN
    ('mexico','brasil','brazil','perú','peru','chile','colombia','argentina')),
  'fixed', 'trim/lower/accents to canonical name; null to Unknown';
INSERT INTO cleaning_log SELECT 12, 'orders', 'negative shipping_cost',
  (SELECT COUNT(*) FROM raw_orders WHERE CAST(shipping_cost AS DOUBLE) < 0), 'fixed', 'set to 0.0';
INSERT INTO cleaning_log SELECT 13, 'orders', 'null discount_rate',
  (SELECT COUNT(*) FROM raw_orders WHERE discount_rate IS NULL), 'fixed', 'set to 0.0 (no discount recorded)';
INSERT INTO cleaning_log SELECT 14, 'order_items', 'quantity <= 0',
  (SELECT COUNT(*) FROM raw_order_items WHERE CAST(quantity AS INTEGER) <= 0),
  'dropped', 'returns live in returns table; negative lines are errors';
INSERT INTO cleaning_log SELECT 15, 'order_items', 'unit_price <= 0',
  (SELECT COUNT(*) FROM raw_order_items WHERE CAST(unit_price AS DOUBLE) <= 0), 'dropped', 'invalid price';
INSERT INTO cleaning_log SELECT 16, 'order_items', 'orphan order_id or product_id',
  (SELECT COUNT(*) FROM raw_order_items
    WHERE order_id NOT IN (SELECT order_id FROM stg_orders)
       OR product_id NOT IN (SELECT product_id FROM stg_products)),
  'dropped', 'referential integrity';
INSERT INTO cleaning_log SELECT 17, 'marketing_touches', 'duplicate touch_id',
  (SELECT COUNT(*) - COUNT(DISTINCT touch_id) FROM raw_marketing_touches), 'dropped', 'keep first row per touch_id';
INSERT INTO cleaning_log SELECT 18, 'marketing_touches', 'null or uppercase channel',
  (SELECT COUNT(*) FROM raw_marketing_touches WHERE channel IS NULL OR channel <> LOWER(TRIM(channel))),
  'fixed', 'lowercase; null to unknown';
INSERT INTO cleaning_log SELECT 19, 'marketing_touches', 'future touch dates',
  (SELECT COUNT(*) FROM raw_marketing_touches WHERE CAST(touch_date AS DATE) > DATE '2025-12-31'),
  'dropped', 'beyond data snapshot';
INSERT INTO cleaning_log SELECT 20, 'support_tickets', 'resolved_at before opened_at',
  (SELECT COUNT(*) FROM raw_support_tickets
    WHERE resolved_at IS NOT NULL AND CAST(resolved_at AS TIMESTAMP) < CAST(opened_at AS TIMESTAMP)),
  'dropped', 'impossible timeline';
INSERT INTO cleaning_log SELECT 21, 'support_tickets', 'null topic',
  (SELECT COUNT(*) FROM raw_support_tickets WHERE topic IS NULL), 'fixed', 'set to unknown';
INSERT INTO cleaning_log SELECT 22, 'support_tickets', 'orphan customer_id',
  (SELECT COUNT(*) FROM raw_support_tickets WHERE customer_id NOT IN (SELECT customer_id FROM stg_customers)),
  'dropped', 'no valid customer reference';
INSERT INTO cleaning_log SELECT 23, 'returns', 'negative refund_amount',
  (SELECT COUNT(*) FROM raw_returns WHERE CAST(refund_amount AS DOUBLE) < 0), 'dropped', 'refunds cannot be negative';
INSERT INTO cleaning_log SELECT 24, 'returns', 'null reason',
  (SELECT COUNT(*) FROM raw_returns WHERE reason IS NULL), 'fixed', 'set to unknown';
INSERT INTO cleaning_log SELECT 25, 'returns', 'future requested_date',
  (SELECT COUNT(*) FROM raw_returns WHERE CAST(requested_date AS DATE) > DATE '2025-12-31'),
  'dropped', 'beyond data snapshot';

CREATE OR REPLACE TABLE dq_findings (
    check_name VARCHAR, table_name VARCHAR, observed BIGINT, expected BIGINT, severity VARCHAR);

INSERT INTO dq_findings SELECT 'no duplicate customers', 'stg_customers',
  (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM stg_customers), 0, 'error';
INSERT INTO dq_findings SELECT 'no null signup_date', 'stg_customers',
  (SELECT COUNT(*) FROM stg_customers WHERE signup_date IS NULL), 0, 'error';
INSERT INTO dq_findings SELECT 'no duplicate orders', 'stg_orders',
  (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM stg_orders), 0, 'error';
INSERT INTO dq_findings SELECT 'no future order dates', 'stg_orders',
  (SELECT COUNT(*) FROM stg_orders WHERE order_date > DATE '2025-12-31'), 0, 'error';
INSERT INTO dq_findings SELECT 'no negative shipping', 'stg_orders',
  (SELECT COUNT(*) FROM stg_orders WHERE shipping_cost < 0), 0, 'error';
INSERT INTO dq_findings SELECT 'no null discount', 'stg_orders',
  (SELECT COUNT(*) FROM stg_orders WHERE discount_rate IS NULL), 0, 'error';
INSERT INTO dq_findings SELECT 'orders have valid customer', 'stg_orders',
  (SELECT COUNT(*) FROM stg_orders o WHERE NOT EXISTS
     (SELECT 1 FROM stg_customers c WHERE c.customer_id = o.customer_id)), 0, 'error';
INSERT INTO dq_findings SELECT 'no non-positive quantities', 'stg_order_items',
  (SELECT COUNT(*) FROM stg_order_items WHERE quantity <= 0), 0, 'error';
INSERT INTO dq_findings SELECT 'no non-positive prices', 'stg_order_items',
  (SELECT COUNT(*) FROM stg_order_items WHERE unit_price <= 0), 0, 'error';
INSERT INTO dq_findings SELECT 'items have valid order', 'stg_order_items',
  (SELECT COUNT(*) FROM stg_order_items i WHERE NOT EXISTS
     (SELECT 1 FROM stg_orders o WHERE o.order_id = i.order_id)), 0, 'error';
INSERT INTO dq_findings SELECT 'items have valid product', 'stg_order_items',
  (SELECT COUNT(*) FROM stg_order_items i WHERE NOT EXISTS
     (SELECT 1 FROM stg_products p WHERE p.product_id = i.product_id)), 0, 'error';
INSERT INTO dq_findings SELECT 'no cost above price', 'stg_products',
  (SELECT COUNT(*) FROM stg_products WHERE cost > list_price), 0, 'error';
INSERT INTO dq_findings SELECT 'tickets have valid timeline', 'stg_support_tickets',
  (SELECT COUNT(*) FROM stg_support_tickets WHERE resolved_at < opened_at), 0, 'error';
INSERT INTO dq_findings SELECT 'no negative refunds', 'stg_returns',
  (SELECT COUNT(*) FROM stg_returns WHERE refund_amount < 0), 0, 'error';
INSERT INTO dq_findings SELECT 'no future touches', 'stg_marketing_touches',
  (SELECT COUNT(*) FROM stg_marketing_touches WHERE touch_date > DATE '2025-12-31'), 0, 'error';
INSERT INTO dq_findings SELECT 'resolution_hours match timestamps', 'stg_support_tickets',
  (SELECT COUNT(*) FROM stg_support_tickets
    WHERE ABS(resolution_hours - (date_diff('second', opened_at, resolved_at) / 3600.0)) > 0.02), 0, 'error';
