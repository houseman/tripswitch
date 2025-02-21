"""Exception classes for integration tests."""

from __future__ import annotations


class FooError(Exception):
    """Raised when foo() fails."""

    def __eq__(self, value) -> bool:
        """Perform a simple equality check for testing purposes."""
        return isinstance(value, FooError) and str(self) == str(value)
