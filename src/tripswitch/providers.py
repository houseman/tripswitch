"""Provider classes for the tripswitch package."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import asdict
from typing import TYPE_CHECKING, cast

from typing_extensions import TypeAlias

from .tripswitch import BackendState, CircuitStatus

if TYPE_CHECKING:
    import redis

    BackendClient: TypeAlias = redis.Redis


class StateNotFoundError(Exception):
    """An exception raised when a state is not found in the backend."""

    def __init__(self, name: str) -> None:
        """Initialize a new StateNotFoundError instance.

        :param name: The name of the circuit breaker instance.
        """
        super().__init__(f"State not found for circuitbreaker {name}.")


class _BaseBackedProvider(metaclass=ABCMeta):
    """Base class for all provider classes."""

    @abstractmethod
    def __init__(self, client: BackendClient) -> None:
        """Initialize a new provider instance.

        :param client: A backend client instance.
        :return: None
        :rtype: None
        """

    @abstractmethod
    def get_or_init(self, name: str) -> BackendState:
        """Initialize the backend.

        Return state if this is set, else initialize the backend.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype BackendState
        """

    @abstractmethod
    def get(self, name: str) -> BackendState:
        """Read state from the backend.

        If no state exists, raises a StateNotFoundError.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype BackendState | None
        :raises StateNotFoundError: If no state exists.
        """

    @abstractmethod
    def set(self, name: str, state: BackendState) -> None:
        """Update the backend.

        :param name: The name of the circuit breaker instance.
        :param state: The state of the circuit breaker.
        :return: None
        :rtype: None
        """


class RedisProvider(_BaseBackedProvider):
    """A provider that uses Redis as a backend."""

    def __init__(self, client: redis.Redis) -> None:
        """Initialize a new RedisProvider instance.

        :param client: A Redis client instance.
        """
        self._client = client

    def get_or_init(self, name: str) -> BackendState:
        """Initialize the Redis backend.

        Return state if this is set, else initialize the backend.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype: BackendState
        """
        # Return the persisted state if it exists.
        try:
            return self.get(name)
        except StateNotFoundError:
            # Persist a new state to the backend.
            self.set(
                name,
                BackendState(
                    status=CircuitStatus.CLOSED,
                    last_failure=None,
                    failure_count=0,
                ),
            )

            # Refresh the state from the backend.
            return self.get(name)

    def get(self, name: str) -> BackendState:
        """Read state from the Redis backend.

        If no state exists, raises a StateNotFoundError.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype: BackendState
        :raises StateNotFoundError: If no state exists.
        """
        if not (state := cast(dict, self._client.hgetall(name))):
            raise StateNotFoundError(name=name)

        # Return the persisted state.
        return BackendState(
            status=CircuitStatus(state["status"]),
            last_failure=state["last_failure"],
            failure_count=int(state["failure_count"]),
        )

    def set(self, name: str, state: BackendState) -> None:
        """Update the Redis backend.

        :param state: The state of the circuit breaker.
        :return: None
        :rtype: None
        """
        self._client.hmset(name, asdict(state))


BackedProvider: TypeAlias = _BaseBackedProvider
