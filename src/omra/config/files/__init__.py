"""Strict models and loaders for record-oriented configuration files."""

from omra.config.files.base import RecordFile
from omra.config.files.goals import (
    GlidePathBand,
    GlidePathCfg,
    Goal,
    GoalsFile,
    WithdrawalCfg,
)
from omra.config.files.market_weights import EquityRegions, MarketWeightsFile
from omra.config.files.targets import TargetsFile
from omra.config.files.universe import UniverseFile, UniverseInstrument

__all__ = [
    "EquityRegions",
    "GlidePathBand",
    "GlidePathCfg",
    "Goal",
    "GoalsFile",
    "MarketWeightsFile",
    "RecordFile",
    "TargetsFile",
    "UniverseFile",
    "UniverseInstrument",
    "WithdrawalCfg",
]
