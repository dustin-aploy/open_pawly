#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
PARENT_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

if [ -d "${PARENT_DIR}/pawprint" ]; then
  python -m pip install --no-build-isolation --no-deps -e "${PARENT_DIR}/pawprint"
fi
python -m pip install --no-build-isolation --no-deps -e .

echo "[pawly] bootstrap complete"
