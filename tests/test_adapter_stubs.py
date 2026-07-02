import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from pawly.types import IntentAction, IntentSource, TaskRequest


def _load_adapter_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class StubGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, *, task, action, confidence, metadata=None, executor):
        intent = TaskRequest(
            task=f"{task} approved",
            action=f"{action} approved",
            confidence=min(1.0, confidence + 0.01),
            metadata={"reviewer": "stub"},
        ).to_intent()
        intent.action = IntentAction(name=intent.action.name, arguments={"task": intent.summary, "mode": "approved"})
        self.calls.append(
            {
                "task": task,
                "action": action,
                "confidence": confidence,
                "metadata": metadata,
            }
        )
        result = executor(intent)
        return {
            "type": "allow",
            "execution": {"executed": True, "result": result},
        }


class AdapterStubTests(unittest.TestCase):
    def test_openai_adapter_uses_shared_gateway_flow(self):
        module = _load_adapter_module(
            REPO_ROOT / "adapters" / "openai-agents" / "adapter_stub.py",
            "openai_agents_adapter_stub",
        )
        audit_events: list[dict] = []
        gateway = StubGateway()
        adapter = module.OpenAIAgentsPawAdapter(runtime=None, audit_hook=audit_events.append, gateway=gateway)
        action = module.OpenAIAgentAction(
            task="answer order status",
            tool_name="draft helpful reply",
            confidence=0.92,
            payload={"channel": "email"},
        )

        received = []
        result = adapter.execute_tool(action, lambda updated: received.append(updated) or {"tool": updated.tool_name})

        self.assertEqual(result["type"], "allow")
        self.assertEqual(gateway.calls[0]["action"], "draft helpful reply")
        self.assertEqual(received[0].tool_name, "draft helpful reply approved")
        self.assertEqual(received[0].payload["mode"], "approved")
        self.assertEqual(audit_events[0]["framework"], "openai-agents")
        self.assertTrue(audit_events[0]["executed"])

    def test_langgraph_adapter_preserves_transition_mapping(self):
        module = _load_adapter_module(
            REPO_ROOT / "adapters" / "langgraph" / "adapter_stub.py",
            "langgraph_adapter_stub",
        )
        audit_events: list[dict] = []
        gateway = StubGateway()
        adapter = module.LangGraphPawAdapter(runtime=None, audit_hook=audit_events.append, gateway=gateway)
        transition = module.GraphTransition(
            from_node="draft",
            to_node="publish",
            task="publish update",
            confidence=0.88,
            metadata={"channel": "blog"},
        )

        received = []
        result = adapter.execute_transition(transition, lambda updated: received.append(updated) or {"to": updated.to_node})

        self.assertEqual(result["type"], "allow")
        self.assertEqual(gateway.calls[0]["action"], "draft->publish")
        self.assertEqual(received[0].from_node, "draft")
        self.assertEqual(received[0].to_node, "publish approved")
        self.assertEqual(received[0].approved_action_name, "draft->publish approved")
        self.assertEqual(received[0].metadata["mode"], "approved")
        self.assertEqual(audit_events[0]["framework"], "langgraph")
        self.assertTrue(audit_events[0]["executed"])


if __name__ == "__main__":
    unittest.main()
