"""A circuit breaker that can share state between instances."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

import circuitbreaker as cb

if TYPE_CHECKING:
    from types import TracebackType

    from .backend import BackedProvider


@dataclass
class CircuitState:
    """A dataclass for storing the state of a circuit breaker."""

    status: CircuitStatus
    last_failure: Exception | None
    failure_count: int


class CircuitStatus(Enum):
    """The possible status of a circuit breaker."""

    CLOSED = cb.STATE_CLOSED
    OPEN = cb.STATE_OPEN
    HALF_OPEN = cb.STATE_HALF_OPEN


class Tripswitch(cb.CircuitBreaker):
    """A circuit breaker that can share state between instances."""

    BACKEND: BackedProvider | None = None

    def __init__(
        self,
        /,
        name: str,
        provider: BackedProvider | None = None,
        *args: tuple,
        **kwargs: dict,
    ) -> None:
        """Initialize a new circuit breaker instance.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.
        provider : BackedProvider | None
            A backend provider for the circuit breaker.

        Returns
        -------
            None

        """
        super().__init__(*args, **kwargs)
        self._name = name
        self._provider = provider if provider is not None else self.BACKEND
        self.init_from_backend_provider()

    def init_from_backend_provider(self) -> None:
        """Initialize the circuit breaker from the backend provider.

        Returns
        -------
            None
        """
        state = self.provider.get_or_init(self._name)
        self._state = state.status.value
        self._last_failure = state.last_failure
        self._failure_count = state.failure_count

    @property
    def provider(self) -> BackedProvider:
        """Return the backend provider for the circuit breaker.

        Returns
        -------
        BackedProvider
            The backend provider for the circuit breaker.
        """
        if self._provider is None:
            message = f"No provider was set for the circuit breaker {self.name}."
            raise ValueError(message)

        return self._provider

    @property
    def failure_threshold(self) -> int:
        """Return the failure threshold for the circuit breaker.

        Returns
        -------
        int
            The failure threshold for the circuit breaker.
        """
        return self._failure_threshold

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the circuit breaker context manager.

        This first calls the parent class's `__exit__` method, then updates the
        backend provider with the current state of the circuit breaker.

        Parameters
        ----------
        exc_type : type[BaseException]
            The type of the exception raised.
        exc_value : BaseException | None
            The exception raised.
        traceback : TracebackType | None
            The traceback of the exception.

        Returns
        -------
        bool
            True if no error occurred, False otherwise.
        """
        super().__exit__(exc_type, exc_value, traceback)

        self.provider.set(
            name=self.name,
            state=CircuitState(
                status=CircuitStatus(self.state),
                last_failure=self.last_failure,
                failure_count=self.failure_count,
            ),
        )

        if exc_type is not None:
            return self.is_failure(exc_type, exc_value)

        return True


def monitor(*, cls: type[Tripswitch] = Tripswitch) -> Callable[..., Any]:
    """Return a Tripswitch circuit breaker decorator.

    Parameters
    ----------
    cls : type[Tripswitch]
        The class to use for the circuit breaker.

    Returns
    -------
    Callable[..., Any]
        A decorator for the circuit breaker.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: tuple, **kwargs: dict) -> Callable[..., Any]:
            return cb.circuit(cls=cls, name=func.__name__)(func)(*args, **kwargs)

        return wrapper

    return decorator
