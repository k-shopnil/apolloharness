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

# Build the derived caches into the image (cache/derived): the PSR search index
# (FlatGeobuf, ~210 MB on disk, ~250 MB peak RAM to build) and the coarse DEM
# used for far-field horizons. Built at runtime instead, they would be rebuilt
# after every restart, because a host's runtime disk is not kept between
# restarts (Render's free tier restarts after 15 idle minutes).
RUN python -c "from src.compute.site_evaluation import DEFAULT_DEM, DEFAULT_PSR; \
from src.compute.proximity import indexed_psr_path; from src.compute.terrain import coarse_grid; \
indexed_psr_path(DEFAULT_PSR); coarse_grid(DEFAULT_DEM)" \
    && test -f cache/derived/LPSR_80S_20MPP_ADJ.fgb \
    && test -f cache/derived/LDEM_80S_80MPP_ADJ_x4.tif

# Hosts such as Render inject PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
