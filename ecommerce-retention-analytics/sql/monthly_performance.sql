WITH completed AS (
    SELECT order_id, customer_id, order_date, amount
    FROM orders WHERE status = 'completed'
),
monthly AS (
    SELECT strftime('%Y-%m', order_date) AS month,
           COUNT(*) AS completed_orders,
           ROUND(SUM(amount), 2) AS revenue,
           COUNT(DISTINCT customer_id) AS purchasing_customers,
           ROUND(AVG(amount), 2) AS average_order_value
    FROM completed GROUP BY strftime('%Y-%m', order_date)
)
SELECT month, completed_orders, revenue, purchasing_customers, average_order_value,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month)) /
         NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS revenue_mom_change_pct
FROM monthly ORDER BY month;
