"""One definition of "this data file is installed", shared by every module.

A clone without ``git lfs pull`` contains ~130-byte Git LFS *pointer* files in
place of the rasters, shapefiles and binary SPICE kernels. They exist on disk,
so a bare ``is_file()`` check passes and the libraries then fail deep inside
with unhelpful errors (``SPICE(FRAMEDATANOTFOUND)``, ``not recognized as a
supported file format``). Every product check goes through this module so that

* optional products treat a pointer exactly like a missing file and degrade
  as documented (``product_not_installed``, terrain fallbacks), and
* required products raise :class:`DataNotInstalledError` naming the fix.

See docs/DATA_SETUP.md and ``python -m src.acquire.verify_data``.
"""
from __future__ import annotations

from pathlib import Path

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"
FIX_HINT = ("run `git lfs pull`, or `python -m src.acquire.verify_data --fetch` to download "
            "it from NASA/NAIF; see docs/DATA_SETUP.md")


class DataNotInstalledError(FileNotFoundError):
    """A required data file is missing or is an unfetched Git LFS pointer."""


def is_lfs_pointer(path: str | Path) -> bool:
    try:
        with Path(path).open("rb") as handle:
            return handle.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError:
        return False


def is_installed(path: str | Path) -> bool:
    """True for a real file (or a GDAL /vsi path); False if missing or an LFS pointer."""
    if str(path).startswith("/vsi"):
        return True
    candidate = Path(path)
    return candidate.is_file() and not is_lfs_pointer(candidate)


def require(path: str | Path, description: str) -> Path:
    """Return ``path`` if installed, else raise :class:`DataNotInstalledError` with the fix."""
    candidate = Path(path)
    if str(path).startswith("/vsi") or is_installed(candidate):
        return candidate
    if candidate.is_file():
        raise DataNotInstalledError(
            f"{description} is a Git LFS pointer, not the data: {candidate}. {FIX_HINT}.")
    raise DataNotInstalledError(f"{description} not found: {candidate}. {FIX_HINT}.")
