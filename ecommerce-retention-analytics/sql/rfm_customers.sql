WITH completed AS (
    SELECT customer_id, order_date, amount FROM orders WHERE status = 'completed'
),
rfm AS (
    SELECT c.customer_id, c.acquisition_channel, c.region,
           CAST(julianday('2024-12-31') - julianday(MAX(o.order_date)) AS INTEGER) AS recency_days,
           COUNT(o.order_date) AS frequency,
           ROUND(SUM(o.amount),2) AS monetary
    FROM customers c JOIN completed o USING(customer_id)
    GROUP BY c.customer_id, c.acquisition_channel, c.region
)
SELECT customer_id, acquisition_channel, region, recency_days, frequency, monetary,
       CASE WHEN frequency >= 4 AND recency_days <= 60 THEN 'Frequent recent'
            WHEN frequency >= 2 THEN 'Repeat'
            ELSE 'One-time' END AS descriptive_segment
FROM rfm
ORDER BY monetary DESC, frequency DESC, recency_days ASC;
