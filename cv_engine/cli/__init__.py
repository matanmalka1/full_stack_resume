"""The `cv` CLI entry point.

The CLI is a runtime and maintenance surface: it starts the Web UI, and it
runs the maintenance operations that have no place in a product interface.
Every product use-case belongs to the API and the Web UI, which call the same
application services this module does.

Importing the handler modules is what populates `_HANDLERS`: each one
registers its commands as a side effect of import, through the `@_command`
decorator defined in `.context`.
"""

from __future__ import annotations

import sys

from ..application.errors import WorkflowError
from ..application.maintenance import EXPORT_SCHEMA_VERSION
from ..runtime.config import ConfigError
from ..runtime.paths import PathConfigurationError
from ..runtime.web import WebRuntimeError

# Imported for their registration side effect: each module's @_command
# handlers add themselves to _HANDLERS when the module is imported.
from . import claims as _claims  # noqa: F401
from . import facts as _facts  # noqa: F401
from . import output as _output  # noqa: F401
from . import queries as _queries  # noqa: F401
from . import web as _web_module  # noqa: F401
from .context import _HANDLERS, CommandContext, Handler, _build_context, _resolve_root
from .output import export_csv
from .parser import build_parser

__all__ = [
    "CommandContext",
    "Handler",
    "EXPORT_SCHEMA_VERSION",
    "_HANDLERS",
    "build_parser",
    "export_csv",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root, config = _resolve_root(args)
    except (ConfigError, PathConfigurationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    needs, handler = _HANDLERS[args.command]
    try:
        return handler(_build_context(args, root, config, needs))
    except (
        ValueError,
        KeyError,
        FileNotFoundError,
        WorkflowError,
        ConfigError,
        PathConfigurationError,
        WebRuntimeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
