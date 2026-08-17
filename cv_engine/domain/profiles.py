from __future__ import annotations

from .facts import FactStore
from .models import Profile, ProfileName, Track
from ..util import canonical_json, sha256_text


class ProfileStoreError(ValueError):
    pass


class ProfileStore:
    def __init__(self, profiles: dict[ProfileName, Profile], sources: dict[ProfileName, str] | None = None):
        self.profiles = profiles
        # Where each profile came from, as an opaque label for messages and
        # records. It is not a path this layer may resolve or open.
        self.sources = sources or {}
        self.version = sha256_text(canonical_json([
            profiles[key].model_dump(mode="json") for key in sorted(profiles, key=str)
        ]))

    @classmethod
    def from_documents(cls, documents: dict[str, dict], facts: FactStore) -> "ProfileStore":
        """Build the store from already-read profile documents, keyed by origin.

        Finding and reading those documents is the storage adapter's job. What
        stays here is what a profile set must satisfy: every profile present,
        none duplicated, and every fact it names known to the fact store.
        """
        if not documents:
            raise ProfileStoreError("no profile files found")
        result: dict[ProfileName, Profile] = {}
        sources: dict[ProfileName, str] = {}
        for origin in sorted(documents):
            try:
                profile = Profile.model_validate(documents[origin])
            except ValueError as exc:
                raise ProfileStoreError(f"invalid profile {origin}: {exc}") from exc
            if profile.profile in result:
                raise ProfileStoreError(f"duplicate profile: {profile.profile}")
            for section in profile.sections:
                for fact_id in section.fact_ids:
                    facts.get(fact_id)
            result[profile.profile] = profile
            sources[profile.profile] = origin
        required = set(ProfileName)
        if set(result) != required:
            missing = sorted(str(item) for item in required - set(result))
            raise ProfileStoreError(f"missing profiles: {', '.join(missing)}")
        return cls(result, sources)

    def get(self, name: ProfileName | str) -> Profile:
        key = ProfileName(name)
        return self.profiles[key]

    def source(self, name: ProfileName | str) -> str:
        key = ProfileName(name)
        try:
            return self.sources[key]
        except KeyError as exc:
            raise ProfileStoreError(f"profile {key.value} has no source file") from exc

    def for_track(self, track: Track) -> list[Profile]:
        return [profile for profile in self.profiles.values() if profile.track is track]


def attach_fact_to_section(
    payload: dict, fact_id: str, section: str, *, origin: str, pin: bool = False
) -> tuple[Profile, dict]:
    """Add a canonical fact to one Profile section's candidate pool.

    A canonical fact is only reachable in a CV once some Profile section offers
    it, so this is the last step of the fact lifecycle rather than a Profile
    redesign: it widens a pool and never reorders, removes, or reweights it.

    Returns the validated profile and the document to store, so what counts as
    a valid attachment is decided here and the writing happens outside.
    """
    matches = [
        spec for spec in payload["sections"]
        if section in {spec["name_en"], spec["name_he"]}
    ]
    if len(matches) != 1:
        available = ", ".join(spec["name_en"] for spec in payload["sections"])
        raise ProfileStoreError(
            f"section {section!r} does not identify exactly one section in {origin} "
            f"(sections: {available})"
        )
    spec = matches[0]
    if fact_id not in spec["fact_ids"]:
        spec["fact_ids"].append(fact_id)
    if pin and fact_id not in spec.setdefault("pinned_fact_ids", []):
        spec["pinned_fact_ids"].append(fact_id)
    return Profile.model_validate(payload), payload
