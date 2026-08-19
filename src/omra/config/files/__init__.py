"""Strict models and loaders for record-oriented configuration files."""

from omra.config.files.base import RecordFile
from omra.config.files.goals import (
    GlidePathBand,
    GlidePathCfg,
    Goal,
    GoalsFile,
    WithdrawalCfg,
)
from omra.config.files.income import ExternalIncome, ExternalIncomeFile
from omra.config.files.market_weights import EquityRegions, MarketWeightsFile
from omra.config.files.schedules import ExternalSchedule, ExternalSchedulesFile
from omra.config.files.secrets_registry import (
    AutoAction,
    SecretRegistryEntry,
    SecretsRegistryFile,
    SecretTier,
)
from omra.config.files.surveillance_map import SurveillanceMapFile, SurvMapEntry
from omra.config.files.targets import TargetsFile
from omra.config.files.universe import UniverseFile, UniverseInstrument

__all__ = [
    "AutoAction",
    "EquityRegions",
    "ExternalIncome",
    "ExternalIncomeFile",
    "ExternalSchedule",
    "ExternalSchedulesFile",
    "GlidePathBand",
    "GlidePathCfg",
    "Goal",
    "GoalsFile",
    "MarketWeightsFile",
    "RecordFile",
    "SecretRegistryEntry",
    "SecretTier",
    "SecretsRegistryFile",
    "SurvMapEntry",
    "SurveillanceMapFile",
    "TargetsFile",
    "UniverseFile",
    "UniverseInstrument",
    "WithdrawalCfg",
]
