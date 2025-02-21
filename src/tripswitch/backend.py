"""Provider classes for the tripswitch package."""

from __future__ import annotations

import pickle
from abc import ABCMeta, abstractmethod
from dataclasses import asdict
from typing import Generic, TypeVar, cast

import redis
import valkey
from pymemcache.client.base import Client as Memcache
from typing_extensions import TypeAlias

from .tripswitch import CircuitState, CircuitStatus

# Define a type variable to represent the backend client type.
ClientT = TypeVar("ClientT")
HashClientT = TypeVar("HashClientT", redis.Redis, valkey.Valkey)


class StateNotFoundError(Exception):
    """An exception raised when a state is not found in the backend."""

    def __init__(self, name: str) -> None:
        """Initialize a new StateNotFoundError instance.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.

        Returns
        -------
        None
        """
        super().__init__(f"State not found for circuitbreaker {name}.")


class _AbstractBackedProvider(Generic[ClientT], metaclass=ABCMeta):
    """Abstract class for all provider classes."""

    @abstractmethod
    def __init__(self, client: ClientT) -> None: ...

    @abstractmethod
    def get_or_init(self, name: str) -> CircuitState: ...

    @abstractmethod
    def get(self, name: str) -> CircuitState: ...

    @abstractmethod
    def set(self, name: str, state: CircuitState) -> None: ...


class _BaseBackendProvider(_AbstractBackedProvider[ClientT]):
    """A base provider class that implements common logic for backend operations."""

    def __init__(self, client: ClientT) -> None:
        """Initialize a new instance.

        Parameters
        ----------
        client : ClientT
            A backend client instance.

        Returns
        -------
        None
        """
        self._client: ClientT = client

    def get_or_init(self, name: str) -> CircuitState:
        """Initialize the backend.

        Return state if this is set, else initialize the backend.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.

        Returns
        -------
        CircuitState
            The state of the circuit breaker.
        """
        # Return the persisted state if it exists.
        try:
            return self.get(name)
        except StateNotFoundError:
            # Persist a new state to the backend.
            self.set(
                name,
                CircuitState(
                    status=CircuitStatus.CLOSED,
                    last_failure=None,
                    failure_count=0,
                ),
            )

            # Refresh the state from the backend.
            return self.get(name)


class _BaseHashKeyBackendProvider(_BaseBackendProvider[HashClientT]):
    """A base provider class that implements common logic for hash key backend operations."""

    def get(self, name: str) -> CircuitState:
        """Read state from the backend.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.

        Returns
        -------
        CircuitState
            The state of the circuit breaker.

        Raises
        ------
        StateNotFoundError
            If no state exists.
        """
        if not (state := cast(dict, self._client.hgetall(name))):
            raise StateNotFoundError(name=name)

        # Return the persisted state.
        return CircuitState(
            status=CircuitStatus(state["status"]),
            last_failure=state["last_failure"],
            failure_count=int(state["failure_count"]),
        )

    def set(self, name: str, state: CircuitState) -> None:
        """Update the backend.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.
        state : CircuitState
            The state of the circuit breaker.

        Returns
        -------
        None
        """
        self._client.hset(name, mapping=asdict(state))


class RedisProvider(_BaseHashKeyBackendProvider[redis.Redis]):
    """A provider that uses Redis as a backend."""


class ValkeyProvider(_BaseHashKeyBackendProvider[valkey.Valkey]):
    """A provider that uses Valkey as a backend."""


class MemcacheProvider(_BaseBackendProvider[Memcache]):
    """A provider that uses Memcache as a backend."""

    def get(self, name: str) -> CircuitState:
        """Read state from the Memcache backend.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.

        Returns
        -------
        CircuitState
            The state of the circuit breaker.

        Raises
        ------
        StateNotFoundError
            If no state exists.
        """
        if not (raw := self._client.get(name)):
            raise StateNotFoundError(name=name)

        # Return the persisted state.
        state: dict = pickle.loads(raw)  # noqa: S301
        return CircuitState(
            status=CircuitStatus(state["status"]),
            last_failure=state["last_failure"],
            failure_count=int(state["failure_count"]),
        )

    def set(self, name: str, state: CircuitState) -> None:
        """Update the Memcache backend.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.
        state : CircuitState
            The state of the circuit breaker.

        Returns
        -------
        None
        """
        self._client.set(name, pickle.dumps(asdict(state)))


BackedProvider: TypeAlias = _AbstractBackedProvider
