import duckdb
try:
    con = duckdb.connect('aconex.duckdb', read_only=False)
    print("Success connecting read-write!")
    con.close()
except Exception as e:
    print("Error connecting read-write:", type(e), e)
