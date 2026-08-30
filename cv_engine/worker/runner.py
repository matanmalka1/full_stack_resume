"""Running one Operation worker until it is asked to stop."""

from __future__ import annotations

import logging
import signal
from threading import Event
from types import FrameType

from ..runtime.composition import build_services
from ..runtime.paths import AppPaths, resolve_root

__all__ = ["run_worker"]

logger = logging.getLogger("cv_engine.worker")


def _install_signal_handlers(stop: Event) -> None:
    """Ask `stop` for a clean shutdown on SIGINT and SIGTERM.

    Signal handlers may only be installed from the main thread of the main
    interpreter. A caller that runs the worker in a thread - a test harness,
    or a caller owning its own signals - already controls `stop`, so the
    handlers are skipped rather than raising.
    """

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        logger.info("worker stopping on signal %s", signal.Signals(signum).name)
        stop.set()

    for received in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(received, request_stop)
        except ValueError:
            logger.debug("not the main thread; leaving %s to the caller", received.name)
            return


def run_worker(stop: Event | None = None) -> None:
    """Serve Operations until `stop` is set or a termination signal arrives.

    `serve` requests cancellation for whatever it still holds when it stops, so
    a signal ends the loop rather than abandoning claimed work.
    """
    stop = Event() if stop is None else stop
    root, config = resolve_root()
    services = build_services(AppPaths.from_root(root), config=config)
    _install_signal_handlers(stop)

    logger.info("worker started against %s", root)
    services.operation_worker.serve(stop)
    logger.info("worker stopped")
