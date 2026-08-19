"""Layered, fail-fast application configuration."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from omra.config.constraints import ConstraintSeverity, ConstraintViolation, check_all
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
    validation_violations,
)
from omra.config.files import (
    ExternalIncomeFile,
    ExternalSchedulesFile,
    GoalsFile,
    MarketWeightsFile,
    OpenQuestionsFile,
    RecordFile,
    SecretsRegistryFile,
    SurveillanceMapFile,
    TargetsFile,
    TaxLawFile,
    TaxParams,
    TrIdsRaw,
    UniverseFile,
    validate_tr_ids_for_env,
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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

    from omra.core import Clock


@dataclass(frozen=True, slots=True)
class LoadedSource:
    """One exact YAML source that participated in a configuration bundle."""

    kind: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class ConfigBundle:
    """Validated scalar and record inputs for one deterministic startup."""

    app: AppConfig
    universe: UniverseFile
    targets: TargetsFile | None
    goals: GoalsFile
    weights: MarketWeightsFile
    schedules: ExternalSchedulesFile
    income: ExternalIncomeFile
    surv_map: SurveillanceMapFile
    tax: VersionedFile[TaxParams]
    registry: SecretsRegistryFile
    trids: TrIdsRaw
    questions: OpenQuestionsFile
    sources: tuple[LoadedSource, ...]
    fingerprint: ConfigFingerprint


def _config_error_violations(  # noqa: PLR0911 - explicit exception-to-violation table
    error: ConfigError,
    *,
    source: Path | None = None,
) -> tuple[Violation, ...]:
    if isinstance(error, ConfigValidationError):
        return error.violations
    if isinstance(error, ConfigSyntaxError):
        return (
            Violation(
                code="yaml_syntax",
                message=error.detail,
                source=error.source,
                line=error.line,
                column=error.column,
            ),
        )
    if isinstance(error, UnsupportedInEnvError):
        return tuple(
            Violation(
                code="unsupported_in_env",
                message=f"unresolved value is unsupported in {error.env}",
                path=path,
                source=source,
            )
            for path in error.paths
        )
    if isinstance(error, EffectiveVersionMissing):
        return (
            Violation(
                code="effective_version_missing",
                message=str(error),
                path="versions",
                source=source,
            ),
        )
    if isinstance(error, ConfigTypeConflict):
        return (
            Violation(
                code="type_conflict",
                message=str(error),
                path=error.path,
                source=source,
            ),
        )
    if isinstance(error, UnknownOverrideError):
        return (
            Violation(
                code="unknown_override",
                message=str(error),
                path=".".join(error.path) or "$",
                source=source,
            ),
        )
    if isinstance(error, ConfigConflictError):
        return (Violation(code="config_conflict", message=str(error), source=source),)
    return (Violation(code="config_error", message=str(error), source=source),)


class _KnownShapeConfig(AppConfig):
    """Validate defaults for override shape discovery without ambient sources."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del cls, settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


def _known_app_shape() -> Mapping[str, object]:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {"absolute_floor": {}}}
    return _KnownShapeConfig.model_validate(values).model_dump(mode="python")


def _load_record[RecordT: BaseModel](
    path: Path,
    model: type[RecordT],
    violations: list[Violation],
    sources: list[LoadedSource],
    *,
    required: bool = True,
) -> RecordT | None:
    try:
        loaded = RecordFile.load(path, model, required=required)
    except ConfigError as error:
        violations.extend(_config_error_violations(error, source=path))
        return None
    if loaded is None:
        return None
    sources.append(LoadedSource(kind="record", path=loaded.path, sha256=f"sha256:{loaded.sha256}"))
    return loaded.data


def load_and_validate_config(  # noqa: PLR0915 - canonical multi-source orchestration
    config_dir: Path = Path("/app/config"),
    *,
    cli_overrides: Mapping[str, object] | None = None,
    clock: Clock,
) -> ConfigBundle:
    """Load the config-only startup bundle and aggregate independent failures."""
    violations: list[Violation] = []
    record_sources: list[LoadedSource] = []

    layered = None
    app = None
    try:
        layered = load_layered_mapping(
            config_dir,
            cli_overrides=cli_overrides,
            known_shape=_known_app_shape(),
        )
    except ConfigError as error:
        violations.extend(_config_error_violations(error))
    else:
        try:
            app = AppConfig.model_validate(layered.values)
        except ValidationError as error:
            violations.extend(validation_violations(error))

    universe = _load_record(config_dir / "universe.yaml", UniverseFile, violations, record_sources)
    targets = _load_record(
        config_dir / "targets.yaml",
        TargetsFile,
        violations,
        record_sources,
        required=False,
    )
    goals = _load_record(config_dir / "goals.yaml", GoalsFile, violations, record_sources)
    weights = _load_record(
        config_dir / "market_weights.yaml", MarketWeightsFile, violations, record_sources
    )
    schedules = _load_record(
        config_dir / "external_schedules.yaml",
        ExternalSchedulesFile,
        violations,
        record_sources,
    )
    income = _load_record(
        config_dir / "external_income.yaml",
        ExternalIncomeFile,
        violations,
        record_sources,
    )
    surv_map = _load_record(
        config_dir / "surveillance.yaml",
        SurveillanceMapFile,
        violations,
        record_sources,
    )
    tax_file = _load_record(config_dir / "tax.yaml", TaxLawFile, violations, record_sources)
    registry = _load_record(
        config_dir / "secrets_registry.yaml",
        SecretsRegistryFile,
        violations,
        record_sources,
    )
    trids = _load_record(config_dir / "tr_ids.kis.yaml", TrIdsRaw, violations, record_sources)
    questions_file = _load_record(
        config_dir / "research_open_questions.yaml",
        OpenQuestionsFile,
        violations,
        record_sources,
        required=False,
    )

    tax = None if tax_file is None else tax_file.to_versioned()
    if tax is not None:
        try:
            tax.at(clock.now_kst().date())
        except ConfigError as error:
            violations.extend(_config_error_violations(error, source=config_dir / "tax.yaml"))

    if trids is not None and layered is not None:
        try:
            validate_tr_ids_for_env(trids, layered.env)
        except ConfigError as error:
            violations.extend(
                _config_error_violations(error, source=config_dir / "tr_ids.kis.yaml")
            )

    if violations:
        raise ConfigValidationError(tuple(violations))

    assert layered is not None
    assert app is not None
    assert universe is not None
    assert goals is not None
    assert weights is not None
    assert schedules is not None
    assert income is not None
    assert surv_map is not None
    assert tax is not None
    assert registry is not None
    assert trids is not None

    try:
        fingerprint = config_fingerprint(config_dir, app=app)
    except ConfigError as error:
        raise ConfigValidationError(_config_error_violations(error)) from error

    layer_sources = tuple(
        LoadedSource(
            kind=layer.kind,
            path=layer.path,
            sha256=fingerprint.files[f"config/{layer.path.name}"],
        )
        for layer in layered.sources
    )
    questions = questions_file or OpenQuestionsFile(version=1, questions=())
    bundle = ConfigBundle(
        app=app,
        universe=universe,
        targets=targets,
        goals=goals,
        weights=weights,
        schedules=schedules,
        income=income,
        surv_map=surv_map,
        tax=tax,
        registry=registry,
        trids=trids,
        questions=questions,
        sources=(*layer_sources, *record_sources),
        fingerprint=fingerprint,
    )
    constraint_violations = check_all(bundle)
    constraint_errors = tuple(
        violation.as_config_violation()
        for violation in constraint_violations
        if violation.severity is ConstraintSeverity.ERROR
    )
    for violation in constraint_violations:
        if violation.severity is ConstraintSeverity.WARNING:
            warnings.warn(violation.render(), RuntimeWarning, stacklevel=2)
    if constraint_errors:
        raise ConfigValidationError(constraint_errors)
    return bundle


__all__ = [
    "CATALOG",
    "AppConfig",
    "ConfigBundle",
    "ConfigConflictError",
    "ConfigError",
    "ConfigFingerprint",
    "ConfigSyntaxError",
    "ConfigTypeConflict",
    "ConfigValidationError",
    "ConstraintSeverity",
    "ConstraintViolation",
    "CredentialSurface",
    "EffectiveVersionMissing",
    "ExecEnv",
    "LayeredMapping",
    "LoadedLayer",
    "LoadedSource",
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
    "check_all",
    "check_credential_placement",
    "config_fingerprint",
    "deep_merge",
    "has_smtp",
    "has_telegram",
    "load_and_validate_config",
    "load_layered_mapping",
    "load_secrets",
    "load_yaml_mapping",
    "parse_env_overrides",
    "parse_override_value",
    "resolve_exec_env",
]
