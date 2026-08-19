"""`python -m cv_engine.cli` entry point.

A package's `__init__.py` does not run as `__main__` under `-m`; this
submodule is what `-m` actually executes, so it has to exist even though
`cli.py` as a plain module never needed one.
"""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    raise SystemExit(main())
