from __future__ import annotations

from .facts import FactStore, FactStoreError
from .models import CandidateContext
from ..util import canonical_json, sha256_text


CANDIDATE_FILE = "candidate.json"

# Projections of canonical facts, filled in at load time. Declaring one in the
# file would recreate the duplication these fields exist to avoid.
RESOLVED_FIELDS = {"names", "link_targets", "resolved_filename_name", "version_hash"}


class CandidateContextError(ValueError):
    pass


def build_candidate_context(
    payload: dict, facts: FactStore, *, origin: str = CANDIDATE_FILE
) -> CandidateContext:
    """Bind an already-read candidate context to canonical facts.

    Every referenced fact must exist and be canonical, so a Workspace whose
    identity or contact facts were removed, renamed, or left pending fails here
    rather than rendering a CV with a missing name or a dead link.
    """
    try:
        context = CandidateContext.model_validate(payload)
    except ValueError as exc:
        raise CandidateContextError(f"invalid candidate context {origin}: {exc}") from exc

    # These fields are resolved from canonical facts below. A file that declares
    # one is a second place to edit what the facts already state, so it is
    # refused rather than silently overwritten.
    declared = sorted(RESOLVED_FIELDS & set(payload))
    if declared:
        raise CandidateContextError(
            f"candidate context declares fields resolved from canonical facts: "
            f"{', '.join(declared)}"
        )

    referenced = [context.name_fact_id, *context.contact_fact_ids]
    for extra in context.track_contact_fact_ids.values():
        referenced.extend(extra)
    try:
        for fact_id in referenced:
            facts.get(fact_id, canonical_only=True)
    except FactStoreError as exc:
        raise CandidateContextError(
            f"candidate context references an unusable fact: {exc}"
        ) from exc

    unknown = sorted(set(context.link_schemes) - set(referenced))
    if unknown:
        raise CandidateContextError(
            f"link policy names facts the candidate context does not use: {', '.join(unknown)}"
        )
    # An https contact's address is display text in its rendering, so it is read
    # from the fact's own `link_target` rather than declared a second time here.
    # The fact stays the single place the address is edited, and the shape of
    # that address — https, and carrying the rendering it displays — is the
    # fact's own invariant rather than a rule repeated beside it.
    link_targets: dict[str, str] = {}
    for fact_id, scheme in sorted(context.link_schemes.items()):
        if scheme != "https":
            continue
        target = facts.get(fact_id, canonical_only=True).link_target
        if not target:
            raise CandidateContextError(
                f"contact {fact_id} declares an https link but its canonical fact "
                "carries no link target"
            )
        link_targets[fact_id] = target

    name_fact = facts.get(context.name_fact_id, canonical_only=True)
    names = dict(name_fact.renderings)
    filename_name = context.filename_name or names.get(context.filename_language)
    if not filename_name:
        raise CandidateContextError(
            f"candidate fact {context.name_fact_id} has no {context.filename_language!r} "
            "rendering for the recruiter-facing filename"
        )
    return context.model_copy(
        update={
            "names": names,
            "link_targets": link_targets,
            "resolved_filename_name": filename_name,
            # The hash covers the declared context and the exact facts it resolved
            # to, so a changed name, contact rendering, or link target is a changed
            # context.
            "version_hash": sha256_text(
                canonical_json(
                    {
                        "context": payload,
                        "names": names,
                        "contacts": {
                            fact_id: {
                                "renderings": facts.get(fact_id).renderings,
                                "link_target": facts.get(fact_id).link_target,
                            }
                            for fact_id in sorted(set(referenced))
                        },
                    }
                )
            ),
        }
    )


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
