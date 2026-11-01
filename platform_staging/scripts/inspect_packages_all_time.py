import duckdb

con = duckdb.connect('aconex.duckdb', read_only=True)

print("=== FACT_RFIS: project_package breakdown (ALL TIME) ===")
rfis_all = con.execute("""
    SELECT project_package, count(*) 
    FROM fact_rfis 
    GROUP BY 1 
    ORDER BY 2 DESC
""").fetchall()
for p, c in rfis_all:
    print(f"  {p:<30}: {c:,}")

print("\n=== FACT_RFIS: Items with 'General' or NULL or unmapped ===")
unmapped_rfis = con.execute("""
    SELECT count(*) 
    FROM fact_rfis 
    WHERE project_package IS NULL OR project_package ILIKE '%General%' OR project_package = ''
""").fetchone()[0]
print(f"Total unmapped/general RFIs: {unmapped_rfis}")

print("\nSample of General RFIs (Subject & Mail No):")
sample_gen = con.execute("""
    SELECT mail_no, subject, from_organization, to_organization, sent_date 
    FROM fact_rfis 
    WHERE project_package IS NULL OR project_package ILIKE '%General%' OR project_package = ''
    LIMIT 10
""").fetchall()
for r in sample_gen:
    print(" ", r)

print("\n=== FACT_MAIL: project_package breakdown (ALL TIME) ===")
mail_pkgs = con.execute("""
    SELECT project_package, count(*) 
    FROM fact_mail 
    GROUP BY 1 
    ORDER BY 2 DESC LIMIT 15
""").fetchall()
for p, c in mail_pkgs:
    print(f"  {p:<30}: {c:,}")

print("\n=== FACT_MAIL: General or NULL ===")
unmapped_mails = con.execute("""
    SELECT count(*) 
    FROM fact_mail 
    WHERE project_package IS NULL OR project_package ILIKE '%General%' OR project_package = ''
""").fetchone()[0]
print(f"Total unmapped/general Mails: {unmapped_mails:,}")

con.close()
