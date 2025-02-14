"""A circuit breaker that can share state between instances."""

from __future__ import annotations

from .tripswitch import Tripswitch, monitor

__all__ = ("Tripswitch", "monitor")
