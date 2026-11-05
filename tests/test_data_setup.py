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
        self.assertEqual(checked, 15)  # 5 kernels, DEM, 3 illumination, 4 PSR, 2 global DEM

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

    def test_offline_catalog_matches_canonical_ids(self) -> None:
        status, fixture = verify_data.check_catalog_alignment()
        self.assertEqual(status, "OK")
        self.assertEqual(fixture, "offline_fixtures/missions.json")

    def test_provenance_inventory_is_citation_complete(self) -> None:
        report = json.loads(Path("data/validation/data_provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], "apolloharness.data_provenance.v1")
        self.assertTrue(report["entries"])
        self.assertTrue(all(entry["citation_status"] in {"present", "present_as_derived"}
                            for entry in report["entries"]))
        self.assertTrue(all(entry["human_review_status"] == "pending"
                            for entry in report["entries"]))


class PointerHandlingTests(unittest.TestCase):
    """A clone without `git lfs pull` must fail clearly or degrade, never cryptically."""

    def test_required_files_raise_with_the_fix(self) -> None:
        from src.compute.datafiles import DataNotInstalledError, require
        with tempfile.TemporaryDirectory() as tmp:
            pointer = Path(tmp) / "de430.bsp"
            pointer.write_bytes(POINTER)
            with self.assertRaisesRegex(DataNotInstalledError, "Git LFS pointer.*git lfs pull"):
                require(pointer, "Required SPICE kernel")
            with self.assertRaisesRegex(DataNotInstalledError, "not found"):
                require(Path(tmp) / "missing.tif", "LOLA DEM")
            self.assertTrue(issubclass(DataNotInstalledError, FileNotFoundError))

    def test_optional_products_degrade_to_not_installed(self) -> None:
        from src.compute import site_evaluation
        with tempfile.TemporaryDirectory() as tmp:
            pointers = []
            for name in ("a.TIF", "b.TIF", "psr.SHP"):
                (Path(tmp) / name).write_bytes(POINTER)
                pointers.append(Path(tmp) / name)
            with mock.patch.object(site_evaluation, "ANNUAL_PRODUCTS", tuple(pointers[:2])):
                self.assertEqual(site_evaluation._annual_illumination(-85.0, 0.0)["status"],
                                 "product_not_installed")
            self.assertEqual(site_evaluation._psr(-85.0, 0.0, pointers[2])["status"],
                             "product_not_installed")


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


class IdentifyResourcesTests(unittest.TestCase):
    def test_classifies_by_content_not_name(self) -> None:
        from src.acquire.identify_resources import run
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "naif0012.tls").write_bytes(Path("data/spice/naif0012.tls").read_bytes())
            (folder / "renamed_catalog.json").write_bytes(Path("data/missions.json").read_bytes())
            (folder / "pck00010.tpc").write_text("a different release\n", encoding="utf-8")
            (folder / "challenge_sites.csv").write_text("name,lat,lon\nA,-89,0\n", encoding="utf-8")
            (folder / ".hidden").write_text("ignored", encoding="utf-8")
            found = {Path(f.path).name: f for f in run([folder])}
        self.assertEqual(set(found), {"naif0012.tls", "renamed_catalog.json", "pck00010.tpc",
                                      "challenge_sites.csv"})
        self.assertEqual(found["naif0012.tls"].status, "KNOWN")
        self.assertEqual(found["renamed_catalog.json"].status, "KNOWN")  # matched by SHA-256
        self.assertEqual(found["renamed_catalog.json"].matches, "data/missions.json")
        self.assertEqual(found["pck00010.tpc"].status, "NEW_VERSION")
        self.assertEqual(found["challenge_sites.csv"].status, "NEW")
        self.assertEqual(found["challenge_sites.csv"].details,
                         {"kind": "table", "columns": ["name", "lat", "lon"], "rows": 1})
