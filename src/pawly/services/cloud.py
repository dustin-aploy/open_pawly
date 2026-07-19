from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_CLOUD_CONSOLE_URL = "https://developer.aploy.ai/pawly"
DEFAULT_CLOUD_API_URL = "https://api.aploy.ai"


@dataclass(slots=True)
class CloudConnection:
    """Hosted connection identified by a single project-scoped API key."""

    api_key: str | None = None
    api_url: str = DEFAULT_CLOUD_API_URL
    console_url: str = DEFAULT_CLOUD_CONSOLE_URL

    def is_configured(self) -> bool:
        return bool(str(self.api_key or "").strip())

    def to_dict(self, *, include_secret: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "hosted",
            "api_url": self.api_url.rstrip("/"),
            "console_url": self.console_url.rstrip("/"),
            "api_key_configured": self.is_configured(),
        }
        if include_secret and self.api_key:
            payload["api_key"] = self.api_key
        return payload
