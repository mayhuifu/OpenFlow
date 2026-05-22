# OpenFlow — V5 Design (Lab Orchestration)

**Status:** Vision-level draft (plan deferred until V4 ships)
**Date:** 2026-05-22
**Supersedes / extends:** [`2026-05-22-openflow-v1-design.md`](./2026-05-22-openflow-v1-design.md), [`2026-05-22-openflow-v2-design.md`](./2026-05-22-openflow-v2-design.md), [`2026-05-22-openflow-v3-design.md`](./2026-05-22-openflow-v3-design.md), [`2026-05-22-openflow-v4-design.md`](./2026-05-22-openflow-v4-design.md)
**Audience:** RF engineering team + framework maintainers

> **Why vision-level:** V5 is four-plus milestones away. Its shape will be substantially informed by how V4 is actually used — the dashboard especially evolves with the data engineers want to see. This spec captures the **why** and the **rough what**, deliberately leaving implementation soft. A full executable plan lands once V4 ships and team usage patterns are visible.

---

## 1. What is V5?

V5 turns OpenFlow from a per-engineer-per-bench tool into **team-coordinated
lab infrastructure**. Three capabilities:

1. **Bench reservation** — engineers don't accidentally run conflicting
   tests on the same bench. A simple lock-by-engineer-name mechanism
   tied to the YAML config, plus a CLI / dashboard view of "who's on
   what bench right now."

2. **Multi-DUT parallel runs** — when a bench has multiple DUTs wired up
   (e.g. 4 U300 boards in a temperature chamber), the framework can
   schedule tests across all of them in parallel. Each DUT gets its own
   pytest session; results aggregate into a single report.

3. **Read-only web dashboard** — the V4 database gets a browser-facing
   query interface. Engineers see live test status (which bench is
   running what, current parametrize iteration, latest measurement) +
   historical trends + comparison views across DUTs.

V5 is **the platform layer**. It's where OpenFlow shifts from "tool RF
engineers use" to "infrastructure RF engineers depend on." The scope
correspondingly expands: V1-V4 were ~250-350 internal tests; V5 is more
like a small webapp + a scheduler + a queue.

---

## 2. V5 scope

### Why each capability matters

**Bench reservation.** Today there's no machine-readable answer to "is
this bench in use?" — engineers walk over to the rack or message each
other. As the team grows beyond 3-4 engineers, the coordination cost
goes up linearly. Reservation cuts it.

**Multi-DUT parallel runs.** RF testing is slow. A full TX EVM sweep
across power + modulation + band on one DUT can take hours. Running it
on 4 DUTs sequentially is days. Running it on 4 in parallel is the same
hours. Many test programs need this scale (yield testing, temperature
sweeps, lot-to-lot variation).

**Web dashboard.** V4 ships a CLI for trend queries. The CLI is good for
power users; engineers who only want to see "today's test results"
don't open a terminal. The dashboard is the discoverable, low-friction
view layer.

### Success criteria

V5 is "shipped" when **all** of the following hold:

1. **Bench reservation prevents conflicts.** Two engineers trying to
   start a test against the same bench (same `instruments.cmw100.resource`)
   simultaneously: the second gets a clear error pointing at the
   reserver and an option to wait or force-take. CLI: `openflow bench
   release` / `openflow bench status`.

2. **Multi-DUT parallel runs work.** With `dut.parallel:
   [u300_board_1, u300_board_2, ...]` in the YAML, `uv run pytest` runs
   the same test against each DUT concurrently. Results are tagged with
   the DUT identifier; the HTML report has per-DUT columns; the V4 DB
   has per-DUT rows.

3. **Dashboard shows live + historical.** A team engineer opens the
   dashboard URL in a browser and sees: which benches are reserved by
   whom, what test is currently running on each bench, current
   parametrize iteration + most recent measurement (refreshes ~5s),
   plus the V4 trend views from V4c.

4. **Read-only API for CI/CD integration.** A separate program (e.g.
   nightly regression dashboard, internal Slack bot) can hit a JSON
   endpoint to ask "list all tests run on board 131694 in the last 24h"
   without going through the database.

5. **CI green.** ≥450 internal tests passing including the dashboard
   server (httpx-based test client + recorded fixtures).

### Explicit non-goals for V5

- Multi-bench cross-correlation (still local-per-bench at the orchestration layer)
- Write API for the dashboard (no editing test data via the web)
- User authentication beyond shared-team-secret (auth is the next phase if needed)
- Mobile app
- ML/AI features (anomaly detection, suggested test ordering, etc.) — out of scope indefinitely
- Test scheduling / queue ("run these 20 tests overnight in this order") — could be added later but not in v1.0 of V5
- Anything that would make the framework require always-on cloud infrastructure

---

## 3. Architecture (sketch — to be sharpened in the plan)

### New components

V5 introduces three new components beyond the V1-V4 stack:

```
openflow/
├── bench/                       # NEW V5
│   ├── __init__.py
│   ├── reservation.py           # bench-reservation file-locks / DB-locks
│   └── cli.py                   # openflow bench {reserve,release,status}
├── parallel/                    # NEW V5
│   ├── __init__.py
│   ├── scheduler.py             # spawns N pytest sessions, aggregates results
│   └── coordinator.py           # cross-session locking on shared instruments
└── dashboard/                   # NEW V5 — separate runtime
    ├── __init__.py
    ├── server.py                # FastAPI or Flask app
    ├── api.py                   # /api/bench, /api/sessions, /api/trends
    ├── templates/               # HTML templates (Jinja2)
    └── static/                  # JS + CSS for the live view

scripts/
└── openflow-dashboard           # systemd unit / launch script
```

### Bench reservation

Two implementations, depending on V4's storage mode:

- **Local-only (SQLite mode):** reservation is a single file in `~/.openflow/reservations.json`. Atomic write + lock via `filelock`. Sufficient for single-server labs.
- **Shared (PostgreSQL mode):** reservation is a row in a `reservations` table with `acquired_by`, `acquired_at`, `expires_at`. Read by all dashboards + CLIs in the team.

CLI:
```sh
openflow bench reserve --resource "TCPIP::cmw1::INSTR" --for 4h --reason "RX gain re-baseline"
openflow bench release --resource "TCPIP::cmw1::INSTR"
openflow bench status
```

The pytest plugin gains a hook: before opening any instrument session,
check the reservation. If reserved by someone else, fail fast with a
message naming the reserver.

### Multi-DUT parallel runs

The hard part of multi-DUT is **safe instrument sharing**. If two
DUTs both want to talk to the same CMW100, they can't actually run in
parallel — they have to time-share. The framework handles this:

- **Per-DUT, exclusive instruments:** instruments listed under
  `dut.<dut_name>.instruments.{cmw100, ...}` belong only to that DUT.
  Tests run in true parallel.
- **Shared instruments:** instruments at the top-level `instruments.`
  block are shared. Tests acquire a per-instrument lock before
  measurement; effectively time-share.

The scheduler uses `pytest-xdist` for the multi-process execution
substrate (already a battle-tested test parallelization tool); OpenFlow
adds the bench-aware coordination layer on top.

### Web dashboard

- **Backend:** FastAPI (modern, typed, ASGI). Reads from V4's database.
  Read-only — no POST endpoints in V5.
- **Frontend:** Server-rendered HTML with HTMX for live updates. Avoid a
  full SPA framework — the dashboard's needs are simple enough that
  HTMX + a touch of Alpine.js handles it without a build pipeline.
- **Realtime:** Server-Sent Events (SSE) for the live test-progress
  view. The pytest plugin posts heartbeat events to a local socket; the
  dashboard reads from that socket.
- **Deployment:** Single binary via PyInstaller, or `uv run openflow
  dashboard serve` for the simple case. Aim for "one engineer can spin
  it up on their machine" rather than requiring kubernetes.

### Data flow

```
[engineer's test session]
       │
       ├─ writes report.json (V1)
       ├─ writes report.html (V2)
       ├─ writes to local SQLite + optional PostgreSQL (V4)
       └─ posts heartbeats to localhost:<port> (V5)
                                    │
                                    ▼
                          [openflow dashboard]
                                    │
                                    ▼
                          [team engineers' browsers]
```

---

## 4. Phase split (proposed; finalize after V4)

### V5a — Bench reservation

The simplest of the three. Ships with both local-only and
PostgreSQL-backed modes. Bench-aware pytest plugin hook.

### V5b — Multi-DUT parallel runs

The most engineering-heavy. Needs careful design around shared-instrument
coordination. Strong "stop here, don't ship V5b without engineer review
of the lock model" gate.

### V5c — Web dashboard

The most user-visible. Iterative — ship a minimum-viable dashboard
(static V4 query view), then layer the live-progress SSE updates, then
add the bench reservation view.

Sequencing: V5a → V5b in parallel with V5c → release.

---

## 5. Risks and unknowns

### Risk: scope blows up

A dashboard with auth, multi-tenant support, full historical query UI,
admin features, and real-time WebSockets is a 12-engineer-quarter
project. V5 needs to ship a *minimum* dashboard and resist creep.

**Mitigation:** The success criterion #3 above is explicit about what
"works" means. If the dashboard does more than what's listed, ship
those features in V6+.

### Risk: multi-DUT shared-instrument deadlock

If multiple sessions hold partial sets of shared-instrument locks and
each waits for the other's, the whole lab grinds to a halt. Classic
distributed-systems failure mode.

**Mitigation:** Sort shared-instrument lock acquisition by resource
name (consistent ordering across sessions); fail-fast with a timeout
rather than blocking indefinitely; add a `openflow bench abort-all`
escape hatch.

### Risk: bench reservation creates social friction more than it solves

If reservations are too easy to override ("just force-take it"), they
add a step without preventing conflicts. If they're too hard to override
("I have to ping someone to release it"), engineers go around the system
and stop reserving.

**Mitigation:** Default to "warn but allow force." Track force-takes in
the DB; if they're frequent the social problem outranks the technical
one.

### Risk: dashboard becomes the source of truth for things it shouldn't

The HTML report (V2) is the engineer-to-engineer artifact. The dashboard
view is the live monitoring tool. If engineers start sending dashboard
URLs in tickets instead of HTML reports, the artifact-vs-monitoring line
blurs.

**Mitigation:** Dashboard URLs are session-scoped and ephemeral by
default. The HTML report stays the durable archive.

### Risk: someone wants to write to the dashboard

V5 is read-only. The instant someone asks for "let me edit a verdict
from the dashboard," V5's scope balloons (auth, audit, undo, etc.).

**Mitigation:** Hold the line. Editing happens by re-running the test
with corrected config, not by clicking a button.

---

## 6. Open questions for engineering review (to revisit when V4 ships)

1. **How many concurrent benches do we plan for?** If the answer is
   "two", V5b's parallel-runs scope is much smaller (no real
   coordination layer needed — just YAML duplication). If "six+", the
   coordinator is unavoidable.

2. **Authentication / authorization story.** V5 ships read-only — does
   that need auth at all (LAN access ≈ trust)? If yes, what's the
   identity provider (LDAP, SSO, shared token)?

3. **Where does the dashboard run?** Engineer's laptop? Lab PC? Dedicated
   server? Affects whether systemd, Docker, or "just `uv run`" is the
   recommended pattern.

4. **Real-time data freshness expectations.** 1 second? 5 seconds?
   30 seconds? Affects whether SSE is overkill or right.

5. **Integration with the engineer's existing tooling.** Do they
   already have a Slack bot / JIRA integration / internal status page?
   Should the dashboard *replace* those or *feed* them via the
   read-only API?

6. **Mobile view.** Engineers in a temperature chamber pulling a phone
   out of their pocket — useful or out of scope?

---

## 7. Sequencing and release plan

After V4 ships (v0.10.0), V5 development sequence:

- **v1.0.0-alpha** (V5a — bench reservation)
- **v1.0.0-beta** (V5b — multi-DUT parallel runs; engineer review gate)
- **v1.0.0** (V5c — dashboard + integration)

The v1.0.0 milestone is significant: at that point OpenFlow has shipped
the full vision — bare-metal Python test framework + bulk migration
tool + complete instrument catalog + queryable history + team
orchestration. That's the "1.0" release as conceived in the V1 design.

Post-1.0 candidates (not specified here):
- ML-assisted regression detection
- Multi-bench load balancing / scheduling
- Cloud-hosted shared dashboard for distributed labs
- Test author auto-completion in IDEs (Python LSP-aware fixture introspection)

Those become the V6+ conversation, not V5.
