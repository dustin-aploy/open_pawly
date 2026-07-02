from __future__ import annotations

import re

KEYWORD_ALIASES = {
    "pricing": {"pricing", "price", "discount", "quote"},
    "contract": {"contract", "agreement", "terms"},
    "refund": {"refund", "credit", "chargeback"},
    "security": {"security", "breach", "fraud", "compromise"},
    "legal": {"legal", "lawsuit", "attorney"},
    "fairness": {"fairness", "bias", "discrimination", "accommodation"},
}


def normalize_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    for canonical, aliases in KEYWORD_ALIASES.items():
        if tokens & aliases:
            expanded.add(canonical)
            expanded.update(aliases)
    return expanded


def text_matches_rule(text: str, rule_text: str) -> bool:
    text_tokens = normalize_tokens(text)
    rule_tokens = normalize_tokens(rule_text)
    if not rule_tokens:
        return False
    if rule_text.lower() in text.lower():
        return True
    overlap = text_tokens & rule_tokens
    return len(overlap) >= max(1, min(2, len(rule_tokens) // 2 or 1))
