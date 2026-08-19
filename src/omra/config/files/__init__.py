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
from omra.config.files.open_questions import OpenQuestion, OpenQuestionsFile
from omra.config.files.schedules import ExternalSchedule, ExternalSchedulesFile
from omra.config.files.secrets_registry import (
    AutoAction,
    SecretRegistryEntry,
    SecretsRegistryFile,
    SecretTier,
)
from omra.config.files.surveillance_map import SurveillanceMapFile, SurvMapEntry
from omra.config.files.targets import TargetsFile
from omra.config.files.taxlaw import TaxLawFile, TaxParams, TaxVersion
from omra.config.files.trids import (
    HttpMethod,
    PriorityBucket,
    RestBaseUrls,
    RestSection,
    RestTr,
    TrIdsRaw,
    WsEndpoint,
    WsSection,
    WsTrTable,
    validate_tr_ids_for_env,
)
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
    "HttpMethod",
    "MarketWeightsFile",
    "OpenQuestion",
    "OpenQuestionsFile",
    "PriorityBucket",
    "RecordFile",
    "RestBaseUrls",
    "RestSection",
    "RestTr",
    "SecretRegistryEntry",
    "SecretTier",
    "SecretsRegistryFile",
    "SurvMapEntry",
    "SurveillanceMapFile",
    "TargetsFile",
    "TaxLawFile",
    "TaxParams",
    "TaxVersion",
    "TrIdsRaw",
    "UniverseFile",
    "UniverseInstrument",
    "WithdrawalCfg",
    "WsEndpoint",
    "WsSection",
    "WsTrTable",
    "validate_tr_ids_for_env",
]
