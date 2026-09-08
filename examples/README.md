# Open Pawly Examples

All examples in this directory are **[OSS Examples]**. They run locally and do
not require a Pawly Cloud account, Hosted Auth, Credential Vault, Cloud Skill
Discovery, Cloud Skill Selection, or Progressive Disclosure.

- `goal_first_support_agent.py`: recommended agent-runtime flow. The agent
  returns a structured plan, and `pawly.achieve(**plan)` is the only execution
  path.
- `basic_usage.py`: same `objective/context/constraints` contract without an
  agent runtime, useful for deterministic business logic or background jobs.
- `adapter_integration_basic.py`: wrapping existing OpenAI or Claude tool/skill
  definitions so they can be registered behind Pawly.
- `execution_gateway_demo.py`: advanced migration example for protecting an
  already-selected action.
- `run_actions_basic.py`: candidate-action routing example for adapter authors
  maintainers, not the normal application integration.
- `agents/`: example Pawprint declarations.
