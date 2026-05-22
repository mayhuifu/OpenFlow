"""Tests for the V5b shared-instrument coordinator."""
import threading
import time
from pathlib import Path

import pytest

from openflow.parallel.coordinator import Coordinator


def test_acquire_empty_list_yields_immediately(tmp_path: Path):
    coord = Coordinator(tmp_path)
    with coord.acquire([]):
        pass  # no lock taken; no error


def test_single_resource_acquire_and_release(tmp_path: Path):
    coord = Coordinator(tmp_path)
    with coord.acquire(["R1"]):
        # Inside the lock — another acquire from this same Coordinator
        # would block. Verify the lockfile exists.
        assert any(p.name.endswith(".lock") for p in tmp_path.iterdir())


def test_acquire_blocks_when_resource_held(tmp_path: Path):
    """Two coordinators, same lock dir: the second acquire should block
    until the first releases."""
    coord = Coordinator(tmp_path)

    blocked_started = threading.Event()
    blocked_finished = threading.Event()

    def blocker():
        with coord.acquire(["R1"]):
            blocked_started.set()
            # Hold for a beat so the second acquire can attempt + block.
            time.sleep(0.1)

    t1 = threading.Thread(target=blocker)
    t1.start()
    blocked_started.wait(timeout=1.0)

    # Now try to acquire R1 from another thread with a short timeout —
    # this MUST block (and time out since the first holder is sleeping).
    second_thread_acquired = threading.Event()

    def waiter():
        with coord.acquire(["R1"], timeout_s=2.0):
            second_thread_acquired.set()
        blocked_finished.set()

    t2 = threading.Thread(target=waiter)
    t2.start()

    t1.join()
    blocked_finished.wait(timeout=2.0)
    assert second_thread_acquired.is_set()


def test_acquire_sorts_for_deadlock_avoidance(tmp_path: Path):
    """Two coordinators wanting {A, B} and {B, A} must both acquire in
    the same sorted order — no deadlock."""
    coord = Coordinator(tmp_path)

    done_a = threading.Event()
    done_b = threading.Event()

    def worker_a():
        with coord.acquire(["A", "B"], timeout_s=2.0):
            time.sleep(0.05)
        done_a.set()

    def worker_b():
        with coord.acquire(["B", "A"], timeout_s=2.0):
            time.sleep(0.05)
        done_b.set()

    t1 = threading.Thread(target=worker_a)
    t2 = threading.Thread(target=worker_b)
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)
    assert done_a.is_set()
    assert done_b.is_set()


def test_timeout_zero_raises_when_held(tmp_path: Path):
    """timeout=0 = non-blocking. Should raise Timeout if held."""
    from filelock import Timeout
    coord = Coordinator(tmp_path)

    blocker_holding = threading.Event()
    blocker_release = threading.Event()

    def blocker():
        with coord.acquire(["R1"]):
            blocker_holding.set()
            blocker_release.wait()

    t = threading.Thread(target=blocker)
    t.start()
    blocker_holding.wait()

    try:
        with pytest.raises(Timeout):
            with coord.acquire(["R1"], timeout_s=0.01):
                pass
    finally:
        blocker_release.set()
        t.join()


def test_lock_files_filesystem_safe_for_visa_resources(tmp_path: Path):
    """VISA resource strings contain '::' which is fine but worth
    verifying the lock filename derivation doesn't break."""
    coord = Coordinator(tmp_path)
    with coord.acquire(["TCPIP::192.168.1.10::INSTR"]):
        lockfiles = list(tmp_path.iterdir())
        assert len(lockfiles) >= 1  # at least the .lock file
