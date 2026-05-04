"""Project-Config Security — Deny sensitive keys at workspace scope.

Inspired by DeepSeek-TUI's project-config security. Prevents malicious
workspace-local config files from overriding api_key, base_url, provider,
and dangerous settings like approval_policy=auto or sandbox_mode=full-access.

Usage:
    safe_config = sanitize_project_config(raw_config)
"""

from __future__ import annotations

from typing import Any

from loguru import logger


DENIED_KEYS = {
    "api_key",
    "base_url",
    "provider",
    "deepseek_api_key",
    "api_base",
    "mcp_config_path",
}

LOOSE_DENIED_VALUES = {
    "approval_policy": ("auto", "yolo"),
    "sandbox_mode": ("danger-full-access", "danger_full_access"),
}


def sanitize_project_config(config: dict[str, Any], source: str = "project") -> dict[str, Any]:
    """Remove sensitive keys from a project-scoped config dict.

    Project-local configs (.livingtree/config.toml) should never be
    able to override sensitive credentials or dangerous security settings.
    Keys like api_key, base_url, and provider are always denied at
    the workspace/project scope.

    Args:
        config: Raw config dict from project .livingtree/config.toml
        source: Config source identifier for logging

    Returns:
        Sanitized config dict with sensitive keys removed
    """
    sanitized = {}
    removed = []

    for key, value in config.items():
        if key in DENIED_KEYS:
            removed.append(key)
            continue

        if key in LOOSE_DENIED_VALUES:
            denied_vals = LOOSE_DENIED_VALUES[key]
            if value in denied_vals:
                removed.append(f"{key}={value}")
                continue

        if isinstance(value, dict):
            sanitized[key] = sanitize_project_config(value, f"{source}.{key}")
        else:
            sanitized[key] = value

    if removed:
        logger.warning(
            f"Project-config security: denied {len(removed)} sensitive key(s) "
            f"from source '{source}': {removed}"
        )

    return sanitized


def validate_project_config(config: dict[str, Any]) -> bool:
    """Check if project config contains denied keys. Returns True if safe."""
    for key in DENIED_KEYS:
        if key in config:
            return False
    for key, banned_values in LOOSE_DENIED_VALUES.items():
        if key in config and config[key] in banned_values:
            return False
    return True


def is_safe_config_key(key: str, value: Any = None) -> bool:
    """Check if a single config key/value pair is safe for project scope."""
    if key in DENIED_KEYS:
        return False
    if key in LOOSE_DENIED_VALUES and value in LOOSE_DENIED_VALUES[key]:
        return False
    return True
