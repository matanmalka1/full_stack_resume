"""Who a command acts for (architecture §18.3).

The API resolves the session to an `Actor` and passes it to every service call; the
worker derives it from the Operation's Application. No service reads identity from
anywhere else, and a record another user owns is the same `UnknownRecord` as one that
does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    user_id: str
