WITH completed AS (
    SELECT order_id, customer_id, order_date, amount
    FROM orders WHERE status = 'completed'
),
customer_orders AS (
    SELECT customer_id, COUNT(*) AS completed_orders
    FROM completed GROUP BY customer_id
),
overall AS (
    SELECT COUNT(*) AS completed_orders,
           ROUND(SUM(amount),2) AS completed_revenue,
           ROUND(AVG(amount),2) AS average_order_value,
           COUNT(DISTINCT customer_id) AS purchasing_customers
    FROM completed
),
repeat AS (
    SELECT SUM(CASE WHEN completed_orders >= 2 THEN 1 ELSE 0 END) AS repeat_customers
    FROM customer_orders
)
SELECT overall.completed_orders, overall.completed_revenue, overall.average_order_value,
       overall.purchasing_customers, repeat.repeat_customers,
       ROUND(100.0*repeat.repeat_customers/NULLIF(overall.purchasing_customers,0),2) AS repeat_customer_rate_pct
FROM overall CROSS JOIN repeat;
