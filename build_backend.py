"""Minimal offline build backend for pawly.

This backend supports editable installs and console script generation without
requiring network-fetched build dependencies.
"""

from __future__ import annotations

import base64
import csv
import hashlib
from io import BytesIO, StringIO
import os
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST_NAME = "pawly"
PROJECT_NAME = "pawly"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST_INFO = f"{DIST_NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{DIST_NAME}-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"{DIST_NAME}-{VERSION}.tar.gz"
ENTRY_POINTS = "[console_scripts]\npawly = pawly.cli:main\n"
REQUIRES_DIST = ["pawly-pawprint>=0.1.0"]


def _metadata_text() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {PROJECT_NAME}",
        f"Version: {VERSION}",
        "Summary: Lightweight reference implementation of the Aploy Pawly execution-boundary controller.",
        "Requires-Python: >=3.10",
        "License: Apache-2.0",
        "Description-Content-Type: text/markdown",
    ]
    lines.extend(f"Requires-Dist: {dependency}" for dependency in REQUIRES_DIST)
    lines.append("")
    if readme:
        lines.append(readme)
    return "\n".join(lines)


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: pawly-build-backend",
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
    (metadata_dir / "top_level.txt").write_text("pawly\n", encoding="utf-8")
    (metadata_dir / "RECORD").write_text("", encoding="utf-8")
    return DIST_INFO


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    return _build_metadata_dir(metadata_directory)


def prepare_metadata_for_build_editable(metadata_directory: str, config_settings=None) -> str:
    return _build_metadata_dir(metadata_directory)


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_sdist(config_settings=None) -> list[str]:
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
            (f"{DIST_INFO}/top_level.txt", b"pawly\n"),
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


def build_sdist(sdist_directory: str, config_settings=None) -> str:
    sdist_path = Path(sdist_directory) / SDIST_NAME
    prefix = f"{DIST_NAME}-{VERSION}"
    included_roots = ["src", "tests", "README.md", "LICENSE", "VERSION", "pyproject.toml", "build_backend.py"]
    with tarfile.open(sdist_path, "w:gz") as tf:
        metadata = _metadata_text().encode("utf-8")
        info = tarfile.TarInfo(f"{prefix}/PKG-INFO")
        info.size = len(metadata)
        tf.addfile(info, BytesIO(metadata))
        for item in included_roots:
            path = ROOT / item
            if path.exists():
                tf.add(path, arcname=f"{prefix}/{item}")
    return SDIST_NAME


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _write_wheel(wheel_directory, editable=True)
