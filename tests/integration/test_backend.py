"""Integration tests for RedisProvider."""

from __future__ import annotations

import time

import pytest
from circuitbreaker import CircuitBreakerError
from pytest_lazy_fixtures import lf

from tripswitch.tripswitch import CircuitState, CircuitStatus

from .errors import FooError


@pytest.fixture
def closed_circuit_state():
    """Fixture for closed circuit state."""
    return CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0, timestamp=0)


@pytest.fixture
def open_circuit_state():
    """Fixture for open circuit state."""
    return CircuitState(status=CircuitStatus.OPEN, last_failure=FooError(), failure_count=10, timestamp=0)


@pytest.fixture(params=[True, False])
def redis_client(request):
    """Fixture for Redis client."""
    from redis import Redis

    return Redis(host="localhost", port=6379, db=0, decode_responses=request.param)


@pytest.fixture
def redis_backend(redis_client):
    """Fixture for RedisProvider."""
    from tripswitch import RedisProvider

    return RedisProvider(client=redis_client)


@pytest.fixture(params=[True, False])
def valkey_client(request):
    """Fixture for Valkey client."""
    from valkey import Valkey

    return Valkey(host="localhost", port=6379, db=0, decode_responses=request.param)


@pytest.fixture
def valkey_backend(valkey_client):
    """Fixture for RedisProvider."""
    from tripswitch import ValkeyProvider

    return ValkeyProvider(client=valkey_client)


@pytest.fixture
def memcache_client():
    """Fixture for Valkey client."""
    from pymemcache.client.base import Client

    return Client(("127.0.0.1", 11211))


@pytest.fixture
def memcache_backend(memcache_client):
    """Fixture for RedisProvider."""
    from tripswitch import MemcacheProvider

    return MemcacheProvider(client=memcache_client)


@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_closed_circuit__opens_past_threshold(backend, closed_circuit_state):
    """Test that a circuit breaker opens after exceeding the failure threshold.

    GIVEN a circuit breaker with a failure threshold of 10
    WHEN the circuit breaker is tripped 15 times
    THEN the circuit breaker should open.
    """
    from tripswitch import Tripswitch

    # Set the initial state to closed
    backend.set("foo", closed_circuit_state)

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    def foo(i: int) -> None:
        if i <= 10:
            pass
        else:
            raise FooError("Boom!")  # noqa: EM101

    raised_error_count = 0
    for i in range(26):
        with tripswitch:
            try:
                foo(i)
            except FooError:
                raised_error_count += 1

    output = backend.get("foo")

    assert i == 25
    assert raised_error_count == 15
    assert output == CircuitState(
        status=CircuitStatus.OPEN,
        last_failure=FooError("Boom!"),
        failure_count=15,
        timestamp=output.timestamp,
    )


@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_open_circuit__closed_on_recovery(backend, open_circuit_state):
    """Test that a circuit breaker closed after a successful call.

    GIVEN an open circuit breaker
    WHEN a successful call is made after the circuit breaker is open
    THEN the circuit breaker should closed.
    """
    from tripswitch import Tripswitch

    # Set the initial state to open
    backend.set("foo", open_circuit_state)

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    def foo(i: int) -> None:
        if i <= 10:
            raise FooError("Boom!")  # noqa: EM101

    raised_error_count = 0
    for i in range(26):
        with tripswitch:
            try:
                foo(i)
            except FooError:
                raised_error_count += 1

    output = backend.get("foo")

    assert i == 25
    assert raised_error_count == 11
    assert output == CircuitState(
        status=CircuitStatus.CLOSED,
        last_failure=None,
        failure_count=0,
        timestamp=output.timestamp,
    )


@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_monitor_decorator(backend, closed_circuit_state):
    """Test the `monitor` decorator."""
    from tripswitch import Tripswitch, monitor

    # Set the initial state to closed
    backend.set("foo", closed_circuit_state)

    class MyTripswitch(Tripswitch):
        EXPECTED_EXCEPTIONS = (FooError,)
        BACKEND = backend
        FAILURE_THRESHOLD = 10
        RECOVERY_TIMEOUT = 0.01  # Set a low recovery timeout for testing

    @monitor(cls=MyTripswitch)
    def foo(i: int) -> None:
        if i <= 10:
            pass
        elif 10 < i <= 20:  # 11 - 20
            raise FooError("Boom!")  # noqa: EM101
        else:  # 21 - 25
            pass

        return True

    raised_error_count = 0

    for i in range(26):
        try:
            foo(i)
        except FooError:  # noqa: PERF203
            raised_error_count += 1
        except CircuitBreakerError:
            time.sleep(0.02)  # Sleep slightly longer than the recovery timeout
    output = backend.get("foo")

    assert i == 25
    assert raised_error_count == 10
    assert output == CircuitState(
        status=CircuitStatus.CLOSED,
        last_failure=None,
        failure_count=0,
        timestamp=output.timestamp,
    )
