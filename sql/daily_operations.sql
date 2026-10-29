SELECT
    SUBSTR(event_timestamp, 1, 10) AS event_date,
    COUNT(*) AS request_count,
    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) AS successful_requests,
    SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited_requests,
    SUM(CASE WHEN status_code = 500 THEN 1 ELSE 0 END) AS server_error_requests,
    ROUND(100.0 * SUM(CASE WHEN status_code <> 200 THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_rate_pct,
    ROUND(AVG(latency_ms), 1) AS average_latency_ms
FROM api_requests
GROUP BY SUBSTR(event_timestamp, 1, 10)
ORDER BY event_date;
