"""Integration tests for RedisProvider."""

from __future__ import annotations

import pytest

from tripswitch.tripswitch import CircuitState, CircuitStatus

from .errors import FooError


@pytest.mark.parametrize("decode_responses", [True, False])
def test_valkey(decode_responses):
    """Integration tests for ValkeyProvider."""
    from valkey import Valkey

    from tripswitch import Tripswitch, ValkeyProvider

    client = Valkey(host="localhost", port=6379, db=0, decode_responses=decode_responses)
    backend = ValkeyProvider(client=client)

    # Force init backend to empty state
    backend.set("foo", CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0))

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    def foo(i: int) -> None:
        if i <= 10:
            pass
        else:
            raise FooError("Boom!")  # noqa: EM101

    for i in range(26):
        with tripswitch:
            foo(i)

    assert i == 25
    assert backend.get("foo") == CircuitState(
        status=CircuitStatus.OPEN,
        last_failure=FooError("Boom!"),
        failure_count=15,
    )
