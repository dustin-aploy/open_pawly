from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAWLY_SRC = REPO_ROOT / "src"
PAWPRINT_SRC = REPO_ROOT.parent / "pawprint" / "src"

for path in (PAWLY_SRC, PAWPRINT_SRC):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
