"""The standalone Operation worker process.

The worker runs beside the API rather than inside it. It claims Operations from
the database under a lease, so the two processes share no memory and neither
supervises the other: an Operation claimed by a worker that dies is recovered
by the next worker's `recover_startup()`.
"""

from __future__ import annotations

from .runner import run_worker

__all__ = ["run_worker"]
