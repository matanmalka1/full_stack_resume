"""Operator commands: `create-user` and `set-password`.

A password is read from a prompt that does not echo, entered twice, or with
`--password-stdin` from standard input. It is never an argument, so it never lands in
shell history or a process listing.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from ..application.errors import ApplicationError
from ..application.services.accounts import AccountService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m cv_engine.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("create-user", "create the one user"),
        ("set-password", "set a user's password and end every session"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--email", required=True)
        command.add_argument(
            "--password-stdin",
            action="store_true",
            help="read the password from standard input instead of a prompt",
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


def _accounts() -> AccountService:
    from ..runtime.composition import build_services
    from ..runtime.paths import AppPaths, resolve_root

    root, config = resolve_root()
    return build_services(AppPaths.from_root(root), config=config).accounts


def main(
    argv: Sequence[str] | None = None,
    *,
    accounts: AccountService | None = None,
    stdin: TextIO | None = None,
    prompt: Callable[[str], str] = getpass.getpass,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        password = _read_password(arguments.password_stdin, stdin or sys.stdin, prompt)
    except _PasswordMismatch:
        print("error: the passwords do not match", file=err)
        return 1
    service = accounts or _accounts()
    try:
        if arguments.command == "create-user":
            user = service.create_user(arguments.email, password)
            print(f"created user {user.email} ({user.id})", file=out)
        else:
            user = service.set_password(arguments.email, password)
            print(f"set the password of {user.email}; every session ended", file=out)
    except ApplicationError as error:
        print(f"error: {error}", file=err)
        return 1
    return 0
