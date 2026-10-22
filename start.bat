@echo off
echo ========================================================
echo   AKADEMIK DERGI INDEKS DENETIM VE DOI YONETIM PORTALI
echo ========================================================
echo.
echo Sanal ortam ve bagimliliklar kontrol ediliyor...
set PYTHONPATH=.
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
