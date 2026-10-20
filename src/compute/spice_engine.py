from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import spiceypy as spice


SPICE_DIR = Path("data/spice")

KERNELS = [
    SPICE_DIR / "naif0012.tls",
    SPICE_DIR / "pck00010.tpc",
    SPICE_DIR / "moon_080317.tf",
    SPICE_DIR / "moon_pa_de421_1900-2050.bpc",
    SPICE_DIR / "de430.bsp",
]


@dataclass
class HourlyGeometry:
    utc: str
    earth_elevation_deg: float
    earth_azimuth_deg: float
    sun_elevation_deg: float
    sun_azimuth_deg: float
    earth_visible: bool


@dataclass
class CommunicationsSummary:
    uptime_percent: float
    longest_blackout_hours: float
    total_hours: int
    visible_hours: int
    blackout_intervals: list[tuple[str, str]]


def load_kernels() -> None:
    """Load the SPICE kernels required by the planetary computation engine."""
    spice.kclear()

    for kernel in KERNELS:
        if not kernel.exists():
            raise FileNotFoundError(
                f"Required SPICE kernel not found: {kernel}"
            )

        spice.furnsh(str(kernel))


def unload_kernels() -> None:
    """Unload all currently loaded SPICE kernels."""
    spice.kclear()


def _observer_position(
    latitude_deg: float,
    longitude_deg: float,
) -> np.ndarray:
    """
    Return lunar surface observer position in MOON_PA coordinates.

    Latitude:
        Positive north, negative south.

    Longitude:
        Positive east, negative west.
    """
    radii = spice.bodvrd("MOON", "RADII", 3)[1]
    radius_km = float(np.mean(radii))

    lat = np.radians(latitude_deg)
    lon = np.radians(longitude_deg)

    return np.array(
        [
            radius_km * np.cos(lat) * np.cos(lon),
            radius_km * np.cos(lat) * np.sin(lon),
            radius_km * np.sin(lat),
        ],
        dtype=float,
    )


def _local_basis(
    latitude_deg: float,
    longitude_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Construct local East-North-Up basis in MOON_PA coordinates.
    """
    lat = np.radians(latitude_deg)
    lon = np.radians(longitude_deg)

    east = np.array(
        [
            -np.sin(lon),
            np.cos(lon),
            0.0,
        ],
        dtype=float,
    )

    north = np.array(
        [
            -np.sin(lat) * np.cos(lon),
            -np.sin(lat) * np.sin(lon),
            np.cos(lat),
        ],
        dtype=float,
    )

    up = np.array(
        [
            np.cos(lat) * np.cos(lon),
            np.cos(lat) * np.sin(lon),
            np.sin(lat),
        ],
        dtype=float,
    )

    return east, north, up


def _elevation_azimuth(
    target_vector: np.ndarray,
    east: np.ndarray,
    north: np.ndarray,
    up: np.ndarray,
) -> tuple[float, float]:
    """
    Calculate local elevation and azimuth.

    Azimuth convention:
        0°   = North
        90°  = East
        180° = South
        270° = West
    """
    direction = target_vector / np.linalg.norm(target_vector)

    east_component = np.dot(direction, east)
    north_component = np.dot(direction, north)
    up_component = np.clip(np.dot(direction, up), -1.0, 1.0)

    elevation_deg = float(np.degrees(np.arcsin(up_component)))

    azimuth_deg = float(
        np.degrees(
            np.arctan2(
                east_component,
                north_component,
            )
        )
        % 360.0
    )

    return elevation_deg, azimuth_deg


def calculate_geometry(
    latitude_deg: float,
    longitude_deg: float,
    utc: str,
) -> HourlyGeometry:
    """
    Calculate Earth and Sun local geometry for a lunar surface location.
    """
    et = spice.str2et(utc)

    observer = _observer_position(
        latitude_deg,
        longitude_deg,
    )

    east, north, up = _local_basis(
        latitude_deg,
        longitude_deg,
    )

    earth_moon, _ = spice.spkpos(
        "EARTH",
        et,
        "MOON_PA",
        "NONE",
        "MOON",
    )

    sun_moon, _ = spice.spkpos(
        "SUN",
        et,
        "MOON_PA",
        "NONE",
        "MOON",
    )

    earth_vector = earth_moon - observer
    sun_vector = sun_moon - observer

    earth_elevation, earth_azimuth = _elevation_azimuth(
        earth_vector,
        east,
        north,
        up,
    )

    sun_elevation, sun_azimuth = _elevation_azimuth(
        sun_vector,
        east,
        north,
        up,
    )

    return HourlyGeometry(
        utc=utc,
        earth_elevation_deg=earth_elevation,
        earth_azimuth_deg=earth_azimuth,
        sun_elevation_deg=sun_elevation,
        sun_azimuth_deg=sun_azimuth,
        earth_visible=earth_elevation > 0.0,
    )


def calculate_hourly_geometry(
    latitude_deg: float,
    longitude_deg: float,
    start_utc: str,
    hours: int,
) -> list[HourlyGeometry]:
    """
    Calculate hourly Earth/Sun geometry over a mission window.
    """
    start = datetime.fromisoformat(
        start_utc.replace("Z", "+00:00")
    ).astimezone(timezone.utc)

    results: list[HourlyGeometry] = []

    for hour in range(hours):
        current = start + timedelta(hours=hour)

        utc = current.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        results.append(
            calculate_geometry(
                latitude_deg,
                longitude_deg,
                utc,
            )
        )

    return results


def summarize_communications(
    geometry: list[HourlyGeometry],
) -> CommunicationsSummary:
    """
    Summarize Earth line-of-sight availability.

    A communication opportunity exists when:
        Earth elevation > 0 degrees.
    """
    if not geometry:
        return CommunicationsSummary(
            uptime_percent=0.0,
            longest_blackout_hours=0.0,
            total_hours=0,
            visible_hours=0,
            blackout_intervals=[],
        )

    visible = [
        item.earth_visible
        for item in geometry
    ]

    total_hours = len(visible)
    visible_hours = sum(visible)

    uptime_percent = (
        visible_hours / total_hours
    ) * 100.0

    blackout_intervals: list[tuple[str, str]] = []

    blackout_start: str | None = None
    longest_blackout_hours = 0.0
    current_blackout_hours = 0.0

    for item in geometry:
        if not item.earth_visible:
            if blackout_start is None:
                blackout_start = item.utc

            current_blackout_hours += 1.0

        else:
            if blackout_start is not None:
                blackout_end = item.utc

                blackout_intervals.append(
                    (
                        blackout_start,
                        blackout_end,
                    )
                )

                longest_blackout_hours = max(
                    longest_blackout_hours,
                    current_blackout_hours,
                )

                blackout_start = None
                current_blackout_hours = 0.0

    if blackout_start is not None:
        blackout_end = geometry[-1].utc

        blackout_intervals.append(
            (
                blackout_start,
                blackout_end,
            )
        )

        longest_blackout_hours = max(
            longest_blackout_hours,
            current_blackout_hours,
        )

    return CommunicationsSummary(
        uptime_percent=uptime_percent,
        longest_blackout_hours=longest_blackout_hours,
        total_hours=total_hours,
        visible_hours=visible_hours,
        blackout_intervals=blackout_intervals,
    )


if __name__ == "__main__":
    load_kernels()

    try:
        latitude = -84.79
        longitude = 29.20

        geometry = calculate_hourly_geometry(
            latitude_deg=latitude,
            longitude_deg=longitude,
            start_utc="2026-10-20T00:00:00Z",
            hours=24,
        )

        summary = summarize_communications(
            geometry
        )

        print(
            f"Location: {latitude}°, {longitude}°"
        )

        print(
            f"Communication uptime: "
            f"{summary.uptime_percent:.2f}%"
        )

        print(
            f"Longest blackout: "
            f"{summary.longest_blackout_hours:.1f} hours"
        )

        print("\nFirst 5 hourly observations:")

        for item in geometry[:5]:
            print(
                item.utc,
                f"Earth elevation={item.earth_elevation_deg:.3f}°",
                f"Earth azimuth={item.earth_azimuth_deg:.3f}°",
                f"Sun elevation={item.sun_elevation_deg:.3f}°",
                f"Sun azimuth={item.sun_azimuth_deg:.3f}°",
                f"Earth visible={item.earth_visible}",
            )

    finally:
        unload_kernels()