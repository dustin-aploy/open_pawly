import unittest
from dataclasses import dataclass
from pathlib import Path

from pawly import (
    ClaudeSkillsPawAdapter,
    OpenAIAgentsPawAdapter,
    PawlyRuntime,
    wrap_claude_skill_executor,
    wrap_claude_skills,
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


if __name__ == "__main__":
    unittest.main()
