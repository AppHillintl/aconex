import csv
import re
import duckdb

CSV_PATH = r"C:\Users\bimst\Downloads\ACONEX\Data\transmittal history by document (1).csv"

# Check row count and headers
with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.reader(f)
    headers = next(reader)
    clean_headers = [h.strip().lstrip('\ufeff') for h in headers]
    print("Columns (total %d):" % len(clean_headers))
    for i, h in enumerate(clean_headers):
        print(f"  {i}: {h}")

    samples = []
    for _ in range(5):
        samples.append(next(reader))

print("\nSample row 0:")
for h, val in zip(clean_headers, samples[0]):
    if val:
        print(f"  {h}: {val[:80]}")
