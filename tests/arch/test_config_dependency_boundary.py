"""The configuration foundation may only depend on core inside OMRA."""

import ast
from pathlib import Path

from omra.config import (
    CATALOG,
    MissingSecrets,
    Secrets,
    SecretSpec,
    UnsupportedInEnvError,
    check_credential_placement,
    has_smtp,
    has_telegram,
    load_secrets,
)
from omra.config.errors import MissingSecrets as ModuleMissingSecrets
from omra.config.errors import UnsupportedInEnvError as ModuleUnsupportedInEnvError
from omra.config.files import (
    AutoAction,
    EquityRegions,
    ExternalIncome,
    ExternalIncomeFile,
    ExternalSchedule,
    ExternalSchedulesFile,
    GlidePathBand,
    GlidePathCfg,
    Goal,
    GoalsFile,
    MarketWeightsFile,
    RecordFile,
    RestBaseUrls,
    RestSection,
    RestTr,
    SecretRegistryEntry,
    SecretsRegistryFile,
    SecretTier,
    SurveillanceMapFile,
    SurvMapEntry,
    TargetsFile,
    TrIdsRaw,
    UniverseFile,
    UniverseInstrument,
    WithdrawalCfg,
    WsEndpoint,
    WsSection,
    WsTrTable,
    validate_tr_ids_for_env,
)
from omra.config.files.base import RecordFile as BaseRecordFile
from omra.config.files.goals import (
    GlidePathBand as ModuleGlidePathBand,
)
from omra.config.files.goals import (
    GlidePathCfg as ModuleGlidePathCfg,
)
from omra.config.files.goals import (
    Goal as ModuleGoal,
)
from omra.config.files.goals import (
    GoalsFile as ModuleGoalsFile,
)
from omra.config.files.goals import (
    WithdrawalCfg as ModuleWithdrawalCfg,
)
from omra.config.files.income import ExternalIncome as ModuleExternalIncome
from omra.config.files.income import ExternalIncomeFile as ModuleExternalIncomeFile
from omra.config.files.market_weights import (
    EquityRegions as ModuleEquityRegions,
)
from omra.config.files.market_weights import (
    MarketWeightsFile as ModuleMarketWeightsFile,
)
from omra.config.files.schedules import ExternalSchedule as ModuleExternalSchedule
from omra.config.files.schedules import ExternalSchedulesFile as ModuleExternalSchedulesFile
from omra.config.files.secrets_registry import AutoAction as ModuleAutoAction
from omra.config.files.secrets_registry import (
    SecretRegistryEntry as ModuleSecretRegistryEntry,
)
from omra.config.files.secrets_registry import (
    SecretsRegistryFile as ModuleSecretsRegistryFile,
)
from omra.config.files.secrets_registry import SecretTier as ModuleSecretTier
from omra.config.files.surveillance_map import (
    SurveillanceMapFile as ModuleSurveillanceMapFile,
)
from omra.config.files.surveillance_map import SurvMapEntry as ModuleSurvMapEntry
from omra.config.files.targets import TargetsFile as ModuleTargetsFile
from omra.config.files.trids import (
    RestBaseUrls as ModuleRestBaseUrls,
)
from omra.config.files.trids import RestSection as ModuleRestSection
from omra.config.files.trids import RestTr as ModuleRestTr
from omra.config.files.trids import TrIdsRaw as ModuleTrIdsRaw
from omra.config.files.trids import WsEndpoint as ModuleWsEndpoint
from omra.config.files.trids import WsSection as ModuleWsSection
from omra.config.files.trids import WsTrTable as ModuleWsTrTable
from omra.config.files.trids import (
    validate_tr_ids_for_env as module_validate_tr_ids_for_env,
)
from omra.config.files.universe import (
    UniverseFile as ModuleUniverseFile,
)
from omra.config.files.universe import (
    UniverseInstrument as ModuleUniverseInstrument,
)
from omra.config.secrets import CATALOG as MODULE_CATALOG
from omra.config.secrets import Secrets as ModuleSecrets
from omra.config.secrets import SecretSpec as ModuleSecretSpec
from omra.config.secrets import check_credential_placement as module_check_credential_placement
from omra.config.secrets import has_smtp as module_has_smtp
from omra.config.secrets import has_telegram as module_has_telegram
from omra.config.secrets import load_secrets as module_load_secrets

_CONFIG_ROOT = Path(__file__).resolve().parents[2] / "src" / "omra" / "config"
_ALLOWED_INTERNAL_ROOTS = frozenset({"omra.config", "omra.core"})


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names if alias.name.startswith("omra."))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("omra."):
            imported.add(node.module)
    return imported


def test_config_only_imports_config_or_core_inside_omra() -> None:
    violations: list[str] = []
    for path in sorted(_CONFIG_ROOT.rglob("*.py")):
        for module in sorted(_internal_imports(path)):
            if not any(
                module == root or module.startswith(f"{root}.") for root in _ALLOWED_INTERNAL_ROOTS
            ):
                violations.append(f"{path.relative_to(_CONFIG_ROOT)} -> {module}")

    assert violations == []


def test_secret_loader_public_coordinates_are_stable() -> None:
    assert CATALOG is MODULE_CATALOG
    assert MissingSecrets is ModuleMissingSecrets
    assert SecretSpec is ModuleSecretSpec
    assert Secrets is ModuleSecrets
    assert check_credential_placement is module_check_credential_placement
    assert has_smtp is module_has_smtp
    assert has_telegram is module_has_telegram
    assert load_secrets is module_load_secrets
    assert UnsupportedInEnvError is ModuleUnsupportedInEnvError


def test_record_file_public_coordinates_are_stable() -> None:
    assert RecordFile is BaseRecordFile
    assert AutoAction is ModuleAutoAction
    assert SecretRegistryEntry is ModuleSecretRegistryEntry
    assert SecretsRegistryFile is ModuleSecretsRegistryFile
    assert SecretTier is ModuleSecretTier
    assert ExternalSchedule is ModuleExternalSchedule
    assert ExternalSchedulesFile is ModuleExternalSchedulesFile
    assert ExternalIncome is ModuleExternalIncome
    assert ExternalIncomeFile is ModuleExternalIncomeFile
    assert SurvMapEntry is ModuleSurvMapEntry
    assert SurveillanceMapFile is ModuleSurveillanceMapFile
    assert TargetsFile is ModuleTargetsFile
    assert Goal is ModuleGoal
    assert GlidePathBand is ModuleGlidePathBand
    assert GlidePathCfg is ModuleGlidePathCfg
    assert WithdrawalCfg is ModuleWithdrawalCfg
    assert GoalsFile is ModuleGoalsFile
    assert EquityRegions is ModuleEquityRegions
    assert MarketWeightsFile is ModuleMarketWeightsFile
    assert UniverseFile is ModuleUniverseFile
    assert UniverseInstrument is ModuleUniverseInstrument
    assert RestBaseUrls is ModuleRestBaseUrls
    assert RestSection is ModuleRestSection
    assert RestTr is ModuleRestTr
    assert TrIdsRaw is ModuleTrIdsRaw
    assert WsEndpoint is ModuleWsEndpoint
    assert WsSection is ModuleWsSection
    assert WsTrTable is ModuleWsTrTable
    assert validate_tr_ids_for_env is module_validate_tr_ids_for_env
