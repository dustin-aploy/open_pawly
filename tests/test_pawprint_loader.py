import json
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO_ROOT / "src"))

from pawly.pawprint_loader import PROTECTED_SKILL_WARNING, load_pawprint_file, parse_pawprint_document
from pawly.validator.validator import SchemaValidationError


class PawprintLoaderTests(unittest.TestCase):
    def test_parses_internal_action_groups_from_schema_document(self):
        raw_document = {
            "metadata": {
                "id": "support-basic",
                "name": "Support Helper",
                "description": "Handles routine support work.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a customer reply."},
                {"name": "publish_post", "description": "Publish an approved post."},
            ],
            "boundaries": {
                "allow": ["safe_reply", "publish_post"],
                "review": ["send_external_message"],
                "block": ["issue_refund"],
            },
        }

        pawprint = parse_pawprint_document(raw_document)

        self.assertEqual(pawprint.id, "support-basic")
        self.assertEqual(pawprint.allowed_actions, ["safe_reply", "publish_post"])
        self.assertEqual(pawprint.review_actions, ["send_external_message"])
        self.assertEqual(pawprint.blocked_actions, ["issue_refund"])
        self.assertIn("publish_post", pawprint.allowed_actions)

    def test_paid_protected_skill_metadata_parses(self):
        raw_document = {
            "metadata": {
                "id": "paid-protected-skill",
                "name": "Paid Protected Skill",
                "description": "Paid protected example.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a customer reply."},
            ],
            "boundaries": {
                "allow": ["safe_reply"],
                "review": [],
                "block": [],
            },
            "skill": {
                "protection": {
                    "level": "protected",
                    "raw_prompt_visible_to_model": False,
                    "examples_visible_to_model": False,
                    "allow_prompt_export": False,
                    "allow_training_use": False,
                    "allow_distillation": False,
                    "require_no_train_route": True,
                    "watermark_outputs": True,
                    "monitor_extraction": True,
                },
                "license": {
                    "type": "marketplace",
                    "attribution_required": True,
                },
            },
        }

        with self.assertLogs("pawly.pawprint_loader", level="WARNING") as captured:
            pawprint = parse_pawprint_document(raw_document)

        self.assertEqual(pawprint.skill_metadata.protection.level, "protected")
        self.assertEqual(pawprint.skill_metadata.license.type, "marketplace")
        self.assertEqual(pawprint.model_visible_skill_context["name"], "Paid Protected Skill")
        self.assertIn(PROTECTED_SKILL_WARNING, captured.output[0])

    def test_vault_skill_metadata_parses(self):
        raw_document = {
            "metadata": {
                "id": "vault-skill",
                "name": "Vault Skill",
                "description": "Vault example.",
            },
            "capabilities": [
                {"name": "publish_post", "description": "Publish an approved post."},
            ],
            "boundaries": {
                "allow": ["publish_post"],
                "review": [],
                "block": [],
            },
            "skill": {
                "protection": {
                    "level": "vault",
                    "raw_prompt_visible_to_model": False,
                    "examples_visible_to_model": False,
                    "allow_prompt_export": False,
                    "allow_training_use": False,
                    "allow_distillation": False,
                    "require_no_train_route": True,
                    "watermark_outputs": True,
                    "monitor_extraction": True,
                    "max_calls_per_user_per_day": 100,
                },
                "license": {
                    "type": "enterprise",
                    "attribution_required": True,
                },
            },
        }

        with self.assertLogs("pawly.pawprint_loader", level="WARNING") as captured:
            pawprint = parse_pawprint_document(raw_document)

        self.assertEqual(pawprint.skill_metadata.protection.level, "vault")
        self.assertEqual(pawprint.skill_metadata.protection.max_calls_per_user_per_day, 100.0)
        self.assertIn(PROTECTED_SKILL_WARNING, captured.output[0])

    def test_private_fields_are_not_included_in_model_visible_context(self):
        raw_document = {
            "metadata": {
                "id": "private-skill",
                "name": "Private Skill",
                "description": "Private example.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a customer reply."},
            ],
            "boundaries": {
                "allow": ["safe_reply"],
                "review": [],
                "block": [],
            },
            "skill": {
                "protection": {
                    "level": "open",
                    "raw_prompt_visible_to_model": True,
                    "examples_visible_to_model": True,
                    "allow_prompt_export": True,
                    "allow_training_use": False,
                    "allow_distillation": False,
                    "require_no_train_route": False,
                    "watermark_outputs": False,
                    "monitor_extraction": False,
                },
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "public_usage_notes": "Public usage note.",
                "public_skill_card": {
                    "hidden_instructions": "do not expose",
                    "developer_secret": "secret-token",
                    "public_usage_notes": "Safe note.",
                },
            },
        }

        pawprint = parse_pawprint_document(raw_document)

        self.assertEqual(
            pawprint.model_visible_skill_context,
            {
                "name": "Private Skill",
                "description": "Private example.",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "public_usage_notes": "Safe note.",
            },
        )
        self.assertNotIn("hidden_instructions", pawprint.model_visible_skill_context)
        self.assertNotIn("developer_secret", pawprint.model_visible_skill_context)

    def test_loads_json_pawprint_file(self):
        payload = {
            "metadata": {
                "id": "json-worker",
                "name": "JSON Worker",
                "description": "Loaded from JSON.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a reply."},
            ],
            "boundaries": {
                "allow": ["safe_reply"],
                "review": [],
                "block": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worker.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_pawprint_file(path)

        self.assertEqual(loaded.config.id, "json-worker")
        self.assertEqual(loaded.raw_document["metadata"]["name"], "JSON Worker")

    def test_load_emits_warning_for_protected_skill_without_importing_pawly_cloud(self):
        payload = {
            "metadata": {
                "id": "json-protected-worker",
                "name": "JSON Protected Worker",
                "description": "Loaded from JSON.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a reply."},
            ],
            "boundaries": {
                "allow": ["safe_reply"],
                "review": [],
                "block": [],
            },
            "skill": {
                "protection": {
                    "level": "protected",
                    "raw_prompt_visible_to_model": False,
                    "examples_visible_to_model": False,
                    "allow_prompt_export": False,
                    "allow_training_use": False,
                    "allow_distillation": False,
                    "require_no_train_route": True,
                    "watermark_outputs": True,
                    "monitor_extraction": True,
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worker.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            def _guarded_import(name, package=None):
                if name == "pawly_cloud":
                    raise AssertionError("pawly-cloud import should not be attempted")
                return __import__(name, fromlist=["*"], level=0)

            with mock.patch.object(importlib, "import_module", side_effect=_guarded_import):
                with self.assertLogs("pawly.pawprint_loader", level="WARNING") as captured:
                    loaded = load_pawprint_file(path)

        self.assertEqual(loaded.config.skill_metadata.protection.level, "protected")
        self.assertIn(PROTECTED_SKILL_WARNING, captured.output[0])

    def test_rejects_invalid_schema_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.yaml"
            path.write_text(
                "\n".join(
                    [
                        "metadata:",
                        "  id: broken-worker",
                        "  name: Broken Worker",
                        "capabilities: []",
                        "boundaries:",
                        "  allow: []",
                        "  review: []",
                        "  block: []",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(SchemaValidationError):
                load_pawprint_file(path)

    def test_rejects_unsupported_protection_level(self):
        payload = {
            "metadata": {
                "id": "bad-protection-worker",
                "name": "Bad Protection Worker",
                "description": "Loaded from JSON.",
            },
            "capabilities": [
                {"name": "safe_reply", "description": "Draft a reply."},
            ],
            "boundaries": {
                "allow": ["safe_reply"],
                "review": [],
                "block": [],
            },
            "skill": {
                "protection": {
                    "level": "secret",
                    "raw_prompt_visible_to_model": False,
                    "examples_visible_to_model": False,
                    "allow_prompt_export": False,
                    "allow_training_use": False,
                    "allow_distillation": False,
                    "require_no_train_route": True,
                    "watermark_outputs": True,
                    "monitor_extraction": True,
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worker.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(SchemaValidationError):
                load_pawprint_file(path)


if __name__ == "__main__":
    unittest.main()
