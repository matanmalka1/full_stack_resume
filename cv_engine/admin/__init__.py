"""The operator CLI: `python -m cv_engine.admin` (architecture §18.7).

It runs as the operator, has no HTTP surface, and calls the same application layer
as the API and the worker.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
