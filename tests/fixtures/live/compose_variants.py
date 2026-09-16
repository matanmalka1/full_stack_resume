"""Materialize the live-run postings: two clean bodies and their injected variants.

Composition, not storage. A variant is one clean posting plus exactly one block
from `injections.json`, so replacing a posting cannot leave a stale adversarial
copy of the old one behind. Nothing here talks to the engine, the database, or a
provider: it writes text files the operator feeds to the running system.

    python tests/fixtures/live/compose_variants.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def compose(job_text: str, anchor: str, injection: dict) -> str:
    block = injection["block"]
    position = injection["position"]
    if position == "top":
        return f"{block}\n\n{job_text}"
    if position == "bottom":
        return f"{job_text}\n\n{block}"
    if position == "after-anchor":
        lines = job_text.splitlines()
        for index, line in enumerate(lines):
            if line.strip() == anchor:
                lines.insert(index + 1, block)
                return "\n".join(lines)
        raise SystemExit(f"anchor {anchor!r} not found in the posting body")
    raise SystemExit(f"unknown position {position!r}")


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE / "out"
    out.mkdir(parents=True, exist_ok=True)

    postings = json.loads((HERE / "postings.json").read_text(encoding="utf-8"))
    injections = json.loads((HERE / "injections.json").read_text(encoding="utf-8"))

    written: list[str] = []
    for case in postings["cases"]:
        case_id = case["id"]
        anchor = injections["anchors"][case_id]
        variants = {"clean": case["job_text"]} | {
            injection["id"]: compose(case["job_text"], anchor, injection)
            for injection in injections["injections"]
        }
        for name, text in variants.items():
            path = out / f"{case_id}-{name}.txt"
            path.write_text(text + "\n", encoding="utf-8")
            written.append(f"{path}  ({len(text)} chars)")

        header = out / f"{case_id}-ingest.json"
        header.write_text(
            json.dumps(
                {key: case[key] for key in ("company", "target_role", "source_url")},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(str(header))

    print("\n".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
