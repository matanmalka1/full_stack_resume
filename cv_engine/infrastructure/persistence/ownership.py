"""The one predicate that resolves an Application for its owner (architecture §18.3).

An Application is the aggregate root every user-owned record hangs from. Reading or
writing one by its ID always says whose it must be, so another user's Application is
the same miss as one that does not exist.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_

from .tables import applications


def owned(application_id: str, user_id: str) -> ColumnElement[bool]:
    return and_(applications.c.id == application_id, applications.c.user_id == user_id)
