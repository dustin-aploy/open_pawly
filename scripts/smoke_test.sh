#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

./scripts/bootstrap.sh
python - <<'INNERPY'
from pathlib import Path
from pawly.loader.yaml_loader import load_yaml_file
from pawly.validator.validator import PawprintValidator
path = Path('examples/agents/basic_worker.yaml')
result = PawprintValidator().validate_agent_config(load_yaml_file(path))
if not result.valid:
    raise SystemExit('\n'.join(result.errors))
print(f'validated {path}')
INNERPY
python examples/basic_usage.py
python -m pytest tests

echo "[pawly] smoke test complete"
