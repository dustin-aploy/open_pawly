from __future__ import annotations

import re
from pathlib import Path


class YAMLParseError(ValueError):
    """Raised when the lightweight YAML parser cannot parse a document."""


def load_yaml_file(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    return loads(text)


def loads(text: str):
    lines = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((number, indent, raw.strip()))
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0][1])
    if index != len(lines):
        raise YAMLParseError(f"Unexpected trailing content near line {lines[index][0]}")
    return value


def _parse_block(lines, index: int, indent: int):
    if index >= len(lines):
        return {}, index
    if lines[index][1] != indent:
        raise YAMLParseError(f"Unexpected indentation near line {lines[index][0]}")
    if lines[index][2].startswith("- "):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines, index: int, indent: int):
    mapping = {}
    while index < len(lines):
        line_no, line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise YAMLParseError(f"Unexpected indentation near line {line_no}")
        if text.startswith("- "):
            break
        key, has_value, remainder = _split_key_value(text, line_no)
        index += 1
        if has_value:
            mapping[key] = _parse_scalar(remainder)
            continue
        if index >= len(lines) or lines[index][1] <= indent:
            mapping[key] = {}
            continue
        child, index = _parse_block(lines, index, lines[index][1])
        mapping[key] = child
    return mapping, index


def _parse_sequence(lines, index: int, indent: int):
    items = []
    while index < len(lines):
        line_no, line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not text.startswith("- "):
            break
        content = text[2:].strip()
        index += 1
        if not content:
            if index >= len(lines) or lines[index][1] <= indent:
                items.append(None)
                continue
            child, index = _parse_block(lines, index, lines[index][1])
            items.append(child)
            continue
        if _looks_like_mapping(content):
            key, has_value, remainder = _split_key_value(content, line_no)
            item = {}
            if has_value:
                item[key] = _parse_scalar(remainder)
            else:
                item[key] = {}
            if index < len(lines) and lines[index][1] > indent:
                child, index = _parse_block(lines, index, lines[index][1])
                if not isinstance(child, dict):
                    raise YAMLParseError(f"List item near line {line_no} must contain a mapping")
                item.update(child)
            items.append(item)
            continue
        items.append(_parse_scalar(content))
    return items, index


def _split_key_value(text: str, line_no: int):
    if ":" not in text:
        raise YAMLParseError(f"Expected ':' in mapping near line {line_no}")
    key, remainder = text.split(":", 1)
    key = key.strip()
    if not key:
        raise YAMLParseError(f"Empty key near line {line_no}")
    remainder = remainder.strip()
    return key, bool(remainder), remainder


def _looks_like_mapping(text: str) -> bool:
    if text.startswith("[") or text.startswith("{"):
        return False
    return ":" in text


def _parse_scalar(value: str):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in _split_flow_items(inner)]
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", value):
        return float(value)
    return value


def _split_flow_items(text: str) -> list[str]:
    items = []
    current = []
    quote = None
    depth = 0
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        items.append("".join(current).strip())
    return items
