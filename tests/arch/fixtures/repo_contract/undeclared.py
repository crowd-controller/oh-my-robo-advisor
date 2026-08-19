"""Mutation fixture: a repo cannot write a table it does not own."""

from typing import Final

from sqlalchemy import insert
from sqlalchemy.sql.dml import Insert

from omra.persistence.models.schema import OrderRow

TABLES: Final[frozenset[str]] = frozenset({"fills"})


def mutation() -> Insert:
    return insert(OrderRow)
