"""Tests for the Tripswitch class."""

# ruff: noqa: ANN202
from __future__ import annotations

import pickle

import pytest
import redis
import valkey
from pymemcache.client import base as memcache

from tripswitch import backend as be
from tripswitch.tripswitch import CircuitState, CircuitStatus


class MockError(Exception):
    """A simple exception class for testing purposes."""

    def __eq__(self, other: MockError) -> bool:
        """Return True if the other object is an instance of MockError."""
        return isinstance(other, MockError)


@pytest.fixture
def fallback_function():
    """Return a simple callable."""
    return lambda x: x


@pytest.fixture
def mock_error():
    """Return a simple `MockError` instance."""
    return MockError("Boom!")


def test_init__valkey(mocker, faker, fallback_function):
    """Test the initialization of a Tripswitch instance.

    GIVEN a name and a backend
    WHEN a Tripswitch is instantiated
    THEN the CircuitBreaker is initialized with the given kwargs
    THEN the name and backend are set
    """
    import circuitbreaker

    init_spy = mocker.spy(circuitbreaker.CircuitBreaker, "__init__")

    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=valkey.Valkey)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.CLOSED, last_failure=None, failure_count=0
    ).serialize()

    backend = be.ValkeyProvider(client=mock_client)

    mock_expected_exceptions = (mocker.Mock(), mocker.Mock())

    instance = Tripswitch(
        mock_name,
        backend=backend,
        fallback_function=fallback_function,
        expected_exception=mock_expected_exceptions,
    )

    init_spy.assert_called_once_with(
        instance, fallback_function=fallback_function, expected_exception=mock_expected_exceptions
    )

    assert instance.name == mock_name
    assert instance._backed == backend


def test_init__memcache(mocker, faker, fallback_function):
    """Test the initialization of a Tripswitch instance.

    GIVEN a name and a backend
    WHEN a Tripswitch is instantiated
    THEN the CircuitBreaker is initialized with the given kwargs
    THEN the name and backend are set
    """
    import circuitbreaker

    init_spy = mocker.spy(circuitbreaker.CircuitBreaker, "__init__")

    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=memcache.Client)
    mock_client.get.side_effect = [
        None,
        pickle.dumps(
            {
                "status": "closed",
                "last_failure": None,
                "failure_count": "0",
            }
        ),
    ]
    backend = be.MemcacheProvider(client=mock_client)

    mock_expected_exceptions = (mocker.Mock(), mocker.Mock())

    instance = Tripswitch(
        mock_name,
        backend=backend,
        fallback_function=fallback_function,
        expected_exception=mock_expected_exceptions,
    )

    init_spy.assert_called_once_with(
        instance, fallback_function=fallback_function, expected_exception=mock_expected_exceptions
    )

    assert instance.name == mock_name
    assert instance._backed == backend


def test_init__provider_backend_state_is_set(mocker, faker):
    """Test the initialization of a Tripswitch instance from the backend state.

    GIVEN a name and a backend
    WHEN a Tripswitch is instantiated
    WHEN the backend has a state for the given name
    THEN the CircuitBreaker is initialized with the state from the backend
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.OPEN, last_failure=ValueError, failure_count=100
    ).serialize()

    backend = be.RedisProvider(client=mock_client)

    instance = Tripswitch(mock_name, backend=backend, failure_threshold=50)

    assert instance.state == CircuitStatus.OPEN.value
    assert instance.last_failure is ValueError
    assert instance.failure_count == 100
    assert instance.failure_threshold == 50


def test_init__provider_backend_state_not_set(mocker, faker):
    """Test the initialization of a Tripswitch instance from the backend state.

    GIVEN a name and a backend
    WHEN a Tripswitch is instantiated
    WHEN the backend has no state for the given name
    THEN the CircuitBreaker is initialized with the default state
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.side_effect = [
        {},
        CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0).serialize(),
    ]

    backend = be.RedisProvider(client=mock_client)

    instance = Tripswitch(mock_name, backend=backend, failure_threshold=50)

    assert instance.state == CircuitStatus.CLOSED.value
    assert instance.last_failure is None
    assert instance.failure_count == 0
    assert instance.failure_threshold == 50


def test_provider__none(faker):
    """Test the backend property.

    GIVEN a Tripswitch instance
    WHEN the backend is not set
    THEN a ValueError is raised
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()

    with pytest.raises(ValueError, match=f"No backend was set for the circuit breaker {mock_name}."):
        Tripswitch(mock_name)


def test_context_manager__closed__error__updates_backend__opens_circuit(mocker, faker, mock_error):
    """Test the update to backend.

    GIVEN a Tripswitch instance
    WHEN the wrapped function is called
    WHEN an exception is raised
    THEN the state is updated in the backend
    THEN the last failure is set
    THEN the failure count is incremented
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.CLOSED, last_failure=None, failure_count=100
    ).serialize()

    instance = Tripswitch(
        mock_name,
        backend=be.RedisProvider(client=mock_client),
        failure_threshold=100,
        expected_exception=(MockError,),
    )

    def foo():
        raise mock_error

    with instance:
        foo()

    mock_client.hset.assert_called_once_with(
        mock_name,
        mapping=CircuitState(
            status=CircuitStatus.OPEN, last_failure=instance.last_failure, failure_count=101
        ).serialize(),
    )


def test_context_manager__closed__non_error__updates_backend__circuit_stays_closed(mocker, faker):
    """Test the update to backend.

    GIVEN a Tripswitch instance
    WHEN the wrapped function is called
    WHEN an exception is raised
    THEN the state is updated in the backend
    THEN the last failure is set
    THEN the failure count is incremented
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.CLOSED, last_failure=None, failure_count=0
    ).serialize()

    instance = Tripswitch(
        mock_name,
        backend=be.RedisProvider(client=mock_client),
        failure_threshold=100,
        expected_exception=(MockError,),
    )

    def foo():
        pass

    with instance:
        foo()

    mock_client.hset.assert_called_once_with(
        mock_name,
        mapping=CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0).serialize(),
    )


def test_context_manager__open__non_error__updates_backend__circuit_closes(mocker, faker, mock_error):
    """Test the update to backend.

    GIVEN a Tripswitch instance
    WHEN the wrapped function is called
    WHEN an exception is raised
    THEN the state is updated in the backend
    THEN the last failure is set
    THEN the failure count is incremented
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.OPEN, last_failure=mock_error, failure_count=101
    ).serialize()

    instance = Tripswitch(
        mock_name,
        backend=be.RedisProvider(client=mock_client),
        failure_threshold=100,
        expected_exception=(MockError,),
    )

    def foo():
        pass

    with instance:
        foo()

    mock_client.hset.assert_called_once_with(
        mock_name,
        mapping=CircuitState(status=CircuitStatus.CLOSED, last_failure=None, failure_count=0).serialize(),
    )


def test_monitor_decorator(mocker, mock_error):
    """Test the `monitor` decorator."""
    from tripswitch import Tripswitch, monitor

    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = CircuitState(
        status=CircuitStatus.CLOSED, last_failure=None, failure_count=0
    ).serialize()

    class MyTripswitch(Tripswitch):
        EXPECTED_EXCEPTIONS = (MockError,)
        BACKEND = be.RedisProvider(mock_client)
        FAILURE_THRESHOLD = 1

    @monitor(cls=MyTripswitch)
    def foo():
        raise mock_error

    foo()

    mock_client.hset.assert_called_once_with(
        "foo",
        mapping=CircuitState(
            status=CircuitStatus.OPEN, last_failure=mock_error, failure_count=1
        ).serialize(),
    )
