"""Request headers more than one router speaks.

`Idempotency-Key` is optional on every asynchronous command: omitted, the
boundary generates one; reused, the Operation that key already created is
returned instead of a second attempt being queued. Declared
once so the description a client reads is the same on every route that accepts
it, rather than drifting per router.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description=(
            "Optional. A retry that reuses the key of an Operation which already "
            "exists returns that Operation instead of queueing a second attempt. "
            "Omitted, the boundary generates a key."
        ),
    ),
]
