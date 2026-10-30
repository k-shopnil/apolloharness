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
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
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
    if not path.is_file():
        raise FileNotFoundError(f"LOLA DEM not found: {path}")
    with rasterio.open(path) as ds:
        _validate_dem_crs(ds)
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
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


def extract_horizon_mask_fast(
    dem_path: str | Path, latitude_deg: float, longitude_deg: float, *,
    max_distance_m: float = 50_000.0, radial_step_m: float = 80.0,
    azimuth_step_deg: float = 1.0, observer_height_m: float = 1.5,
) -> HorizonMask:
    """Vectorized horizon mask for interactive (click-to-pin) evaluation.

    Same physics and completeness rule as ``extract_horizon_mask`` but reads
    one DEM window and samples it with bilinear interpolation in memory,
    which is orders of magnitude faster than per-point ``ds.sample`` calls.
    Rays leaving the DEM footprint before ``max_distance_m`` are NaN.
    """
    _validate_sampling(latitude_deg, longitude_deg, max_distance_m,
                       radial_step_m, azimuth_step_deg)
    with rasterio.open(dem_path) as ds:
        _validate_dem_crs(ds)
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
        x0, y0, east_xy, north_xy = _projected_local_axes(tx, latitude_deg, longitude_deg)
        pixel = float(min(abs(ds.transform.a), abs(ds.transform.e)))
        row_c, col_c = _fractional_index(ds, np.array([x0]), np.array([y0]))
        radius_px = int(np.ceil(max_distance_m / pixel)) + 2
        row_off = max(int(np.floor(row_c[0])) - radius_px, 0)
        col_off = max(int(np.floor(col_c[0])) - radius_px, 0)
        row_end = min(int(np.floor(row_c[0])) + radius_px + 2, ds.height)
        col_end = min(int(np.floor(col_c[0])) + radius_px + 2, ds.width)
        if row_end <= row_off or col_end <= col_off:
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        values = _read_valid(ds, Window(col_off, row_off, col_end - col_off, row_end - row_off))
        base_row, base_col = row_c - row_off, col_c - col_off
        base_value = float(_bilinear(values, base_row, base_col)[0])
        if not np.isfinite(base_value):
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        distances = np.arange(radial_step_m, max_distance_m + radial_step_m, radial_step_m)
        azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
        theta = np.radians(azimuths)[:, None]
        dx = east_xy[0] * np.sin(theta) + north_xy[0] * np.cos(theta)
        dy = east_xy[1] * np.sin(theta) + north_xy[1] * np.cos(theta)
        xs = x0 + dx * distances[None, :]
        ys = y0 + dy * distances[None, :]
        rows, cols = _fractional_index(ds, xs, ys, row_off, col_off)
        heights = _bilinear(values, rows, cols)
    complete = np.isfinite(heights).all(axis=1)
    angles = np.full(azimuths.shape, np.nan)
    if complete.any():
        apparent = _apparent_elevation_deg(distances[None, :], heights[complete],
                                           base_value + observer_height_m)
        angles[complete] = apparent.max(axis=1)
    if not np.isfinite(angles).any():
        raise ValueError("No complete terrain rays found around observer")
    return HorizonMask(azimuths, angles)


def evaluate_site_terrain(latitude_deg: float, longitude_deg: float,
                          dem_path: str | Path = DEFAULT_DEM, **mask_options: float
                          ) -> dict[str, object]:
    """Terrain context for any coordinate: elevation plus horizon mask if covered.

    Outside the LOLA polar DEM the mask is ``None`` and ``horizon_model`` is
    ``spherical_horizon`` so downstream countdowns state their weaker basis.
    """
    elevation = interpolate_elevation(latitude_deg, longitude_deg, dem_path)
    mask: HorizonMask | None = None
    status = elevation["status"]
    if status == "complete":
        try:
            mask = extract_horizon_mask_fast(dem_path, latitude_deg, longitude_deg, **mask_options)
        except ValueError:
            status = "horizon_unavailable"
    incomplete = 0 if mask is None else int(np.count_nonzero(~np.isfinite(mask.elevation_deg)))
    return {
        **elevation,
        "status": status,
        "horizon_model": "lola_terrain_mask" if mask is not None else "spherical_horizon",
        "horizon_mask": mask,
        "horizon_incomplete_azimuths": incomplete,
    }
