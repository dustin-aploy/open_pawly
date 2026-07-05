import unittest
from dataclasses import dataclass
from pathlib import Path

from pawly import (
    ClaudeSkillsPawAdapter,
    CrewAIPawAdapter,
    LangGraphPawAdapter,
    OpenClawPawAdapter,
    OpenAIAgentsPawAdapter,
    PawlyRuntime,
    SelfHostedHTTPAdapter,
    SelfHostedWorkerConfig,
    wrap_claude_skill_executor,
    wrap_claude_skills,
    wrap_crewai_task_executor,
    wrap_langgraph_transition_executor,
    wrap_openclaw_tool_executor,
    wrap_openai_tool_executor,
    wrap_openai_tools,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")

    def test_openai_adapter_accepts_plain_dict_without_manual_action_conversion(self):
        adapter = OpenAIAgentsPawAdapter(self.runtime)
        tool_call = {
            "task": "Answer order status questions for a customer",
            "tool_name": "draft helpful reply",
            "confidence": 0.94,
            "payload": {"channel": "email"},
        }

        seen = []
        result = adapter.execute_native_tool(
            tool_call,
            lambda updated: seen.append(updated) or {"tool_name": updated.tool_name, "payload": updated.payload},
        )

        self.assertEqual(result["type"], "allow")
        self.assertEqual(seen[0].tool_name, "draft helpful reply")
        self.assertEqual(seen[0].payload["channel"], "email")

    def test_claude_adapter_accepts_object_and_can_override_field_names(self):
        @dataclass
        class NativeSkillCall:
            name: str
            prompt: str
            score: float
            extras: dict

        invocation = NativeSkillCall(
            name="draft helpful reply",
            prompt="Answer order status questions for a customer",
            score=0.91,
            extras={"channel": "chat"},
        )
        adapter = ClaudeSkillsPawAdapter(self.runtime)

        seen = []
        result = adapter.execute_native_skill(
            invocation,
            lambda updated: seen.append(updated) or {"skill_name": updated.skill_name, "metadata": updated.metadata},
            skill_name_field="name",
            task_field="prompt",
            confidence_field="score",
            metadata_field="extras",
        )

        self.assertEqual(result["type"], "allow")
        self.assertEqual(seen[0].skill_name, "draft helpful reply")
        self.assertEqual(seen[0].metadata["channel"], "chat")

    def test_wrap_openai_tool_executor_hides_adapter_call(self):
        wrapped = wrap_openai_tool_executor(
            self.runtime,
            lambda updated: {"tool_name": updated.tool_name, "payload": updated.payload},
        )
        result = wrapped(
            {
                "task": "Answer order status questions for a customer",
                "tool_name": "draft helpful reply",
                "confidence": 0.93,
                "payload": {"channel": "email"},
            }
        )
        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["execution"]["result"]["tool_name"], "draft helpful reply")

    def test_wrap_claude_skill_executor_hides_adapter_call(self):
        @dataclass
        class NativeClaudeSkill:
            name: str
            prompt: str
            score: float
            extras: dict

        wrapped = wrap_claude_skill_executor(
            self.runtime,
            lambda updated: {"skill_name": updated.skill_name, "metadata": updated.metadata},
            skill_name_field="name",
            task_field="prompt",
            confidence_field="score",
            metadata_field="extras",
        )
        result = wrapped(
            NativeClaudeSkill(
                name="draft helpful reply",
                prompt="Answer order status questions for a customer",
                score=0.9,
                extras={"channel": "chat"},
            )
        )
        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["execution"]["result"]["skill_name"], "draft helpful reply")

    def test_wrap_openai_tools_builds_named_wrapped_tool_registry(self):
        tools = [
            {
                "tool_name": "draft helpful reply",
                "executor": lambda updated: {"tool_name": updated.tool_name, "payload": updated.payload},
            }
        ]
        wrapped_tools = wrap_openai_tools(self.runtime, tools)

        result = wrapped_tools["draft helpful reply"](
            {
                "task": "Answer order status questions for a customer",
                "tool_name": "draft helpful reply",
                "confidence": 0.92,
                "payload": {"channel": "email"},
            }
        )

        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["execution"]["result"]["tool_name"], "draft helpful reply")

    def test_wrap_claude_skills_builds_named_wrapped_skill_registry(self):
        @dataclass
        class NativeSkillDefinition:
            name: str
            handler: object

        skills = [
            NativeSkillDefinition(
                name="draft helpful reply",
                handler=lambda updated: {"skill_name": updated.skill_name, "metadata": updated.metadata},
            )
        ]
        wrapped_skills = wrap_claude_skills(
            self.runtime,
            skills,
            executor_field="handler",
            skill_name_field="name",
            task_field="prompt",
            confidence_field="score",
            metadata_field="extras",
        )

        @dataclass
        class NativeClaudeSkill:
            name: str
            prompt: str
            score: float
            extras: dict

        result = wrapped_skills["draft helpful reply"](
            NativeClaudeSkill(
                name="draft helpful reply",
                prompt="Answer order status questions for a customer",
                score=0.9,
                extras={"channel": "chat"},
            )
        )

        self.assertEqual(result["type"], "allow")
        self.assertEqual(result["execution"]["result"]["skill_name"], "draft helpful reply")

    def test_crewai_adapter_accepts_plain_dict(self):
        adapter = CrewAIPawAdapter(self.runtime)
        seen = []
        result = adapter.execute_native_task(
            {
                "task": "Answer order status questions for a customer",
                "action": "draft helpful reply",
                "confidence": 0.88,
                "payload": {"channel": "email"},
            },
            lambda updated: seen.append(updated) or {"action": updated.action, "payload": updated.payload},
        )
        self.assertEqual(result["type"], "allow")
        self.assertEqual(seen[0].action, "draft helpful reply")

    def test_langgraph_adapter_accepts_object(self):
        @dataclass
        class NativeTransition:
            from_node: str
            to_node: str
            task: str
            confidence: float
            metadata: dict

        adapter = LangGraphPawAdapter(self.runtime)
        seen = []
        result = adapter.execute_native_transition(
            NativeTransition(
                from_node="classify",
                to_node="reply",
                task="Answer order status questions for a customer",
                confidence=0.9,
                metadata={"channel": "chat"},
            ),
            lambda updated: seen.append(updated) or {"to_node": updated.to_node, "metadata": updated.metadata},
        )
        self.assertEqual(result["type"], "allow")
        self.assertEqual(seen[0].to_node, "reply")

    def test_openclaw_adapter_accepts_plain_dict(self):
        adapter = OpenClawPawAdapter(self.runtime)
        seen = []
        result = adapter.execute_native_tool(
            {
                "task": "Answer order status questions for a customer",
                "action": "draft helpful reply",
                "confidence": 0.87,
                "metadata": {"channel": "chat"},
            },
            lambda updated: seen.append(updated) or {"action": updated.action, "metadata": updated.metadata},
        )
        self.assertEqual(result["type"], "allow")
        self.assertEqual(seen[0].action, "draft helpful reply")

    def test_http_self_hosted_adapter_builds_requests(self):
        adapter = SelfHostedHTTPAdapter(
            SelfHostedWorkerConfig(
                invoke_url="https://worker.example/invoke",
                healthcheck_url="https://worker.example/health",
                auth_token="secret-token",
            )
        )
        invoke = adapter.build_native_invoke_request(
            {
                "task": "Answer order status questions for a customer",
                "action": "draft helpful reply",
                "confidence": 0.9,
                "metadata": {"channel": "email"},
            }
        )
        self.assertEqual(invoke["url"], "https://worker.example/invoke")
        self.assertEqual(invoke["headers"]["Authorization"], "Bearer secret-token")
        health = adapter.build_healthcheck_request()
        self.assertEqual(health["url"], "https://worker.example/health")

    def test_framework_wrappers_hide_new_adapter_calls(self):
        crew_wrapped = wrap_crewai_task_executor(
            self.runtime,
            lambda updated: {"action": updated.action, "payload": updated.payload},
        )
        crew_result = crew_wrapped(
            {
                "task": "Answer order status questions for a customer",
                "action": "draft helpful reply",
                "confidence": 0.9,
                "payload": {"channel": "email"},
            }
        )
        self.assertEqual(crew_result["type"], "allow")

        langgraph_wrapped = wrap_langgraph_transition_executor(
            self.runtime,
            lambda updated: {"transition": f"{updated.from_node}->{updated.to_node}"},
        )
        langgraph_result = langgraph_wrapped(
            {
                "from_node": "classify",
                "to_node": "reply",
                "task": "Answer order status questions for a customer",
                "confidence": 0.9,
                "metadata": {"channel": "chat"},
            }
        )
        self.assertEqual(langgraph_result["type"], "allow")

        openclaw_wrapped = wrap_openclaw_tool_executor(
            self.runtime,
            lambda updated: {"action": updated.action},
        )
        openclaw_result = openclaw_wrapped(
            {
                "task": "Answer order status questions for a customer",
                "action": "draft helpful reply",
                "confidence": 0.9,
                "metadata": {"channel": "chat"},
            }
        )
        self.assertEqual(openclaw_result["type"], "allow")


if __name__ == "__main__":
    unittest.main()
