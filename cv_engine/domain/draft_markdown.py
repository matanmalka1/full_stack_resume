from __future__ import annotations

import json
import re

from .facts import FactStore
from .models import ClaimLine, DraftDocument

CLAIM_MARKER = re.compile(r"^<!-- claim:([^:]+):[0-9a-f]{64} -->$")


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


def _claims(draft: DraftDocument) -> list[ClaimLine]:
    return [
        draft.headline,
        *draft.contacts,
        *(claim for section in draft.sections for claim in section.claims),
    ]


def _decode_claim_line(line: str, style: str) -> str:
    if style == "heading" and line.startswith("### "):
        return line[4:]
    if style == "date" and line.startswith("**") and line.endswith("**"):
        return line[2:-2]
    if style in {"bullet", "item"} and line.startswith("- "):
        return line[2:]
    if style in {"paragraph", "contact", "headline"}:
        return line
    raise ValueError(f"edited claim line does not preserve its {style!r} Markdown style")


def _extract_marked_claims(
    markdown: str, claims: dict[str, ClaimLine]
) -> tuple[dict[str, str], str]:
    lines = markdown.splitlines()
    extracted: dict[str, str] = {}
    skeleton: list[str] = []
    index = 0
    while index < len(lines):
        match = CLAIM_MARKER.fullmatch(lines[index])
        if not match:
            skeleton.append(lines[index])
            index += 1
            continue
        claim_id = match.group(1)
        if claim_id not in claims or claim_id in extracted or index + 1 >= len(lines):
            raise ValueError(f"invalid or duplicate claim marker: {claim_id}")
        extracted[claim_id] = _decode_claim_line(lines[index + 1], claims[claim_id].style)
        skeleton.extend([f"<!-- claim:{claim_id}:<hash> -->", f"<claim:{claim_id}>"])
        index += 2
    return extracted, "\n".join(skeleton)


def synchronize_markdown_claims(
    draft: DraftDocument,
    markdown: str,
    facts: FactStore,
) -> DraftDocument:
    # Imported lazily to keep the document-assembly module independent of this codec.
    from .drafts import apply_claim_edit

    current_claims = {claim.claim_id: claim for claim in _claims(draft)}
    extracted, actual_skeleton = _extract_marked_claims(markdown, current_claims)
    expected, expected_skeleton = _extract_marked_claims(serialize_markdown(draft), current_claims)
    if actual_skeleton != expected_skeleton or set(extracted) != set(current_claims):
        raise ValueError("manual Markdown changed document structure or removed claim markers")
    updated = draft
    for claim_id, edited_text in extracted.items():
        prior = current_claims[claim_id]
        if edited_text != expected[claim_id]:
            updated = apply_claim_edit(
                updated,
                claim_id,
                prior.fact_ids,
                facts,
                text=edited_text,
            )
    return updated
