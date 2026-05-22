"""Cross-session shared-instrument coordinator.

When multiple pytest-xdist workers share an instrument (e.g. one CMW100
serving 4 parallel DUT sessions), each worker must wait its turn to
talk to that instrument. Without coordination, two workers can write
SCPI commands at the same time and the instrument's behavior becomes
undefined.

The Coordinator uses per-resource ``filelock`` instances. Two workers
both wanting the same resource block; the lock file lives at
``<lock_dir>/<resource-hash>.lock``.

Deadlock avoidance: workers always acquire locks in sorted resource-name
order. If worker A wants {CMW100, SA} and worker B wants {SA, CMW100},
both sort to (CMW100, SA) and acquire in that order — no circular wait.

Usage:

    coord = Coordinator(lock_dir=Path("/tmp/openflow-locks"))
    with coord.acquire(["TCPIP::cmw1::INSTR", "TCPIP::sa1::INSTR"]):
        # Both locks held; safe to drive both instruments.
        cmw100.setup_NrTx(...)
        sa.set_center_frequency(...)
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


class Coordinator:
    """Per-resource lock manager for shared-instrument coordination."""

    def __init__(self, lock_dir: Path | str) -> None:
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def acquire(self, resources: list[str],
                timeout_s: float = -1.0) -> Iterator[None]:
        """Acquire all the named resource locks in sorted order, then
        release on exit. ``timeout_s=-1`` waits forever; ``timeout_s=0``
        is non-blocking (raises Timeout if any lock is held).
        """
        if not resources:
            yield
            return
        # Sort for deadlock avoidance.
        sorted_resources = sorted(resources)
        locks = [self._lock_for(r) for r in sorted_resources]
        acquired: list[FileLock] = []
        try:
            for lock in locks:
                lock.acquire(timeout=timeout_s)
                acquired.append(lock)
            yield
        finally:
            for lock in reversed(acquired):
                lock.release()

    def _lock_for(self, resource: str) -> FileLock:
        """Map a resource name to its per-process lockfile."""
        # Hash so resource strings with slashes / VISA syntax become
        # filesystem-safe.
        digest = hashlib.sha1(resource.encode("utf-8")).hexdigest()[:16]
        return FileLock(str(self.lock_dir / f"{digest}.lock"))
