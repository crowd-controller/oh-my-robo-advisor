"""Deterministic raw-file and effective configuration fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from omra.config.errors import ConfigValidationError, Violation
from omra.config.layers import load_layered_mapping
from omra.config.settings import AppConfig

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ConfigFingerprint:
    """Immutable hashes for source YAML bytes and the effective scalar model."""

    files: Mapping[str, str]
    effective: str

    def __post_init__(self) -> None:
        frozen = MappingProxyType(dict(sorted(self.files.items())))
        object.__setattr__(self, "files", frozen)


def _read_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ConfigValidationError(
            (
                Violation(
                    code="file_unreadable",
                    message=str(error),
                    source=path,
                ),
            )
        ) from error


def _file_hashes(config_dir: Path) -> Mapping[str, str]:
    paths = sorted(path for path in config_dir.glob("*.yaml") if path.is_file())
    return {f"config/{path.name}": _sha256(_read_file(path)) for path in paths}


def _effective_hash(app: AppConfig) -> str:
    payload = app.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(canonical)


def config_fingerprint(
    config_dir: Path,
    *,
    app: AppConfig | None = None,
) -> ConfigFingerprint:
    """Hash every source YAML and the validated effective scalar configuration.

    A caller that already merged CLI overrides may supply its validated ``app``;
    otherwise the canonical base, environment overlay, and OMRA__ layers are loaded.
    """
    effective_app = app
    if effective_app is None:
        layered = load_layered_mapping(config_dir)
        effective_app = AppConfig.model_validate(layered.values)
    return ConfigFingerprint(
        files=_file_hashes(config_dir),
        effective=_effective_hash(effective_app),
    )


__all__ = ["ConfigFingerprint", "config_fingerprint"]
