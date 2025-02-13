"""Tests for the Tripswitch class."""

from __future__ import annotations

import pytest
import redis

from tripswitch import providers
from tripswitch.tripswitch import CircuitStatus


@pytest.fixture
def fallback_function():
    """Return a simple callable."""
    return lambda x: x


class MockError(Exception):
    """A simple exception class for testing purposes."""

    def __eq__(self, other: MockError) -> bool:
        """Return True if the other object is an instance of MockError."""
        return isinstance(other, MockError)


def test_init(mocker, faker, fallback_function):
    """Test the initialization of a Tripswitch instance.

    GIVEN a name and a provider
    WHEN a Tripswitch is instantiated
    THEN the CircuitBreaker is initialized with the given kwargs
    THEN the name and provider are set
    """
    import circuitbreaker

    init_spy = mocker.spy(circuitbreaker.CircuitBreaker, "__init__")

    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_provider = mocker.Mock(spec=providers.RedisProvider)
    mock_expected_exceptions = (mocker.Mock(), mocker.Mock())

    instance = Tripswitch(
        mock_name,
        provider=mock_provider,
        fallback_function=fallback_function,
        expected_exception=mock_expected_exceptions,
    )

    init_spy.assert_called_once_with(
        instance, fallback_function=fallback_function, expected_exception=mock_expected_exceptions
    )

    assert instance.name == mock_name
    assert instance._provider == mock_provider


def test_init_from_provider__backend_set(mocker, faker):
    """Test the initialization of a Tripswitch instance from the backend state.

    GIVEN a name and a provider
    WHEN a Tripswitch is instantiated
    WHEN the provider has a state for the given name
    THEN the CircuitBreaker is initialized with the state from the provider
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = {
        "status": "open",
        "last_failure": ValueError,
        "failure_count": "100",
    }

    provider = providers.RedisProvider(client=mock_client)

    instance = Tripswitch(mock_name, provider=provider, failure_threshold=50)

    assert instance.state == CircuitStatus.OPEN.value
    assert instance.last_failure is ValueError
    assert instance.failure_count == 100
    assert instance.failure_threshold == 50


def test_init_from_provider__backend_not_set(mocker, faker):
    """Test the initialization of a Tripswitch instance from the backend state.

    GIVEN a name and a provider
    WHEN a Tripswitch is instantiated
    WHEN the provider has no state for the given name
    THEN the CircuitBreaker is initialized with the default state
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = {}

    provider = providers.RedisProvider(client=mock_client)

    instance = Tripswitch(mock_name, provider=provider, failure_threshold=50)

    assert instance.state == CircuitStatus.CLOSED.value
    assert instance.last_failure is None
    assert instance.failure_count == 0
    assert instance.failure_threshold == 50


def test_update_provider__error_updates_backend(mocker, faker):
    """Test the update to backend provider.

    GIVEN a Tripswitch instance
    WHEN the wrapped function is called
    WHEN an exception is raised
    THEN the state is updated in the provider
    THEN the last failure is set
    THEN the failure count is incremented
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = {
        "status": "closed",
        "last_failure": None,
        "failure_count": "100",
    }

    instance = Tripswitch(
        mock_name,
        provider=providers.RedisProvider(client=mock_client),
        failure_threshold=100,
        expected_exception=(MockError,),
    )

    exception = MockError("Boom!")

    def foo() -> None:
        raise exception

    with instance:
        foo()

    mock_client.hmset.assert_called_once_with(
        mock_name,
        {"status": CircuitStatus.OPEN, "last_failure": instance.last_failure, "failure_count": 101},
    )


def test_update_provider__non_error_updates_backend(mocker, faker):
    """Test the update to backend provider.

    GIVEN a Tripswitch instance
    WHEN the wrapped function is called
    WHEN an exception is raised
    THEN the state is updated in the provider
    THEN the last failure is set
    THEN the failure count is incremented
    """
    from tripswitch import Tripswitch

    mock_name = faker.word()
    mock_client = mocker.Mock(spec=redis.Redis)
    mock_client.hgetall.return_value = {
        "status": "closed",
        "last_failure": None,
        "failure_count": "0",
    }

    instance = Tripswitch(
        mock_name,
        provider=providers.RedisProvider(client=mock_client),
        failure_threshold=100,
        expected_exception=(MockError,),
    )

    def foo() -> None:
        pass

    with instance:
        foo()

    mock_client.hmset.assert_called_once_with(
        mock_name,
        {"status": CircuitStatus.CLOSED, "last_failure": None, "failure_count": 0},
    )
