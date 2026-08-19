"""Fail-fast configuration errors with actionable source locations."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from omra.core.errors import OmraError


@dataclass(frozen=True, slots=True)
class Violation:
    """One configuration violation suitable for aggregated diagnostics."""

    code: str
    message: str
    path: str = "$"
    source: Path | None = None
    line: int | None = None
    column: int | None = None

    def render(self) -> str:
        """Render a deterministic, operator-facing diagnostic."""
        location = str(self.source) if self.source is not None else "<configuration>"
        if self.line is not None:
            location = f"{location}:{self.line}"
            if self.column is not None:
                location = f"{location}:{self.column}"
        return f"{location} [{self.code}] {self.path}: {self.message}"


class ConfigError(OmraError):
    """Base class for configuration failures that must stop startup."""


class ConfigSyntaxError(ConfigError):
    """A YAML document could not be parsed unambiguously."""

    def __init__(
        self,
        source: Path,
        detail: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.source = source
        self.detail = detail
        self.line = line
        self.column = column
        violation = Violation(
            code="yaml_syntax",
            message=detail,
            source=source,
            line=line,
            column=column,
        )
        super().__init__(violation.render())


class ConfigTypeConflict(ConfigError):  # noqa: N818 - canonical design error name
    """Two layers disagree whether a path is a mapping or a value."""

    def __init__(self, path: str, base_type: type[object], overlay_type: type[object]) -> None:
        self.path = path
        self.base_type = base_type
        self.overlay_type = overlay_type
        super().__init__(
            f"configuration structure conflict at {path}: "
            f"{base_type.__name__} cannot be overlaid by {overlay_type.__name__}"
        )


class ConfigValidationError(ConfigError):
    """One or more configuration documents violate their structural contract."""

    def __init__(self, violations: tuple[Violation, ...]) -> None:
        if not violations:
            msg = "ConfigValidationError requires at least one violation"
            raise ValueError(msg)
        self.violations = violations
        rendered = "\n".join(violation.render() for violation in violations)
        super().__init__(f"configuration validation failed ({len(violations)}):\n{rendered}")


class UnknownOverrideError(ConfigError):
    """An OMRA__ override names a path absent from the declared shape."""

    def __init__(self, path: tuple[str, ...], *, variable: str | None = None) -> None:
        self.path = path
        self.variable = variable
        dotted = ".".join(path) if path else "<empty>"
        origin = f" ({variable})" if variable is not None else ""
        super().__init__(f"unknown configuration override {dotted}{origin}")


class ConfigConflictError(ConfigError):
    """Two explicit configuration declarations are mutually inconsistent."""


class MissingSecrets(ConfigError):  # noqa: N818 - canonical design error name
    """Required environment-only secret names are absent."""

    def __init__(self, names: Iterable[str]) -> None:
        self.names = tuple(sorted(set(names)))
        if not self.names:
            raise ValueError("MissingSecrets requires at least one secret name")
        super().__init__(
            f"required secrets are missing: {', '.join(self.names)}",
            code="config.secrets_missing",
        )


class UnsupportedInEnvError(ConfigError):
    """Unresolved configuration values are unsafe in the requested environment."""

    def __init__(self, env: str, paths: Iterable[str]) -> None:
        self.env = env
        self.paths = tuple(dict.fromkeys(paths))
        if not self.paths:
            raise ValueError("UnsupportedInEnvError requires at least one path")
        super().__init__(
            f"unresolved configuration is unsupported in {env}: {', '.join(self.paths)}",
            code="config.unsupported_in_env",
        )


class EffectiveVersionMissing(ConfigError):  # noqa: N818 - canonical design error name
    """No configuration value is effective on the requested KST date."""

    def __init__(self, kst_date: date, available_from: Iterable[date]) -> None:
        self.kst_date = kst_date
        self.available_from = tuple(sorted(set(available_from)))
        rendered = ", ".join(day.isoformat() for day in self.available_from) or "<none>"
        super().__init__(
            f"no effective configuration version for {kst_date.isoformat()} "
            f"(available effective_from: {rendered})",
            code="config.effective_version_missing",
        )
