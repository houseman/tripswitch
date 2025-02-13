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


class _BaseBackedProvider(metaclass=ABCMeta):
    """Base class for all provider classes."""

    @abstractmethod
    def __init__(self, client: BackendClient) -> None:
        pass

    @abstractmethod
    def initialize(self, name: str) -> BackendState:
        pass

    @abstractmethod
    def update(self, name: str, state: BackendState) -> None:
        pass


class RedisProvider(_BaseBackedProvider):
    """A provider that uses Redis as a backend."""

    def __init__(self, client: redis.Redis) -> None:
        """Initialize a new RedisProvider instance.

        :param client: A Redis client instance.
        """
        self._client = client

    def initialize(self, name: str) -> BackendState:
        """Initialize the Redis backend.

        :param name: The name of the circuit breaker instance.
        :return: The state of the circuit breaker.
        :rtype: BackendState
        """
        backend_state = cast(dict, self._client.hgetall(name))

        # Return the persisted state if it exists.
        if backend_state:
            return BackendState(
                status=CircuitStatus(backend_state["status"]),
                last_failure=backend_state["last_failure"],
                failure_count=int(backend_state["failure_count"]),
            )

        # Create a new state if one does not exist.
        new_state = BackendState(
            status=CircuitStatus.CLOSED,
            last_failure=None,
            failure_count=0,
        )

        self._client.hmset(name, asdict(new_state))

        return new_state

    def update(self, name: str, state: BackendState) -> None:
        """Update the Redis backend.

        :param state: The state of the circuit breaker.
        :return: None
        :rtype: None
        """
        self._client.hmset(name, asdict(state))


BackedProvider: TypeAlias = _BaseBackedProvider
