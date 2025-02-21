"""A circuit breaker that can share state between instances."""

from __future__ import annotations

import importlib.metadata

from .tripswitch import Tripswitch, monitor

__all__ = ("Tripswitch", "monitor")
__version__ = importlib.metadata.version("tripswitch")
