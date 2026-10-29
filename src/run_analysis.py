"""Build a reproducible synthetic LLM-usage analytics case study.

The main analysis uses only the Python standard library and SQLite.
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "sample_api_requests.jsonl"
SCENARIO_PATH = ROOT / "config" / "model_scenarios.csv"
REPORTS = ROOT / "reports"
SEED = 42
N_REQUESTS = 2_500
MILLION = 1_000_000


def generate_requests() -> list[dict[str, object]]:
    """Generate a fixed, synthetic 30-day request sample."""
    rng = random.Random(SEED)
    teams = ["team_alpha", "team_bravo", "team_charlie", "team_delta"]
    models = ["economy", "standard", "premium"]
    start = datetime(2026, 9, 1)
    requests: list[dict[str, object]] = []

    for index in range(1, N_REQUESTS + 1):
        team = rng.choices(teams, weights=[40, 28, 20, 12], k=1)[0]
        model = rng.choices(models, weights=[55, 30, 15], k=1)[0]
        failure_rates = {
            "economy": (0.020, 0.004),
            "standard": (0.030, 0.007),
            "premium": (0.025, 0.010),
        }
        rate_limited, server_error = failure_rates[model]
        draw = rng.random()
        if draw < rate_limited:
            status = 429
        elif draw < rate_limited + server_error:
            status = 500
        else:
            status = 200

        prompt = max(1, int(rng.lognormvariate(6.55, 0.55)))
        completion = max(1, int(rng.lognormvariate(5.75, 0.60)))
        if status != 200:
            # The scenario treats failed requests as having no billable tokens.
            prompt = 0
            completion = 0
        timestamp = start + timedelta(seconds=rng.randrange(30 * 24 * 60 * 60))
        latency = max(25.0, 120 + prompt * 0.45 + completion * 1.15 + rng.gauss(0, 90))
        requests.append(
            {
                "request_id": f"req_{index:05d}",
                "event_timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "team_id": team,
                "model_tier": model,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "status_code": status,
                "latency_ms": round(latency, 1),
            }
        )
    return requests


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_requests(requests: list[dict[str, object]]) -> dict[str, int]:
    required = {
        "request_id",
        "event_timestamp",
        "team_id",
        "model_tier",
        "prompt_tokens",
        "completion_tokens",
        "status_code",
        "latency_ms",
    }
    duplicate_ids = len(requests) - len({row["request_id"] for row in requests})
    missing_values = sum(
        1 for row in requests for field in required if row.get(field) in (None, "")
    )
    invalid_statuses = sum(row["status_code"] not in (200, 429, 500) for row in requests)
    negative_tokens = sum(
        int(row["prompt_tokens"]) < 0 or int(row["completion_tokens"]) < 0
        for row in requests
    )
    invalid_timestamps = 0
    for row in requests:
        try:
            datetime.strptime(str(row["event_timestamp"]), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            invalid_timestamps += 1

    qa = {
        "rows_received": len(requests),
        "duplicate_request_ids": duplicate_ids,
        "missing_required_values": missing_values,
        "invalid_status_codes": invalid_statuses,
        "negative_token_values": negative_tokens,
        "invalid_timestamps": invalid_timestamps,
    }
    if any(value for key, value in qa.items() if key != "rows_received"):
        raise ValueError(f"Input validation failed: {qa}")
    return qa


def execute_query(connection: sqlite3.Connection, filename: str) -> list[dict[str, object]]:
    sql = (ROOT / "sql" / filename).read_text(encoding="utf-8")
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def write_svg_bar_chart(path: Path, values: list[tuple[str, float]]) -> None:
    width, height = 820, 420
    left, right, top, bottom = 180, 40, 55, 55
    chart_width = width - left - right
    chart_height = height - top - bottom
    max_value = max((value for _, value in values), default=1.0) or 1.0
    row_height = chart_height / max(len(values), 1)
    colors = ["#1F5A7A", "#3C86A8", "#76A9BD", "#B5D3DC"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#263746}.title{font-size:20px;font-weight:700}.label{font-size:14px}.value{font-size:13px}</style>',
        f'<text class="title" x="{left}" y="30">Estimated spend by model tier</text>',
    ]
    for index, (label, value) in enumerate(values):
        y = top + index * row_height + row_height * 0.20
        bar_height = row_height * 0.58
        bar_width = chart_width * value / max_value
        parts.append(f'<text class="label" text-anchor="end" x="{left - 12}" y="{y + bar_height * 0.75:.1f}">{label}</text>')
        parts.append(f'<rect x="{left}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" rx="4" fill="{colors[index % len(colors)]}"/>')
        parts.append(f'<text class="value" x="{left + bar_width + 8:.1f}" y="{y + bar_height * 0.75:.1f}">${value:,.2f}</text>')
    parts.append(f'<text class="label" x="{left}" y="{height - 15}">Illustrative USD scenario; successful requests only</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def write_svg_line_chart(path: Path, values: list[tuple[str, float]]) -> None:
    width, height = 900, 420
    left, right, top, bottom = 65, 30, 55, 75
    chart_width = width - left - right
    chart_height = height - top - bottom
    max_value = max((value for _, value in values), default=1.0)
    max_value = max(10.0, max_value * 1.15)
    points = []
    for index, (_, value) in enumerate(values):
        x = left + chart_width * index / max(len(values) - 1, 1)
        y = top + chart_height * (1 - value / max_value)
        points.append((x, y))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#263746}.title{font-size:20px;font-weight:700}.label{font-size:12px}</style>',
        '<text class="title" x="65" y="30">Daily request error rate</text>',
    ]
    for tick in range(0, 11, 2):
        y = top + chart_height * (1 - tick / max_value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e7edf0"/>')
        parts.append(f'<text class="label" text-anchor="end" x="{left - 10}" y="{y + 4:.1f}">{tick}%</text>')
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    parts.append(f'<polyline fill="none" stroke="#B24C3E" stroke-width="3" points="{polyline}"/>')
    for index in sorted(set([0, len(values) // 2, len(values) - 1])):
        if values:
            x, y = points[index]
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#B24C3E"/>')
            parts.append(f'<text class="label" text-anchor="middle" x="{x:.1f}" y="{height - 38}">{values[index][0]}</text>')
    parts.append(f'<text class="label" x="{left}" y="{height - 15}">Non-200 requests / all requests</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def write_findings(
    costs: list[dict[str, object]],
    daily: list[dict[str, object]],
    failures: list[dict[str, object]],
    qa: dict[str, int],
) -> None:
    spend_by_model: dict[str, float] = {}
    spend_by_team: dict[str, float] = {}
    for row in costs:
        spend_by_model[str(row["model_tier"])] = spend_by_model.get(str(row["model_tier"]), 0.0) + float(row["estimated_spend_usd"])
        spend_by_team[str(row["team_id"])] = spend_by_team.get(str(row["team_id"]), 0.0) + float(row["estimated_spend_usd"])
    top_model = max(spend_by_model, key=spend_by_model.get)
    top_team = max(spend_by_team, key=spend_by_team.get)
    peak_error = max(daily, key=lambda row: float(row["error_rate_pct"]))
    top_failure = max(failures, key=lambda row: int(row["failed_requests"]))

    lines = [
        "# Findings from the synthetic sample",
        "",
        f"The run generated **{qa['rows_received']:,} synthetic requests**. Input QA found "
        f"{qa['duplicate_request_ids']} duplicate IDs, {qa['missing_required_values']} missing required values, "
        f"{qa['invalid_status_codes']} invalid statuses, {qa['negative_token_values']} negative token rows, "
        f"and {qa['invalid_timestamps']} invalid timestamps.",
        "",
        f"- Under the configured illustrative rates, **{top_model}** has the highest estimated spend "
        f"(${spend_by_model[top_model]:,.2f}).",
        f"- **{top_team}** has the highest estimated spend across the sample "
        f"(${spend_by_team[top_team]:,.2f}).",
        f"- The highest daily non-200 rate is **{float(peak_error['error_rate_pct']):.1f}%** on "
        f"{peak_error['event_date']}.",
        f"- The most frequent failure group is **{top_failure['team_id']} / {top_failure['model_tier']}** "
        f"with {int(top_failure['failed_requests'])} failed requests.",
        "",
        "## Possible follow-up",
        "Review high-spend and high-failure groups together before proposing an intervention. In a real setting, "
        "validate retry behavior, provider billing rules, traffic volume, and service-level targets first.",
        "",
        "## Limitations",
        "This is a deterministic synthetic demonstration. The rate card is illustrative, failures are assigned zero "
        "billable tokens, and the sample does not support claims about real users, current provider prices, or causal savings.",
    ]
    (REPORTS / "findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    requests = generate_requests()
    qa = validate_requests(requests)
    with RAW_PATH.open("w", encoding="utf-8") as stream:
        for row in requests:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    scenarios = read_csv(SCENARIO_PATH)

    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            """CREATE TABLE api_requests (
                request_id TEXT PRIMARY KEY,
                event_timestamp TEXT NOT NULL,
                team_id TEXT NOT NULL,
                model_tier TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE model_scenarios (
                model_tier TEXT PRIMARY KEY,
                input_usd_per_million REAL NOT NULL,
                output_usd_per_million REAL NOT NULL,
                scenario_note TEXT NOT NULL
            )"""
        )
        connection.executemany(
            "INSERT INTO api_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(row.values()) for row in requests],
        )
        connection.executemany(
            "INSERT INTO model_scenarios VALUES (?, ?, ?, ?)",
            [
                (
                    row["model_tier"],
                    float(row["input_usd_per_million"]),
                    float(row["output_usd_per_million"]),
                    row["scenario_note"],
                )
                for row in scenarios
            ],
        )
        cost_by_team_model = execute_query(connection, "cost_by_team_model.sql")
        daily_operations = execute_query(connection, "daily_operations.sql")
        failure_ranking = execute_query(connection, "failure_ranking.sql")

    write_csv(REPORTS / "cost_by_team_model.csv", cost_by_team_model)
    write_csv(REPORTS / "daily_operations.csv", daily_operations)
    write_csv(REPORTS / "failure_ranking.csv", failure_ranking)
    (REPORTS / "qa_summary.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    totals: dict[str, float] = {}
    for row in cost_by_team_model:
        model = str(row["model_tier"])
        totals[model] = totals.get(model, 0.0) + float(row["estimated_spend_usd"])
    model_values = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    write_svg_bar_chart(REPORTS / "spend_by_model.svg", model_values)
    daily_values = [(str(row["event_date"]), float(row["error_rate_pct"])) for row in daily_operations]
    write_svg_line_chart(REPORTS / "daily_error_rate.svg", daily_values)
    write_findings(cost_by_team_model, daily_operations, failure_ranking, qa)

    print(f"Generated {len(requests):,} synthetic requests.")
    print(f"Wrote reports to: {REPORTS}")
    print(f"Top model tier by scenario spend: {model_values[0][0]}")


if __name__ == "__main__":
    main()
