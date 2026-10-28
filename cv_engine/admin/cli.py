"""Operator account, Knowledge, and whole-instance maintenance commands.

A password is read from a prompt that does not echo, entered twice, or with
`--password-stdin` from standard input. It is never an argument, so it never lands in
shell history or a process listing.

`import-knowledge` reads Knowledge in the installation's file layout (`base/` and
`profiles/` under one directory) into one user's rows, once. `export-knowledge` writes
one user's rows in that layout, which is how Knowledge reaches another installation.
The installation's own `profiles/` hold templates only, so it is never the source.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from ..application.errors import ApplicationError

if TYPE_CHECKING:
    from ..runtime.composition import Services


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m cv_engine.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("create-user", "create a user"),
        ("set-password", "set a user's password and end every session"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--email", required=True)
        command.add_argument(
            "--password-stdin",
            action="store_true",
            help="read the password from standard input instead of a prompt",
        )
    importing = commands.add_parser(
        "import-knowledge", help="import Knowledge files into one user's rows, once"
    )
    importing.add_argument("--email", required=True)
    importing.add_argument(
        "--from",
        dest="source",
        type=Path,
        required=True,
        help="the directory holding base/ and profiles/, as export-knowledge writes it",
    )
    exporting = commands.add_parser(
        "export-knowledge", help="write one user's Knowledge as files import-knowledge reads"
    )
    exporting.add_argument("--email", required=True)
    exporting.add_argument(
        "--to", dest="target", type=Path, required=True, help="a directory that does not exist"
    )
    commands.add_parser(
        "reconcile", help="verify immutable evidence and every user's fact lifecycle"
    )
    commands.add_parser(
        "inspect-orphans", help="list old immutable payloads with no database reference"
    )
    return parser


class _PasswordMismatch(Exception):
    pass


def _read_password(from_stdin: bool, stdin: TextIO, prompt: Callable[[str], str]) -> str:
    if from_stdin:
        return stdin.readline().removesuffix("\n").removesuffix("\r")
    password = prompt("Password: ")
    if prompt("Repeat password: ") != password:
        raise _PasswordMismatch
    return password


def _services() -> Services:
    from ..runtime.composition import build_services
    from ..runtime.paths import AppPaths, resolve_root

    root, config = resolve_root()
    return build_services(AppPaths.from_root(root), config=config)


def main(
    argv: Sequence[str] | None = None,
    *,
    services: Services | None = None,
    stdin: TextIO | None = None,
    prompt: Callable[[str], str] = getpass.getpass,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr
    password = ""
    if arguments.command in {"create-user", "set-password"}:
        try:
            password = _read_password(arguments.password_stdin, stdin or sys.stdin, prompt)
        except _PasswordMismatch:
            print("error: the passwords do not match", file=err)
            return 1
    services = services or _services()
    try:
        if arguments.command == "create-user":
            user = services.accounts.create_user(arguments.email, password)
            print(f"created user {user.email} ({user.id})", file=out)
        elif arguments.command == "set-password":
            user = services.accounts.set_password(arguments.email, password)
            print(f"set the password of {user.email}; every session ended", file=out)
        elif arguments.command == "import-knowledge":
            from ..infrastructure.knowledge import FileKnowledge

            result = services.knowledge_import.import_knowledge(
                arguments.email, FileKnowledge(arguments.source.resolve())
            )
            print(
                f"imported {result.facts} facts and {result.profiles} profile bindings "
                f"for {result.email}",
                file=out,
            )
        elif arguments.command == "export-knowledge":
            from ..infrastructure.knowledge import write_file_knowledge

            target = arguments.target.resolve()
            if target.exists():
                print(f"error: {target} already exists", file=err)
                return 1
            policy_root = services.paths.knowledge_root
            exported = services.knowledge_export.export_knowledge(
                arguments.email,
                lambda knowledge: write_file_knowledge(knowledge, target, policy_root),
            )
            print(
                f"exported {exported.facts} facts and {exported.profiles} profiles "
                f"of {exported.email} to {target}",
                file=out,
            )
        elif arguments.command == "reconcile":
            report = services.maintenance.reconcile()
            print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True), file=out)
            return 0 if report.passed else 2
        else:
            inventory = services.maintenance.inspect_orphans()
            print(
                json.dumps({"candidates": inventory.candidates}, indent=2, sort_keys=True),
                file=out,
            )
    except ApplicationError as error:
        print(f"error: {error}", file=err)
        return 1
    return 0
