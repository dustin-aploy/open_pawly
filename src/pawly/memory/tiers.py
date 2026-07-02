from __future__ import annotations

from enum import Enum


class MemoryTier(str, Enum):
    NONE = "none"
    SESSION_ONLY = "session-only"
    BOUNDED_PERSISTENT = "bounded-persistent"
