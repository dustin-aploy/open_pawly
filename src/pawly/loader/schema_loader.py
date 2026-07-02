from __future__ import annotations

from importlib import resources
import json
from functools import lru_cache
from pathlib import Path


class PawprintDependencyError(RuntimeError):
    """Raised when the runtime cannot load schema assets."""


PAWLY_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _schema_path(name: str) -> Path:
    if name == "pawprint.schema.json":
        schema_path = _pawprint_resource_path("schemas", name)
    else:
        schema_path = PAWLY_SCHEMA_DIR / name
    if not schema_path.exists():
        raise PawprintDependencyError(f"schema not found: {schema_path}")
    return schema_path


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    schema_path = _schema_path(name)
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_pawprint_version() -> str:
    version_path = _pawprint_resource_path("VERSION")
    if not version_path.exists():
        raise PawprintDependencyError(f"pawprint version file not found: {version_path}")
    return version_path.read_text(encoding="utf-8").strip()


def resolve_schema_path(name: str) -> Path:
    return _schema_path(name)


def _pawprint_resource_path(*parts: str) -> Path:
    try:
        resource = resources.files("pawprint").joinpath(*parts)
    except ModuleNotFoundError as exc:
        raise PawprintDependencyError(
            "pawprint package is not installed. Install 'pawprint' before using pawly."
        ) from exc
    return Path(str(resource))
