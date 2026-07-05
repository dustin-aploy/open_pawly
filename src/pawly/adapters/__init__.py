"""Public adapter helpers for rapid framework integration."""

from .claude_skills import (
    ClaudeSkillInvocation,
    ClaudeSkillsPawAdapter,
    wrap_claude_skill_executor,
    wrap_claude_skills,
)
from .crewai import CrewAIPawAdapter, CrewTaskAction, wrap_crewai_task_executor, wrap_crewai_tasks
from .http_self_hosted import InvokeRequest, SelfHostedHTTPAdapter, SelfHostedWorkerConfig
from .langgraph import GraphTransition, LangGraphPawAdapter, wrap_langgraph_transition_executor, wrap_langgraph_transitions
from .openclaw import OpenClawActionContext, OpenClawPawAdapter, wrap_openclaw_tool_executor, wrap_openclaw_tools
from .openai_agents import (
    OpenAIAgentAction,
    OpenAIAgentsPawAdapter,
    wrap_openai_tool_executor,
    wrap_openai_tools,
)

__all__ = [
    "ClaudeSkillInvocation",
    "ClaudeSkillsPawAdapter",
    "CrewAIPawAdapter",
    "CrewTaskAction",
    "GraphTransition",
    "InvokeRequest",
    "LangGraphPawAdapter",
    "OpenClawActionContext",
    "OpenClawPawAdapter",
    "OpenAIAgentAction",
    "OpenAIAgentsPawAdapter",
    "SelfHostedHTTPAdapter",
    "SelfHostedWorkerConfig",
    "wrap_claude_skill_executor",
    "wrap_claude_skills",
    "wrap_crewai_task_executor",
    "wrap_crewai_tasks",
    "wrap_langgraph_transition_executor",
    "wrap_langgraph_transitions",
    "wrap_openclaw_tool_executor",
    "wrap_openclaw_tools",
    "wrap_openai_tool_executor",
    "wrap_openai_tools",
]
