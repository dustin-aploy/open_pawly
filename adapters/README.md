# Paw Adapters

`pawly/adapters` contains thin integration guidance for mapping external frameworks and environments onto Aploy Pawly.

These adapters are execution-boundary wrappers. They are not planner rewrites and they are not alternate host runtimes.

Adapters must:
- depend on the Pawprint contract from [`pawprint`](https://github.com/dustin-aploy/pawprint)
- align with reference behavior from the `pawly` runtime when useful
- avoid redefining the public Pawprint shape or turning the workspace into a framework monolith

They should wrap existing execution boundaries, not replace host planning logic.

This area currently contains:
- framework-specific wrapper stubs under subdirectories such as `openai-agents/`, `langgraph/`, `crewai/`, `openclaw/`, and `claude-skills/`
- shared adapter notes under `common/`
- a minimal self-hosted HTTP example under `http-self-hosted/`

For developers using the packaged `pawly` runtime directly, prefer the built-in public adapter API instead of hand-building `Action` objects:

- `pawly.OpenAIAgentsPawAdapter`
- `pawly.ClaudeSkillsPawAdapter`
- `pawly.wrap_openai_tool_executor(...)`
- `pawly.wrap_claude_skill_executor(...)`
- `pawly.wrap_openai_tools(...)`
- `pawly.wrap_claude_skills(...)`

These adapters can accept plain `dict` values or native objects and extract `task`, `skill/tool name`, `confidence`, and `metadata` internally.

Use the single-item wrappers when you already have one executor to govern. Use the batch wrappers when you want to register a whole set of existing tools or skills in one call and get back a name-to-wrapper registry.
