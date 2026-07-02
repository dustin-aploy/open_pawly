from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pawly.loader.yaml_loader import load_yaml_file
from pawly.validator.validator import PawprintValidator


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_declaration(path: str | Path) -> dict[str, Any]:
    return load_yaml_file(path)


def validate_self_hosted_declaration(path: str | Path) -> list[str]:
    validator = PawprintValidator()
    config = load_declaration(path)
    result = validator.validate_agent_config(config)
    return list(result.errors)


def validate_invoke_example(declaration: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("method") != "POST":
        errors.append("$.method must equal 'POST'")
    url = payload.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        errors.append("$.url must be an http or https URL")
    headers = payload.get("headers")
    if not isinstance(headers, dict):
        errors.append("$.headers must be an object")
    body = payload.get("body")
    if not isinstance(body, dict):
        errors.append("$.body must be an object")
        return errors
    for key in ("task", "action", "confidence"):
        if key not in body:
            errors.append(f"$.body.{key} is required")
    return errors


def validate_healthcheck_example(declaration: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("method") != "GET":
        errors.append("$.method must equal 'GET'")
    url = payload.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        errors.append("$.url must be an http or https URL")
    if payload.get("expected_status") != 200:
        errors.append("$.expected_status must equal 200")
    return errors
