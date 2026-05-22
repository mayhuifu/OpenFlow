"""Abstract base for OpenFlow instrument drivers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class Instrument(ABC):
    """Minimal interface every OpenFlow instrument driver implements.

    Concrete drivers (e.g. CMW100) inherit from this and implement open/close/write/query.
    """

    def __init__(self, resource: str) -> None:
        self.resource = resource

    @abstractmethod
    def open(self) -> None:
        """Open the VISA (or other) session. Idempotent allowed but not required."""

    @abstractmethod
    def close(self) -> None:
        """Close the session and free resources."""

    @abstractmethod
    def write(self, scpi: str) -> None:
        """Send a SCPI command, no response expected."""

    @abstractmethod
    def query(self, scpi: str) -> str:
        """Send a SCPI command and return the device's text response."""

    def identify(self) -> str:
        """Return the response to ``*IDN?``."""
        return self.query("*IDN?")

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()
