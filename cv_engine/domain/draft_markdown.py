from __future__ import annotations

import json

from .models import ClaimLine, DraftDocument


def _marker(claim: ClaimLine) -> str:
    return f"<!-- claim:{claim.claim_id}:{claim.text_hash} -->"


def _render_claim(claim: ClaimLine) -> list[str]:
    if claim.style == "heading":
        line = f"### {claim.text}"
    elif claim.style == "date":
        line = f"**{claim.text}**"
    elif claim.style in {"bullet", "item"}:
        line = f"- {claim.text}"
    else:
        line = claim.text
    return [_marker(claim), line]


def serialize_markdown(draft: DraftDocument) -> str:
    front = {
        "schema_version": draft.schema_version,
        "application_id": draft.application_id,
        "job_snapshot_id": draft.job_snapshot_id,
        # Omitted for pre-binding "1.0" manifests so their immutable approved
        # Markdown still serializes byte-for-byte as it was approved.
        **({"job_analysis_id": draft.job_analysis_id} if draft.job_analysis_id else {}),
        "language": draft.language,
        "track": draft.track.value,
        "profile": draft.profile.value,
        "emphasis": draft.emphasis.value,
        "fact_store_version": draft.fact_store_version,
    }
    lines = ["---"]
    lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items())
    lines.extend(["---", "", f"# {draft.name}", ""])
    lines.extend(_render_claim(draft.headline))
    lines.append("")
    for contact in draft.contacts:
        lines.extend(_render_claim(contact))
    for section in draft.sections:
        lines.extend(["", "---", "", f"## {section.name}", ""])
        for claim in section.claims:
            lines.extend(_render_claim(claim))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_draft(manifest: str) -> DraftDocument:
    return DraftDocument.model_validate_json(manifest)
