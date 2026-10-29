WITH completed AS (
    SELECT o.customer_id, o.order_date,
           strftime('%Y-%m', o.order_date) AS order_month
    FROM orders o
    WHERE o.status = 'completed'
),
cohorts AS (
    SELECT customer_id, strftime('%Y-%m', signup_date) AS cohort_month
    FROM customers
),
activity AS (
    SELECT c.cohort_month, o.order_month,
           (CAST(substr(o.order_month,1,4) AS INTEGER) - CAST(substr(c.cohort_month,1,4) AS INTEGER))*12
           + CAST(substr(o.order_month,6,2) AS INTEGER) - CAST(substr(c.cohort_month,6,2) AS INTEGER) AS month_number,
           COUNT(DISTINCT o.customer_id) AS active_customers
    FROM cohorts c JOIN completed o USING(customer_id)
    GROUP BY c.cohort_month, o.order_month
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS customers
    FROM cohorts GROUP BY cohort_month
)
SELECT a.cohort_month, a.month_number, s.customers AS cohort_customers,
       a.active_customers,
       ROUND(100.0*a.active_customers/s.customers, 2) AS retention_pct
FROM activity a JOIN cohort_size s USING(cohort_month)
ORDER BY a.cohort_month, a.month_number;
