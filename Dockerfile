FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (libexpat1 is required by rasterio wheels on debian-slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application assets
COPY src/ /app/src/
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY offline_fixtures/ /app/offline_fixtures/

ENV PYTHONPATH=/app
ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
