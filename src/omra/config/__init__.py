"""Layered, fail-fast application configuration."""

from omra.config.errors import (
    ConfigConflictError,
    ConfigError,
    ConfigSyntaxError,
    ConfigTypeConflict,
    ConfigValidationError,
    MissingSecrets,
    UnknownOverrideError,
    Violation,
)
from omra.config.layers import (
    LayeredMapping,
    LoadedLayer,
    Override,
    apply_overrides,
    deep_merge,
    load_layered_mapping,
    load_yaml_mapping,
    parse_env_overrides,
    parse_override_value,
    resolve_exec_env,
)
from omra.config.schema.run import ExecEnv, RunCfg
from omra.config.secrets import CATALOG, Secrets, SecretSpec, load_secrets
from omra.config.settings import AppConfig

__all__ = [
    "CATALOG",
    "AppConfig",
    "ConfigConflictError",
    "ConfigError",
    "ConfigSyntaxError",
    "ConfigTypeConflict",
    "ConfigValidationError",
    "ExecEnv",
    "LayeredMapping",
    "LoadedLayer",
    "MissingSecrets",
    "Override",
    "RunCfg",
    "SecretSpec",
    "Secrets",
    "UnknownOverrideError",
    "Violation",
    "apply_overrides",
    "deep_merge",
    "load_layered_mapping",
    "load_secrets",
    "load_yaml_mapping",
    "parse_env_overrides",
    "parse_override_value",
    "resolve_exec_env",
]
