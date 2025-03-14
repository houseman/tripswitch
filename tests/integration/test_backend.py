"""Integration tests for RedisProvider."""

from __future__ import annotations

import pytest
from pytest_lazy_fixtures import lf

from tripswitch.tripswitch import CircuitState, CircuitStatus

from .errors import FooError


@pytest.fixture
def initial_circuit_state():
    """Fixture for initial circuit state."""
    return CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0, timestamp=0)


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
def test_redis__closed_circuit__opens_past_threshold(backend):
    """Integration tests for RedisProvider."""
    from tripswitch import Tripswitch

    tripswitch = Tripswitch("foo", backend=backend, expected_exception=FooError, failure_threshold=10)

    def foo(i: int) -> None:
        if i <= 10:
            pass
        else:
            raise FooError("Boom!")  # noqa: EM101

    for i in range(26):
        with tripswitch:
            foo(i)

    output = backend.get("foo")

    assert i == 25
    assert output == CircuitState(
        status=CircuitStatus.OPEN,
        last_failure=FooError("Boom!"),
        failure_count=15,
        timestamp=output.timestamp,
    )
