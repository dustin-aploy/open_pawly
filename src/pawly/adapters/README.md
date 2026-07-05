# Pawly Public Adapters

`pawly.adapters` is the single public adapter surface for framework and transport wrappers.

Use these modules when you need to insert Pawly checks at an execution boundary without
rewriting the host runtime:

- `openai_agents.py`
- `claude_skills.py`
- `crewai.py`
- `langgraph.py`
- `openclaw.py`
- `http_self_hosted.py`

These adapters should stay thin:

- wrap an existing execution boundary
- translate native objects or dicts into Pawly action context
- reuse the gateway/runtime logic instead of redefining policy behavior
- avoid maintaining a second adapter implementation outside `src/pawly/adapters`

If you are importing Pawly as a package, prefer these public exports:

- `pawly.OpenAIAgentsPawAdapter`
- `pawly.ClaudeSkillsPawAdapter`
- `pawly.CrewAIPawAdapter`
- `pawly.LangGraphPawAdapter`
- `pawly.OpenClawPawAdapter`
- `pawly.SelfHostedHTTPAdapter`
