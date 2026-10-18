-- Business question: Do slow support resolutions increase churn?
-- Buckets on the resolution time of tickets linked to the customer's first order.
SELECT CASE WHEN first_order_ticket_hours IS NULL THEN '1_no_ticket'
            WHEN first_order_ticket_hours <= 24 THEN '2_resolved_24h'
            WHEN first_order_ticket_hours <= 72 THEN '3_resolved_72h'
            ELSE '4_over_72h' END AS ticket_bucket,
       COUNT(*) AS customers,
       ROUND(AVG(is_repeat_90d), 4) AS repeat_rate_90d
FROM dim_customer
WHERE has_full_90d_window = 1
GROUP BY ticket_bucket
ORDER BY ticket_bucket;
