# Findings from the synthetic sample

The run generated **2,500 synthetic requests**. Input QA found 0 duplicate IDs, 0 missing required values, 0 invalid statuses, 0 negative token rows, and 0 invalid timestamps.

- Under the configured illustrative rates, **standard** has the highest estimated spend ($5.91).
- **team_alpha** has the highest estimated spend across the sample ($3.94).
- The highest daily non-200 rate is **6.6%** on 2026-09-28.
- The most frequent failure group is **team_alpha / economy** with 17 failed requests.

## Possible follow-up
Review high-spend and high-failure groups together before proposing an intervention. In a real setting, validate retry behavior, provider billing rules, traffic volume, and service-level targets first.

## Limitations
This is a deterministic synthetic demonstration. The rate card is illustrative, failures are assigned zero billable tokens, and the sample does not support claims about real users, current provider prices, or causal savings.
