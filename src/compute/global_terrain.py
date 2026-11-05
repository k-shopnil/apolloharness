"""Per-site metric terrain tiles from the global LOLA GDR (LDEM_64).

The global product cannot be fed to the horizon code directly:

* Heights: DN x 0.5 m is height above the 1737.4 km sphere. GDAL also reports
  the label's OFFSET (1737400 m), which would turn heights into radii, so the
  offset is deliberately not applied.
* Geometry: simple-cylindrical pixels stretch east-west by 1/cos(latitude),
  which biases ray distances. Each tile is therefore resampled to a
  site-centred stereographic grid (conformal; scale error < 0.05 % at 80 km).

Tiles are small, so the ones for catalog sites are committed for offline use:

    python -m src.compute.global_terrain            # tiles for catalog sites
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window

from .datafiles import is_installed, require
from .terrain import DATA_DIR, MOON_GEOGRAPHIC, MOON_RADIUS_M, PROJECT_ROOT, cached_transformer

GLOBAL_DEM = PROJECT_ROOT / "cache" / "nasa" / "pds" / "ldem_64.lbl"
TILE_DIR = DATA_DIR / "lola" / "tiles"
PRODUCT_NAME = "LOLA GDR LDEM_64"
EXPECTED_SCALE = 0.5
EXPECTED_OFFSET_M = MOON_RADIUS_M
# Exceeds terrain.HORIZON_MAX_DISTANCE_M (100 km) so clicks up to ~55 km from a
# catalog site still find complete rays inside its committed tile.
DEFAULT_HALF_WIDTH_M = 160_000.0


def site_crs(latitude_deg: float, longitude_deg: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=stere +lat_0={latitude_deg} +lon_0={longitude_deg} +k=1 +x_0=0 +y_0=0 "
        f"+R={MOON_RADIUS_M} +units=m +type=crs +no_defs")


def _recentred_band(src: rasterio.DatasetReader, latitude_deg: float, longitude_deg: float,
                    half_width_m: float) -> tuple[np.ndarray, rasterio.Affine, CRS]:
    """Latitude band around the site, re-centred so the site longitude is mid-grid.

    In simple-cylindrical projection, changing ``lon_0`` is an exact column
    roll. Re-centring removes the 0/360 seam and keeps the warp well posed
    near the poles, where a tile spans most longitudes.
    """
    pad_deg = np.degrees(half_width_m / MOON_RADIUS_M) * 1.2
    lat_lo, lat_hi = max(latitude_deg - pad_deg, -90.0), min(latitude_deg + pad_deg, 90.0)
    inverse = ~src.transform
    row_hi = int(np.floor(inverse.e * (np.radians(lat_hi) * MOON_RADIUS_M) + inverse.f)) - 1
    row_lo = int(np.ceil(inverse.e * (np.radians(lat_lo) * MOON_RADIUS_M) + inverse.f)) + 1
    row0, row1 = max(row_hi, 0), min(row_lo, src.height)
    data = src.read(1, window=Window(0, row0, src.width, row1 - row0), masked=True)
    data = np.ma.asarray(data, dtype="float32").filled(np.nan)
    to_geo = cached_transformer(src.crs, MOON_GEOGRAPHIC)
    first_lon, _ = to_geo.transform(src.transform.c + src.transform.a / 2, 0.0)
    pixels_per_degree = 1.0 / np.degrees(abs(src.transform.a) / MOON_RADIUS_M)
    # Column holding the site longitude in the original grid -> move to centre.
    site_col = ((longitude_deg - first_lon) % 360.0) * pixels_per_degree
    shift = int(round(site_col - (src.width - 1) / 2))
    data = np.roll(data, -shift, axis=1)
    crs = CRS.from_proj4(f"+proj=eqc +lat_ts=0 +lat_0=0 +lon_0={longitude_deg} +x_0=0 +y_0=0 "
                         f"+R={MOON_RADIUS_M} +units=m +type=crs +no_defs")
    # Residual sub-pixel offset of the roll, applied to the grid origin.
    residual_m = (site_col - (src.width - 1) / 2 - shift) * abs(src.transform.a)
    transform = rasterio.Affine(src.transform.a, 0.0, src.transform.c - residual_m,
                                0.0, src.transform.e, src.transform.f + row0 * src.transform.e)
    return data, transform, crs


def build_site_tile(latitude_deg: float, longitude_deg: float, output: str | Path | None = None,
                    *, global_dem: str | Path = GLOBAL_DEM,
                    half_width_m: float = DEFAULT_HALF_WIDTH_M,
                    resolution_m: float | None = None) -> Path | MemoryFile:
    """Resample LDEM_64 heights (m) onto a stereographic grid centred on a site.

    Returns the written GeoTIFF path, or an open ``MemoryFile`` when ``output``
    is None (interactive use; the caller should close it).
    """
    if not (-90 <= latitude_deg <= 90) or not (-180 <= longitude_deg <= 180):
        raise ValueError("Latitude/longitude out of range")
    path = require(global_dem, "Global LOLA DEM (optional; "
                   "`python -m src.acquire.nasa_products lola_gdr_global_64ppd`)")
    with rasterio.open(path) as src:
        scale = float(src.scales[0]) if src.scales else 1.0
        offset = float(src.offsets[0]) if src.offsets else 0.0
        if not np.isclose(scale, EXPECTED_SCALE) or offset not in (0.0, EXPECTED_OFFSET_M):
            raise ValueError(f"Unexpected DEM scaling (scale={scale}, offset={offset}); "
                             "refusing to guess the height convention")
        res = float(resolution_m or abs(src.transform.a))
        size = int(np.ceil(2 * half_width_m / res))
        dst_crs = site_crs(latitude_deg, longitude_deg)
        dst_transform = from_origin(-size * res / 2, size * res / 2, res, res)
        band, band_transform, band_crs = _recentred_band(src, latitude_deg, longitude_deg,
                                                         half_width_m)
        dn = np.full((size, size), np.nan, dtype="float32")
        reproject(band, dn, src_transform=band_transform, src_crs=band_crs,
                  dst_transform=dst_transform, dst_crs=dst_crs, src_nodata=np.nan,
                  dst_nodata=np.nan, resampling=Resampling.bilinear)
        if not np.isfinite(dn).any():
            raise ValueError("Tile resampling produced no valid pixels; refusing an empty tile")
    heights = dn * scale  # DN x SCALING_FACTOR; OFFSET (sphere radius) intentionally omitted
    profile = {"driver": "GTiff", "height": size, "width": size, "count": 1,
               "dtype": "float32", "crs": dst_crs, "transform": dst_transform,
               "nodata": np.nan, "compress": "deflate", "predictor": 3}
    tags = {"source_product": PRODUCT_NAME, "source_file": path.name,
            "height_reference": f"sphere radius {MOON_RADIUS_M:.0f} m",
            "center_lat_deg": str(latitude_deg), "center_lon_deg": str(longitude_deg),
            "resampling": "bilinear"}
    if output is None:
        memory = MemoryFile()
        with memory.open(**profile) as ds:
            ds.write(heights, 1); ds.update_tags(**tags)
        return memory
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", **profile) as ds:
        ds.write(heights, 1); ds.update_tags(**tags)
    return out


TILE_INDEX = "index.json"


def _angular_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    cosine = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dlon)
    return float(MOON_RADIUS_M * np.arccos(np.clip(cosine, -1.0, 1.0)))


def find_committed_tile(latitude_deg: float, longitude_deg: float, *,
                        max_ray_m: float = 50_000.0, tile_dir: Path | None = None) -> Path | None:
    """Return a committed tile whose extent covers every horizon ray from the point."""
    directory = TILE_DIR if tile_dir is None else tile_dir
    index_path = directory / TILE_INDEX
    if not index_path.is_file():
        return None
    for tile in json.loads(index_path.read_text(encoding="utf-8"))["tiles"]:
        path = directory / tile["file"]
        offset = _angular_distance_m(latitude_deg, longitude_deg, tile["center_lat_deg"],
                                     tile["center_lon_deg"])
        # The inscribed circle of the square tile must contain point + ray length.
        if is_installed(path) and offset + max_ray_m <= tile["half_width_m"] * 0.98:
            return path
    return None


_TILE_CACHE: list[tuple[float, float, float, MemoryFile]] = []
_TILE_CACHE_LOCK = __import__("threading").Lock()
TILE_CACHE_SIZE = 6
ON_THE_FLY_MARGIN_M = 30_000.0


def cached_site_tile(latitude_deg: float, longitude_deg: float, *, max_ray_m: float,
                     global_dem: str | Path | None = None) -> str:
    """Return a /vsimem tile covering every ray from the point, building if needed.

    Tiles are sized to the ray length plus ``ON_THE_FLY_MARGIN_M`` so repeated
    clicks within ~30 km reuse one tile. A small LRU owns the in-memory files.
    """
    source = GLOBAL_DEM if global_dem is None else Path(global_dem)
    with _TILE_CACHE_LOCK:
        for index, (lat, lon, half, memory) in enumerate(_TILE_CACHE):
            offset = _angular_distance_m(latitude_deg, longitude_deg, lat, lon)
            if offset + max_ray_m <= half * 0.98:
                _TILE_CACHE.append(_TILE_CACHE.pop(index))  # mark most recently used
                return memory.name
        half_width = max_ray_m + ON_THE_FLY_MARGIN_M
        memory = build_site_tile(latitude_deg, longitude_deg, None, global_dem=source,
                                 half_width_m=half_width)
        _TILE_CACHE.append((latitude_deg, longitude_deg, half_width, memory))
        while len(_TILE_CACHE) > TILE_CACHE_SIZE:
            _TILE_CACHE.pop(0)[3].close()
        return memory.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LDEM_64 site tiles for catalog sites")
    parser.add_argument("--manifest", type=Path, default=DATA_DIR / "missions.json")
    parser.add_argument("--output", type=Path, default=TILE_DIR)
    parser.add_argument("--polar-limit-deg", type=float, default=-83.0,
                        help="skip sites south of this: their 50 km rays stay inside the 80 m polar DEM")
    args = parser.parse_args(argv)
    tiles = []
    for mission in json.loads(args.manifest.read_text(encoding="utf-8")):
        site = mission.get("landing_site") or {}
        lat, lon = site.get("latitude_deg"), site.get("longitude_deg")
        if lat is None or lon is None or lat <= args.polar_limit_deg:
            continue
        out = build_site_tile(lat, lon, args.output / f"{mission['id']}.tif")
        tiles.append({"site_id": mission["id"], "file": out.name, "center_lat_deg": lat,
                      "center_lon_deg": lon, "half_width_m": DEFAULT_HALF_WIDTH_M})
        print(f"{mission['id']}: {out.name} ({out.stat().st_size // 1024} KB)")
    (args.output / TILE_INDEX).write_text(json.dumps({
        "schema": "apolloharness.lola_tiles.v1", "source_product": PRODUCT_NAME,
        "source_sha256": "1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6",
        "projection": "site-centred stereographic, R=1737400 m",
        "height_reference": "metres above 1737.4 km sphere", "tiles": tiles,
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
