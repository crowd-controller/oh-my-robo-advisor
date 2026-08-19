"""Mutation fixture: a dynamic table target cannot bypass static ownership checks."""

from typing import Final

from sqlalchemy import Table, insert
from sqlalchemy.sql.dml import Insert

TABLES: Final[frozenset[str]] = frozenset({"orders"})


def mutation(target: Table) -> Insert:
    return insert(target)
