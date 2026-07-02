from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pawly import (
    PawlyRuntime,
    wrap_claude_skill_executor,
    wrap_claude_skills,
    wrap_openai_tool_executor,
    wrap_openai_tools,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    runtime = PawlyRuntime(REPO_ROOT / "examples" / "agents" / "basic_worker.yaml")

    wrapped_openai_tool = wrap_openai_tool_executor(
        runtime,
        lambda updated: {
            "tool_name": updated.tool_name,
            "task": updated.task,
            "payload": updated.payload,
        },
    )
    openai_call = {
        "task": "Answer order status questions for a customer",
        "tool_name": "draft helpful reply",
        "confidence": 0.94,
        "payload": {"channel": "email"},
    }
    openai_result = wrapped_openai_tool(openai_call)

    wrapped_openai_tools = wrap_openai_tools(
        runtime,
        [
            {
                "tool_name": "draft helpful reply",
                "executor": lambda updated: {
                    "tool_name": updated.tool_name,
                    "task": updated.task,
                    "payload": updated.payload,
                },
            }
        ],
    )
    openai_batch_result = wrapped_openai_tools["draft helpful reply"](openai_call)

    @dataclass
    class NativeClaudeSkill:
        name: str
        prompt: str
        score: float
        extras: dict

    wrapped_claude_skill = wrap_claude_skill_executor(
        runtime,
        lambda updated: {
            "skill_name": updated.skill_name,
            "task": updated.task,
            "metadata": updated.metadata,
        },
        skill_name_field="name",
        task_field="prompt",
        confidence_field="score",
        metadata_field="extras",
    )
    claude_call = NativeClaudeSkill(
        name="draft helpful reply",
        prompt="Answer order status questions for a customer",
        score=0.91,
        extras={"channel": "chat"},
    )
    claude_result = wrapped_claude_skill(claude_call)

    @dataclass
    class NativeClaudeSkillDefinition:
        name: str
        handler: object

    wrapped_claude_skills = wrap_claude_skills(
        runtime,
        [
            NativeClaudeSkillDefinition(
                name="draft helpful reply",
                handler=lambda updated: {
                    "skill_name": updated.skill_name,
                    "task": updated.task,
                    "metadata": updated.metadata,
                },
            )
        ],
        executor_field="handler",
        skill_name_field="name",
        task_field="prompt",
        confidence_field="score",
        metadata_field="extras",
    )
    claude_batch_result = wrapped_claude_skills["draft helpful reply"](claude_call)

    print(
        json.dumps(
            {
                "openai_wrapped_tool_registry": openai_batch_result,
                "openai_native_tool_call": openai_result,
                "claude_wrapped_skill_registry": claude_batch_result,
                "claude_native_skill_call": claude_result,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
