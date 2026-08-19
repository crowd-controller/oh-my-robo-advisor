"""Layered, fail-fast application configuration."""

from omra.config.errors import (
    ConfigConflictError,
    ConfigError,
    ConfigSyntaxError,
    ConfigTypeConflict,
    ConfigValidationError,
    EffectiveVersionMissing,
    MissingSecrets,
    UnknownOverrideError,
    UnsupportedInEnvError,
    Violation,
)
from omra.config.fingerprint import ConfigFingerprint, config_fingerprint
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
from omra.config.secrets import (
    CATALOG,
    CredentialSurface,
    Secrets,
    SecretSpec,
    SecretSurface,
    check_credential_placement,
    has_smtp,
    has_telegram,
    load_secrets,
)
from omra.config.settings import AppConfig
from omra.config.versioned import VersionedFile

__all__ = [
    "CATALOG",
    "AppConfig",
    "ConfigConflictError",
    "ConfigError",
    "ConfigFingerprint",
    "ConfigSyntaxError",
    "ConfigTypeConflict",
    "ConfigValidationError",
    "CredentialSurface",
    "EffectiveVersionMissing",
    "ExecEnv",
    "LayeredMapping",
    "LoadedLayer",
    "MissingSecrets",
    "Override",
    "RunCfg",
    "SecretSpec",
    "SecretSurface",
    "Secrets",
    "UnknownOverrideError",
    "UnsupportedInEnvError",
    "VersionedFile",
    "Violation",
    "apply_overrides",
    "check_credential_placement",
    "config_fingerprint",
    "deep_merge",
    "has_smtp",
    "has_telegram",
    "load_layered_mapping",
    "load_secrets",
    "load_yaml_mapping",
    "parse_env_overrides",
    "parse_override_value",
    "resolve_exec_env",
]
