"""A circuit breaker that can share state between instances."""

from __future__ import annotations

import base64
import datetime
import functools
import pickle
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

import circuitbreaker as cb

if TYPE_CHECKING:
    from types import TracebackType

    from .backend import Backend


@dataclass
class CircuitState:
    """A dataclass for storing the state of a circuit breaker."""

    status: CircuitStatus
    last_failure: Exception | None
    failure_count: int
    timestamp: int

    def serialize(self) -> dict[str, str]:
        """Return the state as a dictionary containing serialized values.

        Returns
        -------
        dict
            The state as a dictionary.
        """
        return {
            "status": self.status.value,
            "last_failure": base64.b64encode(pickle.dumps(self.last_failure)).decode("utf-8"),
            "failure_count": str(self.failure_count),
            "timestamp": str(self.timestamp),
        }

    @classmethod
    def deserialize(cls, state: dict[str | bytes, str | bytes]) -> CircuitState:
        """Load the state from a dictionary containing serialised values.

        Parameters
        ----------
        state : dict
            The state as a dictionary.

        Returns
        -------
            None
        """
        # This is necessary if e.g. Redis is not configured with `decode_responses=True`
        decoded_state: dict[str, str] = {
            (key.decode("utf-8") if isinstance(key, bytes) else key): (
                value.decode("utf-8") if isinstance(value, bytes) else value
            )
            for key, value in state.items()
        }
        return cls(
            status=CircuitStatus(decoded_state["status"]),
            last_failure=pickle.loads(base64.b64decode(decoded_state["last_failure"])),  # noqa: S301
            failure_count=int(decoded_state["failure_count"]),
            timestamp=int(decoded_state["timestamp"]),
        )


class CircuitStatus(Enum):
    """The possible status of a circuit breaker."""

    CLOSED = cb.STATE_CLOSED  # Circuit is closed, calls are allowed.
    OPEN = cb.STATE_OPEN  # Circuit is open, calls are blocked.
    HALF_OPEN = cb.STATE_HALF_OPEN  # Circuit is half open, next call will be passed through.


class Tripswitch(cb.CircuitBreaker):
    """A circuit breaker that can share state between instances."""

    BACKEND: Backend | None = None

    def __init__(
        self,
        /,
        name: str,
        backend: Backend | None = None,
        *args: tuple,
        **kwargs: dict,
    ) -> None:
        """Initialize a new circuit breaker instance.

        Parameters
        ----------
        name : str
            The name of the circuit breaker instance.
        backend : Backend | None
            A backend for the circuit breaker.

        Returns
        -------
            None

        """
        super().__init__(*args, **kwargs)
        self._name = name
        self._backed = backend if backend is not None else self.BACKEND
        self._timestamp = 0

        # As this class instance is being initialized, we need to sync an initial state.
        self.sync(
            state=CircuitState(
                status=CircuitStatus.CLOSED,
                last_failure=None,
                failure_count=0,
                timestamp=self.timestamp,
            )
        )

    def sync(self, state: CircuitState) -> None:
        """Synchronize the given state to the backend.

        Returns
        -------
            None
        """
        self._set_timestamp()
        backend_state = self.backend.get_or_init(self._name, state)
        if state.timestamp > backend_state.timestamp:
            self.backend.set(self._name, state)
            return

        self._state = backend_state.status.value
        self._last_failure = backend_state.last_failure
        self._failure_count = backend_state.failure_count

    @property
    def backend(self) -> Backend:
        """Return the backend for the circuit breaker.

        Returns
        -------
        Backend
            The backend for the circuit breaker.
        """
        if self._backed is None:
            message = f"No backend was set for the circuit breaker {self.name}."
            raise ValueError(message)

        return self._backed

    @property
    def failure_threshold(self) -> int:
        """Return the failure threshold for the circuit breaker.

        Returns
        -------
        int
            The failure threshold for the circuit breaker.
        """
        return self._failure_threshold

    @property
    def timestamp(self) -> int:
        """Return the timestamp for the circuit breaker.

        This timestamp includes microseconds, as an integer.

        Returns
        -------
        float
            The timestamp for the circuit breaker.
        """
        return self._timestamp

    def _set_timestamp(self) -> None:
        """Set the timestamp for the circuit breaker.

        This sets the timestamp to the current timestamp including microseconds, as an integer.

        Returns
        -------
        None
        """
        self._timestamp = int(datetime.datetime.now(tz=None).timestamp() * 1_000_000)

    def __enter__(self) -> None:
        """Enter the circuit breaker context manager.

        This refreshed the state from backend before entering the context manager.
        """
        return super().__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Exit the circuit breaker context manager.

        This first calls the parent class's `__exit__` method, then updates the
        backend with the current state of the circuit breaker.

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

        self.sync(
            state=CircuitState(
                status=CircuitStatus(self.state),
                last_failure=self.last_failure,
                failure_count=self.failure_count,
                timestamp=self.timestamp,
            )
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
