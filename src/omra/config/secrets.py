"""Environment-only secret catalog and safe value loader."""

import stat
import sys
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from omra.config.errors import ConfigError, MissingSecrets
from omra.config.files.secrets_registry import SecretTier
from omra.config.schema.run import ExecEnv


@dataclass(frozen=True, slots=True)
class SecretSpec:
    """Placement and lifecycle metadata for one environment variable."""

    name: str
    required_in: frozenset[ExecEnv]
    surface: Literal["app", "litestream", "tools"]
    tier: SecretTier
    registry_tracked: bool


CATALOG: Final[tuple[SecretSpec, ...]] = (
    SecretSpec("KIS_APP_KEY", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER1, True),
    SecretSpec("KIS_APP_SECRET", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER1, True),
    SecretSpec("KIS_PAPER_APP_KEY", frozenset({ExecEnv.PAPER}), "app", SecretTier.TIER2, True),
    SecretSpec(
        "KIS_PAPER_APP_SECRET",
        frozenset({ExecEnv.PAPER}),
        "app",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec(
        "KIS_ACCOUNT_NO",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER1,
        False,
    ),
    SecretSpec(
        "KIS_HTS_ID",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec("UPBIT_ACCESS", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER1, True),
    SecretSpec("UPBIT_SECRET", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER1, True),
    SecretSpec(
        "TELEGRAM_BOT_TOKEN",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec(
        "TELEGRAM_CHAT_ID",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER2,
        False,
    ),
    SecretSpec("SMTP_HOST", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER2, False),
    SecretSpec("SMTP_PORT", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER2, False),
    SecretSpec("SMTP_USER", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER2, False),
    SecretSpec("SMTP_PASS", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER2, True),
    SecretSpec(
        "DEADMAN_WEBHOOK_URL",
        frozenset({ExecEnv.LIVE}),
        "app",
        SecretTier.TIER2,
        False,
    ),
    SecretSpec(
        "WEB_SESSION_SECRET",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER3,
        True,
    ),
    SecretSpec(
        "WEB_ADMIN_PASSWORD_HASH",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER3,
        True,
    ),
    SecretSpec(
        "SAFETY_CODE_SECRET",
        frozenset({ExecEnv.LIVE, ExecEnv.PAPER}),
        "app",
        SecretTier.TIER3,
        True,
    ),
    SecretSpec(
        "LITESTREAM_BUCKET",
        frozenset({ExecEnv.LIVE}),
        "litestream",
        SecretTier.TIER2,
        False,
    ),
    SecretSpec(
        "LITESTREAM_ACCESS_KEY_ID",
        frozenset({ExecEnv.LIVE}),
        "litestream",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec(
        "LITESTREAM_SECRET_ACCESS_KEY",
        frozenset({ExecEnv.LIVE}),
        "litestream",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec(
        "RESTIC_REPOSITORY",
        frozenset({ExecEnv.LIVE}),
        "app",
        SecretTier.TIER2,
        False,
    ),
    SecretSpec("RESTIC_PASSWORD", frozenset({ExecEnv.LIVE}), "app", SecretTier.TIER2, True),
    SecretSpec(
        "RESTIC_ACCESS_KEY_ID",
        frozenset({ExecEnv.LIVE}),
        "app",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec(
        "RESTIC_SECRET_ACCESS_KEY",
        frozenset({ExecEnv.LIVE}),
        "app",
        SecretTier.TIER2,
        True,
    ),
    SecretSpec("ANTHROPIC_API_KEY", frozenset(), "app", SecretTier.TIER3, True),
)

_CATALOG_NAMES: Final[frozenset[str]] = frozenset(spec.name for spec in CATALOG)
_EXPECTED_ENV_MODE: Final = 0o600


class Secrets(BaseSettings):
    """Immutable secret values loaded independently from scalar configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=True,
        frozen=True,
        populate_by_name=True,
    )

    kis_app_key: SecretStr | None = Field(default=None, validation_alias="KIS_APP_KEY")
    kis_app_secret: SecretStr | None = Field(default=None, validation_alias="KIS_APP_SECRET")
    kis_paper_app_key: SecretStr | None = Field(
        default=None,
        validation_alias="KIS_PAPER_APP_KEY",
    )
    kis_paper_app_secret: SecretStr | None = Field(
        default=None,
        validation_alias="KIS_PAPER_APP_SECRET",
    )
    kis_account_no: SecretStr | None = Field(default=None, validation_alias="KIS_ACCOUNT_NO")
    kis_hts_id: SecretStr | None = Field(default=None, validation_alias="KIS_HTS_ID")
    upbit_access: SecretStr | None = Field(default=None, validation_alias="UPBIT_ACCESS")
    upbit_secret: SecretStr | None = Field(default=None, validation_alias="UPBIT_SECRET")
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_chat_id: SecretStr | None = Field(
        default=None,
        validation_alias="TELEGRAM_CHAT_ID",
    )
    smtp_host: SecretStr | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: SecretStr | None = Field(default=None, validation_alias="SMTP_PORT")
    smtp_user: SecretStr | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_pass: SecretStr | None = Field(default=None, validation_alias="SMTP_PASS")
    deadman_webhook_url: SecretStr | None = Field(
        default=None,
        validation_alias="DEADMAN_WEBHOOK_URL",
    )
    web_session_secret: SecretStr | None = Field(
        default=None,
        validation_alias="WEB_SESSION_SECRET",
    )
    web_admin_password_hash: SecretStr | None = Field(
        default=None,
        validation_alias="WEB_ADMIN_PASSWORD_HASH",
    )
    safety_code_secret: SecretStr | None = Field(
        default=None,
        validation_alias="SAFETY_CODE_SECRET",
    )
    litestream_bucket: SecretStr | None = Field(
        default=None,
        validation_alias="LITESTREAM_BUCKET",
    )
    litestream_access_key_id: SecretStr | None = Field(
        default=None,
        validation_alias="LITESTREAM_ACCESS_KEY_ID",
    )
    litestream_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="LITESTREAM_SECRET_ACCESS_KEY",
    )
    restic_repository: SecretStr | None = Field(
        default=None,
        validation_alias="RESTIC_REPOSITORY",
    )
    restic_password: SecretStr | None = Field(
        default=None,
        validation_alias="RESTIC_PASSWORD",
    )
    restic_access_key_id: SecretStr | None = Field(
        default=None,
        validation_alias="RESTIC_ACCESS_KEY_ID",
    )
    restic_secret_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="RESTIC_SECRET_ACCESS_KEY",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
    )
    kis_accounts: Mapping[str, SecretStr] = Field(
        default_factory=dict,
        validation_alias="KIS_ACCOUNT",
    )

    @field_validator("kis_accounts")
    @classmethod
    def _normalize_account_ids(
        cls,
        value: Mapping[str, SecretStr],
    ) -> Mapping[str, SecretStr]:
        normalized: dict[str, SecretStr] = {}
        for account_id, secret in value.items():
            canonical = account_id.lower()
            if canonical in normalized:
                raise ValueError(
                    f"duplicate KIS_ACCOUNT account_id after case normalization: {canonical}"
                )
            normalized[canonical] = secret
        return normalized

    def require(
        self,
        env: ExecEnv,
        surface: Literal["app", "litestream", "tools"],
    ) -> None:
        """Raise with every required secret name absent for an environment and surface."""
        missing = tuple(
            sorted(
                spec.name
                for spec in CATALOG
                if spec.surface == surface
                and env in spec.required_in
                and not self._is_present(spec.name)
            )
        )
        if missing:
            raise MissingSecrets(missing)

    def assert_absent(self, names: Iterable[str]) -> None:
        """Fail when a forbidden catalog secret is present, without exposing its value."""
        requested = frozenset(names)
        unknown = sorted(requested - _CATALOG_NAMES)
        if unknown:
            raise ValueError(f"unknown secret names: {unknown}")

        present = tuple(sorted(name for name in requested if self._is_present(name)))
        if present:
            raise ConfigError(
                f"forbidden secrets are present: {', '.join(present)}",
                code="config.secret_placement",
            )

    def all_values(self) -> frozenset[str]:
        """Return non-empty raw values exclusively for the shared masking boundary."""
        values = {
            raw
            for spec in CATALOG
            if (secret := self._catalog_secret(spec.name)) is not None
            if (raw := secret.get_secret_value())
        }
        values.update(
            raw for secret in self.kis_accounts.values() if (raw := secret.get_secret_value())
        )
        return frozenset(values)

    def _catalog_secret(self, name: str) -> SecretStr | None:
        value = getattr(self, name.lower())
        return value if isinstance(value, SecretStr) else None

    def _is_present(self, name: str) -> bool:
        secret = self._catalog_secret(name)
        if secret is not None and secret.get_secret_value():
            return True
        return name == "KIS_ACCOUNT_NO" and any(
            secret.get_secret_value() for secret in self.kis_accounts.values()
        )


def load_secrets(env_files: Sequence[Path]) -> Secrets:
    """Load the ordered dotenv sources and warn about weak Linux file modes."""
    paths = tuple(Path(path) for path in env_files)
    if sys.platform.startswith("linux"):
        for path in paths:
            if path.is_file():
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode != _EXPECTED_ENV_MODE:
                    warnings.warn(
                        f"secret env file {path} has mode {mode:#05o}; expected 0o600",
                        RuntimeWarning,
                        stacklevel=2,
                    )
    return Secrets(_env_file=paths, _env_file_encoding="utf-8")


__all__ = ["CATALOG", "SecretSpec", "Secrets", "load_secrets"]
