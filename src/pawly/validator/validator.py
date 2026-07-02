from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from pawly.loader.schema_loader import load_schema


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    errors: list[str]


class SchemaValidationError(ValueError):
    pass


class PawprintValidator:
    def __init__(self) -> None:
        self.schemas = {
            "pawprint.schema.json": load_schema("pawprint.schema.json"),
            "intent.schema.json": load_schema("intent.schema.json"),
            "decision.schema.json": load_schema("decision.schema.json"),
            "report.schema.json": load_schema("report.schema.json"),
        }

    def validate_agent_config(self, config: dict[str, Any]) -> ValidationResult:
        errors = self._validate_with_schema(
            config,
            self.schemas["pawprint.schema.json"],
            "$",
            self.schemas["pawprint.schema.json"],
        )
        errors.extend(self._validate_pawprint_rules(config))
        return ValidationResult(valid=not errors, errors=errors)

    def validate_report(self, report: dict[str, Any]) -> ValidationResult:
        errors = self._validate_with_schema(report, self.schemas["report.schema.json"], "$", self.schemas["report.schema.json"])
        return ValidationResult(valid=not errors, errors=errors)

    def validate_intent(self, intent: dict[str, Any]) -> ValidationResult:
        errors = self._validate_with_schema(intent, self.schemas["intent.schema.json"], "$", self.schemas["intent.schema.json"])
        return ValidationResult(valid=not errors, errors=errors)

    def validate_decision(self, decision: dict[str, Any]) -> ValidationResult:
        errors = self._validate_with_schema(
            decision,
            self.schemas["decision.schema.json"],
            "$",
            self.schemas["decision.schema.json"],
        )
        return ValidationResult(valid=not errors, errors=errors)

    def _validate_with_schema(self, instance: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if "$ref" in schema:
            resolved, resolved_root = self._resolve_ref(schema["$ref"], root_schema)
            return self._validate_with_schema(instance, resolved, path, resolved_root)
        if "oneOf" in schema:
            variants = []
            for option in schema["oneOf"]:
                option_errors = self._validate_with_schema(instance, option, path, root_schema)
                if not option_errors:
                    variants.append(option)
            if len(variants) != 1:
                errors.append(f"{path} must match exactly one schema option")
            return errors
        if "const" in schema and instance != schema["const"]:
            errors.append(f"{path} must equal {schema['const']!r}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path} must be one of {schema['enum']!r}")
        if instance is None:
            return errors
        schema_type = schema.get("type")
        if schema_type == "object":
            if not isinstance(instance, dict):
                return errors + [f"{path} must be an object"]
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    errors.append(f"{path}.{key} is required")
            properties = schema.get("properties", {})
            pattern_properties = schema.get("patternProperties", {})
            additional_allowed = schema.get("additionalProperties", True)
            for key, value in instance.items():
                if key in properties:
                    errors.extend(self._validate_with_schema(value, properties[key], f"{path}.{key}", root_schema))
                    continue
                matched_pattern = False
                for pattern, pattern_schema in pattern_properties.items():
                    if re.fullmatch(pattern, key):
                        errors.extend(self._validate_with_schema(value, pattern_schema, f"{path}.{key}", root_schema))
                        matched_pattern = True
                        break
                if matched_pattern:
                    continue
                if additional_allowed is False:
                    errors.append(f"{path}.{key} is not allowed by the Pawprint schema")
                elif isinstance(additional_allowed, dict):
                    errors.extend(self._validate_with_schema(value, additional_allowed, f"{path}.{key}", root_schema))
            return errors
        if schema_type == "array":
            if not isinstance(instance, list):
                return errors + [f"{path} must be an array"]
            if len(instance) < schema.get("minItems", 0):
                errors.append(f"{path} must contain at least {schema['minItems']} items")
            item_schema = schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(instance):
                    errors.extend(self._validate_with_schema(item, item_schema, f"{path}[{index}]", root_schema))
            return errors
        if schema_type == "string":
            if not isinstance(instance, str):
                return errors + [f"{path} must be a string"]
            if len(instance) < schema.get("minLength", 0):
                errors.append(f"{path} must be at least {schema['minLength']} characters")
            if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
                errors.append(f"{path} does not match required pattern")
            return errors
        if schema_type == "integer":
            if not isinstance(instance, int) or isinstance(instance, bool):
                return errors + [f"{path} must be an integer"]
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path} must be >= {schema['minimum']}")
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                errors.append(f"{path} must be > {schema['exclusiveMinimum']}")
            return errors
        if schema_type == "number":
            if not isinstance(instance, (int, float)) or isinstance(instance, bool):
                return errors + [f"{path} must be a number"]
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path} must be >= {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(f"{path} must be <= {schema['maximum']}")
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                errors.append(f"{path} must be > {schema['exclusiveMinimum']}")
            return errors
        if schema_type == "boolean":
            if not isinstance(instance, bool):
                errors.append(f"{path} must be a boolean")
            return errors
        return errors

    def _resolve_ref(self, ref: str, root_schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if ref.startswith("#/"):
            target = root_schema
            for part in ref[2:].split("/"):
                target = target[part]
            return target, root_schema
        if ref.endswith(".json"):
            target_root = self.schemas[ref]
            return target_root, target_root
        raise SchemaValidationError(f"Unsupported schema reference: {ref}")

    def _validate_pawprint_rules(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        capabilities = config.get("capabilities")
        metadata = config.get("metadata")
        boundaries = config.get("boundaries")
        if isinstance(metadata, dict):
            if not isinstance(capabilities, list) or not isinstance(boundaries, dict):
                return errors
            capability_set = {
                str(item.get("name", ""))
                for item in capabilities
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            }
        else:
            if not isinstance(capabilities, list) or not isinstance(boundaries, dict):
                return errors
            capability_set = {item for item in capabilities if isinstance(item, str)}

        if not capability_set:
            return errors
        return errors
