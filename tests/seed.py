"""The canonical knowledge a test project starts from.

This was `cv_engine/infrastructure/canonical_data.py`: 831 lines, of which about
770 were the candidate's facts written out as Python literals. Nothing in the
engine ever imported it — only tests did — so it was a second canonical location
for facts whose first one is `base/*.md`, living inside the product for no
reason. CLAUDE.md allows exactly one canonical location per fact.

It is now four data files plus this loader. Two things follow from that.

The seed stays frozen rather than being read from `base/` directly, which is
the reason this is a copy at all and not a deletion. Tests that seeded from the
live `base/` would change meaning whenever the candidate edits their own facts,
and a suite whose assertions move when you update your CV is worse than a
duplicate.

Because it is a duplicate, `test_facts_profiles.py` compares it against `base/`
and fails when the two disagree on anything but serialization. A copy nobody
checks is the thing that quietly rots.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).parent / "fixtures/seed"
SEED_SOURCES = ("common.md", "sales.md", "development.md", "situational_skills.md")

# Added through the normal fact lifecycle rather than baked into the seed, so the
# fixture exercises the path a real new fact takes. New v2 facts take UUIDv4
# technical identity.
V2_IDENTITY_FACT: dict[str, Any] = json.loads(
    (SEED_DIR / "identity_fact.json").read_text(encoding="utf-8")
)


def source_texts() -> dict[str, str]:
    return {name: (SEED_DIR / name).read_text(encoding="utf-8") for name in SEED_SOURCES}


def write_canonical_sources(base_dir: Path) -> list[Path]:
    base_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in SEED_SOURCES:
        target = base_dir / name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite canonical source: {target}")
        shutil.copy2(SEED_DIR / name, target)
        written.append(target)
    return written


_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def facts_in(text: str) -> dict[str, dict[str, Any]]:
    """The facts a rendered source carries, keyed by id.

    Parsed from the embedded JSON rather than the prose, because the prose is a
    rendering of the JSON and only the JSON is the record.
    """
    match = _JSON_BLOCK.search(text)
    if not match:
        return {}
    return {fact["fact_id"]: fact for fact in json.loads(match.group(1))["facts"]}
