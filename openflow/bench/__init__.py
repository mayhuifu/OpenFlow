"""V5a: bench reservation — prevents two engineers from running
conflicting tests on the same bench simultaneously.

Two stores share an interface:

* ``LocalReservationStore`` — JSON file + ``filelock`` for cross-process
  safety. Default for single-server labs.
* ``SharedReservationStore`` — row in the V4 ``reservations`` table.
  Use when the team's bench DSN is shared across engineers.

Both expose: ``reserve / release / status / get``.
"""
from openflow.bench.reservation import (
    LocalReservationStore,
    ReservationConflict,
    ReservationInfo,
    SharedReservationStore,
)

__all__ = [
    "LocalReservationStore",
    "ReservationConflict",
    "ReservationInfo",
    "SharedReservationStore",
]
