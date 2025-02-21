"""A circuit breaker that can share state between instances."""

from __future__ import annotations

import importlib.metadata

from .backend import MemcacheProvider, RedisProvider, ValkeyProvider
from .tripswitch import Tripswitch, monitor

__all__ = ("MemcacheProvider", "RedisProvider", "Tripswitch", "ValkeyProvider", "monitor")
__version__ = importlib.metadata.version("tripswitch")
