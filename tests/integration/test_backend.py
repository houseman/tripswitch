"""Integration tests for RedisProvider."""

from __future__ import annotations

import pytest
from circuitbreaker import CircuitBreakerError
from pytest_lazy_fixtures import lf

from tripswitch.tripswitch import CircuitState, TripswitchState

from .errors import FooError


@pytest.fixture
def closed_circuit_state():
    """Fixture for closed circuit state."""
    return TripswitchState(status=CircuitState.CLOSED, last_failure=None, failure_count=0, timestamp=0)


@pytest.fixture
def open_circuit_state():
    """Fixture for open circuit state."""
    return TripswitchState(status=CircuitState.OPEN, last_failure=FooError(), failure_count=10, timestamp=0)


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


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.valkey
@pytest.mark.memcache
@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_backend__creates_initial_state(backend, closed_circuit_state):
    """Test that the backend creates an initial state.

    GIVEN a backend
    WHEN the backend is initialized
    THEN the backend should create an initial state.
    """
    from tripswitch import Tripswitch

    Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    output = backend.get("foo")

    assert output == closed_circuit_state


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.valkey
@pytest.mark.memcache
@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_closed_circuit__opens_past_threshold(backend, closed_circuit_state):
    """Test that a circuit breaker opens after exceeding the failure threshold.

    GIVEN a circuit breaker with a failure threshold of 10
    WHEN the circuit breaker is tripped 10 times
    THEN the circuit breaker should open.
    THEN the circuit breaker should raise CircuitbreakerError on subsequent calls
    """
    from tripswitch import Tripswitch

    # Set the initial state to closed
    closed_circuit_state.failure_count = 9
    backend.set("foo", closed_circuit_state)

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    @tripswitch
    def foo():
        raise FooError("Boom!")  # noqa: EM101

    circuit_open_error_count = 0
    raised_error_count = 0

    for _ in range(1, 11):
        try:
            foo()
        except CircuitBreakerError:  # noqa: PERF203
            circuit_open_error_count += 1
        except FooError:
            raised_error_count += 1

    output = backend.get("foo")

    assert raised_error_count == 1  # 9 + 1 = 10
    assert circuit_open_error_count == 9
    assert output == TripswitchState(
        status=CircuitState.OPEN,
        last_failure=FooError("Boom!"),
        failure_count=10,
        timestamp=output.timestamp,
    )


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.valkey
@pytest.mark.memcache
@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_open_circuit__call_raises_circuit_breaker_error(backend, open_circuit_state):
    """Test that a open circuit breaker raises a CircuitBreakerError.

    GIVEN an open circuit breaker
    WHEN a call is made after the circuit breaker is open
    THEN the circuit breaker should raise a CircuitBreakerError
    """
    from tripswitch import Tripswitch

    # Set the initial state to open
    backend.set("foo", open_circuit_state)

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    @tripswitch
    def foo(i: int):
        pass

    with pytest.raises(CircuitBreakerError):
        foo()

    output = backend.get("foo")

    assert output == open_circuit_state


@pytest.mark.integration
@pytest.mark.redis
@pytest.mark.valkey
@pytest.mark.memcache
@pytest.mark.parametrize("backend", [lf("redis_backend"), lf("valkey_backend"), lf("memcache_backend")])
def test_open_circuit__closes_after_recovery(backend, open_circuit_state):
    """Test that a open circuit breaker closes after the recovery timeout.

    GIVEN an open circuit breaker
    WHEN the recovery timeout is set to 0
    THEN the circuit breaker should close after the recovery timeout.
    """
    from tripswitch import Tripswitch, monitor

    # Set the initial state to closed
    backend.set("foo", open_circuit_state)

    class MyTripswitch(Tripswitch):
        EXPECTED_EXCEPTIONS = (FooError,)
        BACKEND = backend
        FAILURE_THRESHOLD = open_circuit_state.failure_count
        RECOVERY_TIMEOUT = 0

    @monitor(cls=MyTripswitch)
    def foo():
        pass

    foo()

    output = backend.get("foo")

    assert output == TripswitchState(
        status=CircuitState.CLOSED,
        last_failure=None,
        failure_count=0,
        timestamp=output.timestamp,
    )
