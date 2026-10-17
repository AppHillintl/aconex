import duckdb

con = duckdb.connect("aconex.duckdb", read_only=True)
print("=== DISTINCT TO_ORGANIZATIONS IN FACT_RFIS (since 2026-03-01) ===")
rows = con.execute("""
    SELECT to_organization, count(*) as cnt, sum(case when is_overdue or days_late > 0 then 1 else 0 end) as ov_cnt
    FROM fact_rfis
    WHERE sent_date >= TIMESTAMP '2026-03-01'
    GROUP BY 1
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f"  {r[0]}: total={r[1]}, overdue={r[2]}")

print("\n=== CONTRACTOR RFIs BY PROJECT AND TO_ORG ===")
rows2 = con.execute("""
    SELECT project_package, to_organization, count(*) as cnt, sum(case when is_overdue or days_late > 0 then 1 else 0 end) as ov_cnt
    FROM fact_rfis
    WHERE sent_date >= TIMESTAMP '2026-03-01'
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
""").fetchall()
for r in rows2[:25]:
    print(f"  [{r[0]}] -> {r[1]}: total={r[2]}, overdue={r[3]}")
