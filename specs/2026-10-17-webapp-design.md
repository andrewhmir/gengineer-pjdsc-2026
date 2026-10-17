# Hinigram Web Application — Design Specification

**Status:** proposed, awaiting maintainer review. Nothing in this document is implemented.
**Date:** 2026-10-17
**Scope:** the `webapp/` lane only. Firmware, data acquisition, and the research notebook are
out of scope and are referenced where the web application depends on them.

This is a **frozen design record** once approved, in the same sense as
[`2026-10-10-repo-bootstrap-design.md`](2026-10-10-repo-bootstrap-design.md): it records the
decision and the reasons for it, and later work is measured against it rather than editing
it. It is written to be read by a judge who has not seen the branch, and by a teammate who
has to finish the work in a week.

## 1. Context and goal

### 1.1 What this document decides

The repository bootstrap deferred the web framework (§9 of the bootstrap design; the lane
[`README.md`](../webapp/README.md) records the deferral). This document makes that decision
and describes the application that follows from it: a local, offline, single-process
dashboard for the Hinigram respiratory triage prototype, whose backend is itself drawn as a
graph of live API checks so that a fault is localised to a specific component.

Decisions taken here: the framework, the runtime shape, the data contracts, the detector
the UI renders, the five screens, the fault-localisation rules, and the acceptance criteria.

**A note on repository consistency.** Until the first implementation task lands,
[`webapp/README.md`](../webapp/README.md) still states that no framework has been chosen,
and [`tests/test_placeholders.py`](../tests/test_placeholders.py) still asserts that the lane
holds only two files. That is expected: the lane is updated in the same change that adds the
first code, not before. A reader who finds the contradiction should treat this document as
the decision and the lane README as not yet synchronised.

### 1.2 What the proposal asks the software to do

The five objectives in the submitted proposal map to the web lane as follows.

| Proposal objective | Target | What the web lane must show or do |
|---|---|---|
| (1) Data acquisition | 100 Hz, 3 Tx + 1 Rx, ≥ 95% delivery | Accept the frame stream, expose per-channel rate and delivery, and never hide a gap |
| (2) Signal processing | RR within 1 bpm of reference | Display RR with the window and method that produced it |
| (3) Multi-person separation | 3 subjects, RR within 2 bpm | One track per subject, clearly labelled, with no averaging across subjects |
| (4) Anomaly detection | ≥ 90% sensitivity, ≥ 85% precision | Show PLV, the decision rule, and the event it produced; show evaluation only from a generated artifact |
| (5) Real-time deployment | ≤ 2 s packet-to-alert | Display measured latency against the target, continuously |

The proposal's Phase 4 names a command-line dashboard (`rich`, `plotext`). This design
delivers a browser dashboard instead; §16 records the consequence for the write-up.

### 1.3 What this lane does not cover

- Extracting CSI from the ESP32 nodes, or the ESP-NOW channel plan. The application consumes
  a frame contract (§6.1) that the Rx node will emit; until that exists, the simulator and
  the replay fixture produce the same contract.
- The research study itself. The notebook (`D01_10-17_Gengineer.ipynb`) trains and evaluates
  the complex-valued `ResonanceNetwork` on EEG; it is not shipped in the dashboard and its
  results are not restated as the app's results.
- Clinical validation. This is a prototype; §12 and the UI copy say so on every route.

## 2. Requirements

Every requirement is testable and is traced to an acceptance criterion in §15.

| ID | Requirement | Traces to |
|---|---|---|
| REQ-101 | One command from a clean clone starts the app and prints its URL: `cd webapp && uv sync && uv run hinigram`. No Node, no build step, no network at run time. | O5, rubric reproducibility |
| REQ-102 | The app runs with **no hardware attached**, from a committed synthetic replay fixture and a simulator. | O2, rubric reproducibility |
| REQ-103 | Every clinical surface states its data source (`LIVE`, `REPLAY`, `SIM`). Simulated data must never look live. | Honesty rule, §12 |
| REQ-104 | The monitor shows up to three subjects, each with RR, PLV, amplitude, state, age of last update, and a 60 s rhythm strip. | O3, O5 |
| REQ-105 | Each subject has a detail page with the 3D phase-space torus and its 2D circular twin. | O4, §8 |
| REQ-106 | Alerts are listed with onset, rule, RR, PLV, and measured latency; the list exports to CSV. | O4, O5 |
| REQ-107 | The system page draws nine nodes and their data-flow edges; every check is a real HTTP probe with a 500 ms timeout or an explicit data-liveness check, timestamped. | Fault isolation |
| REQ-108 | A fault is reported as one root cause; downstream nodes are marked `unknown — blocked by X`, never `down`. | Fault isolation |
| REQ-109 | Packet age and packet-to-alert latency are shown against the 2 000 ms target. | O5 |
| REQ-110 | No patient identifiers are collected, stored, or rendered. Subjects are session-scoped `S1`–`S3`. | RA 10173, DATA.md |
| REQ-111 | The disclaimer "research prototype — not a medical device, not for diagnosis" appears on every route, in the page body, not only the footer. | Scope statement in the proposal |
| REQ-112 | Status is never encoded by colour alone; text and an icon carry the same information. Contrast meets WCAG 2.2 AA (≥ 4.5:1 body text). Keyboard reachable, visible focus. | Accessibility |
| REQ-113 | Demo controls can force tachypnea and apnea in simulator mode so the demo can be driven from the UI. Controls are absent in serial mode. | O4, O5 |
| REQ-114 | The test suite runs offline, with no hardware, deterministically, and completes in under 15 s. | Rubric reproducibility |
| REQ-115 | Evaluation numbers appear only from a generated artifact; no metric is typed into a template. When no artifact exists the page says "evaluation pending". | Honesty rule |
| REQ-116 | A method page states the pipeline, the detector, the thresholds, and their citations. | Rubric: sources |
| REQ-117 | The server binds `127.0.0.1` by default. Any other bind requires an explicit flag and prints a warning. | Privacy |
| REQ-118 | `webapp/` owns its dependency manifest and lockfile; the root `pyproject.toml` gains a `tool.uv.workspace` exclusion so root `uv sync` does not resolve it. | Bootstrap §4 |

## 3. Decisions

Each decision names the alternative that was rejected and why.

| # | Decision | Rejected alternative | Reason |
|---|---|---|---|
| D-1 | **FastAPI + Jinja2 + vanilla JS on canvas.** No Node toolchain. | React/Vite SPA; HTMX + Chart.js | The rubric weights clean-clone reproducibility highest. A judge with `uv` and the repository gets a running UI; a Node build adds a second toolchain, a lockfile, and a CI job, and fails the "no network at run time" spirit when assets come from a CDN. |
| D-2 | **One process, components mounted as health sub-resources, probed over real HTTP.** | Separate uvicorn processes; in-process function calls | Real HTTP exercises the path that actually fails (port, hang, 5xx) and keeps one command. Function calls cannot distinguish a hung service from a wrong probe. Separate processes cost a message bus and a launcher in a one-week build. |
| D-3 | **Complex Hopf oscillator per subject integrated with numpy RK4**; the notebook's torch `ResonanceNetwork` stays in the research lane. | Ship torch and load the trained bank | The live detector needs 1–3 oscillators, not 16–64; RK4 in numpy is exact enough at 100 Hz and removes a 2 GB dependency from the demo laptop. The Method page states the split so no reader confuses the study with the product. |
| D-4 | **3D torus drawn with a perspective projection on canvas.** No WebGL library. | Three.js; a 2D-only phase plot | The torus needs ~200 lines and no dependency, stays offline, and renders at 30 fps for 300 points. A 2D circular plot is not a fallback gimmick here: the resultant vector of the phase difference *is* the PLV, so the twin is shown alongside the torus, always. |
| D-5 | **Cascade suppression with a single verdict sentence.** | Per-node red/green only | Eight red nodes do not answer "is this the microcontroller or the backend". One root cause plus one action does. |
| D-6 | **Light clinical surfaces; dark surfaces only for engineering.** | Dark mode for everything; dark mode toggle | Clinical reading benefits from light surfaces and high contrast under room lighting. The dark ops panel is a semantic signal ("this is engineering, not patient data"), not a theme. No toggle in the MVP. |
| D-7 | **SQLite via the standard library, 24 h retention.** | Postgres; in-memory only | Events must survive a page reload without a service dependency. In-memory loses the audit trail a judge asks about. |
| D-8 | **Session-scoped subject IDs, no names, no video.** | Named patients; camera-assisted tracking | The Data Privacy Act prohibits real patient identifiers in a public repository and in the demo. The sensing model does not need identity. |

## 4. Runtime architecture

```
                    ┌──────────────────────────── one uvicorn process ───────────────────────────┐
                    │                                                                            │
 serial  ──┐        │  Source ──► inbox (ring buffers, 100 Hz)                                   │
 replay  ──┼────────┼────►│                                                                     │
 simulator ┘        │      └─► DSP loop (1 Hz): Hampel → unwrap → FastICA → Butterworth 0.2–0.5  │
                    │             └─► analyzer: per-subject Hopf (numpy RK4) → φ_breath, φ_osc,  │
                    │                   PLV, RR → rules (5 s epoch, 1 s hop) → state, event       │
                    │                          │                                                 │
                    │                          ├─► SQLite (events, checks)                      │
                    │                          ├─► SSE broadcast (1 Hz snapshot)                 │
                    │                          └─► /healthz/{ingest,dsp,analyzer,store,api}       │
                    │  prober (3 s): real HTTP GET, 500 ms timeout ──► /api/v1/topology           │
                    └────────────────────────────────────────────────────────────────────────────┘
```

Two background tasks run inside the app's lifespan: the **pipeline loop** (source read → DSP →
analyzer → rules → store → broadcast) and the **prober loop** (checks → topology cache). Both
are `asyncio` tasks; the DSP and ICA work is CPU-bound and runs in a worker thread
(`asyncio.to_thread`) so a slow window cannot stall SSE delivery.

Time budget for one cycle at 100 Hz × 3 nodes: parse < 5 ms, DSP on a 10 s window < 250 ms,
analyzer < 30 ms, rules < 1 ms. The measured latency is displayed, not assumed.

## 5. Module layout

```
webapp/
  pyproject.toml            own manifest; console script `hinigram`
  uv.lock                   locked
  README.md                 dated framework decision (updated in task 0)
  AGENTS.md                 lane rules, updated in task 0
  hinigram/
    __init__.py
    cli.py                  argument parsing, uvicorn launch, startup banner
    app.py                  app factory, lifespan, routes, SSE endpoint
    config.py               pydantic-settings, HINIGRAM_* env vars and CLI flags
    contracts.py            pydantic models for frame, state, trace, topology, event
    sources.py              Source protocol: SerialSource, ReplaySource, SimulatorSource
    pipeline/
      frames.py             frame parsing, per-channel counters, ring buffers
      dsp.py                Hampel, phase unwrap, FastICA, Butterworth bandpass, RR
      hopf.py               oscillator integration, Hilbert phase, PLV
      rules.py              epoch state machine, hysteresis, event creation
    topology/
      registry.py           node and edge definitions
      probes.py             HTTP probe with timeout, liveness checks, history
      diagnosis.py          root-cause rules, cascade suppression, verdict text
    store.py                SQLite schema, writes, retention, CSV export
    templates/              base, monitor, subject, system, events, method, error
    static/
      css/app.css           design tokens and components
      js/app.js             SSE client, formatting, table behaviour
      js/wave.js            rhythm strip rendering
      js/torus.js           torus geometry, projection, interaction
      js/rose.js            circular phase-difference plot
      js/system.js          graph layout and probe table
  fixtures/
    replay_session.jsonl    synthetic replay (small, labelled synthetic)
    scenarios.json          tachypnea / apnea demo definitions
  tests/                    pytest, offline, deterministic
```

Rules that keep this lane testable: `pipeline/` and `topology/` import no FastAPI; `app.py`
imports them. Routes stay thin enough to read in one screen. `static/js/*` holds no business
rule that a test needs to assert; the rules live in Python.

## 6. Data contracts

All timestamps are integer epoch milliseconds, UTC, and all durations are integer
milliseconds. Field names do not change without a version bump.

### 6.1 Frame (source → pipeline), JSON Lines

```json
{"v": 1, "t": 1792243200123, "tx": "tx2", "ch": 6, "seq": 84213,
 "rssi": -42.5, "amp": [12, 14, 9], "phase": [-31, 5, 77]}
```

`amp` and `phase` are per-subcarrier arrays; their length is not fixed by the contract. A
frame missing `v`, `t`, or `tx` is counted as malformed and never reaches the DSP. The
simulator, the replay fixture, and the future Rx firmware emit exactly this line.

### 6.2 State snapshot (`GET /api/v1/state`)

```json
{"generated_ms": 1792243211000, "mode": "sim",
 "subjects": [{"id": "S2", "rr_bpm": 26.4, "plv": 0.31, "amp_db": -12.4,
               "state": "distress", "rule": "tachypnea", "state_since_ms": 1792243170000,
               "age_ms": 600, "locked": false}],
 "alerts": [{"id": 17, "subject": "S2", "kind": "tachypnea", "onset_ms": 1792243170000,
             "rr_bpm": 26.4, "plv": 0.31, "latency_ms": 1300, "acknowledged": false}],
 "slo": {"packet_age_p95_ms": 96, "alert_latency_p95_ms": 1300, "target_ms": 2000},
 "health": {"status": "degraded", "ok": 8, "degraded": 1, "down": 0, "unknown": 0}}
```

`age_ms` is the age of the newest frame behind this subject's state. It is shown, never
hidden: a stale value rendered as fresh is the one failure mode a medical UI must not have.

### 6.3 Trace (`GET /api/v1/subjects/{id}/trace?window_s=30`)

```json
{"subject": "S2", "window_s": 30, "decim_hz": 10,
 "t": [0.0, 0.1, 0.2], "amp": [0.12, 0.14, 0.11],
 "phi_breath": [0.0, 0.31, 0.62], "phi_osc": [0.05, 0.30, 0.66],
 "plv": 0.31, "rr_bpm": 26.4, "amp_db": -12.4, "locked": false,
 "winding": 1.07, "no_breath": false}
```

`phi_*` are unwrapped radians, decimated to 10 Hz for transport. `winding` is the mean phase
rate ratio over the window; it is displayed as `1:1` when within 5% of 1.

### 6.4 Topology (`GET /api/v1/topology`)

```json
{"generated_ms": 1792243211000, "cadence_ms": 3000,
 "nodes": [{"id": "tx2", "kind": "hardware", "label": "TX-2", "status": "down",
            "checked_ms": 1792243210900, "latency_ms": null, "blocked_by": null,
            "detail": "0.0 Hz on channel 6", "history": ["ok", "ok", "down"]}],
 "edges": [{"from": "tx2", "to": "rx", "status": "down", "metric": "0.0 Hz"}],
 "diagnosis": {"code": "tx_silent", "severity": "degraded",
               "message": "TX-2 silent on channel 6; other nodes healthy.",
               "action": "Check node power and the channel-6 plan before restarting services.",
               "root_causes": ["tx2"]}}
```

Status is one of `ok`, `degraded`, `down`, `unknown`. `blocked_by` names the upstream node
whose failure makes this node's state unknowable.

### 6.5 Events CSV (`GET /events.csv`)

Header exactly:
`id,onset_iso,subject,kind,rr_bpm,plv,latency_ms,acknowledged`

No other column may be added without a privacy review: this file is the artifact most likely
to be opened outside the app.

## 7. Signal path and detector

### 7.1 Pipeline

1. **Parse** each line; drop malformed; increment per-channel counters.
2. **Ring buffer** per (tx, channel), 30 s at 100 Hz.
3. **Hampel filter** on the phase series (window 7, 3 MAD) to remove unwrapping spikes.
4. **Unwrap** phase along the time axis, per subcarrier; then reduce subcarriers by their
   first principal component to one series per transmitter.
5. **FastICA** over the three transmitter series to obtain up to three independent sources
   (the per-subject breathing). Whitening plus symmetric fixed-point iteration with a `tanh`
   nonlinearity, implemented in `dsp.py`; it is ~60 lines and is tested against a synthetic
   two-source mixture (§14).
6. **Butterworth bandpass** 0.2–0.5 Hz, 4th order, zero-phase (`sosfiltfilt`) — the proposal's
   respiratory band, 12–30 breaths per minute.
7. **Rate estimate**: dominant spectral peak on a 20 s window, with parabolic interpolation;
   reported with its window length.
8. **Amplitude**: RMS of the bandpassed source, converted to dB relative to full scale.

### 7.2 Oscillator and PLV

Per subject, one complex Hopf oscillator driven by the subject's bandpassed source `x(t)`:

```
dz/dt = (μ + iω) z − |z|² z + g·x(t),    μ = −0.5, ω = 2π·0.25, g = 1.0
```

integrated with RK4 at the frame rate (100 Hz); `x(t)` is normalised to unit RMS before it
enters the forcing, so `g` is dimensionless and not fitted per subject. `ω` is the natural
frequency at 15 breaths per minute; the forcing pulls it. Phase-locking value over a 10 s
window:

```
PLV = | mean_t exp( i ( φ_breath(t) − φ_osc(t) ) ) |
```

with `φ_breath` from the Hilbert transform of `x(t)` and `φ_osc = arg z(t)`. PLV is in
[0, 1]; 1 means a constant phase difference, 0 means no preferred difference. This is the
same quantity the research notebook computes as `|C_ij|`; the Method page says so and cites
Lachaux et al. (1999).

### 7.3 Decision rules

Epochs are 5 s with a 1 s hop. Thresholds are configuration, shown on the Method page, and
are prototype thresholds, not clinical ones.

| Condition | State | Event |
|---|---|---|
| PLV ≥ 0.60 and 8 ≤ RR ≤ 20 | Normal | — |
| 0.40 ≤ PLV < 0.60, or 20 < RR ≤ 24 | Watch | — |
| RR > 24 and PLV < 0.60 for 3 consecutive epochs | Distress (tachypnea) | `tachypnea` |
| Band power < −30 dB and no defined breath phase for ≥ 10 s | Distress (apnea) | `apnea` |
| No frame for > 5 s | Unknown | system fault, not a clinical event |

**Hysteresis:** a Distress state clears after 5 consecutive non-triggering epochs. One event is
written per onset, with `latency_ms` measured from the newest frame in the triggering epoch
to the event's `onset_ms`. Acknowledging an event records the acknowledgement; it does not
change the subject's state, because the physiology has not changed.

## 8. The phase-space torus

### 8.1 What it encodes

The breathing phase `θ_b = φ_breath mod 2π` and the oscillator phase `θ_o = φ_osc mod 2π` are
two angles, so the pair lives on a torus. The trajectory over the window is a curve on that
surface:

- **Locked** rhythm → the curve is a closed loop (winding 1:1): the same phase difference
  recurs every cycle, which is exactly what a high PLV measures.
- **Unlocking** → the curve drifts across the surface and never closes; the phase difference
  spreads, and PLV falls.
- **Apnea** → no breath phase exists. The torus is drawn empty with the caption "no
  detectable respiratory motion", never a fabricated curve.

This is the visual the proposal calls "a stable limit cycle (torus) in phase-space". The app
makes it literal, and it is the evidence for an alert rather than decoration beside it.

### 8.2 Geometry and rendering

Surface: standard torus, `P(u,v) = ((R + r cos v) cos u, (R + r cos v) sin u, r sin v)` with
`R = 1.0`, `r = 0.38`. Wireframe at 32 × 12 segments. Camera: yaw, pitch (clamped ±70°),
distance; perspective projection with `f = 520`, near plane 0.1.

Depth handling: wireframe and trajectory segments are painted back-to-front with alpha and
width scaled by depth, so the front of the surface occludes the back without a depth buffer.
Trajectory: up to 300 points, colour interpolated over time (cool → warm), 2 px nominal
width, a 4 px dot at the newest sample.

Interaction: drag to orbit, wheel to zoom, auto-rotate at 0.05 rad/s when idle, paused when
the tab is hidden (`visibilitychange`) and disabled under `prefers-reduced-motion`. Rendering
is capped at 30 fps and only redraws when the camera moves or a new snapshot arrives.

### 8.3 The 2D twin

Beside the torus, always: a circular histogram of `Δφ = φ_breath − φ_osc` over the window,
with the mean resultant vector drawn from the origin. **The length of that vector is the
PLV**, by definition, and its angle is the mean phase lag. When the 3D view is illegible on a
projector, this panel still carries the claim, and it teaches the definition to a judge in
one glance.

### 8.4 Failure modes and their display

| Condition | Display |
|---|---|
| Fewer than 5 s of window | Torus at rest with "collecting data (3.2 s)" |
| No breath phase, amplitude below floor | Torus empty, "no detectable respiratory motion", last winding value greyed |
| PLV high but RR out of band | Loop drawn normally; the caption names the rate fault, not the lock |
| WebGL-free browser | Nothing to do; canvas 2D is universal |
| Data stale > 5 s | Whole panel desaturated with a "stale" chip and the age |

## 9. Backend graph

### 9.1 Nodes and checks

| Node | Kind | Check | ok | degraded | down |
|---|---|---|---|---|---|
| `tx1`–`tx3` | hardware liveness | frames/s from Rx counters over 5 s | ≥ 90 Hz | 1–90 Hz | 0 Hz |
| `rx` | hardware liveness | age of last parsed frame; port state | ≤ 500 ms | ≤ 2 000 ms | > 2 000 ms or port closed |
| `ingest` | HTTP | `GET /healthz/ingest` (200 + queue depth < 80%) | as stated | queue ≥ 80% | timeout or 5xx |
| `dsp` | HTTP | `GET /healthz/dsp` (age of last completed window) | ≤ 3 s | ≤ 10 s | > 10 s |
| `analyzer` | HTTP | `GET /healthz/analyzer` (age of last PLV update) | ≤ 3 s | ≤ 10 s | > 10 s |
| `api` | HTTP | `GET /healthz/api` (self) | 200 | — | fail |
| `store` | HTTP | `GET /healthz/store` (write+read roundtrip) | < 50 ms | < 250 ms | error |

Each probe is `httpx.AsyncClient.get(url, timeout=0.5)` with one retry on timeout, run every
3 s on the loop thread pool. Results, including latency, are kept for the last 60 checks, so
a flapping node is visible as a dotted history rather than a momentary colour.

Edges (`tx1..3 → rx`, `rx → ingest`, `ingest → dsp`, `dsp → analyzer`, `analyzer → api`,
`api → store`, `api → browser`) carry the metric that proves flow: Hz, frame age, windows
processed, event write age, p95 latency.

### 9.2 Cascade suppression

The prober computes root faults first, then marks every descendant of a failed node `unknown`
with `blocked_by` set to the root cause. Of the nine nodes, one dead Rx therefore produces one
red node, five `unknown` nodes (`ingest`, `dsp`, `analyzer`, `api`, `store`), and one verdict —
not six red nodes that each claim a separate problem.

### 9.3 Diagnosis rules

First match wins. The verdict is one sentence plus one action; the graph is the evidence.

| Code | Condition | Verdict | Action |
|---|---|---|---|
| `api_down` | self check fails | The API is not answering. | Restart the process; the static error page names the last good check time. |
| `serial_lost` | `rx` down | USB link to the receiver is lost; detection is paused. | Reseat the Rx USB cable, then check the port name. |
| `no_frames` | `rx` ok, frames 0 for > 2 s | The receiver is connected but no CSI frames are arriving. | Check the ESP-NOW channel plan and Tx power. |
| `tx_silent` | one or more Tx at 0 Hz, others ok | TX-2 silent on channel 6; the rest of the system is healthy. | Check that node's power before touching software. |
| `all_tx_silent` | all Tx at 0 Hz | No transmitter is being heard at all. | Check the Tx nodes and the receiver's channel setting. |
| `dsp_stalled` | `dsp` stale while `ingest` ok | Windows are arriving but processing has stalled. | Look at the DSP log; the frames are not the problem. |
| `analyzer_stalled` | `analyzer` stale while `dsp` ok | Detection is paused; PLV is not updating. | Restart the analyzer task; subjects show `unknown`. |
| `store_failing` | `store` down | Events are not being persisted. | Check disk space and file permissions. |
| `slo_breach` | packet age p95 > 500 ms or alert latency p95 > 2 000 ms | SLO breach: lag at `<node>`. | Fix the named stage; the target is 2 s. |
| `healthy` | all ok | All checks passing; detection is running. | — |

## 10. Screens

Five routes, each with an explicit empty, stale, and simulated state.

### 10.1 `/` — Triage board (default)

Header: product/room label, live clock, source chip, connection state. Disclaimer bar.
Acuity strip (distress / watch / normal / unassigned counts). Table, sorted by acuity then
recency: subject ID, RR with unit, PLV with threshold bar, 60 s sparkline, state chip, age.
Below: the selected subject's rhythm strip and metrics. Footer strip: nine health checks as
compact pills, overall verdict, link to `/system`. Clicking a subject opens `/subject/{id}`.

### 10.2 `/subject/{id}` — Phase space

Large torus (left), 2D circular twin (right), rhythm strip and PLV-over-time beneath, the
active rule and its thresholds, and the subject's events. This is the page a judge is shown
when the demo flags someone.

### 10.3 `/system` — Backend graph

Dark engineering surface. The nine nodes laid out as the data flow (three Tx merging into
Rx, then the service chain, with the store hanging off the API), edges labelled with live
metrics, node status by dot + word, and the verdict banner at the top. Below: the probe table
with the last 60 checks per node, a "Run checks now" button, and the cadence plus timeout
statement. This page is the answer to "is it the microcontroller or the backend".

### 10.4 `/events` — Event log

Table of events with onset (absolute and relative), subject, kind, RR, PLV, latency,
acknowledged. Filter by kind. CSV download. Empty state explains what would create an event.

### 10.5 `/method` — Method and provenance

Pipeline diagram (text and SVG, no external assets), the PLV definition with the resultant
vector figure, thresholds and where they are configured, the evaluation section (artifact or
"pending"), the deviation notes (§16), and the citation list with APA entries matching
[`docs/SOURCES.md`](../docs/SOURCES.md).

## 11. Visual system

Tokens in `static/css/app.css`, one place only.

| Token | Value | Use |
|---|---|---|
| surface | `#eef1f5` | page background |
| card | `#ffffff` | clinical panels |
| ink / muted / faint | `#0e1a28` / `#5b6b7d` / `#8697a9` | body / secondary / tertiary text |
| line | `#dfe6ee` | borders and rules |
| accent | `#0d6e78` | selection, links, focus ring |
| ok / warn / crit | `#0f7b4f` / `#8f5600` / `#b3261e` | status, always with a word and a dot |
| ops / ops-line | `#0d1621` / `#22344a` | engineering surfaces only |

Type: system sans (`Inter` if present, else Segoe UI/Roboto/sans), 12.5 px base, 1.45 line
height, tabular numerals everywhere a number can change. RR is the largest number on any
card. Units are always rendered, never implied. Time is shown both absolutely (24 h) and
relatively ("42 s ago").

Status is double-encoded (dot + word) and never by colour alone. Red is reserved for clinical
distress and system failure; amber for watch and degraded; nothing else uses either. Focus is
visible at 2 px accent outline. Motion is limited to the live indicator and the torus; it
stops under `prefers-reduced-motion`.

## 12. Privacy, security, retention

- Bind `127.0.0.1`. A non-loopback `--host` prints a warning and is not the documented path.
- No authentication in the MVP because the app is single-operator and local; the Method page
  and the README say so plainly rather than implying security that does not exist.
- No identifiers: subject IDs are assigned per session, `S1`–`S3`, and are not persisted
  across sessions. No images, audio, names, or device identifiers are stored.
- SQLite file `webapp/.data/hinigram.db`, gitignored, WAL mode, 24 h retention, pruned on
  start and hourly. The event CSV carries no free-text field.
- Logs contain counters, node IDs, and timings, never frame payloads.

## 13. Configuration and commands

```
cd webapp
uv sync
uv run hinigram                       # simulator, http://127.0.0.1:8765
uv run hinigram --source replay       # committed synthetic fixture
uv run hinigram --source serial --port COM5
uv run pytest                         # lane suite
```

Flags and their `HINIGRAM_*` equivalents: `--source`, `--serial-port`, `--replay-file`,
`--host`, `--port`, `--demo` (enables demo controls), `--plv-threshold`, `--rr-max`,
`--epoch-s`, `--verbose`. Defaults are the values in §7.3.

## 14. Testing

Offline, deterministic, under 15 s, no hardware. Tests assert behaviour, not implementation.

| File | Cases |
|---|---|
| `test_dsp.py` | synthetic 15 bpm sine → RR within 1 bpm; 26 bpm → within 1; Hampel removes injected spikes but keeps the rhythm; bandpass rejects 0.05 Hz and 2 Hz; FastICA recovers two mixed sources with correlation > 0.95; PLV ≈ 1 for identical phase, ≈ 0 for randomised phase |
| `test_rules.py` | each rule's boundary; 3-epoch confirmation; hysteresis clear after 5 epochs; one event per onset; latency calculation from newest frame |
| `test_probes.py` | ok / timeout / 5xx via `httpx.MockTransport`; retry once; latency recorded; cascade suppression marks descendants `unknown` and names one root cause; verdict text per code |
| `test_contracts.py` | every endpoint's JSON validates against its pydantic model; CSV header exact; no extra columns |
| `test_store.py` | event roundtrip, acknowledgement, retention prune, WAL survives reopen |
| `test_sources.py` | simulator is deterministic for a seed; replay parses the committed fixture; serial parser handles a fragmented line and a malformed line |
| `test_templates.py` | every route renders 200 with the disclaimer and source chip; no `http://` or `https://` asset reference in any template; torus canvas present with `data-` attributes |
| `test_accessibility.py` | status text present alongside every status dot in rendered HTML; focus styles declared; no colour-only state class without a word |

The JS canvas modules are verified by the demo script and a visual check, not by a JS test
runner: adding Node would reverse D-1. This is a conscious tradeoff, recorded here.

## 15. Acceptance criteria

| ID | Criterion | How it is checked |
|---|---|---|
| AC-101 | From a clean clone: `cd webapp && uv sync && uv run hinigram` serves `http://127.0.0.1:8765`. | Manual, then documented in the lane README |
| AC-102 | `/`, `/system`, `/events`, `/method`, `/subject/S2` return 200 within 1 s of start. | `test_templates.py` |
| AC-103 | With the simulator set to 26 bpm, an event is written within 20 s, the subject shows Distress, and the recorded latency is ≤ 2 000 ms. | Scripted scenario test |
| AC-104 | With a source whose frames stop, `/system` marks `rx` down, descendants `unknown`, and the verdict names the USB link. | `test_probes.py` + scenario |
| AC-105 | With the analyzer task stopped, the verdict names the analyzer, not the microcontrollers. | Scenario test |
| AC-106 | No template references an external host. | `test_templates.py` |
| AC-107 | The CSV has the exact header of §6.5 and no identifier column. | `test_contracts.py` |
| AC-108 | Every route renders the disclaimer and the source chip. | `test_templates.py` |
| AC-109 | `uv run pytest` in `webapp/` passes offline in under 15 s. | CI |
| AC-110 | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` pass for `webapp/`. | CI |
| AC-111 | The Method page shows "evaluation pending" when the artifact is absent, and artifact values only when it is present. | `test_templates.py` |
| AC-112 | The torus renders 300 points at ≥ 30 fps on the demo laptop, and the 2D twin's vector length equals the reported PLV within 0.01. | Manual + `test_contracts.py` for the value |
| AC-113 | Root suite (`uv run pytest` at the repository root) still passes, with the placeholder test updated to the new lane shape. | CI |

## 16. Deviations from the proposal

Two, both of which the slide deck and the report must state.

1. **Dashboard: CLI → web.** The proposal specifies `rich` and `plotext`. The web dashboard is
   the delivered interface; the CLI is retained only as a headless fallback if the browser
   fails during the demonstration. The requirement it serves (a low-latency visual interface
   for triage personnel) is unchanged.
2. **Live detector: PyTorch → numpy RK4.** The proposal says "PyTorch solves this differential
   in real time". The live path integrates one oscillator per subject, where numpy RK4 is
   sufficient and costs no 2 GB dependency; the torch `ResonanceNetwork` remains the research
   implementation and the source of the reported study. The app does not claim to run the
   trained bank.

## 17. Deferred decisions

| Deferred | Reopens when |
|---|---|
| Authentication and multi-operator sessions | A second operator, or any non-loopback deployment |
| Multi-room / multi-receiver support | A second receiver node exists |
| HL7 FHIR or CSV exchange with a facility system | A facility asks, which is beyond the prototype |
| Real WebGL/Three.js scene | The canvas torus cannot carry the geometry needed |
| Persistent subject identity across sessions | Ethics approval and a consent process exist |
| Postgres or a time-series store | Event volume exceeds a day's retention window |
| Evaluation artifact generator | The detector evaluation notebook cell is written |
| Model registry / versioned checkpoints | A second trained model exists |

## 18. Risks and cut order

| Risk | Mitigation |
|---|---|
| No Rx firmware yet, so no live frames | The frame contract is the interface; simulator and replay exercise it identically. The serial path is one adapter, tested with a fake stream. |
| CSI payload differs from §6.1 | `v` field and a parser that rejects unknown versions loudly rather than silently mis-reading. |
| Torus illegible at 1280 × 720 on a projector | The 2D twin carries the claim; sizes are set for 720p from the first build. |
| Schedule: one week to submission | Cut order below; the demo spine never depends on a cut item. |
| FastICA convergence on real CSI | Falls back to per-transmitter tracks with a visible "separation unchecked" note rather than producing a confident wrong number. |

**Cut order when time runs short** (cut from the top): Method page → Events CSV export →
event acknowledgement → probe history sparklines → torus interaction (keep the static
render) → `/events` page (fold the last three events into the board). **Never cut:** the
monitor, the system verdict, the disclaimer, the source chip, the latency display.

## 19. Open items for the maintainer

1. Confirm the demo date; the plan assumes a working demo by 2026-10-23.
2. Confirm whether the Rx firmware will emit the §6.1 contract, or whether an adapter should
   be written for a different serial format.
3. Confirm that a synthetic replay fixture may live in `webapp/fixtures/` (labelled synthetic)
   rather than `data/samples/`, since it is application input rather than analysis data.
4. Confirm the subject count for the demo: three (proposal) or fewer if only two people can
   be seated in the demonstration.

## References

Full APA 7th Edition entries are recorded in
[`docs/SOURCES.md`](../docs/SOURCES.md), under *Web application and detection sources*; that
file is authoritative. This section names the works the design depends on and what each one
supports.

- Cretikos et al. (2008) — respiratory rate as the neglected vital sign, the problem the
  project addresses.
- Lachaux et al. (1999) — the phase-locking value, the detector's statistic in §7.2.
- Righetti, Buchli, & Ijspeert (2006) — adaptive Hopf oscillators, the model in §7.2.
- Hampel (1974) — the robust outlier filter in §7.1 step 3.
- Hyvärinen & Oja (2000) — FastICA, the separation step in §7.1 step 5.
- Wang et al. (2016); Liu et al. (2015); Soto et al. (2022) — CSI respiration sensing and its
  limits, the sensing assumptions the UI must not overstate.
- W3C (2023) — WCAG 2.2 AA, the basis of REQ-112.
- The research notebook `D01_10-17_Gengineer.ipynb` — the Resonance Network study whose
  notation and PLV definition the Method page follows. It is a team artifact, not a
  publication, and is cited as such.
