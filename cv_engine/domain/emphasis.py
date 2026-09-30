"""Emphasis policies: guidance `draft_resume` receives, never a refusal."""

from __future__ import annotations

from ..util import canonical_json, sha256_text
from .contracts.knowledge import EmphasisPolicy
from .contracts.taxonomy import Emphasis


class EmphasisPolicyError(ValueError):
    pass


class EmphasisPolicyStore:
    def __init__(self, policies: dict[Emphasis, EmphasisPolicy], policy_version: str):
        self.policies = policies
        self.policy_version = policy_version
        self.version = sha256_text(
            canonical_json(
                {
                    "policy_version": policy_version,
                    "emphases": [
                        policies[key].model_dump(mode="json") for key in sorted(policies, key=str)
                    ],
                }
            )
        )

    @classmethod
    def from_payload(cls, payload: dict, *, origin: str = "emphasis policy") -> EmphasisPolicyStore:
        """Build the store from an already-read policy document.

        Locating and reading it belongs to the storage adapter; what a complete
        and self-consistent policy set is stays here.
        """
        try:
            policies = {
                Emphasis(key): EmphasisPolicy.model_validate(value)
                for key, value in payload["emphases"].items()
            }
            policy_version = payload["policy_version"]
        except (KeyError, ValueError) as exc:
            raise EmphasisPolicyError(f"invalid emphasis policy {origin}: {exc}") from exc
        for emphasis, policy in policies.items():
            if policy.emphasis is not emphasis:
                raise EmphasisPolicyError(
                    f"emphasis policy {emphasis} is filed under the wrong key"
                )
        missing = sorted(str(item) for item in set(Emphasis) - set(policies))
        if missing:
            raise EmphasisPolicyError(f"missing emphasis policies: {', '.join(missing)}")
        return cls(policies, policy_version)

    def get(self, emphasis: Emphasis | str) -> EmphasisPolicy:
        return self.policies[Emphasis(emphasis)]
