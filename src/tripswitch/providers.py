"""Provider classes for the tripswitch package."""

from __future__ import annotations

import pickle
from abc import ABCMeta, abstractmethod
from dataclasses import asdict
from typing import TYPE_CHECKING, Union, cast

from typing_extensions import TypeAlias

from .tripswitch import BackendState, CircuitStatus

if TYPE_CHECKING:
    import pymemcache.client.base as memcache
    import redis
    import valkey

    BackendClient: TypeAlias = Union[redis.Redis, valkey.Valkey, memcache.Client]


class StateNotFoundError(Exception):
    """An exception raised when a state is not found in the backend."""

    def __init__(self, name: str) -> None:
        """Initialize a new StateNotFoundError instance.

        :param name: The name of the circuit breaker instance.
        """
        super().__init__(f"State not found for circuitbreaker {name}.")


class _AbstractBackedProvider(metaclass=ABCMeta):
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


class _BaseProvider(_AbstractBackedProvider):
    """A base provider class for backend."""

    def __init__(self, client: BackendClient) -> None:
        """Initialize a new instance.

        :param client: A client instance.
        """
        self._client = client  # pragma: no cover

    def get_or_init(self, name: str) -> BackendState:
        """Initialize the backend.

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
        """Read state from the backend.

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
        """Update the backend.

        :param state: The state of the circuit breaker.
        :return: None
        :rtype: None
        """
        self._client.hmset(name, asdict(state))


class RedisProvider(_BaseProvider):
    """A provider that uses Redis as a backend."""

    def __init__(self, client: redis.Redis) -> None:
        """Initialize a new RedisProvider instance.

        :param client: A Redis client instance.
        """
        self._client = client


class ValkeyProvider(_BaseProvider):
    """A provider that uses Valkey as a backend."""

    def __init__(self, client: valkey.Valkey) -> None:
        """Initialize a new ValkeyProvider instance.

        :param client: A Valkey client instance.
        """
        self._client = client


class MemcacheProvider(_BaseProvider):
    """A provider that uses Memcache as a backend."""

    def __init__(self, client: memcache.Client) -> None:
        """Initialize a new MemcacheProvider instance.

        :param client: A Memcache client instance.
        """
        self._client = client

    def get(self, name: str) -> BackendState:
        """Read state from the Memcache backend.

        If no state exists, raises a StateNotFoundError.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype: BackendState
        :raises StateNotFoundError: If no state exists.
        """
        if not (raw := self._client.get(name)):
            raise StateNotFoundError(name=name)

        # Return the persisted state.
        state: dict = pickle.loads(raw)  # noqa: S301
        return BackendState(
            status=CircuitStatus(state["status"]),
            last_failure=state["last_failure"],
            failure_count=int(state["failure_count"]),
        )

    def set(self, name: str, state: BackendState) -> None:
        """Update the Memcache backend.

        :param state: The state of the circuit breaker.
        :return: None
        :rtype: None
        """
        self._client.set(name, pickle.dumps(asdict(state)))


BackedProvider: TypeAlias = _AbstractBackedProvider
