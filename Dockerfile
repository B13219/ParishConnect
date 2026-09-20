FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend ./backend
COPY frontend ./frontend

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ./backend

WORKDIR /app/backend

CMD ["sh", "-c", "alembic upgrade head && python -m app.scripts.bootstrap_admin && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
