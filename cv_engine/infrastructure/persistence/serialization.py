from __future__ import annotations

from types import MappingProxyType

SERIALIZATION_VERSIONS = MappingProxyType(
    {
        "payload_manifest": "1",
    }
)


def serialization_version(payload_type: str) -> str:
    """Return the registered version for a payload introduced by v2."""
    try:
        return SERIALIZATION_VERSIONS[payload_type]
    except KeyError as exc:
        raise ValueError(f"unregistered serialization payload type: {payload_type}") from exc
