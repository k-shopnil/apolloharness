"""LOLA DEM access and observer-centered terrain horizon sampling.

Raster coordinates must describe a lunar south-polar stereographic grid in
meters (MOON_SPS). Dataset-specific frame metadata should be checked before use.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import CRS, Transformer

from .datafiles import is_installed, require

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DEM = DATA_DIR / "lola" / "LDEM_80S_80MPP_ADJ.TIF"
MOON_RADIUS_M = 1_737_400.0
MOON_ME_GEOGRAPHIC = CRS.from_proj4(
    f"+proj=longlat +a={MOON_RADIUS_M} +b={MOON_RADIUS_M} "
    "+type=crs +no_defs"
)
MOON_ME_SPS = CRS.from_proj4(
    f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 "
    f"+a={MOON_RADIUS_M} +b={MOON_RADIUS_M} +units=m +type=crs +no_defs"
)
_TRANSFORMERS = __import__("threading").local()


def _crs_key(crs: object) -> str:
    """Cheap identity for a CRS (pyproj ``srs``/rasterio WKT) without re-parsing it."""
    if isinstance(crs, str):
        return crs
    srs = getattr(crs, "srs", None)  # pyproj CRS
    if isinstance(srs, str):
        return srs
    to_wkt = getattr(crs, "to_wkt", None)  # rasterio CRS; to_string() is slow
    return to_wkt() if callable(to_wkt) else repr(crs)


def cached_transformer(source: object, target: object) -> Transformer:
    """Per-thread cached ``always_xy`` transformer (construction costs ~15 ms).

    pyproj ``Transformer`` objects are not thread-safe, so each thread keeps
    its own cache instead of sharing one.
    """
    cache = getattr(_TRANSFORMERS, "cache", None)
    if cache is None:
        cache = _TRANSFORMERS.cache = {}
    key = (_crs_key(source), _crs_key(target))
    transformer = cache.get(key)
    if transformer is None:
        transformer = cache[key] = Transformer.from_crs(source, target, always_xy=True)
    return transformer


# Backwards-compatible names; coordinates in NASA PGDA products use MOON_ME.
MOON_GEOGRAPHIC = MOON_ME_GEOGRAPHIC
MOON_SPS = MOON_ME_SPS


@dataclass(frozen=True)
class HorizonMask:
    """Terrain horizon elevation angles indexed by north-clockwise azimuth."""
    azimuth_deg: np.ndarray
    elevation_deg: np.ndarray

    def to_dict(self) -> dict[str, list[float | None]]:
        return {"azimuth_deg": [float(a) for a in self.azimuth_deg],
                "elevation_deg": [float(e) if np.isfinite(e) else None for e in self.elevation_deg]}

    def elevation_at(self, azimuth_deg: float) -> float:
        if len(self.azimuth_deg) != len(self.elevation_deg) or not len(self.azimuth_deg):
            raise ValueError("Horizon mask must contain matching, non-empty arrays")
        azimuth = azimuth_deg % 360.0
        step = float(self.azimuth_deg[1] - self.azimuth_deg[0]) if len(self.azimuth_deg) > 1 else 360.0
        position = azimuth / step
        lower = int(np.floor(position)) % len(self.azimuth_deg)
        fraction = position - np.floor(position)
        upper = (lower + 1) % len(self.azimuth_deg)
        if np.isclose(fraction, 0.0):
            return float(self.elevation_deg[lower])
        low, high = self.elevation_deg[lower], self.elevation_deg[upper]
        if not np.isfinite(low) or not np.isfinite(high):
            return float("nan")
        return float(low + fraction * (high - low))


def extract_horizon_mask(
    dem_path: str | Path, latitude_deg: float, longitude_deg: float, *,
    max_distance_m: float = 20_000.0, radial_step_m: float = 100.0,
    azimuth_step_deg: float = 1.0, observer_height_m: float = 1.5,
) -> HorizonMask:
    """Sample 360 radial terrain profiles from a projected lunar DEM.

    Elevation is the maximum apparent terrain angle along each radial profile.
    Uses the input GeoTIFF's declared CRS and rejects geographic/non-metric rasters.
    """
    _validate_sampling(latitude_deg, longitude_deg, max_distance_m,
                       radial_step_m, azimuth_step_deg)
    with rasterio.open(dem_path) as ds:
        _validate_dem_crs(ds)
        tx = cached_transformer(MOON_GEOGRAPHIC, ds.crs)
        x0, y0, east_xy, north_xy = _projected_local_axes(tx, latitude_deg, longitude_deg)
        distances = np.arange(radial_step_m, max_distance_m + radial_step_m, radial_step_m)
        azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
        angles = np.full(azimuths.shape, np.nan)
        base = ds.sample([(x0, y0)], masked=True)
        base_value = np.ma.asarray(next(base), dtype=float).filled(np.nan)[0]
        if not np.isfinite(base_value):
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        for i, az in enumerate(azimuths):
            theta = np.radians(az)
            projected_direction = east_xy * np.sin(theta) + north_xy * np.cos(theta)
            coords = [(x0 + d * projected_direction[0],
                       y0 + d * projected_direction[1]) for d in distances]
            heights = np.ma.vstack(list(ds.sample(coords, masked=True)), dtype=float).filled(np.nan)[:, 0]
            valid = np.isfinite(heights)
            # A horizon is valid only when the requested radial extent is
            # fully covered; partial coverage cannot prove there is no farther obstruction.
            if valid.all():
                # Account for lunar curvature: DEM heights are relative to a
                # reference sphere, not a locally flat tangent plane.
                angles[i] = float(np.max(_apparent_elevation_deg(
                    distances, heights, base_value + observer_height_m)))
        if not np.isfinite(angles).any():
            raise ValueError("No complete terrain rays found around observer")
        return HorizonMask(azimuths, angles)


def _validate_sampling(latitude_deg: float, longitude_deg: float, max_distance_m: float,
                       radial_step_m: float, azimuth_step_deg: float) -> None:
    if not (-90 <= latitude_deg <= 90) or not (-180 <= longitude_deg <= 180):
        raise ValueError("Latitude/longitude out of range")
    if min(max_distance_m, radial_step_m, azimuth_step_deg) <= 0:
        raise ValueError("Sampling distances and azimuth step must be positive")
    if not np.isclose(360.0 / azimuth_step_deg, round(360.0 / azimuth_step_deg)):
        raise ValueError("azimuth_step_deg must divide 360 evenly")


def _validate_dem_crs(ds: rasterio.DatasetReader) -> None:
    if ds.crs is None or not ds.crs.is_projected:
        raise ValueError("LOLA DEM must declare a projected lunar CRS")
    pyproj_crs = CRS.from_user_input(ds.crs)
    if pyproj_crs.axis_info and any(
        (axis.unit_name or "").lower() not in {"metre", "meter"}
        for axis in pyproj_crs.axis_info[:2]
    ):
        raise ValueError("LOLA DEM projected axes must use meters")


def _projected_local_axes(tx: Transformer, latitude_deg: float, longitude_deg: float
                          ) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Return observer map position and unit east/north directions in map meters."""
    x0, y0 = tx.transform(longitude_deg, latitude_deg)
    # North is undefined exactly at a pole; there, azimuth is referenced to the
    # requested longitude's meridian by deriving axes a few cm off the pole.
    axis_lat = float(np.clip(latitude_deg, -89.99999, 89.99999))
    delta_deg = 1.0e-6
    xa, ya = tx.transform(longitude_deg, axis_lat)
    x_north, y_north = tx.transform(longitude_deg, axis_lat + delta_deg)
    north_xy = np.array([x_north - xa, y_north - ya], dtype=float)
    north_xy /= np.linalg.norm(north_xy)
    # Polar stereographic is conformal, so east is exactly perpendicular to
    # north; a finite longitude step would be a skewed chord near the pole.
    east_xy = np.array([north_xy[1], -north_xy[0]])
    x_east, y_east = tx.transform(longitude_deg + delta_deg, axis_lat)
    if np.dot(east_xy, [x_east - xa, y_east - ya]) < 0:
        east_xy = -east_xy
    return float(x0), float(y0), east_xy, north_xy


def _apparent_elevation_deg(distances_m: np.ndarray, heights_m: np.ndarray,
                            observer_height_m: float) -> np.ndarray:
    """Apparent terrain elevation angles from the observer, including curvature.

    DEM heights are relative to a reference sphere, not a locally flat plane.
    """
    angular_distance = distances_m / MOON_RADIUS_M
    terrain_radius = MOON_RADIUS_M + heights_m
    observer_radius = MOON_RADIUS_M + observer_height_m
    vertical = terrain_radius * np.cos(angular_distance) - observer_radius
    horizontal = terrain_radius * np.sin(angular_distance)
    return np.degrees(np.arctan2(vertical, horizontal))


def _bilinear(values: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Bilinear interpolation at fractional pixel-center indices; NaN outside/nodata.

    A sample is NaN if any of its four neighbours is NaN, so nodata never
    leaks into interpolated heights as a fabricated value.
    """
    rows = np.asarray(rows, dtype=float)
    cols = np.asarray(cols, dtype=float)
    out = np.full(rows.shape, np.nan)
    r0 = np.floor(rows).astype(int)
    c0 = np.floor(cols).astype(int)
    inside = (r0 >= 0) & (c0 >= 0) & (r0 + 1 < values.shape[0]) & (c0 + 1 < values.shape[1])
    # Allow samples landing exactly on the last row/column.
    edge = (~inside & (r0 >= 0) & (c0 >= 0) & (r0 < values.shape[0]) & (c0 < values.shape[1])
            & np.isclose(rows, np.minimum(r0, values.shape[0] - 1))
            & np.isclose(cols, np.minimum(c0, values.shape[1] - 1)))
    out[edge] = values[r0[edge], c0[edge]]
    if inside.any():
        r, c = r0[inside], c0[inside]
        fr, fc = rows[inside] - r, cols[inside] - c
        out[inside] = (values[r, c] * (1 - fr) * (1 - fc) + values[r, c + 1] * (1 - fr) * fc
                       + values[r + 1, c] * fr * (1 - fc) + values[r + 1, c + 1] * fr * fc)
    return out


def _read_valid(ds: rasterio.DatasetReader, window: Window) -> np.ndarray:
    data = ds.read(1, window=window, masked=True, boundless=False)
    return np.ma.asarray(data, dtype=float).filled(np.nan)


def _fractional_index(ds: rasterio.DatasetReader, x: np.ndarray, y: np.ndarray,
                      row_off: int = 0, col_off: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Map coordinates to fractional pixel-centre (row, col) relative to a window."""
    inv = ~ds.transform
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    cols = inv.a * x + inv.b * y + inv.c
    rows = inv.d * x + inv.e * y + inv.f
    return rows - 0.5 - row_off, cols - 0.5 - col_off


def interpolate_elevation(latitude_deg: float, longitude_deg: float,
                          dem_path: str | Path = DEFAULT_DEM) -> dict[str, object]:
    """Bilinearly interpolate LOLA terrain height at an arbitrary coordinate.

    Heights are meters relative to the DEM's reference sphere (1737.4 km for
    LDEM_80S_80MPP_ADJ). Coordinates outside the DEM footprint or on nodata
    return ``elevation_m=None`` with an explicit status instead of a guess.
    """
    _validate_sampling(latitude_deg, longitude_deg, 1.0, 1.0, 1.0)
    path = Path(dem_path)
    # GDAL virtual paths (e.g. /vsimem/ in-memory tiles) are not on disk.
    require(dem_path, "LOLA DEM")
    with rasterio.open(dem_path) as ds:
        _validate_dem_crs(ds)
        tx = cached_transformer(MOON_GEOGRAPHIC, ds.crs)
        x, y = tx.transform(longitude_deg, latitude_deg)
        row, col = _fractional_index(ds, np.array([x]), np.array([y]))
        r0, c0 = int(np.floor(row[0])), int(np.floor(col[0]))
        if not (0 <= r0 < ds.height and 0 <= c0 < ds.width):
            value = float("nan")
        else:
            window = Window(c0, r0, min(2, ds.width - c0), min(2, ds.height - r0))
            values = _read_valid(ds, window)
            value = float(_bilinear(values, row - r0, col - c0)[0])
        resolution_m = float(abs(ds.transform.a))
    valid = np.isfinite(value)
    return {
        "latitude_deg": latitude_deg, "longitude_deg": longitude_deg,
        "elevation_m": value if valid else None,
        "status": "complete" if valid else "outside_dem_coverage",
        "interpolation": "bilinear",
        "dem_resolution_m": resolution_m,
        "reference_radius_m": MOON_RADIUS_M,
        "source_dataset": path.name,
        "map_xy_m": [float(x), float(y)],
    }


# Horizon defaults selected on a development split against NASA PGDA product 69
# and confirmed once on a disjoint test split (docs/ML_VALIDATION_REPORT.md,
# data/validation/annual_illumination_validation.json): the former 50 km rays
# missed distant massifs and over-predicted polar sunlight by ~1.6 pp; 100 km
# multi-resolution rays are unbiased (test bias -0.05 pp, R^2 0.95).
HORIZON_MAX_DISTANCE_M = 100_000.0
# Multi-resolution tracing: full DEM resolution out to NEAR_FIELD_M, then a
# block-averaged copy (FAR_FIELD_FACTOR x coarser). Distant terrain subtends
# tiny angles, so this keeps accuracy while cutting latency ~3x.
NEAR_FIELD_M = 20_000.0
FAR_FIELD_FACTOR = 4
# Only DEMs finer than this use the coarse far field (LDEM_64 tiles do not).
MULTIRES_MAX_PIXEL_M = 200.0
DERIVED_DIR = PROJECT_ROOT / "cache" / "derived"


@dataclass(frozen=True)
class _Grid:
    """An in-memory raster with its inverse affine, for bilinear sampling."""
    values: np.ndarray
    inverse: tuple[float, float, float, float, float, float]
    pixel_m: float

    @classmethod
    def from_window(cls, ds: rasterio.DatasetReader, window: Window) -> "_Grid":
        values = _read_valid(ds, window)
        transform = ds.window_transform(window)
        inv = ~transform
        return cls(values, (inv.a, inv.b, inv.c, inv.d, inv.e, inv.f),
                   float(min(abs(transform.a), abs(transform.e))))

    def sample(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        a, b, c, d, e, f = self.inverse
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        return _bilinear(self.values, d * x + e * y + f - 0.5, a * x + b * y + c - 0.5)


_COARSE_CACHE: dict[tuple[str, float, int], _Grid] = {}
_COARSE_LOCK = __import__("threading").Lock()


def coarse_grid(dem_path: str | Path, factor: int = FAR_FIELD_FACTOR) -> _Grid:
    """Whole-DEM block average (``factor`` x coarser), cached in memory and on disk.

    GDAL's average resampling ignores nodata, so blocks on the DEM edge use
    their valid pixels. The disk copy lives in git-ignored ``cache/derived``.
    """
    path = Path(dem_path)
    key = (str(path.resolve()), path.stat().st_mtime, factor)
    with _COARSE_LOCK:
        if key in _COARSE_CACHE:
            return _COARSE_CACHE[key]
        cached = DERIVED_DIR / f"{path.stem}_x{factor}.tif"
        if not cached.is_file() or cached.stat().st_mtime < path.stat().st_mtime:
            from rasterio.enums import Resampling
            with rasterio.open(path) as ds:
                shape = (ds.height // factor, ds.width // factor)
                data = ds.read(1, out_shape=shape, resampling=Resampling.average,
                               masked=True).astype("float32").filled(np.nan)
                transform = ds.transform * ds.transform.scale(ds.width / shape[1],
                                                              ds.height / shape[0])
                profile = {"driver": "GTiff", "height": shape[0], "width": shape[1],
                           "count": 1, "dtype": "float32", "crs": ds.crs,
                           "transform": transform, "nodata": np.nan,
                           "compress": "deflate", "predictor": 3}
            DERIVED_DIR.mkdir(parents=True, exist_ok=True)
            temporary = cached.with_suffix(".tmp.tif")
            with rasterio.open(temporary, "w", **profile) as out:
                out.write(data, 1)
            temporary.replace(cached)
        with rasterio.open(cached) as ds:
            grid = _Grid.from_window(ds, Window(0, 0, ds.width, ds.height))
        _COARSE_CACHE[key] = grid
        return grid


def _ray_distances(max_distance_m: float, radial_step_m: float, near_m: float,
                   far_step_m: float) -> tuple[np.ndarray, np.ndarray]:
    near = np.arange(radial_step_m, min(near_m, max_distance_m) + radial_step_m / 2, radial_step_m)
    far = (np.arange(near[-1] + far_step_m, max_distance_m + far_step_m / 2, far_step_m)
           if max_distance_m > near_m else np.empty(0))
    return near, far


def trace_horizon(fine: _Grid, coarse: _Grid | None, x0: float, y0: float,
                  east_xy: np.ndarray, north_xy: np.ndarray, base_height_m: float, *,
                  max_distance_m: float, radial_step_m: float, azimuth_step_deg: float,
                  near_field_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Shared ray tracer: returns (azimuths, horizon elevations; NaN = incomplete)."""
    if coarse is None:
        near_field_m = max_distance_m
    far_step = coarse.pixel_m if coarse is not None else radial_step_m
    near_d, far_d = _ray_distances(max_distance_m, radial_step_m, near_field_m, far_step)
    azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
    theta = np.radians(azimuths)[:, None]
    dx = east_xy[0] * np.sin(theta) + north_xy[0] * np.cos(theta)
    dy = east_xy[1] * np.sin(theta) + north_xy[1] * np.cos(theta)
    heights = fine.sample(x0 + dx * near_d, y0 + dy * near_d)
    distances = near_d
    if far_d.size:
        assert coarse is not None
        heights = np.concatenate([heights, coarse.sample(x0 + dx * far_d, y0 + dy * far_d)], axis=1)
        distances = np.concatenate([near_d, far_d])
    complete = np.isfinite(heights).all(axis=1)
    angles = np.full(azimuths.shape, np.nan)
    if complete.any():
        apparent = _apparent_elevation_deg(distances[None, :], heights[complete], base_height_m)
        angles[complete] = apparent.max(axis=1)
    return azimuths, angles


def extract_horizon_mask_fast(
    dem_path: str | Path, latitude_deg: float, longitude_deg: float, *,
    max_distance_m: float = HORIZON_MAX_DISTANCE_M, radial_step_m: float = 80.0,
    azimuth_step_deg: float = 1.0, observer_height_m: float = 1.5,
    near_field_m: float = NEAR_FIELD_M,
) -> HorizonMask:
    """Vectorized horizon mask for interactive (click-to-pin) evaluation.

    Same physics and completeness rule as ``extract_horizon_mask``, with
    bilinear sampling in memory. For fine DEMs, terrain beyond
    ``near_field_m`` is sampled from a cached block-averaged copy
    (``coarse_grid``); pass ``near_field_m=max_distance_m`` for a
    single-resolution trace. Rays leaving the DEM footprint are NaN.
    """
    _validate_sampling(latitude_deg, longitude_deg, max_distance_m,
                       radial_step_m, azimuth_step_deg)
    with rasterio.open(dem_path) as ds:
        _validate_dem_crs(ds)
        tx = cached_transformer(MOON_GEOGRAPHIC, ds.crs)
        x0, y0, east_xy, north_xy = _projected_local_axes(tx, latitude_deg, longitude_deg)
        pixel = float(min(abs(ds.transform.a), abs(ds.transform.e)))
        multires = pixel < MULTIRES_MAX_PIXEL_M and max_distance_m > near_field_m
        fine_reach = near_field_m if multires else max_distance_m
        row_c, col_c = _fractional_index(ds, np.array([x0]), np.array([y0]))
        radius_px = int(np.ceil(fine_reach / pixel)) + 2
        row_off = max(int(np.floor(row_c[0])) - radius_px, 0)
        col_off = max(int(np.floor(col_c[0])) - radius_px, 0)
        row_end = min(int(np.floor(row_c[0])) + radius_px + 2, ds.height)
        col_end = min(int(np.floor(col_c[0])) + radius_px + 2, ds.width)
        if row_end <= row_off or col_end <= col_off:
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        fine = _Grid.from_window(ds, Window(col_off, row_off, col_end - col_off, row_end - row_off))
    base_value = float(fine.sample(np.array([x0]), np.array([y0]))[0])
    if not np.isfinite(base_value):
        raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
    coarse = coarse_grid(dem_path) if multires and not str(dem_path).startswith("/vsi") else None
    azimuths, angles = trace_horizon(
        fine, coarse, x0, y0, east_xy, north_xy, base_value + observer_height_m,
        max_distance_m=max_distance_m, radial_step_m=radial_step_m,
        azimuth_step_deg=azimuth_step_deg, near_field_m=near_field_m if coarse else max_distance_m)
    if not np.isfinite(angles).any():
        raise ValueError("No complete terrain rays found around observer")
    return HorizonMask(azimuths, angles)


POLAR_DEM_PRODUCT = "LOLA LDEM_80S_80MPP_ADJ (PGDA product 90)"


def evaluate_site_terrain(latitude_deg: float, longitude_deg: float,
                          dem_path: str | Path = DEFAULT_DEM, *, global_terrain: bool = True,
                          **mask_options: float) -> dict[str, object]:
    """Terrain context for any coordinate: elevation plus horizon mask if covered.

    Source order: the 80 m polar DEM (``dem_path``), then, outside it and when
    ``global_terrain`` is set, a committed LDEM_64 site tile covering the point,
    then a tile built on the fly from the global product if installed. With no
    terrain source the mask is ``None`` and ``horizon_model`` is
    ``spherical_horizon`` so downstream countdowns state their weaker basis.
    """
    from . import global_terrain as gt
    if is_installed(dem_path):
        elevation = interpolate_elevation(latitude_deg, longitude_deg, dem_path)
        product: str | None = POLAR_DEM_PRODUCT if elevation["status"] == "complete" else None
    else:
        elevation = {"elevation_m": None, "status": "product_not_installed"}
        product = None
    mask: HorizonMask | None = None
    status = elevation["status"]
    filled = 0
    if product is not None:
        try:
            mask = extract_horizon_mask_fast(dem_path, latitude_deg, longitude_deg, **mask_options)
        except ValueError:
            status = "horizon_unavailable"
    needs_global = mask is None or not np.isfinite(mask.elevation_deg).all()
    if needs_global and global_terrain:
        max_ray = float(mask_options.get("max_distance_m", HORIZON_MAX_DISTANCE_M))
        tile: str | Path | None = gt.find_committed_tile(latitude_deg, longitude_deg,
                                                         max_ray_m=max_ray)
        on_the_fly = False
        if tile is None and is_installed(gt.GLOBAL_DEM):
            tile = gt.cached_site_tile(latitude_deg, longitude_deg, max_ray_m=max_ray,
                                       global_dem=gt.GLOBAL_DEM)
            on_the_fly = True
        if tile is not None:
            coarse_elevation = interpolate_elevation(latitude_deg, longitude_deg, tile)
            coarse = None
            if coarse_elevation["status"] == "complete":
                try:
                    coarse = extract_horizon_mask_fast(tile, latitude_deg, longitude_deg,
                                                       **mask_options)
                except ValueError:
                    coarse = None
            if coarse is not None and mask is None:
                elevation, mask, product, status = coarse_elevation, coarse, gt.PRODUCT_NAME, "complete"
                if on_the_fly:
                    elevation["source_dataset"] = "ldem_64.img (on-the-fly site tile)"
            elif coarse is not None and np.array_equal(coarse.azimuth_deg, mask.azimuth_deg):
                # Polar-DEM edge: rays that leave the 80 m grid take the
                # complete LDEM_64 ray for the same azimuth.
                gaps = ~np.isfinite(mask.elevation_deg)
                filled = int(np.count_nonzero(gaps & np.isfinite(coarse.elevation_deg)))
                mask = HorizonMask(mask.azimuth_deg,
                                   np.where(gaps, coarse.elevation_deg, mask.elevation_deg))
                product = f"{POLAR_DEM_PRODUCT} + {gt.PRODUCT_NAME} (edge fill)"
    incomplete = 0 if mask is None else int(np.count_nonzero(~np.isfinite(mask.elevation_deg)))
    return {
        **elevation,
        "status": status,
        "dem_product": product,
        "horizon_model": "lola_terrain_mask" if mask is not None else "spherical_horizon",
        "horizon_mask": mask,
        "horizon_incomplete_azimuths": incomplete,
        "horizon_azimuths_filled_from_global": filled,
    }
