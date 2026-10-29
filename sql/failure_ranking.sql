WITH grouped_failures AS (
    SELECT
        model_tier,
        team_id,
        SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited_requests,
        SUM(CASE WHEN status_code = 500 THEN 1 ELSE 0 END) AS server_error_requests,
        COUNT(*) AS failed_requests
    FROM api_requests
    WHERE status_code <> 200
    GROUP BY model_tier, team_id
), ranked AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            PARTITION BY model_tier
            ORDER BY failed_requests DESC
        ) AS failure_rank_within_model
    FROM grouped_failures
)
SELECT
    model_tier,
    team_id,
    rate_limited_requests,
    server_error_requests,
    failed_requests,
    failure_rank_within_model
FROM ranked
ORDER BY model_tier, failure_rank_within_model, team_id;
