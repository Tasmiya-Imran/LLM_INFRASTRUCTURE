import csv
import random
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
SQL = ROOT / "sql"
SEED = 20261029
CUTOFF = date(2024, 12, 31)
CHANNELS = ["Search", "Social", "Referral", "Email"]
REGIONS = ["North", "South", "West", "East"]
CATEGORIES = ["Home", "Beauty", "Electronics", "Books", "Fitness"]


def month_start(y, m):
    return date(y, m, 1)


def month_add(d, n):
    idx = d.year * 12 + d.month - 1 + n
    return date(idx // 12, idx % 12 + 1, 1)


def month_end(d):
    return month_add(d, 1) - timedelta(days=1)


def generate_inputs():
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    customers = []
    orders = []
    next_order = 1
    for i in range(1, 2501):
        signup_month = rng.randint(1, 6)
        signup = month_start(2024, signup_month) + timedelta(days=rng.randint(0, 27))
        channel = rng.choices(CHANNELS, weights=[35, 25, 20, 20])[0]
        customer = {"customer_id": f"C{i:05d}", "signup_date": signup.isoformat(),
                    "acquisition_channel": channel, "region": rng.choice(REGIONS)}
        customers.append(customer)
        activity_months = [signup_month]
        for m in range(signup_month + 1, 13):
            base = {"Search": .21, "Social": .17, "Referral": .26, "Email": .24}[channel]
            if rng.random() < base * (0.94 ** (m - signup_month - 1)):
                activity_months.append(m)
        for m in activity_months:
            d0 = max(month_start(2024, m), signup)
            d = d0 + timedelta(days=rng.randint(0, (month_end(month_start(2024, m)) - d0).days))
            amount = round(rng.uniform(12, 240), 2)
            status = rng.choices(["completed", "refunded", "cancelled"], [0.90, 0.06, 0.04])[0]
            orders.append({"order_id": f"O{next_order:06d}", "customer_id": customer["customer_id"],
                           "order_date": d.isoformat(), "amount": f"{amount:.2f}",
                           "category": rng.choice(CATEGORIES), "status": status})
            next_order += 1
    for filename, rows in [("customers.csv", customers), ("orders.csv", orders)]:
        with (DATA / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return len(customers), len(orders)


def load_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE customers(customer_id TEXT, signup_date TEXT, acquisition_channel TEXT, region TEXT)")
    db.execute("CREATE TABLE orders(order_id TEXT, customer_id TEXT, order_date TEXT, amount REAL, category TEXT, status TEXT)")
    with (DATA / "customers.csv").open(encoding="utf-8", newline="") as f:
        db.executemany("INSERT INTO customers VALUES(:customer_id,:signup_date,:acquisition_channel,:region)", csv.DictReader(f))
    with (DATA / "orders.csv").open(encoding="utf-8", newline="") as f:
        db.executemany("INSERT INTO orders VALUES(:order_id,:customer_id,:order_date,:amount,:category,:status)", csv.DictReader(f))
    return db


def export_query(db, filename, outname):
    sql_text = (SQL / filename).read_text(encoding="utf-8-sig")
    cur = db.execute(sql_text)
    headers = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with (REPORTS / outname).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return headers, rows


def write_svg(monthly, cohorts):
    width, height, left, bottom = 760, 390, 72, 310
    vals = [float(row[2]) for row in monthly]
    maxv = max(vals) or 1
    bars = []
    bw = 42
    gap = 12
    for i, row in enumerate(monthly):
        x = left + i * (bw + gap)
        h = 220 * float(row[2]) / maxv
        y = bottom - h
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="{bw}" height="{h:.1f}" rx="4" fill="#3976c5"><title>{escape(row[0])}: ${float(row[2]):,.0f}</title></rect>')
        bars.append(f'<text x="{x+bw/2}" y="{bottom+20}" text-anchor="middle" font-size="10" fill="#344054">{escape(row[0][5:])}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#fff"/><text x="{left}" y="35" font-size="20" font-family="Arial" font-weight="bold" fill="#172b4d">Monthly completed-order revenue</text>
<text x="{left}" y="56" font-size="12" font-family="Arial" fill="#667085">Synthetic sample · USD · completed orders only</text>
<line x1="{left}" y1="{bottom}" x2="{width-24}" y2="{bottom}" stroke="#98a2b3"/>{''.join(bars)}
<text x="22" y="190" transform="rotate(-90 22 190)" font-size="12" font-family="Arial" fill="#667085">Revenue (USD)</text></svg>'''
    (REPORTS / "monthly_revenue.svg").write_text(svg, encoding="utf-8")
    # Cohort heatmap for month 0-6.
    by_cohort = defaultdict(dict)
    for cohort, month_no, size, active, pct in cohorts:
        by_cohort[cohort][int(month_no)] = float(pct)
    cols = 7
    cellw, cellh = 70, 34
    x0, y0 = 145, 108
    w, h = 760, y0 + len(by_cohort)*cellh + 42
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#fff"/>',
             '<text x="24" y="34" font-family="Arial" font-size="20" font-weight="bold" fill="#172b4d">Signup cohort repeat-purchase retention</text>',
             '<text x="24" y="56" font-family="Arial" font-size="12" fill="#667085">Share of cohort with a completed order in each month after signup</text>']
    for j in range(cols):
        parts.append(f'<text x="{x0+j*cellw+cellw/2}" y="88" text-anchor="middle" font-family="Arial" font-size="12" fill="#344054">Month {j}</text>')
    for r, cohort in enumerate(sorted(by_cohort)):
        y = y0 + r*cellh
        parts.append(f'<text x="{x0-12}" y="{y+22}" text-anchor="end" font-family="Arial" font-size="12" fill="#344054">{cohort}</text>')
        for j in range(cols):
            value = by_cohort[cohort].get(j)
            color = "#f2f4f7" if value is None else f'rgb({int(228-1.2*value)},{int(239-0.65*value)},{int(250-0.15*value)})'
            label = "—" if value is None else f"{value:.0f}%"
            parts.append(f'<rect x="{x0+j*cellw}" y="{y}" width="{cellw-3}" height="{cellh-3}" rx="3" fill="{color}"/><text x="{x0+j*cellw+(cellw-3)/2}" y="{y+21}" text-anchor="middle" font-family="Arial" font-size="11" fill="#172b4d">{label}</text>')
    parts.append('</svg>')
    (REPORTS / "cohort_retention.svg").write_text("".join(parts), encoding="utf-8")


def main():
    REPORTS.mkdir(exist_ok=True)
    n_customers, n_orders = generate_inputs()
    db = load_db()
    export_query(db, "executive_kpis.sql", "executive_kpis.csv")
    monthly = export_query(db, "monthly_performance.sql", "monthly_performance.csv")[1]
    channels = export_query(db, "channel_performance.sql", "channel_performance.csv")[1]
    cohorts = export_query(db, "cohort_retention.sql", "cohort_retention.csv")[1]
    rfm = export_query(db, "rfm_customers.sql", "rfm_customers.csv")[1]
    totals = db.execute("""WITH p AS (SELECT customer_id, COUNT(*) n FROM orders WHERE status='completed' GROUP BY customer_id)
        SELECT COUNT(*), ROUND((SELECT SUM(amount) FROM orders WHERE status='completed'),2),
        (SELECT COUNT(*) FROM p), (SELECT COUNT(*) FROM p WHERE n>=2),
        ROUND(100.0*(SELECT COUNT(*) FROM p WHERE n>=2)/NULLIF((SELECT COUNT(*) FROM p),0),2)
        FROM orders WHERE status='completed'""").fetchone()
    write_svg(monthly, cohorts)
    best = max(channels, key=lambda row: float(row[3]))
    revenue_change = next((row[5] for row in monthly if row[0] == "2024-12"), None)
    summary = f'''# Sample findings

This report was generated from **{n_customers:,} synthetic customers** and **{n_orders:,} synthetic orders** with a fixed random seed. The figures below describe only this practice dataset.

- Completed orders: **{totals[0]:,}**
- Completed-order revenue: **${totals[1]:,.2f}**
- Customers with a completed order: **{totals[2]:,}**
- Repeat customer rate: **{totals[4]:.2f}%** ({totals[3]:,} customers with at least two completed orders)
- Highest-revenue acquisition channel in this sample: **{best[0]}** (${float(best[3]):,.2f})
- December revenue month-over-month change: **{float(revenue_change):.2f}%**

## How to read this

These results are generated from a simple simulation with a fixed channel-specific repeat-purchase probability. They demonstrate metric definitions and SQL workflow; they do not imply that an acquisition channel causes retention or that these rates apply to a real store. Cohort month 0 is the signup month. Cancelled and refunded orders are excluded from completed-order revenue.
'''
    (REPORTS / "summary.md").write_text(summary, encoding="utf-8")
    db.close()
    print(f"Generated {n_customers:,} synthetic customers and {n_orders:,} orders; wrote reports to {REPORTS}.")

if __name__ == "__main__":
    main()


