from __future__ import annotations

import uuid


def new_id() -> str:
    """Return one opaque UUIDv4 identity for a new persistence record."""
    return str(uuid.uuid4())
