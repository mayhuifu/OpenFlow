"""Tests for V5a bench reservation stores (local + shared)."""
from pathlib import Path

import pytest

from openflow.bench.reservation import (
    LocalReservationStore,
    ReservationConflict,
    SharedReservationStore,
)


# Parametrize across both backends — they implement the same contract.
@pytest.fixture(params=["local", "shared"], ids=["local", "shared"])
def store(request, tmp_path: Path):
    if request.param == "local":
        return LocalReservationStore(tmp_path / "reservations.json")
    return SharedReservationStore(tmp_path / "test.db")


def test_reserve_returns_info(store):
    info = store.reserve("TCPIP::1::INSTR", by="alice",
                         duration_s=3600, reason="baseline")
    assert info.resource == "TCPIP::1::INSTR"
    assert info.acquired_by == "alice"
    assert info.reason == "baseline"
    assert not info.is_expired


def test_reserve_conflict_when_held_by_other(store):
    store.reserve("TCPIP::1::INSTR", by="alice", duration_s=3600)
    with pytest.raises(ReservationConflict) as exc:
        store.reserve("TCPIP::1::INSTR", by="bob", duration_s=3600)
    assert "alice" in str(exc.value)


def test_reserve_same_engineer_renews(store):
    store.reserve("TCPIP::1::INSTR", by="alice", duration_s=3600)
    # Alice can re-reserve her own resource (extends the duration).
    info = store.reserve("TCPIP::1::INSTR", by="alice", duration_s=7200,
                         reason="extend")
    assert info.acquired_by == "alice"
    assert info.reason == "extend"


def test_release_removes_reservation(store):
    store.reserve("TCPIP::1::INSTR", by="alice", duration_s=3600)
    store.release("TCPIP::1::INSTR")
    # Bob can now reserve.
    info = store.reserve("TCPIP::1::INSTR", by="bob", duration_s=3600)
    assert info.acquired_by == "bob"


def test_release_nonexistent_is_no_op(store):
    store.release("nonexistent")  # must not raise


def test_status_lists_active(store):
    store.reserve("R1", by="alice", duration_s=3600)
    store.reserve("R2", by="bob", duration_s=3600)
    rows = store.status()
    resources = {r.resource for r in rows}
    assert resources == {"R1", "R2"}


def test_status_empty(store):
    assert store.status() == []


def test_get_returns_info(store):
    store.reserve("R1", by="alice", duration_s=3600)
    info = store.get("R1")
    assert info is not None
    assert info.acquired_by == "alice"


def test_get_missing_returns_none(store):
    assert store.get("nope") is None


# --- expired-reservation behavior ----------------------------------------

def test_expired_reservation_does_not_block_new_one(store):
    """A reservation whose expires_at is in the past shouldn't block."""
    # Reserve for -1 second so it's already expired.
    store.reserve("R1", by="alice", duration_s=-1)
    # Bob can now reserve.
    info = store.reserve("R1", by="bob", duration_s=3600)
    assert info.acquired_by == "bob"


def test_expired_reservation_visible_in_status(store):
    store.reserve("R1", by="alice", duration_s=-1)
    rows = store.status()
    assert len(rows) == 1
    assert rows[0].is_expired


# --- local-specific: file-lock + persistence -----------------------------

def test_local_store_persists_across_instances(tmp_path: Path):
    path = tmp_path / "reservations.json"
    LocalReservationStore(path).reserve("R1", by="alice", duration_s=3600)
    # New instance — must see the existing reservation.
    rows = LocalReservationStore(path).status()
    assert len(rows) == 1
    assert rows[0].acquired_by == "alice"


def test_local_store_handles_missing_file_gracefully(tmp_path: Path):
    """First reserve creates the file."""
    path = tmp_path / "subdir" / "reservations.json"
    store = LocalReservationStore(path)
    assert store.status() == []
    store.reserve("R1", by="alice", duration_s=3600)
    assert path.exists()


def test_local_store_handles_corrupt_json(tmp_path: Path):
    """A corrupt JSON file shouldn't crash status()."""
    path = tmp_path / "reservations.json"
    path.write_text("not valid json")
    store = LocalReservationStore(path)
    assert store.status() == []  # treated as empty
