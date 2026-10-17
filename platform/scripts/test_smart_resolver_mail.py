import duckdb

con = duckdb.connect('aconex.duckdb', read_only=True)

gen_mails = con.execute("""
    SELECT mail_no, subject, from_organization, to_organization, mail_type 
    FROM fact_mail 
    WHERE project_package IS NULL OR project_package ILIKE '%General%' OR project_package = ''
""").fetchall()

print(f"Total 'General' Mails: {len(gen_mails):,}")

from test_smart_resolver import smart_resolve_rfi

resolved_mail_counts = {}
for m in gen_mails:
    pkg = smart_resolve_rfi(m[0], m[1], m[2], m[3])
    resolved_mail_counts[pkg] = resolved_mail_counts.get(pkg, 0) + 1

print("\nResolution results for 'General' Mails:")
for p, c in sorted(resolved_mail_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  -> {p:<30}: {c:,}")

con.close()
