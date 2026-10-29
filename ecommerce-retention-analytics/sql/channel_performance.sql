WITH completed AS (
    SELECT o.customer_id, o.amount, o.order_id
    FROM orders o WHERE o.status = 'completed'
),
per_customer AS (
    SELECT customer_id, COUNT(*) AS order_count, SUM(amount) AS spend
    FROM completed GROUP BY customer_id
),
channel AS (
    SELECT c.acquisition_channel,
           COUNT(p.customer_id) AS purchasing_customers,
           SUM(p.order_count) AS completed_orders,
           ROUND(SUM(p.spend),2) AS revenue,
           SUM(CASE WHEN p.order_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers
    FROM customers c LEFT JOIN per_customer p USING(customer_id)
    GROUP BY c.acquisition_channel
)
SELECT acquisition_channel, purchasing_customers, completed_orders, revenue,
       ROUND(100.0*repeat_customers/NULLIF(purchasing_customers,0),2) AS repeat_rate_pct,
       ROUND(revenue/NULLIF(purchasing_customers,0),2) AS revenue_per_purchasing_customer
FROM channel ORDER BY revenue DESC;
