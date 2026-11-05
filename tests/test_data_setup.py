"""The data inventory (docs/DATA_SETUP.md) stays complete and consistent."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.acquire import verify_data
from src.acquire.nasa_products import PRODUCTS

POINTER = (b"version https://git-lfs.github.com/spec/v1\n"
           b"oid sha256:0000000000000000000000000000000000000000000000000000000000000000\nsize 5\n")


class InventoryTests(unittest.TestCase):
    def test_checksums_agree_with_download_registry(self) -> None:
        manifest = {Path(e.path).name: e for e in verify_data.MANIFEST}
        checked = 0
        for spec in PRODUCTS.values():
            files = spec.get("files") or {spec["filename"]: (spec["url"], spec["size_bytes"],
                                                            spec.get("sha256", ""))}
            for name, (url, size, sha) in files.items():
                entry = manifest[name]
                self.assertEqual((entry.size, entry.sha256, entry.source), (size, sha, url), name)
                checked += 1
        self.assertEqual(checked, 14)  # 5 kernels, DEM, 2 illumination, 4 PSR, 2 global DEM

    def test_tiles_in_manifest_match_tile_index(self) -> None:
        index = json.loads(Path("data/lola/tiles/index.json").read_text(encoding="utf-8"))
        indexed = {f"data/lola/tiles/{t['file']}" for t in index["tiles"]}
        listed = {e.path for e in verify_data.MANIFEST if e.group == "Site terrain tiles"}
        self.assertEqual(indexed, listed)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_every_lfs_file_is_inventoried(self) -> None:
        # From .gitattributes rules, so staged changes count (git lfs ls-files reads HEAD).
        files = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
        names = [n for n in files.decode().split("\0") if n]
        attrs = subprocess.run(["git", "check-attr", "--stdin", "-z", "filter"],
                               input="\0".join(names).encode(), capture_output=True,
                               check=True).stdout.decode().split("\0")
        tracked = [attrs[i] for i in range(0, len(attrs) - 2, 3) if attrs[i + 2] == "lfs"]
        self.assertTrue(tracked)
        listed = {e.path for e in verify_data.MANIFEST}
        self.assertEqual(sorted(set(tracked) - listed), [],
                         "new LFS file: add it to verify_data.MANIFEST and docs/DATA_SETUP.md")

    def test_small_text_files_are_not_in_lfs(self) -> None:
        # Code json/csv-parses these; an LFS pointer would crash instead of degrading.
        for relative in verify_data.TEXT_FILES:
            self.assertFalse(verify_data.is_lfs_pointer(Path(relative)), relative)
            attr = subprocess.run(["git", "check-attr", "filter", relative], capture_output=True,
                                  text=True).stdout
            self.assertNotIn("filter: lfs", attr, relative)


class CheckTests(unittest.TestCase):
    def _entry(self, **overrides) -> verify_data.DataFile:
        base = dict(path="x.bin", size=5, sha256="2cf24dba5fb0a30e26e83b2ac5b9e29e"
                    "1b161e5c1fa7425e73043362938b9824", group="g", required=True,
                    source="s", fix="f")
        base.update(overrides)
        return verify_data.DataFile(**base)

    def test_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(verify_data, "PROJECT_ROOT", Path(tmp)):
            entry = self._entry()
            self.assertEqual(verify_data.check(entry), "MISSING")
            (Path(tmp) / "x.bin").write_bytes(POINTER)
            self.assertEqual(verify_data.check(entry), "LFS_POINTER")
            (Path(tmp) / "x.bin").write_bytes(b"hellx")
            self.assertEqual(verify_data.check(entry), "WRONG_CHECKSUM")
            self.assertEqual(verify_data.check(entry, quick=True), "OK")
            self.assertEqual(verify_data.check(self._entry(exact_bytes=False)), "REBUILT")
            (Path(tmp) / "x.bin").write_bytes(b"hello")
            self.assertEqual(verify_data.check(entry), "OK")
            (Path(tmp) / "x.bin").write_bytes(b"hello!")
            self.assertEqual(verify_data.check(entry), "WRONG_SIZE")


if __name__ == "__main__":
    unittest.main()
