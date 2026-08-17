from __future__ import annotations

import json
from pathlib import Path

from .facts import FactStore, FactStoreError
from .models import CandidateContext
from .util import canonical_json, sha256_text


CANDIDATE_FILE = "candidate.json"


class CandidateContextError(ValueError):
    pass


def load_candidate_context(knowledge_root: Path, facts: FactStore) -> CandidateContext:
    """Load the one CandidateContext and bind it to canonical facts.

    Every referenced fact must exist and be canonical, so a Workspace whose
    identity or contact facts were removed, renamed, or left pending fails here
    rather than rendering a CV with a missing name or a dead link.
    """
    path = Path(knowledge_root) / "base" / CANDIDATE_FILE
    if not path.is_file():
        raise CandidateContextError(f"no candidate context in this Workspace: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        context = CandidateContext.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CandidateContextError(f"invalid candidate context {path}: {exc}") from exc

    referenced = [context.name_fact_id, *context.contact_fact_ids]
    for extra in context.track_contact_fact_ids.values():
        referenced.extend(extra)
    try:
        for fact_id in referenced:
            facts.get(fact_id, canonical_only=True)
    except FactStoreError as exc:
        raise CandidateContextError(f"candidate context references an unusable fact: {exc}") from exc

    unknown = sorted((set(context.link_schemes) | set(context.link_targets)) - set(referenced))
    if unknown:
        raise CandidateContextError(
            f"link policy names facts the candidate context does not use: {', '.join(unknown)}"
        )
    for fact_id, scheme in sorted(context.link_schemes.items()):
        if scheme == "https" and not context.link_targets.get(fact_id):
            raise CandidateContextError(f"contact {fact_id} declares an https link with no target")
    for fact_id, target in sorted(context.link_targets.items()):
        if not target.startswith("https://"):
            raise CandidateContextError(f"contact {fact_id} has a non-https link target: {target}")

    name_fact = facts.get(context.name_fact_id, canonical_only=True)
    names = dict(name_fact.renderings)
    filename_name = context.filename_name or names.get(context.filename_language)
    if not filename_name:
        raise CandidateContextError(
            f"candidate fact {context.name_fact_id} has no {context.filename_language!r} "
            "rendering for the recruiter-facing filename"
        )
    return context.model_copy(update={
        "names": names,
        "resolved_filename_name": filename_name,
        # The hash covers the declared context and the exact facts it resolved
        # to, so a changed name or contact rendering is a changed context.
        "version_hash": sha256_text(canonical_json({
            "context": payload,
            "names": names,
            "contacts": {
                fact_id: facts.get(fact_id).renderings
                for fact_id in sorted(set(referenced))
            },
        })),
    })


def contact_href(context: CandidateContext, fact_id: str, text: str) -> str | None:
    """The link a contact claim should carry, or None for plain text.

    The address itself always comes from the canonical fact's rendering; the
    context only decides which scheme wraps it.
    """
    scheme = context.scheme(fact_id)
    if scheme == "text":
        return None
    if scheme == "mailto":
        return f"mailto:{text}"
    if scheme == "tel":
        digits = "".join(character for character in text if character.isdigit() or character == "+")
        return f"tel:{digits}"
    return context.link_targets[fact_id]
