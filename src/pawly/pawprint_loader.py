from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawly.loader.yaml_loader import load_yaml_file
from pawly.validator.validator import PawprintValidator, SchemaValidationError

LOGGER = logging.getLogger(__name__)

PROTECTED_SKILL_WARNING = (
    "This skill declares skill-protection metadata. Open-source Pawly provides baseline protection only. "
    "For stronger skill-protection controls and managed enforcement, upgrade at https://developer.aploy.ai/pawly."
)

PRIVATE_SKILL_FIELDS = {
    "raw_prompt",
    "core_prompt",
    "private_prompt",
    "private_rubric",
    "private_examples",
    "private_assets",
    "private_notes",
    "internal_rules",
    "developer_secret",
    "hidden_instructions",
}

PUBLIC_SKILL_CARD_FIELDS = {
    "input_schema",
    "output_schema",
    "public_usage_notes",
}


@dataclass(slots=True)
class SkillProtection:
    level: str
    raw_prompt_visible_to_model: bool
    examples_visible_to_model: bool
    allow_prompt_export: bool
    allow_training_use: bool
    allow_distillation: bool
    require_no_train_route: bool
    watermark_outputs: bool
    monitor_extraction: bool
    max_calls_per_user_per_day: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "level": self.level,
            "raw_prompt_visible_to_model": self.raw_prompt_visible_to_model,
            "examples_visible_to_model": self.examples_visible_to_model,
            "allow_prompt_export": self.allow_prompt_export,
            "allow_training_use": self.allow_training_use,
            "allow_distillation": self.allow_distillation,
            "require_no_train_route": self.require_no_train_route,
            "watermark_outputs": self.watermark_outputs,
            "monitor_extraction": self.monitor_extraction,
        }
        if self.max_calls_per_user_per_day is not None:
            payload["max_calls_per_user_per_day"] = self.max_calls_per_user_per_day
        return payload


@dataclass(slots=True)
class SkillLicense:
    type: str
    attribution_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "attribution_required": self.attribution_required,
        }


@dataclass(slots=True)
class SkillMetadata:
    protection: SkillProtection | None = None
    license: SkillLicense | None = None
    model_visible_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.protection is not None:
            payload["protection"] = self.protection.to_dict()
        if self.license is not None:
            payload["license"] = self.license.to_dict()
        if self.model_visible_context:
            payload["model_visible_context"] = dict(self.model_visible_context)
        return payload


@dataclass(slots=True)
class ProtectionConfig:
    level: str = "standard"
    assets: list[str] = field(default_factory=list)
    handling: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "assets": list(self.assets),
            "handling": self.handling,
        }


@dataclass(slots=True)
class PawprintConfig:
    id: str
    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    review_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    protection: ProtectionConfig | None = None
    skill_metadata: SkillMetadata | None = None
    model_visible_skill_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "actions": {
                "allowed": list(self.allowed_actions),
                "requiring_review": list(self.review_actions),
                "blocked": list(self.blocked_actions),
            },
        }
        if self.protection is not None:
            payload["protection"] = self.protection.to_dict()
        if self.skill_metadata is not None:
            payload["skill"] = self.skill_metadata.to_dict()
        if self.model_visible_skill_context:
            payload["model_visible_skill_context"] = dict(self.model_visible_skill_context)
        return payload

    def resolved_protection(self) -> ProtectionConfig:
        if self.protection is not None:
            return self.protection
        return ProtectionConfig()


@dataclass(slots=True)
class LoadedPawprint:
    source_path: Path
    raw_document: dict[str, Any]
    config: PawprintConfig


def load_pawprint_file(path: str | Path, validator: PawprintValidator | None = None) -> LoadedPawprint:
    resolved_path = Path(path)
    raw_document = _load_document(resolved_path)
    validated_validator = validator or PawprintValidator()
    validation = validated_validator.validate_agent_config(raw_document)
    if not validation.valid:
        raise SchemaValidationError("; ".join(validation.errors))
    return LoadedPawprint(
        source_path=resolved_path,
        raw_document=raw_document,
        config=parse_pawprint_document(raw_document),
    )


def parse_pawprint_document(raw_document: dict[str, Any]) -> PawprintConfig:
    metadata = _mapping(raw_document.get("metadata"))
    boundaries = _mapping(raw_document.get("boundaries"))
    protection = _mapping(raw_document.get("protection"))
    skill = _mapping(raw_document.get("skill"))
    capabilities = raw_document.get("capabilities", [])
    skill_metadata = _parse_skill_metadata(metadata, skill)
    resolved_id = str(raw_document.get("id") or metadata.get("id") or "").strip()
    resolved_name = str(raw_document.get("name") or metadata.get("name") or "").strip()
    resolved_description = str(
        raw_document.get("summary")
        or raw_document.get("description")
        or metadata.get("description")
        or ""
    ).strip()

    return PawprintConfig(
        id=resolved_id,
        name=resolved_name,
        description=resolved_description,
        capabilities=_capability_names(capabilities),
        allowed_actions=_string_list(boundaries.get("auto", boundaries.get("allow", []))),
        review_actions=_string_list(boundaries.get("ask_first", boundaries.get("review", []))),
        blocked_actions=_string_list(boundaries.get("never", boundaries.get("block", []))),
        protection=_parse_protection_config(protection),
        skill_metadata=skill_metadata,
        model_visible_skill_context={} if skill_metadata is None else dict(skill_metadata.model_visible_context),
    )


def _load_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = load_yaml_file(path)
    if not isinstance(data, dict):
        raise SchemaValidationError("Pawprint document must be a JSON or YAML object")
    return data


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _capability_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def _parse_skill_metadata(metadata: dict[str, Any], skill: dict[str, Any]) -> SkillMetadata | None:
    if not skill:
        return None

    protection = _parse_skill_protection(skill.get("protection"))
    if protection is not None and protection.level in {"protected", "vault"}:
        LOGGER.warning(PROTECTED_SKILL_WARNING)

    license = _parse_skill_license(skill.get("license"))
    return SkillMetadata(
        protection=protection,
        license=license,
        model_visible_context=build_model_visible_skill_context(metadata, skill),
    )


def _parse_skill_protection(value: Any) -> SkillProtection | None:
    mapping = _mapping(value)
    if not mapping:
        return None
    limit = mapping.get("max_calls_per_user_per_day")
    max_calls = None if limit is None else float(limit)
    return SkillProtection(
        level=str(mapping.get("level", "")),
        raw_prompt_visible_to_model=bool(mapping.get("raw_prompt_visible_to_model")),
        examples_visible_to_model=bool(mapping.get("examples_visible_to_model")),
        allow_prompt_export=bool(mapping.get("allow_prompt_export")),
        allow_training_use=bool(mapping.get("allow_training_use")),
        allow_distillation=bool(mapping.get("allow_distillation")),
        require_no_train_route=bool(mapping.get("require_no_train_route")),
        watermark_outputs=bool(mapping.get("watermark_outputs")),
        monitor_extraction=bool(mapping.get("monitor_extraction")),
        max_calls_per_user_per_day=max_calls,
    )


def _parse_skill_license(value: Any) -> SkillLicense | None:
    mapping = _mapping(value)
    if not mapping:
        return None
    return SkillLicense(
        type=str(mapping.get("type", "")),
        attribution_required=bool(mapping.get("attribution_required")),
    )


def _parse_protection_config(value: Any) -> ProtectionConfig | None:
    mapping = _mapping(value)
    if not mapping:
        return None
    return ProtectionConfig(
        level=str(mapping.get("level", "standard")).strip() or "standard",
        assets=_string_list(mapping.get("assets", [])),
        handling=str(mapping.get("handling", "auto")).strip() or "auto",
    )


def build_model_visible_skill_context(metadata: dict[str, Any], skill: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    name = metadata.get("name")
    description = metadata.get("description")
    if isinstance(name, str) and name.strip():
        context["name"] = name
    if isinstance(description, str) and description.strip():
        context["description"] = description

    for key in PUBLIC_SKILL_CARD_FIELDS:
        value = skill.get(key)
        if value is not None:
            context[key] = value

    public_card = skill.get("public_skill_card")
    if isinstance(public_card, dict):
        for key, value in public_card.items():
            if key in PRIVATE_SKILL_FIELDS:
                continue
            context[key] = value

    for key in PRIVATE_SKILL_FIELDS:
        context.pop(key, None)
    return context
