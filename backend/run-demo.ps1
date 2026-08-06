$env:PARISHCONNECT_DATABASE_URL = "sqlite:///./parishconnect_demo.db"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8003
