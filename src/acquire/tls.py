"""One TLS context for every download, built on certifi's CA bundle.

The operating system's trust store is not always current. Some Windows
machines and slim Linux images lack newer roots such as "SSL.com TLS RSA Root
CA 2022", which NASA's PDS Geosciences node chains to, and downloads then fail
with "unable to get local issuer certificate". certifi is a pinned dependency
(requirements.txt) and ships the current Mozilla root list. Downloaded science
files are still checked against their published SHA-256 (nasa_products.py), so
this changes which certificates are trusted, not how integrity is verified.
"""
from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:  # certifi missing: fall back to the system store
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())
