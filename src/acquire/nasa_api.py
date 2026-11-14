"""Minimal, key-safe client for the NASA API portal (https://api.nasa.gov).

The key is read, in order, from the ``NASA_API_KEY`` environment variable or
the ``NASA_API_KEY=`` line of the git-ignored ``.env`` at the repository root
(see ``.env.example``). Without either, NASA's public ``DEMO_KEY`` is used
(30 requests/hour, 50/day per IP; a personal key allows 1,000/hour).

The key is never printed, logged, written to disk or included in an
exception message: request URLs are only ever recorded in redacted form.
This client is for data-pipeline scripts and the backend. Never ship the key
to the frontend.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .tls import context as _tls_context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
BASE_URL = "https://api.nasa.gov"
DEMO_KEY = "DEMO_KEY"
USER_AGENT = "ApolloHarness/1.0 (NASA Space Apps 2026)"


class NasaApiError(RuntimeError):
    """An api.nasa.gov request failed; the message never contains the key."""

    def __init__(self, message: str, status: int | str | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ApiResponse:
    data: Any
    status: int
    rate_limit_remaining: int | None
    request: str  # redacted: path and parameters, never the key


def api_key(env_file: Path = ENV_FILE) -> tuple[str, str]:
    """Return (key, origin). Origin is "environment", ".env" or "DEMO_KEY"."""
    value = os.environ.get("NASA_API_KEY", "").strip()
    if value:
        return value, "environment"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, sep, rest = line.strip().partition("=")
            if sep and name.strip() == "NASA_API_KEY":
                value = rest.strip().strip('"').strip("'")
                if value:
                    return value, ".env"
    return DEMO_KEY, "DEMO_KEY"


def redact(text: str, key: str) -> str:
    return text.replace(key, "***") if key and key != DEMO_KEY else text


def get_json(path: str, *, timeout: float = 90.0, env_file: Path = ENV_FILE,
             **params: str) -> ApiResponse:
    """GET ``https://api.nasa.gov/<path>?<params>&api_key=...`` and parse JSON.

    Raises ``NasaApiError`` (with a redacted message and the HTTP status) on
    failure. An empty body is returned as ``[]``, as DONKI does for "no events".
    """
    key, _ = api_key(env_file)
    shown = f"{BASE_URL}/{path.lstrip('/')}?{urllib.parse.urlencode(params)}"
    url = f"{shown}&{urllib.parse.urlencode({'api_key': key})}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_tls_context()) as response:
            body = response.read()
            remaining = response.headers.get("X-RateLimit-Remaining")
            return ApiResponse(json.loads(body) if body.strip() else [], response.status,
                               int(remaining) if remaining and remaining.isdigit() else None,
                               shown)
    except urllib.error.HTTPError as error:
        raise NasaApiError(f"HTTP {error.code} from {shown}", error.code) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = redact(str(getattr(error, "reason", error)), key)
        raise NasaApiError(f"network error ({reason}) for {shown}", "network") from None
