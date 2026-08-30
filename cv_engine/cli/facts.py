"""Fact lifecycle command dispatch and the reconcile maintenance command."""

from __future__ import annotations

import argparse
from typing import Any

from ..application.maintenance import reconcile_artifacts
from .context import CommandContext, _command
from .output import _print


def fact_command(knowledge: Any, args: argparse.Namespace) -> int:
    """Dispatch the fact lifecycle commands.

    Promotion is refused without `--confirm`: the confirmation is what the
    specification requires for a status change, so an unconfirmed request must
    fail rather than be interpreted.
    """
    if args.fact_command == "list":
        result = knowledge.list_facts(args.status)
        _print(
            [
                {**item.fact.model_dump(mode="json"), "recorded_status": item.recorded_status}
                for item in result.items
            ]
        )
    elif args.fact_command == "show":
        result = knowledge.show_fact(args.fact_id)
        _print(
            {
                **result.fact.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in result.events],
            }
        )
    elif args.fact_command == "history":
        _print(
            [event.model_dump(mode="json") for event in knowledge.fact_history(args.fact_id).events]
        )
    elif args.fact_command == "add":
        renderings = {"en": args.en}
        if args.he:
            renderings["he"] = args.he
        _print(
            knowledge.add_fact(
                args.source,
                {
                    "fact_id": args.fact_id,
                    "meaning": args.meaning,
                    "renderings": renderings,
                    "tags": args.tag,
                    "provenance": args.provenance,
                    "effective_dates": args.dates,
                    "replaces": args.replaces,
                    "resume_style": args.style,
                },
                canonical=args.canonical,
                reason=args.reason,
            )
        )
    elif args.fact_command == "capture":
        _print(
            knowledge.capture_claim_fact(
                args.application_id,
                args.claim_id,
                source=args.source,
                fact_id=args.fact_id,
                meaning=args.meaning,
                tags=args.tag,
                english=args.en,
                hebrew=args.he,
                provenance=args.provenance,
                effective_dates=args.dates,
                replaces=args.replaces,
                canonical=args.canonical,
                reason=args.reason,
            )
        )
    elif args.fact_command in {"confirm", "promote"}:
        _print(
            knowledge.transition_fact(
                args.fact_id,
                args.fact_command,
                explicitly_confirmed=args.confirm,
                reason=args.reason,
            )
        )
    elif args.fact_command == "attach":
        _print(knowledge.attach_fact(args.fact_id, args.profile, args.section, pin=args.pin))
    return 0


@_command("reconcile")
def _reconcile(context: CommandContext) -> int:
    services = context.built_services
    report = reconcile_artifacts(services.payloads, context.repository)
    fact_lifecycle = services.knowledge_lifecycle.reconcile_facts()
    report["fact_lifecycle"] = fact_lifecycle.model_dump(mode="json")
    report["passed"] = report["passed"] and fact_lifecycle.passed
    _print(report)
    return 0 if report["passed"] else 1


@_command("fact")
def _fact(context: CommandContext) -> int:
    return fact_command(context.built_services.knowledge_lifecycle, context.args)
