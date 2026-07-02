"""Minimal offline build backend for pawly-test-suite."""

from __future__ import annotations

import base64
import csv
import hashlib
from io import StringIO
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST_NAME = "pawly_test_suite"
PROJECT_NAME = "pawly-test-suite"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
RUNTIME_DEPENDENCY_URI = (ROOT.parent / "runtime").resolve().as_uri()
DIST_INFO = f"{DIST_NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{DIST_NAME}-{VERSION}-py3-none-any.whl"
ENTRY_POINTS = "[console_scripts]\npawly-test-suite = pawly_test_suite.runner:main\n"


def _metadata_text() -> str:
    return "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {PROJECT_NAME}",
            f"Version: {VERSION}",
            "Summary: Minimal local validation suite for Pawprint-based workers.",
            "Requires-Python: >=3.10",
            f"Requires-Dist: pawly @ {RUNTIME_DEPENDENCY_URI}",
            "License: Apache-2.0",
            "",
        ]
    )


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: pawly-test-suite-build-backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _record_line(path: str, content: bytes) -> tuple[str, str, str]:
    digest = hashlib.sha256(content).digest()
    b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return path, f"sha256={b64}", str(len(content))


def _package_files() -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for root, _, names in os.walk(SRC, followlinks=True):
        root_path = Path(root)
        for name in sorted(names):
            path = root_path / name
            rel = path.relative_to(SRC).as_posix()
            files.append((rel, path.read_bytes()))
    return files


def _build_metadata_dir(metadata_directory: str) -> str:
    metadata_dir = Path(metadata_directory) / DIST_INFO
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (metadata_dir / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (metadata_dir / "entry_points.txt").write_text(ENTRY_POINTS, encoding="utf-8")
    (metadata_dir / "top_level.txt").write_text("pawly_test_suite\n", encoding="utf-8")
    (metadata_dir / "RECORD").write_text("", encoding="utf-8")
    return DIST_INFO


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    return _build_metadata_dir(metadata_directory)


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return _build_metadata_dir(metadata_directory)


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def _write_wheel(wheel_directory: str, editable: bool) -> str:
    wheel_path = Path(wheel_directory) / WHEEL_NAME
    entries: list[tuple[str, bytes]] = []

    if editable:
        entries.append((f"{DIST_NAME}.pth", f"import sys; sys.path.insert(0, {str(SRC.resolve())!r})\n".encode("utf-8")))
    else:
        entries.extend(_package_files())

    entries.extend(
        [
            (f"{DIST_INFO}/METADATA", _metadata_text().encode("utf-8")),
            (f"{DIST_INFO}/WHEEL", _wheel_text().encode("utf-8")),
            (f"{DIST_INFO}/entry_points.txt", ENTRY_POINTS.encode("utf-8")),
            (f"{DIST_INFO}/top_level.txt", b"pawly_test_suite\n"),
        ]
    )

    record_path = f"{DIST_INFO}/RECORD"
    rows = [_record_line(path, content) for path, content in entries]
    rows.append((record_path, "", ""))

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in entries:
            zf.writestr(path, content)
        sio = StringIO()
        writer = csv.writer(sio, lineterminator="\n")
        writer.writerows(rows)
        zf.writestr(record_path, sio.getvalue().encode("utf-8"))

    return WHEEL_NAME


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _write_wheel(wheel_directory, editable=False)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _write_wheel(wheel_directory, editable=True)
