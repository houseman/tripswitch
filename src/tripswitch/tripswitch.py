"""A circuit breaker that can share state between instances."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import circuitbreaker as cb

if TYPE_CHECKING:
    from types import TracebackType

    from .providers import BackedProvider


@dataclass
class BackendState:
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

    NAMESPACE: str

    def __init__(
        self,
        /,
        name: str,
        provider: BackedProvider,
        *args: tuple,
        **kwargs: dict,
    ) -> None:
        """Initialize a new circuit breaker instance.

        :param name: The name of the circuit breaker instance.
        :param provider: A backend provider for the circuit breaker.
            :return: None
            :rtype: None
        """
        super().__init__(*args, **kwargs)
        self._name = name
        self._provider = provider
        self.init_from_backend_provider()

    def init_from_backend_provider(self) -> None:
        """Initialize the circuit breaker from the backend provider.

        :return: None
        :rtype: None
        """
        state = self._provider.get_or_init(self._name)
        self._state = state.status.value
        self._last_failure = state.last_failure
        self._failure_count = state.failure_count

    @property
    def failure_threshold(self) -> int:
        """Return the failure threshold for the circuit breaker.

        :return: The failure threshold for the circuit breaker.
        :rtype: int
        """
        return self._failure_threshold

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> bool:
        """Exit the circuit breaker context manager.

        This first calls the parent class's `__exit__` method, then updates the
        backend provider with the current state of the circuit breaker.

        :param exc_type: The type of the exception raised.
        :param exc_value: The exception raised.
        :param _traceback: The traceback of the exception.
        :return: True if no error occurred, False otherwise.
        :rtype: bool
        """
        super().__exit__(exc_type, exc_value, _traceback)

        self._provider.set(
            name=self.name,
            state=BackendState(
                status=CircuitStatus(self.state),
                last_failure=self.last_failure,
                failure_count=self.failure_count,
            ),
        )

        if exc_type is not None:
            return self.is_failure(exc_type, exc_value)

        return True
