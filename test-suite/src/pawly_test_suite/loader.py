from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pawly.loader.schema_loader import load_pawprint_version as load_runtime_pawprint_version
from pawly.loader.schema_loader import load_schema
from pawly.loader.yaml_loader import load_yaml_file

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "fixtures"
SCHEMAS_DIR = ROOT / "schemas"


def load_agent(path: str | Path) -> dict:
    return load_yaml_file(path)


def load_fixture(name: str) -> dict:
    return load_yaml_file(FIXTURES_DIR / name)


def load_json_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def load_report_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "compliance-report.schema.json").read_text(encoding="utf-8"))


def load_local_report_schema_copy() -> dict:
    return json.loads((SCHEMAS_DIR / "compliance-report.schema.json").read_text(encoding="utf-8"))

def load_pawprint_version() -> str:
    return load_runtime_pawprint_version()


def declaration_digest(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()
