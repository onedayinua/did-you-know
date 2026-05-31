"""YAML config loader with ${ENV_VAR} substitution and caching."""

import os
import re
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_CACHE: dict[str, dict] = {}
_CONFIG_DIR = Path(__file__).parent.parent / "config"

# Match ${VAR_NAME} or ${VAR_NAME:default_value}
_ENV_VAR_PATTERN = re.compile(r'\$\{([^}:]+)(?::([^}]*))?\}')


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} and ${VAR_NAME:default} patterns with env var values.

    If the env var is not found and no default is provided, leaves the pattern
    as-is and logs a WARNING.
    """
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        logger.warning("Environment variable %s not found; keeping literal", var_name)
        return match.group(0)

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _substitute_recursively(obj: Any) -> Any:
    """Walk a nested structure and substitute env vars in all string values."""
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: _substitute_recursively(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_recursively(item) for item in obj]
    return obj


def load_config(name: str) -> dict[str, Any]:
    """Load a YAML config file by name (without .yaml extension).

    Args:
        name: Config name (e.g. "platforms" loads config/platforms.yaml).

    Returns:
        Parsed YAML content with env vars substituted.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the YAML content is malformed.
    """
    if name in _CONFIG_CACHE:
        return _CONFIG_CACHE[name]

    config_path = _CONFIG_DIR / f"{name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info("Loading config from %s", config_path)
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    # Handle empty or comment-only YAML files
    if data is None:
        data = {}

    result = _substitute_recursively(data)
    _CONFIG_CACHE[name] = result
    return result


def get_content_template() -> dict[str, Any]:
    """Shortcut for load_config('content_template')."""
    return load_config("content_template")


def get_platforms_config() -> dict[str, Any]:
    """Shortcut for load_config('platforms')."""
    return load_config("platforms")


def get_backup_trends() -> dict[str, Any]:
    """Shortcut for load_config('backup_trends')."""
    return load_config("backup_trends")


def clear_cache() -> None:
    """Clear the config cache (useful in tests)."""
    _CONFIG_CACHE.clear()