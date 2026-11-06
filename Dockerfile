FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY src ./src
COPY data ./data
COPY demo_fixtures ./demo_fixtures
COPY offline_fixtures ./offline_fixtures
COPY scripts ./scripts
COPY tests ./tests
COPY pytest.ini .

# Build-time CI assertions: validate schema and run test suite
# Immediate build failure if schemas are broken or fixtures are missing
RUN python scripts/validate_mission_schemas.py
RUN pytest tests/test_api.py tests/test_offline.py tests/test_api_payloads.py

EXPOSE 8000

# Container runtime healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
