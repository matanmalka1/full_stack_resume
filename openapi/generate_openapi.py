"""Write `openapi/openapi.json` from the FastAPI application.

Run from the repository root:

    python openapi/generate_openapi.py

The committed file is the contract the TypeScript types are generated from and
the drift test compares against. Regenerating it is deliberate: the diff is
stated in the commit message, the same way the frozen schema fingerprint is.

Only the route table is read, so no Workspace, database, or provider is needed.
The container is filled with placeholders for exactly that reason - a schema
dump that required a live Workspace would make the contract depend on whichever
Workspace happened to be open.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cv_engine.api.app import API_VERSION, create_app  # noqa: E402
from cv_engine.api.services import ApiLimits, ApiServices, InstanceIdentity  # noqa: E402
from cv_engine.runtime.config import API_MAX_BODY_BYTES_DEFAULT  # noqa: E402

OUTPUT = ROOT / "openapi" / "openapi.json"


def schema_only_services() -> ApiServices:
    placeholder = cast(Any, None)
    return ApiServices(
        applications=placeholder,
        queries=placeholder,
        analysis=placeholder,
        drafts=placeholder,
        rendering=placeholder,
        tracking=placeholder,
        knowledge=placeholder,
        operations=placeholder,
        settings=placeholder,
        identity=InstanceIdentity(
            installation_id="schema-only",
            workspace_id="schema-only",
            product_version="schema-only",
            api_version=API_VERSION,
            schema_version="schema-only",
        ),
        limits=ApiLimits(max_body_bytes=API_MAX_BODY_BYTES_DEFAULT),
    )


def build_schema() -> dict[str, Any]:
    return create_app(schema_only_services()).openapi()


def render(schema: dict[str, Any]) -> str:
    # Sorted keys and a trailing newline so the file is diffable and a
    # regeneration that changed nothing produces no diff at all.
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(build_schema()), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
