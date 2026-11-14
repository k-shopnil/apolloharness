FROM python:3.12-slim

WORKDIR /app

# libexpat1 is required by the rasterio wheels on debian-slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY offline_fixtures/ /app/offline_fixtures/

ENV PYTHONPATH=/app

# If the build context came from a clone without Git LFS (some hosts don't pull
# LFS objects), data/ holds pointer files. Download those from the original
# publishers (NASA PDS, NAIF, USGS), then fail the build unless every required
# file is present and valid, so the API never starts on placeholder data.
RUN python -m src.acquire.verify_data --quick > /dev/null \
    || python -m src.acquire.verify_data --fetch \
    && python -m src.acquire.verify_data --quick

# Hosts such as Render inject PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
