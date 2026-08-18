from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_payload(path: Path, expected_hash: str) -> Literal["ok", "missing", "tampered"]:
    """Classify one immutable payload without imposing caller-specific messages."""
    if not path.is_file():
        return "missing"
    if sha256_file(path) != expected_hash:
        return "tampered"
    return "ok"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
