"""Pure effective-date selection for immutable configuration values."""

from dataclasses import dataclass
from datetime import date

from omra.config.errors import EffectiveVersionMissing


@dataclass(frozen=True, slots=True)
class VersionedFile[ValueT]:
    """A non-empty, unique effective-date sequence normalized newest first."""

    versions: tuple[tuple[date, ValueT], ...]

    def __post_init__(self) -> None:
        if not self.versions:
            raise ValueError("VersionedFile requires at least one version")

        effective_dates = tuple(effective_from for effective_from, _ in self.versions)
        duplicates = sorted(
            effective_from
            for effective_from in set(effective_dates)
            if effective_dates.count(effective_from) > 1
        )
        if duplicates:
            rendered = ", ".join(value.isoformat() for value in duplicates)
            raise ValueError(f"effective_from dates must be unique (duplicates={rendered})")

        normalized = tuple(sorted(self.versions, key=lambda item: item[0], reverse=True))
        object.__setattr__(self, "versions", normalized)

    def at(self, kst_date: date) -> ValueT:
        """Return the newest value effective on the supplied KST calendar date."""
        for effective_from, value in self.versions:
            if effective_from <= kst_date:
                return value
        raise EffectiveVersionMissing(
            kst_date,
            (effective_from for effective_from, _ in self.versions),
        )

    def at_or_none(self, kst_date: date) -> ValueT | None:
        """Return the effective value, or ``None`` when every version is in the future."""
        for effective_from, value in self.versions:
            if effective_from <= kst_date:
                return value
        return None

    def latest(self) -> ValueT:
        """Return the value with the greatest effective date, even when it is future-dated."""
        return self.versions[0][1]


__all__ = ["VersionedFile"]
