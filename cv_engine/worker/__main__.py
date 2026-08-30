"""`python -m cv_engine.worker` entry point."""

from __future__ import annotations

import logging

from .runner import run_worker

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_worker()
