"""The `cv` CLI entry point.

Assembles the command surface out of the package's modules and re-exports
the names other code and tests import from `cv_engine.cli` as if it were
still one module. Importing the handler modules is what populates
`_HANDLERS`: each one registers its commands as a side effect of import,
through the `@_command` decorator defined in `.context`.
"""

from __future__ import annotations

import sys

from ..application.errors import WorkflowError
from ..runtime.backup import BackupError
from ..runtime.workspace import WorkspaceError

# Imported for their registration side effect: each module's @_command
# handlers add themselves to _HANDLERS when the module is imported.
from . import claims as _claims  # noqa: F401
from . import facts as _facts  # noqa: F401
from . import pipeline as _pipeline  # noqa: F401
from . import queries as _queries  # noqa: F401
from . import workspace as _workspace_module  # noqa: F401
from .context import _HANDLERS, CommandContext, Handler, _build_context, _resolve_root
from .fast import _fast, _latest_job_analysis_id, _latest_job_snapshot_id
from .output import EXPORT_SCHEMA_VERSION, export_csv
from .parser import build_parser

__all__ = [
    "CommandContext",
    "Handler",
    "EXPORT_SCHEMA_VERSION",
    "_HANDLERS",
    "_fast",
    "_latest_job_analysis_id",
    "_latest_job_snapshot_id",
    "build_parser",
    "export_csv",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root, config = _resolve_root(args)
    except (WorkspaceError, ValueError) as exc:
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
        WorkspaceError,
        BackupError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
