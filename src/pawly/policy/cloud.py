"""Compatibility shim for the optional external pawly-cloud package."""

from __future__ import annotations

from importlib import import_module


def __getattr__(name: str):
    if name != "CloudPolicy":
        raise AttributeError(name)
    try:
        module = import_module("pawly_cloud")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "CloudPolicy moved to the optional sibling package 'pawly-cloud'. "
            "Install or add 'pawly-cloud' and import CloudPolicy from 'pawly_cloud'. "
            "If you need a managed project key, create one at https://developer.aploy.ai/pawly."
        ) from exc
    return getattr(module, "CloudPolicy")
