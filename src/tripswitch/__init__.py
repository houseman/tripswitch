"""A circuit breaker that can share state between instances."""

from __future__ import annotations

from .tripswitch import Tripswitch

__all__ = ("Tripswitch",)
