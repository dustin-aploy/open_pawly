from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from wsgiref.simple_server import make_server

from pawly.audit.events import AuditEvent
from pawly.backends.audit import CompositeAuditSink, HostedActionSyncAuditSink, LocalAuditSink, build_default_audit_sink

try:
    from pawly_cloud.hosted_server import create_hosted_api_application

    HAS_PAWLY_CLOUD = True
except ImportError:
    create_hosted_api_application = None  # type: ignore[assignment]
    HAS_PAWLY_CLOUD = False


@unittest.skipUnless(HAS_PAWLY_CLOUD, "pawly-cloud is not installed; skipping cloud integration test")
class CloudActionSyncTests(unittest.TestCase):
    def test_hosted_action_sync_uploads_event(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            app = create_hosted_api_application(store_path=f"{tempdir}/hosted.json")
            registration = app.service.register_account(email="dev@example.com", password="password123", display_name="Dev")
            api_key = registration["api_key"]["api_key"]
            project_id = registration["project"]["project_id"]

            server = make_server("127.0.0.1", 0, app)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                sink = HostedActionSyncAuditSink(
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    api_key=api_key,
                )
                sink.append(_sample_event())
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

            records = app.service.list_action_events(api_key, {})
            self.assertEqual(records["total"], 1)
            self.assertEqual(records["items"][0]["action"]["name"], "publish_post")

    def test_build_default_audit_sink_returns_composite_when_pawly_auth_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env = {
                "PAWLY_CLOUD_BASE_URL": "http://127.0.0.1:8787",
                "PAWLY_AUTH_PATH": f"{tempdir}/pawly_auth.yaml",
            }
            original = {key: os.environ.get(key) for key in env}
            os.environ.update(env)
            try:
                Path(env["PAWLY_AUTH_PATH"]).write_text("api_key: demo-key\n", encoding="utf-8")
                sink = build_default_audit_sink(Path(tempdir) / "audit.jsonl")
            finally:
                for key, value in original.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            self.assertIsInstance(sink, CompositeAuditSink)
            self.assertIsInstance(sink.sinks[0], LocalAuditSink)

    def test_build_default_audit_sink_reads_pawly_auth_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            auth_path = Path(tempdir) / "pawly_auth.yaml"
            original_auth_path = os.environ.get("PAWLY_AUTH_PATH")
            os.environ["PAWLY_AUTH_PATH"] = str(auth_path)
            try:
                auth_path.write_text("api_key: demo-key\n", encoding="utf-8")
                sink = build_default_audit_sink(Path(tempdir) / "audit.jsonl")
            finally:
                if original_auth_path is None:
                    os.environ.pop("PAWLY_AUTH_PATH", None)
                else:
                    os.environ["PAWLY_AUTH_PATH"] = original_auth_path
            self.assertIsInstance(sink, CompositeAuditSink)

    def test_build_default_audit_sink_returns_local_only_without_pawly_auth_file(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            original_auth_path = os.environ.get("PAWLY_AUTH_PATH")
            os.environ["PAWLY_AUTH_PATH"] = str(Path(tempdir) / "missing.yaml")
            try:
                sink = build_default_audit_sink(Path(tempdir) / "audit.jsonl")
            finally:
                if original_auth_path is None:
                    os.environ.pop("PAWLY_AUTH_PATH", None)
                else:
                    os.environ["PAWLY_AUTH_PATH"] = original_auth_path
            self.assertIsInstance(sink, LocalAuditSink)


def _sample_event() -> AuditEvent:
    return AuditEvent(
        event_id="evt-demo",
        event_type="governed-execution",
        timestamp=datetime.now(UTC).isoformat(),
        agent_id="agent-1",
        pawprint_version="v1",
        decision_id="dec-1",
        outcome="allow",
        action={"name": "publish_post", "approved": True},
        original_intent={"task": "publish"},
        normalized_intent={"task": "publish"},
        policy_evaluation={"source": "rules"},
        runtime_overlays={},
        policy_references=[],
        matched_policy_rules=[],
        final_decision={"type": "allow"},
        reason_codes=["allowed"],
        executed_action={"name": "publish_post"},
        execution={"executed": True},
        risk_score=0.1,
        tenant_id="tenant-1",
        user_id="user-1",
        protection_level="protected",
        protection_handling="cautious",
        protection_assets=["customer_data"],
        action_argument_summary={"draft_id": "post-42"},
        output_summary={"status": "ok"},
    )
