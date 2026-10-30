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
from pyproj import CRS, Transformer
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window

from .terrain import DATA_DIR, MOON_GEOGRAPHIC, MOON_RADIUS_M, PROJECT_ROOT

GLOBAL_DEM = PROJECT_ROOT / "cache" / "nasa" / "pds" / "ldem_64.lbl"
TILE_DIR = DATA_DIR / "lola" / "tiles"
PRODUCT_NAME = "LOLA GDR LDEM_64"
EXPECTED_SCALE = 0.5
EXPECTED_OFFSET_M = MOON_RADIUS_M
DEFAULT_HALF_WIDTH_M = 80_000.0


def site_crs(latitude_deg: float, longitude_deg: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=stere +lat_0={latitude_deg} +lon_0={longitude_deg} +k=1 +x_0=0 +y_0=0 "
        f"+R={MOON_RADIUS_M} +units=m +type=crs +no_defs")


def _source_window(src: rasterio.DatasetReader, latitude_deg: float, longitude_deg: float,
                   half_width_m: float) -> Window | None:
    """Source pixel window covering the tile, or None when it crosses the map seam."""
    pad_deg = np.degrees(half_width_m / MOON_RADIUS_M) * 1.2
    lat_lo, lat_hi = max(latitude_deg - pad_deg, -90.0), min(latitude_deg + pad_deg, 90.0)
    widest = max(abs(lat_lo), abs(lat_hi))
    if widest >= 89.0:
        return None  # polar cap: let the warper read what it needs
    lon_pad = pad_deg / np.cos(np.radians(widest))
    to_map = Transformer.from_crs(MOON_GEOGRAPHIC, src.crs, always_xy=True)
    xs, ys = [], []
    for lon in (longitude_deg - lon_pad, longitude_deg + lon_pad):
        for lat in (lat_lo, lat_hi):
            x, y = to_map.transform(lon, lat)
            xs.append(x); ys.append(y)
    # Longitudes across the product's 0/360 seam map to opposite edges.
    if max(xs) - min(xs) > 0.5 * (src.bounds.right - src.bounds.left):
        return None
    inverse = ~src.transform
    cols = [inverse.a * x + inverse.b * y + inverse.c for x, y in zip(xs, ys)]
    rows = [inverse.d * x + inverse.e * y + inverse.f for x, y in zip(xs, ys)]
    col0, col1 = max(int(np.floor(min(cols))) - 2, 0), min(int(np.ceil(max(cols))) + 2, src.width)
    row0, row1 = max(int(np.floor(min(rows))) - 2, 0), min(int(np.ceil(max(rows))) + 2, src.height)
    return Window(col0, row0, col1 - col0, row1 - row0)


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
    path = Path(global_dem)
    if not path.is_file():
        raise FileNotFoundError(
            f"Global LOLA DEM not found: {path}. Run "
            "`python -m src.acquire.nasa_products lola_gdr_global_64ppd`.")
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
        window = _source_window(src, latitude_deg, longitude_deg, half_width_m)
        source = src.read(1, window=window, masked=True) if window is not None else None
        dn = np.full((size, size), np.nan, dtype="float32")
        if source is not None:
            data = np.ma.asarray(source, dtype="float32").filled(np.nan)
            reproject(data, dn, src_transform=src.window_transform(window), src_crs=src.crs,
                      dst_transform=dst_transform, dst_crs=dst_crs, src_nodata=np.nan,
                      dst_nodata=np.nan, resampling=Resampling.bilinear)
        else:
            reproject(rasterio.band(src, 1), dn, dst_transform=dst_transform, dst_crs=dst_crs,
                      src_nodata=src.nodata, dst_nodata=np.nan, resampling=Resampling.bilinear)
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
        if path.is_file() and offset + max_ray_m <= tile["half_width_m"] * 0.98:
            return path
    return None


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
