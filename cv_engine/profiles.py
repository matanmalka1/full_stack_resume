from __future__ import annotations

import json
from pathlib import Path

from .facts import FactStore
from .models import Profile, ProfileName, Track
from .util import canonical_json, sha256_text


class ProfileStoreError(ValueError):
    pass


class ProfileStore:
    def __init__(self, profiles: dict[ProfileName, Profile]):
        self.profiles = profiles
        self.version = sha256_text(canonical_json([
            profiles[key].model_dump(mode="json") for key in sorted(profiles, key=str)
        ]))

    @classmethod
    def load(cls, root: Path, facts: FactStore) -> "ProfileStore":
        paths = sorted((root / "profiles").glob("**/*.yaml"))
        if not paths:
            raise ProfileStoreError("no profile files found")
        result: dict[ProfileName, Profile] = {}
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
        required = set(ProfileName)
        if set(result) != required:
            missing = sorted(str(item) for item in required - set(result))
            raise ProfileStoreError(f"missing profiles: {', '.join(missing)}")
        return cls(result)

    def get(self, name: ProfileName | str) -> Profile:
        key = ProfileName(name)
        return self.profiles[key]

    def for_track(self, track: Track) -> list[Profile]:
        return [profile for profile in self.profiles.values() if profile.track is track]
