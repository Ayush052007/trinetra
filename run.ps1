# TRINETRA development server
$env:PYTHONPATH = "backend;database;ai;graph"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
