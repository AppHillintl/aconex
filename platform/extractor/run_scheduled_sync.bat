@echo off
cd /d "C:\Users\bimst\Downloads\ACONEX\platform\extractor"
echo ============================================================ >> sync_live.log
echo [%date% %time%] Aconex Full Pipeline Triggered >> sync_live.log
echo ============================================================ >> sync_live.log

echo [1/2] Running Aconex Master Data Extraction... >> sync_live.log
"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" master_aconex_extractor.py >> sync_live.log 2>&1

echo [2/2] Running DuckDB Parallel Ingestion (ETL)... >> sync_live.log
cd /d "C:\Users\bimst\Downloads\ACONEX\platform\etl"
"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" run_full_update.py >> "C:\Users\bimst\Downloads\ACONEX\platform\extractor\sync_live.log" 2>&1

echo ============================================================ >> "C:\Users\bimst\Downloads\ACONEX\platform\extractor\sync_live.log"
echo [%date% %time%] Aconex Pipeline Completed Successfully! >> "C:\Users\bimst\Downloads\ACONEX\platform\extractor\sync_live.log"
echo ============================================================ >> "C:\Users\bimst\Downloads\ACONEX\platform\extractor\sync_live.log"
