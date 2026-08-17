from __future__ import annotations

import json
from pathlib import Path

from .facts import FactStore
from .models import Profile, ProfileName, Track
from .util import canonical_json, sha256_text


class ProfileStoreError(ValueError):
    pass


class ProfileStore:
    def __init__(self, profiles: dict[ProfileName, Profile], paths: dict[ProfileName, Path] | None = None):
        self.profiles = profiles
        self.paths = paths or {}
        self.version = sha256_text(canonical_json([
            profiles[key].model_dump(mode="json") for key in sorted(profiles, key=str)
        ]))

    @classmethod
    def load(cls, root: Path, facts: FactStore) -> "ProfileStore":
        paths = sorted((root / "profiles").glob("**/*.yaml"))
        if not paths:
            raise ProfileStoreError("no profile files found")
        result: dict[ProfileName, Profile] = {}
        files: dict[ProfileName, Path] = {}
        for path in paths:
            try:
                profile = Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ProfileStoreError(f"invalid profile {path}: {exc}") from exc
            if profile.profile in result:
                raise ProfileStoreError(f"duplicate profile: {profile.profile}")
            for section in profile.sections:
                for fact_id in section.fact_ids:
                    facts.get(fact_id)
            result[profile.profile] = profile
            files[profile.profile] = path
        required = set(ProfileName)
        if set(result) != required:
            missing = sorted(str(item) for item in required - set(result))
            raise ProfileStoreError(f"missing profiles: {', '.join(missing)}")
        return cls(result, files)

    def get(self, name: ProfileName | str) -> Profile:
        key = ProfileName(name)
        return self.profiles[key]

    def path(self, name: ProfileName | str) -> Path:
        key = ProfileName(name)
        try:
            return self.paths[key]
        except KeyError as exc:
            raise ProfileStoreError(f"profile {key.value} has no source file") from exc

    def for_track(self, track: Track) -> list[Profile]:
        return [profile for profile in self.profiles.values() if profile.track is track]


def attach_fact_to_section(path: Path, fact_id: str, section: str, *, pin: bool = False) -> Profile:
    """Add a canonical fact to one Profile section's candidate pool.

    A canonical fact is only reachable in a CV once some Profile section offers
    it, so this is the last step of the fact lifecycle rather than a Profile
    redesign: it widens a pool and never reorders, removes, or reweights it.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        spec for spec in payload["sections"]
        if section in {spec["name_en"], spec["name_he"]}
    ]
    if len(matches) != 1:
        available = ", ".join(spec["name_en"] for spec in payload["sections"])
        raise ProfileStoreError(
            f"section {section!r} does not identify exactly one section in {path.name} "
            f"(sections: {available})"
        )
    spec = matches[0]
    if fact_id not in spec["fact_ids"]:
        spec["fact_ids"].append(fact_id)
    if pin and fact_id not in spec.setdefault("pinned_fact_ids", []):
        spec["pinned_fact_ids"].append(fact_id)
    profile = Profile.model_validate(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profile
