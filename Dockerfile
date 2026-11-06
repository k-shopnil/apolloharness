FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY src ./src
COPY data ./data
COPY demo_fixtures ./demo_fixtures
COPY scripts ./scripts
COPY tests ./tests
COPY pytest.ini .

# Build-time CI assertions: validate schema and run test suite
# Immediate build failure if schemas are broken or fixtures are missing
RUN python scripts/validate_mission_schemas.py
RUN pytest

EXPOSE 8000

# Container runtime healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; p = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{p}/api/v1/health')" || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
