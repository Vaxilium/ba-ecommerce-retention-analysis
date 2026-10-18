-- Business question: Is the 90-day repeat rate actually declining, and by how much?
-- Method: monthly first-order cohorts + 3-month rolling average + 12-month delta (window functions).
SELECT cohort_month,
       customers,
       repeaters_90d,
       repeat_rate_90d,
       censored,
       ROUND(AVG(repeat_rate_90d) OVER (ORDER BY cohort_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 4) AS rolling_3m_rate,
       ROUND(repeat_rate_90d - LAG(repeat_rate_90d, 12) OVER (ORDER BY cohort_month), 4) AS delta_vs_12m_ago
FROM mart_cohort_retention
ORDER BY cohort_month;
