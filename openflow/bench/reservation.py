"""Bench reservation stores — local (file-locked JSON) and shared (V4 DB).

Both stores implement the same interface:

    store.reserve(resource, by, duration_s, reason=None)
        -> ReservationInfo on success
        -> raises ReservationConflict if an unexpired reservation by
           someone else already holds it
    store.release(resource)         -> None (no-op if not reserved)
    store.status()                  -> list[ReservationInfo]
    store.get(resource)             -> ReservationInfo | None

The conflict exception's message names the reserver + expiry so the
engineer sees who to talk to.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from filelock import FileLock


@dataclass
class ReservationInfo:
    """One active reservation row."""
    resource: str
    acquired_by: str
    acquired_at: datetime
    expires_at: datetime
    reason: str | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "acquired_by": self.acquired_by,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "reason": self.reason,
        }


class ReservationConflict(Exception):
    """Raised when an attempted reserve hits an active reservation by
    a different engineer."""

    def __init__(self, info: ReservationInfo) -> None:
        self.info = info
        super().__init__(
            f"{info.resource!r} reserved by {info.acquired_by} "
            f"until {info.expires_at.isoformat()}"
            + (f" — {info.reason}" if info.reason else "")
        )


# --- Local backend ---------------------------------------------------------

class LocalReservationStore:
    """JSON-file-backed reservation store. Cross-process-safe via
    ``filelock``. Single-server labs.

    The file holds a JSON object keyed by resource:

        {
          "TCPIP::cmw1::INSTR": {
            "acquired_by": "alice",
            "acquired_at": "2026-05-22T20:00:00",
            "expires_at": "2026-05-22T22:00:00",
            "reason": "TX EVM baseline"
          },
          ...
        }
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = FileLock(str(self.path) + ".lock")

    def reserve(self, resource: str, *, by: str, duration_s: int,
                reason: str | None = None) -> ReservationInfo:
        """Atomically check + insert. Raises ReservationConflict if held."""
        with self._lock:
            data = self._read()
            existing = data.get(resource)
            if existing is not None:
                info = self._info_from_dict(resource, existing)
                if not info.is_expired and info.acquired_by != by:
                    raise ReservationConflict(info)
            now = datetime.utcnow()
            info = ReservationInfo(
                resource=resource,
                acquired_by=by,
                acquired_at=now,
                expires_at=now + timedelta(seconds=duration_s),
                reason=reason,
            )
            data[resource] = {
                "acquired_by": info.acquired_by,
                "acquired_at": info.acquired_at.isoformat(),
                "expires_at": info.expires_at.isoformat(),
                "reason": info.reason,
            }
            self._write(data)
            return info

    def release(self, resource: str) -> None:
        with self._lock:
            data = self._read()
            data.pop(resource, None)
            self._write(data)

    def status(self) -> list[ReservationInfo]:
        """Return all current reservations (including expired — so engineers
        can see history)."""
        with self._lock:
            data = self._read()
        return [self._info_from_dict(r, d) for r, d in data.items()]

    def get(self, resource: str) -> ReservationInfo | None:
        with self._lock:
            data = self._read()
        if resource not in data:
            return None
        return self._info_from_dict(resource, data[resource])

    # --- internals --------------------------------------------------------
    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data: dict[str, dict[str, Any]] = json.loads(self.path.read_text())
            return data
        except json.JSONDecodeError:
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    @staticmethod
    def _info_from_dict(resource: str, d: dict[str, Any]) -> ReservationInfo:
        return ReservationInfo(
            resource=resource,
            acquired_by=d["acquired_by"],
            acquired_at=datetime.fromisoformat(d["acquired_at"]),
            expires_at=datetime.fromisoformat(d["expires_at"]),
            reason=d.get("reason"),
        )


# --- Shared backend --------------------------------------------------------

class SharedReservationStore:
    """SQLAlchemy-backed reservation store. Reads/writes the V4
    ``reservations`` table on either SQLite or PostgreSQL.

    Multi-bench shared labs point this at the team's shared DSN; all
    engineers see the same reservation state.
    """

    def __init__(self, db_path_or_dsn: str | Path) -> None:
        from sqlalchemy import create_engine

        if isinstance(db_path_or_dsn, Path) or (
                isinstance(db_path_or_dsn, str)
                and not db_path_or_dsn.startswith(("postgresql", "postgres"))):
            url = f"sqlite:///{db_path_or_dsn}"
        else:
            url = db_path_or_dsn
        self._engine = create_engine(url)
        # Ensure the schema (including the reservations table) is in place.
        from openflow.report.db.schema import metadata
        metadata.create_all(self._engine)

    def reserve(self, resource: str, *, by: str, duration_s: int,
                reason: str | None = None) -> ReservationInfo:
        from sqlalchemy import delete, insert, select

        from openflow.report.db.schema import reservations

        with self._engine.begin() as conn:
            row = conn.execute(
                select(reservations).where(reservations.c.resource == resource)
            ).mappings().first()
            if row is not None:
                info = ReservationInfo(
                    resource=row["resource"],
                    acquired_by=row["acquired_by"],
                    acquired_at=row["acquired_at"],
                    expires_at=row["expires_at"],
                    reason=row["reason"],
                )
                if not info.is_expired and info.acquired_by != by:
                    raise ReservationConflict(info)
                # Same engineer or expired — clear the old row.
                conn.execute(delete(reservations)
                             .where(reservations.c.resource == resource))
            now = datetime.utcnow()
            info = ReservationInfo(
                resource=resource,
                acquired_by=by,
                acquired_at=now,
                expires_at=now + timedelta(seconds=duration_s),
                reason=reason,
            )
            conn.execute(insert(reservations).values(
                resource=info.resource,
                acquired_by=info.acquired_by,
                acquired_at=info.acquired_at,
                expires_at=info.expires_at,
                reason=info.reason,
            ))
            return info

    def release(self, resource: str) -> None:
        from sqlalchemy import delete

        from openflow.report.db.schema import reservations
        with self._engine.begin() as conn:
            conn.execute(delete(reservations)
                         .where(reservations.c.resource == resource))

    def status(self) -> list[ReservationInfo]:
        from sqlalchemy import select

        from openflow.report.db.schema import reservations
        with self._engine.begin() as conn:
            rows = conn.execute(select(reservations)).mappings().all()
        return [ReservationInfo(
            resource=r["resource"],
            acquired_by=r["acquired_by"],
            acquired_at=r["acquired_at"],
            expires_at=r["expires_at"],
            reason=r["reason"],
        ) for r in rows]

    def get(self, resource: str) -> ReservationInfo | None:
        from sqlalchemy import select

        from openflow.report.db.schema import reservations
        with self._engine.begin() as conn:
            row = conn.execute(
                select(reservations).where(reservations.c.resource == resource)
            ).mappings().first()
        if row is None:
            return None
        return ReservationInfo(
            resource=row["resource"],
            acquired_by=row["acquired_by"],
            acquired_at=row["acquired_at"],
            expires_at=row["expires_at"],
            reason=row["reason"],
        )
