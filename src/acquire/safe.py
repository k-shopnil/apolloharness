from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "cache"
FIXTURE_DIR = PROJECT_ROOT / "demo_fixtures"


class SafeFetchError(RuntimeError):
    """Raised when online, cache, and fixture retrieval all fail."""


def _cache_path(cache_name: str) -> Path:
    """Return the local cache path for a named resource."""
    return CACHE_DIR / cache_name


def _fixture_path(fixture_name: str) -> Path:
    """Return the committed demo fixture path."""
    return FIXTURE_DIR / fixture_name


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")

    temporary_path.replace(path)


def fetch_json(
    url: str,
    *,
    cache_name: str,
    fixture_name: str,
    timeout: float = 10.0,
) -> Any:
    """
    Safely retrieve JSON using a three-tier strategy.

    Tier 1:
        Fetch from the online URL and save the result to cache/.

    Tier 2:
        If the online request fails, read the existing cache.

    Tier 3:
        If no cache exists, read the committed demo fixture.

    The function never propagates normal network failures from Tier 1.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = _cache_path(cache_name)
    fixture_path = _fixture_path(fixture_name)

    # Tier 1: Online
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ApolloHarness/1.0 NASA-Space-Apps-2026"
            },
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_data = response.read()

        data = json.loads(raw_data.decode("utf-8"))
        _write_json(cache_path, data)

        return data

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        pass

    # Tier 2: Cache
    if cache_path.exists():
        try:
            return _read_json(cache_path)
        except (OSError, json.JSONDecodeError):
            pass

    # Tier 3: Fixture
    if fixture_path.exists():
        try:
            return _read_json(fixture_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise SafeFetchError(
                f"Demo fixture could not be read: {fixture_path}"
            ) from exc

    raise SafeFetchError(
        "Unable to retrieve resource. "
        f"Online request failed, cache is unavailable at {cache_path}, "
        f"and fixture is unavailable at {fixture_path}."
    )


def fetch_file(
    url: str,
    *,
    cache_name: str,
    fixture_name: str,
    timeout: float = 10.0,
) -> Path:
    """
    Safely retrieve a binary/file resource using three tiers.

    Returns the local path containing the retrieved file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = _cache_path(cache_name)
    fixture_path = _fixture_path(fixture_name)

    # Tier 1: Online
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ApolloHarness/1.0 NASA-Space-Apps-2026"
            },
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")

        with temporary_path.open("wb") as file:
            file.write(data)

        temporary_path.replace(cache_path)

        return cache_path

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
    ):
        pass

    # Tier 2: Cache
    if cache_path.exists():
        return cache_path

    # Tier 3: Fixture
    if fixture_path.exists():
        return fixture_path

    raise SafeFetchError(
        "Unable to retrieve file. "
        f"Online request failed, cache is unavailable at {cache_path}, "
        f"and fixture is unavailable at {fixture_path}."
    )


def copy_fixture_to_cache(
    *,
    fixture_name: str,
    cache_name: str,
) -> Path:
    """
    Copy a committed fixture into the runtime cache.

    Useful for preparing an offline demo environment.
    """
    fixture_path = _fixture_path(fixture_name)
    cache_path = _cache_path(cache_name)

    if not fixture_path.exists():
        raise SafeFetchError(
            f"Fixture does not exist: {fixture_path}"
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_path, cache_path)

    return cache_path


if __name__ == "__main__":
    print("Safe fetcher module loaded successfully.")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Cache directory: {CACHE_DIR}")
    print(f"Fixture directory: {FIXTURE_DIR}")
