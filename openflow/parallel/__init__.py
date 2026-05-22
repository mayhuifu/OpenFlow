"""V5b: multi-DUT parallel runs.

Two pieces:

* ``Coordinator`` — cross-session lock on shared instruments. Acquired
  in sorted order by resource name so concurrent sessions can't
  deadlock.
* ``ParallelConfig`` (in ``openflow.config``) — YAML schema for declaring
  multiple DUTs that run in parallel.

The actual parallel execution uses ``pytest-xdist`` (already a battle-
tested test parallelization framework). OpenFlow adds the bench-aware
coordination layer on top.
"""
from openflow.parallel.coordinator import Coordinator

__all__ = ["Coordinator"]
