"""Public adapter helpers for rapid framework integration."""

from .claude_skills import (
    ClaudeSkillInvocation,
    ClaudeSkillsPawAdapter,
    wrap_claude_skill_executor,
    wrap_claude_skills,
)
from .openai_agents import (
    OpenAIAgentAction,
    OpenAIAgentsPawAdapter,
    wrap_openai_tool_executor,
    wrap_openai_tools,
)

__all__ = [
    "ClaudeSkillInvocation",
    "ClaudeSkillsPawAdapter",
    "OpenAIAgentAction",
    "OpenAIAgentsPawAdapter",
    "wrap_claude_skill_executor",
    "wrap_claude_skills",
    "wrap_openai_tool_executor",
    "wrap_openai_tools",
]
