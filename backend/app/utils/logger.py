"""Structured (JSON) logging helper."""
# TODO(plan: Phase 0) — replace with full JSON formatter + correlation ids.
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a module logger. Phase 0 placeholder for structured JSON logging."""
    return logging.getLogger(name)
