"""Integration tests for RedisProvider."""

from __future__ import annotations

import pytest

from tripswitch.tripswitch import CircuitState, CircuitStatus

from .errors import FooError


@pytest.mark.parametrize("decode_responses", [True, False])
def test_redis(decode_responses):
    """Integration tests for RedisProvider."""
    from redis import Redis

    from tripswitch import RedisProvider, Tripswitch

    client = Redis(host="localhost", port=6379, db=0, decode_responses=decode_responses)
    backend = RedisProvider(client=client)

    # Force init backend to empty state
    backend.set("foo", CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0))

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    def foo() -> int:
        for i in range(21):
            if i < 10:
                pass
            else:
                # The circuit will open after 10 iterations.
                raise FooError("Boom!")  # noqa: EM101
        return i

    with tripswitch:
        output = foo()
        assert output == 20

    assert backend.get("foo") == CircuitState(
        status=CircuitStatus.CLOSED,  # TODO: This should be OPEN
        last_failure=FooError("Boom!"),
        failure_count=1,  # TODO: This should be 10
    )
