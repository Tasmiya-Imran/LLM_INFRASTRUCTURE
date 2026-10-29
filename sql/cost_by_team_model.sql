WITH request_costs AS (
    SELECT
        r.request_id,
        r.team_id,
        r.model_tier,
        r.status_code,
        r.prompt_tokens,
        r.completion_tokens,
        CASE
            WHEN r.status_code = 200 THEN
                (r.prompt_tokens * s.input_usd_per_million
                    + r.completion_tokens * s.output_usd_per_million) / 1000000.0
            ELSE 0.0
        END AS estimated_spend_usd
    FROM api_requests AS r
    INNER JOIN model_scenarios AS s
        ON r.model_tier = s.model_tier
), team_model AS (
    SELECT
        model_tier,
        team_id,
        COUNT(*) AS request_count,
        SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) AS successful_requests,
        SUM(prompt_tokens) AS total_prompt_tokens,
        SUM(completion_tokens) AS total_completion_tokens,
        SUM(estimated_spend_usd) AS estimated_spend_usd
    FROM request_costs
    GROUP BY model_tier, team_id
), ranked AS (
    SELECT
        *,
        SUM(estimated_spend_usd) OVER (PARTITION BY model_tier) AS model_spend_usd,
        DENSE_RANK() OVER (
            PARTITION BY model_tier
            ORDER BY estimated_spend_usd DESC
        ) AS team_rank_within_model
    FROM team_model
)
SELECT
    model_tier,
    team_id,
    request_count,
    successful_requests,
    total_prompt_tokens,
    total_completion_tokens,
    ROUND(estimated_spend_usd, 4) AS estimated_spend_usd,
    ROUND(model_spend_usd, 4) AS model_spend_usd,
    ROUND(100.0 * estimated_spend_usd / NULLIF(model_spend_usd, 0), 2) AS model_spend_share_pct,
    team_rank_within_model
FROM ranked
ORDER BY model_tier, team_rank_within_model, team_id;
