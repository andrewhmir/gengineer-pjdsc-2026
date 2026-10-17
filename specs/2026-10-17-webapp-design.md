# Hinigram Web Application — Design Specification

**Status:** proposed, awaiting maintainer review. Nothing in this document is implemented.
**Date:** 2026-10-17 (revised from the same-day bay-monitoring draft)
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
and describes the application that follows from it: a **self-service respiratory screening
station**. One person stands on a marked spot in front of a three-transmitter ESP32 array,
presses Start, and thirty seconds later reads one of three outcomes — breathing looks
regular, irregular breathing (speak to the nurse), or the reading was not clear (try again).

The application has a second, completely different audience: the people running it. A staff
surface draws the backend as a graph whose edges are live API checks, so a fault is attributed
to a node, the receiver link, or a service rather than blamed on "the system" — and a method
page states the pipeline, the thresholds, and their sources.

Decisions taken here: the framework, the runtime shape, the session state machine, the data
contracts, the detector, the station scene, the staff surfaces, and the acceptance criteria.

**A note on repository consistency.** Until the first implementation task lands,
[`webapp/README.md`](../webapp/README.md) still states that no framework has been chosen, and
[`tests/test_placeholders.py`](../tests/test_placeholders.py) still asserts that the lane holds
only two files. That is expected: the lane is updated in the same change that adds the first
code, not before. A reader who finds the contradiction should treat this document as the
decision and the lane README as not yet synchronised.

### 1.2 What the proposal asks the software to do

| Proposal objective | Target | What the web lane does |
|---|---|---|
| (1) Data acquisition | 100 Hz, 3 Tx + 1 Rx, ≥ 95% delivery | Accepts the frame stream, exposes per-channel rate, never hides a gap |
| (2) Signal processing | RR within 1 bpm of reference | Reports RR with the window and method that produced it |
| (3) Multi-person separation | 3 subjects, within 2 bpm | **Not demonstrated by the app.** The station screens one person at a time; separation stays an offline result on public CSI data, and §16 says how the write-up must present that |
| (4) Anomaly detection | ≥ 90% sensitivity, ≥ 85% precision | Shows the decision rule and the event it produced; evaluation only from a generated artifact |
| (5) Real-time deployment | ≤ 2 s packet-to-alert | Shows measured latency against the target on the staff surface |

The proposal's Phase 4 names a command-line dashboard (`rich`, `plotext`). This design delivers
a browser application instead; §16 records the consequence for the write-up.

### 1.3 What this lane does not cover

- Extracting CSI from the ESP32 nodes, or the ESP-NOW channel plan. The application consumes
  the frame contract (§6.1) that the Rx node emits; until that exists, the simulator and the
  replay fixture produce the same contract.
- The research study. The notebook (`D01_10-17_Gengineer.ipynb`) trains and evaluates the
  complex-valued `ResonanceNetwork` on EEG; it is not shipped in the station and its results
  are not restated as the station's results.
- Clinical validity. This is a prototype; §12 and the on-screen copy say so plainly.

## 2. Requirements

Every requirement is testable and is traced to an acceptance criterion in §15.

| ID | Requirement | Traces to |
|---|---|---|
| REQ-101 | One command from a clean clone starts the app and prints its URL: `cd webapp && uv sync && uv run hinigram`. No Node, no build step, no network at run time. | O5, rubric reproducibility |
| REQ-102 | The station runs with **no hardware attached**, from a committed synthetic replay fixture and a simulator. | O2, rubric reproducibility |
| REQ-103 | Every clinical surface states its data source (`LIVE`, `REPLAY`, `SIM`). Simulated data must never look live. | Honesty rule, §12 |
| REQ-104 | The station measures **one person per session**: idle → settle → 30 s capture → result. A session cannot be in two states at once. | O1, O2, O5 |
| REQ-105 | **Nothing is measured before an explicit Start press.** There is no passive capture, no background session, and no recording on the idle screen. | Privacy, consent |
| REQ-106 | The result is one of exactly three outcomes — `regular`, `irregular`, `unclear` — plus the RR and the rule that produced it. Patient-facing copy exists for all three. | O4, §7.3 |
| REQ-107 | The staff surface draws nine nodes and their data-flow edges; every check is a real HTTP probe with a 500 ms timeout or an explicit data-liveness check, timestamped. | Fault isolation |
| REQ-108 | A fault is reported as one root cause; downstream nodes are marked `unknown — blocked by X`, never `down`. | Fault isolation |
| REQ-109 | Packet age and packet-to-alert latency are shown against the 2 000 ms target. | O5 |
| REQ-110 | No patient identifiers are collected, stored, or rendered. Sessions are random IDs; the default store keeps aggregate counts only. | RA 10173, DATA.md |
| REQ-111 | The disclaimer — research prototype, not a diagnosis — appears on the idle screen, on every result, and on every staff route. | Proposal scope statement |
| REQ-112 | Patient-facing text is at least 16 px, primary actions at least 56 px tall, status never encoded by colour alone, contrast meets WCAG 2.2 AA. | Accessibility |
| REQ-113 | Demo controls can force tachypnea, apnea and an unclear reading in simulator mode so the demonstration is reproducible. Controls are absent in serial mode. | O4, O5 |
| REQ-114 | The test suite runs offline, with no hardware, deterministically, and completes in under 15 s. | Rubric reproducibility |
| REQ-115 | Evaluation numbers appear only from a generated artifact; no metric is typed into a template. When no artifact exists the page says "evaluation pending". | Honesty rule |
| REQ-116 | A method page states the pipeline, the detector, the thresholds, and their citations. | Rubric: sources |
| REQ-117 | The server binds `127.0.0.1` by default. Any other bind requires an explicit flag and prints a warning. | Privacy |
| REQ-118 | `webapp/` owns its dependency manifest and lockfile; the root `pyproject.toml` gains a `tool.uv.workspace` exclusion so root `uv sync` does not resolve it. | Bootstrap §4 |
| REQ-119 | The station scene never claims to see the patient. The figure is an abstract guide, no camera is involved, and the caption says so. | Honesty rule, §8.1 |
| REQ-120 | A staff result view shows the phase-space torus and its 2D circular twin for the finished session, reachable from the result's staff details. | O4, §8.2 |
| REQ-121 | A session ends at Done or after 20 s on the result screen, and returns the station to idle. The next person never inherits the previous result. | Privacy, O5 |
| REQ-122 | A motion or low-quality reading produces `unclear` with a retry path, never a confident `regular` or `irregular`. | O4 |

## 3. Decisions

| # | Decision | Rejected alternative | Reason |
|---|---|---|---|
| D-1 | **FastAPI + Jinja2 + vanilla JS on canvas.** No Node toolchain. | React/Vite SPA; HTMX + Chart.js | The rubric weights clean-clone reproducibility highest. A judge with `uv` and the repository gets a running station; a Node build adds a second toolchain, a lockfile and a CI job, and a CDN asset breaks the offline requirement. |
| D-2 | **One process, components mounted as health sub-resources, probed over real HTTP.** | Separate uvicorn processes; in-process calls | Real HTTP exercises the path that actually fails (port, hang, 5xx) and keeps one command. Function calls cannot distinguish a hung service from a wrong probe. |
| D-3 | **A session state machine, not a continuous monitor.** | Three-bed continuous monitoring; a free-running page | A screening station answers one question per person and then resets. A continuous monitor invites passive surveillance, which is a privacy problem this project cannot justify. |
| D-4 | **Explicit Start; no capture before it.** | Presence-triggered auto-start | Auto-start measures people who did not consent. The kiosk measures only after a deliberate press. |
| D-5 | **Single-subject detector: no FastICA on the live path.** | Run ICA over three transmitters in the demo | With one person in the zone there is nothing to separate. The station picks the transmitter with the best respiratory-band SNR and reports which one; ICA remains an offline result on public multi-subject data (§16). |
| D-6 | **Both 3D views — the station and the torus — use a perspective projection on canvas.** No WebGL library. | Three.js | A standing figure, a floor and a torus are small fixed geometry; projection plus painter's ordering is ~300 lines and no dependency, stays offline, and renders at 30 fps. |
| D-7 | **Light surfaces for the patient; dark surfaces only for engineering.** | Dark mode for everything; a theme toggle | A kiosk in a lit room needs light, high-contrast surfaces. The dark system panel is a semantic signal ("this is engineering"), not a theme. |
| D-8 | **SQLite via the standard library; aggregate counters by default.** | Per-session records always; Postgres | A screening record is health data. The default keeps counts, not people. Per-session rows exist only in demo mode, which is labelled. |
| D-9 | **Eight-second-padded 30 s capture with a 3 s settle.** | 10 s or 60 s | 30 s gives 7–8 breaths at 15 br/min, enough for a rate estimate inside 1 bpm and a PLV with a usable confidence interval; 10 s is too few breaths and 60 s doubles the queue. |
| D-10 | **The torus is a staff explanation, not a patient screen.** | Torus on the result screen for the patient | A patient cannot act on a phase portrait. It lives behind "Details for staff" so a judge can see the mechanism and a nurse can inspect a flag. |

## 4. Runtime architecture

```
                 ┌──────────────────────────── one uvicorn process ────────────────────────────┐
                 │                                                                             │
 serial  ──┐     │  Source ──► inbox (ring buffer, 100 Hz)                                     │
 replay  ──┼─────┼────►│                                                                        │
 simulator ┘     │      └─► session loop: settle 3 s → capture 30 s → evaluate                 │
                 │             DSP: Hampel → unwrap → best-Tx → Butterworth 0.2–0.5 Hz         │
                 │             analyzer: Hopf oscillator → φ, PLV, RR → rules → outcome        │
                 │                          │                                                  │
                 │                          ├─► store (counters; demo-mode rows)               │
                 │                          ├─► SSE (session state, 4 Hz while measuring)      │
                 │                          └─► /healthz/{ingest,dsp,analyzer,store,api}        │
                 │  prober (3 s): real HTTP GET, 500 ms timeout ──► /api/v1/topology            │
                 └─────────────────────────────────────────────────────────────────────────────┘
```

The **session state machine** is the heart of the app:

```
idle ──Start──► settle (3 s, checks presence and stillness)
                  │             │
                  │ too noisy   └─► measuring (30 s, restarts on 2 s of motion)
                  ▼                          │
               idle (guidance)               ▼
                                        evaluate ──► regular │ irregular │ unclear
                                                          │
                                          Done / 20 s ◄───┘
                                                ▼
                                              idle
```

Timing for one session: settle 3 s, capture 30 s, evaluation < 400 ms, so a person is at the
station for about 35 s. The measured packet-to-alert latency is displayed on the staff surface,
not assumed.

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
    contracts.py            pydantic models for frame, session, trace, topology, result
    sources.py              Source protocol: SerialSource, ReplaySource, SimulatorSource
    station.py              session state machine: idle → settle → measuring → result
    pipeline/
      frames.py             frame parsing, per-channel counters, ring buffers
      dsp.py                Hampel, unwrap, best-Tx choice, Butterworth, RR
      hopf.py               oscillator integration, Hilbert phase, PLV
      rules.py              outcome rules, quality gates, patient copy
    topology/
      registry.py           node and edge definitions
      probes.py             HTTP probe with timeout, liveness checks, history
      diagnosis.py          root-cause rules, cascade suppression, verdict text
    store.py                SQLite schema, counters, demo rows, CSV export
    templates/              base, kiosk, kiosk_result, system, sessions, method, error
    static/
      css/app.css           design tokens and components
      js/app.js             SSE client, formatting, state transitions
      js/wave.js            rhythm strip rendering
      js/station.js         station scene: projection, figure, rings, capture arc
      js/torus.js           torus geometry, projection, interaction
      js/rose.js            circular phase-difference plot
      js/system.js          graph layout and probe table
  fixtures/
    replay_session.jsonl    synthetic replay (small, labelled synthetic)
    scenarios.json          tachypnea / apnea / unclear demo definitions
  tests/                    pytest, offline, deterministic
```

Rules that keep this lane testable: `pipeline/`, `station.py` and `topology/` import no FastAPI;
`app.py` imports them. Routes stay thin enough to read in one screen. `static/js/*` holds no
business rule a test needs to assert; the rules live in Python.

## 6. Data contracts

All timestamps are integer epoch milliseconds, UTC; all durations are integer milliseconds.

### 6.1 Frame (source → pipeline), JSON Lines

```json
{"v": 1, "t": 1792243200123, "tx": "tx2", "ch": 6, "seq": 84213,
 "rssi": -42.5, "amp": [12, 14, 9], "phase": [-31, 5, 77]}
```

A frame missing `v`, `t`, or `tx` is counted as malformed and never reaches the DSP. The
simulator, the replay fixture, and the future Rx firmware emit exactly this line.

### 6.2 Session state (`GET /api/v1/session`)

```json
{"id": "s-7f3a91", "state": "measuring", "source": "sim",
 "started_ms": 1792243200000, "elapsed_ms": 12400, "duration_ms": 30000,
 "presence": true, "quality": "ok", "motion": false,
 "live": {"rr_bpm": 24.1, "amp_db": -13.8, "breaths": 3},
 "result": null}
```

`result` is null until the state is `result`. A new session always gets a new random `id`; the
id is not derived from anything about the person.

### 6.3 Result (`GET /api/v1/session` once finished)

```json
{"outcome": "irregular", "rule": "tachypnea",
 "rr_bpm": 26.4, "plv": 0.31, "breaths": 7, "usable_s": 30,
 "confidence": "high", "advice": "speak_to_nurse",
 "thresholds": {"rr_max": 24, "plv_min": 0.6}}
```

`outcome` is one of `regular`, `irregular`, `unclear`. `rule` is `none`, `tachypnea`,
`apnea`, `unsteady`, or `low_quality`. `confidence` is `high`, `low`, or `none`; a low or
none confidence forces `unclear`, never a clinical outcome (REQ-122).

### 6.4 Trace (`GET /api/v1/session/trace?window_s=30`)

```json
{"t": [0.0, 0.1], "amp": [0.12, 0.14], "phi_breath": [0.0, 0.31], "phi_osc": [0.05, 0.30],
 "plv": 0.31, "rr_bpm": 26.4, "amp_db": -12.4, "locked": false,
 "winding": 1.07, "no_breath": false, "tx_used": "tx1"}
```

Unwrapped radians, decimated to 10 Hz for transport.

### 6.5 Topology (`GET /api/v1/topology`) and events CSV (`GET /sessions.csv`)

Topology is unchanged from the bay draft: nodes, edges, `history`, `diagnosis`, `blocked_by`.
The CSV header is exactly:

`session_id,started_iso,duration_s,outcome,rule,rr_bpm,plv,quality`

No name, no bed, no free-text field. Added only in demo mode; otherwise the export is a daily
counter table.

## 7. Signal path and detector

### 7.1 Pipeline

1. **Parse** each line; drop malformed; increment per-channel counters.
2. **Ring buffer** per (tx, channel), 40 s at 100 Hz (30 s capture plus settle).
3. **Hampel filter** on the phase series (window 7, 3 MAD) to remove unwrapping spikes.
4. **Unwrap** phase along time, per subcarrier; reduce subcarriers to one series per
   transmitter by their first principal component.
5. **Choose a transmitter**: the one whose series has the highest respiratory-band SNR
   (band power in 0.2–0.5 Hz over total power). Recorded as `tx_used` and shown on the staff
   view; a poorly placed subject is visible as a weak SNR, not as a wrong number.
6. **Butterworth bandpass** 0.2–0.5 Hz, 4th order, zero-phase (`sosfiltfilt`).
7. **Rate estimate**: dominant spectral peak on the 30 s window with parabolic interpolation;
   reported with its window and breath count.
8. **Quality gate**: settle and capture windows are scanned for motion (band power above
   3 Hz) and for breath amplitude below the calibrated floor. More than 2 s of motion in the
   capture window, or fewer than 3 detectable breaths, yields `unclear`.

FastICA is **not** in this path (D-5). It remains in the offline notebooks for the
multi-subject result.

### 7.2 Oscillator and PLV

Per session, one complex Hopf oscillator driven by the chosen transmitter's bandpassed series
`x(t)`:

```
dz/dt = (μ + iω) z − |z|² z + g·x(t),    μ = −0.5, ω = 2π·0.25, g = 1.0
```

integrated with RK4 at the frame rate (100 Hz); `x(t)` is normalised to unit RMS before it
enters the forcing. Phase-locking value over the 30 s window:

```
PLV = | mean_t exp( i ( φ_breath(t) − φ_osc(t) ) ) |
```

with `φ_breath` from the Hilbert transform of `x(t)` and `φ_osc = arg z(t)`. This is the same
statistic the research notebook computes as `|C_ij|`; the Method page says so and cites
Lachaux et al. (1999).

### 7.3 Outcome rules

First match wins. Thresholds are configuration, shown on the Method page, and are prototype
thresholds, not clinical ones.

| Condition | Outcome | Rule |
|---|---|---|
| Quality gate failed (motion, < 3 breaths, amplitude floor) | `unclear` | `low_quality` |
| No breath phase for ≥ 10 s, amplitude below floor | `irregular` | `apnea` |
| RR > 24 and PLV < 0.60 | `irregular` | `tachypnea` |
| PLV < 0.40 with RR in band | `irregular` | `unsteady` |
| 8 ≤ RR ≤ 20 and PLV ≥ 0.60 | `regular` | `none` |
| 20 < RR ≤ 24, or 0.40 ≤ PLV < 0.60 | `regular` with `advice: "watch"` | `none` |
| anything else | `unclear` | `low_quality` |

A session produces exactly one outcome. There is no hysteresis across sessions: the next
person is a new measurement, not a continuation.

## 8. Spatial views

### 8.1 The station scene (patient-facing)

The patient sees a simple scene: the floor, the mark they stand on, three transmitter stands,
the receiver, and — once measuring — an abstract figure at the mark with a chest that rises
at their measured rate and a capture ring filling around them.

- **Idle**: the mark is a dashed ring; no figure. The screen says step onto the mark.
- **Measure**: the ring is a progress arc; the figure breathes; a small chip reads
  "in position" or "keep still".
- **Result**: `irregular` rings the figure and the mark in red with a tag
  (`IRREGULAR · 26.4 /min`); `regular` rings them in green with no tag; `unclear` rings them
  in amber with "try again".

**It never claims to see the patient.** The figure is a guide drawn from the CSI-derived rate,
not a camera image, and no camera exists in the system. The caption says this in one line, and
REQ-119 makes it a requirement rather than a caption.

Rendering: perspective projection on canvas with painter's ordering (D-6). Camera: orbit by
drag, a `Top` preset, clamped so the mark cannot leave the frame. The rig geometry — three
transmitter positions and the receiver — is three constants at the top of `station.js`; moving
the rig means editing them, and the Method page says where they are.

Motion: the chest scale and the ring pulse stop under `prefers-reduced-motion`; the rings,
tags and progress bar remain.

### 8.2 The phase-space torus (staff)

The breathing phase `θ_b = φ_breath mod 2π` and the oscillator phase `θ_o = φ_osc mod 2π` are
two angles, so the pair lives on a torus. The trajectory over the window is a curve on that
surface:

- **Locked** rhythm → a closed loop (winding 1:1): the same phase difference recurs every
  cycle, which is what a high PLV measures.
- **Unlocking** → the curve drifts across the surface and never closes; PLV falls.
- **Apnea** → no breath phase exists. The torus is drawn empty with "no detectable respiratory
  motion", never a fabricated curve.

Geometry: `P(u,v) = ((R + r cos v) cos u, (R + r cos v) sin u, r sin v)` with `R = 1.0`,
`r = 0.38`; wireframe 32 × 12; yaw, pitch (clamped ±70°), distance; perspective with `f = 520`.
Segments are painted back-to-front with depth-scaled alpha and width, so the front of the
surface occludes the back without a depth buffer. Trajectory: up to 300 points over 12 s,
segments interpolated along the surface, a faint band for the whole window, the last two
seconds drawn on top, a dashed guide where a locked 1:1 rhythm would sit, and a dot at the
newest sample. Drag to orbit; auto-rotate at 0.05 rad/s when idle unless reduced motion.

### 8.3 The 2D twin

Beside the torus, always: a circular plot of `Δφ = φ_breath − φ_osc` samples around a ring,
with the mean resultant vector drawn from the centre. **The length of that vector is the PLV**,
by definition, and its angle is the mean phase lag. When the 3D view is illegible on a
projector, this panel still carries the claim, and it teaches the definition in one glance.

### 8.4 Failure modes and their display

| Condition | Display |
|---|---|
| Fewer than 5 s of data | Torus at rest with "collecting data (3.2 s)" |
| No breath phase | Torus empty, "no detectable respiratory motion", last winding greyed |
| Data stale > 5 s | Whole panel desaturated with a "stale" chip and the age |
| Session ended | Torus frozen at the result, labelled with the session id |

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
| `store` | HTTP | `GET /healthz/store` (write + read roundtrip) | < 50 ms | < 250 ms | error |

Each probe is `httpx.AsyncClient.get(url, timeout=0.5)` with one retry, run every 3 s. Results
including latency are kept for the last 60 checks, so a flapping node is visible as a dotted
history rather than a momentary colour.

Edges (`tx1..3 → rx`, `rx → ingest`, `ingest → dsp`, `dsp → analyzer`, `analyzer → api`,
`api → store`, `api → browser`) carry the metric that proves flow.

### 9.2 Cascade suppression

The prober computes root faults first, then marks every descendant of a failed node `unknown`
with `blocked_by` set to the root cause. Of the nine nodes, a dead Rx produces one red node,
five `unknown` nodes, and one verdict — not six red nodes that each claim a separate problem.

### 9.3 Diagnosis rules

First match wins. The verdict is one sentence plus one action; the graph is the evidence.

| Code | Condition | Verdict | Action |
|---|---|---|---|
| `api_down` | self check fails | The API is not answering. | Restart the process; the error page names the last good check. |
| `serial_lost` | `rx` down | USB link to the receiver is lost; screening is paused. | Reseat the Rx cable, then check the port name. |
| `no_frames` | `rx` ok, frames 0 for > 2 s | Receiver connected, no CSI frames arriving. | Check the ESP-NOW channel plan and Tx power. |
| `tx_silent` | one or more Tx at 0 Hz | TX-2 silent on channel 6; the rest is healthy. | Check that node's power before touching software. |
| `all_tx_silent` | all Tx at 0 Hz | No transmitter is being heard at all. | Check the Tx nodes and the receiver's channel. |
| `dsp_stalled` | `dsp` stale, `ingest` ok | Frames arrive but processing has stalled. | Look at the DSP log; the frames are not the problem. |
| `analyzer_stalled` | `analyzer` stale, `dsp` ok | Detection is paused; PLV is not updating. | Restart the analyzer task; sessions show `unclear`. |
| `store_failing` | `store` down | Counters are not being persisted. | Check disk space and permissions. |
| `slo_breach` | frame age p95 > 500 ms or evaluation > 2 000 ms | SLO breach: lag at `<node>`. | Fix the named stage; the target is 2 s. |
| `healthy` | all ok | All checks passing; the station is ready. | — |

## 10. Screens

Every route shares a header: product and station label, clock, source chip, and the
disclaimer where the audience is a patient.

### 10.1 `/` — Station (default, patient-facing)

Two panels. Left: the station scene of §8.1 with a stage caption ("the figure is an abstract
guide, not a camera image"). Right: the state panel, which is the whole flow:

| State | Panel |
|---|---|
| `idle` | "Step onto the mark" · what happens · a three-step strip · **Start** · "nothing is measured until you press Start" |
| `settle` / `measuring` | Countdown, progress bar, position chip (`in position` / `keep still`), **Stop**, step strip |
| `result` | Headline in the outcome colour, one line of advice, RR and rhythm, a flagged chip when irregular, a collapsed **Details for staff**, and **Done** |

The patient never sees PLV, thresholds, or the backend graph.

### 10.2 `/staff` — Backend graph

Dark engineering surface. Nine nodes as the data flow (three Tx merging into Rx, then the
service chain, with the store hanging off the API), edges labelled with live metrics, node
status by dot and word, and the verdict banner at the top. Below: the probe table with the
last 60 checks per node, **Run checks now**, and the cadence plus timeout statement. This page
answers "is it the microcontroller or the backend".

### 10.3 `/staff/sessions` — Recent screenings (demo mode)

Table of the last 50 sessions: time, duration, outcome, rule, RR, PLV, quality. CSV download.
When demo mode is off, the page states that only counters are kept and shows the counters.

### 10.4 `/staff/session/{id}` — Phase space

The torus (§8.2) and 2D twin (§8.3) for a finished session, the rhythm strip, the active rule
with its thresholds, and the numeric trace. This is the page a judge is shown when the demo
flags someone; it is staff-only by design (D-10).

### 10.5 `/method` — Method and provenance

Pipeline diagram (SVG, no external assets), the PLV definition with the resultant-vector
figure, thresholds and where they are configured, the evaluation section (artifact or
"pending"), the deviation notes (§16), and the citations in APA 7th Edition matching
[`docs/SOURCES.md`](../docs/SOURCES.md).

## 11. Visual system

Tokens in `static/css/app.css`, one place only.

| Token | Value | Use |
|---|---|---|
| surface | `#eef1f5` | page background |
| card | `#ffffff` | patient and staff panels |
| ink / muted / faint | `#0e1a28` / `#5b6b7d` / `#8697a9` | body / secondary / tertiary |
| line | `#dfe6ee` | borders and rules |
| accent | `#0d6e78` | selection, links, focus ring, progress |
| ok / warn / crit | `#0f7b4f` / `#8f5600` / `#b3261e` | outcomes, always with a word |
| ops / ops-line | `#0d1621` / `#22344a` | engineering surfaces only |

Patient-facing type: 13.5 px base minimum 16 px for body copy in the panel, 25 px headline,
tabular numerals for every number that changes, units always rendered. RR is the largest
number on a result. Time is shown absolutely (24 h) and relatively where it helps.

Status is double-encoded (dot + word, or headline + icon) and never by colour alone. Red is
reserved for `irregular` and system failure; amber for `unclear` and degraded; green for
`regular` and healthy. Focus is visible at 2 px accent outline. Motion is limited to the live
indicator, the station figure's chest, the capture ring, and the torus; all stop under
`prefers-reduced-motion`.

## 12. Privacy, security, retention

- **No measurement without Start** (REQ-105). The idle screen captures nothing, stores
  nothing, and starts no session.
- Bind `127.0.0.1`. A non-loopback `--host` prints a warning and is not the documented path.
- No authentication in the MVP because the app is single-operator and local; the Method page
  and the README say so plainly rather than implying security that does not exist.
- No identifiers, no images, no audio, no video. Session IDs are random and are not derived
  from the person. The station scene draws an abstract figure, not a reconstruction.
- SQLite `webapp/.data/hinigram.db`, gitignored, WAL, 24 h retention. Default content is
  aggregate counters (sessions, outcomes). Per-session rows exist only with `--demo`, are
  labelled in the UI, and are pruned on the same schedule.
- Logs contain counters, node IDs and timings, never frame payloads or traces.
- The CSV export carries the header of §6.5 and nothing else.

## 13. Configuration and commands

```
cd webapp
uv sync
uv run hinigram                      # simulator, http://127.0.0.1:8765
uv run hinigram --source replay      # committed synthetic fixture
uv run hinigram --source serial --port COM5
uv run hinigram --demo               # keeps per-session rows and shows /staff/sessions
uv run pytest                        # lane suite
```

Flags and their `HINIGRAM_*` equivalents: `--source`, `--serial-port`, `--replay-file`,
`--host`, `--port`, `--demo`, `--capture-s`, `--settle-s`, `--plv-threshold`, `--rr-max`,
`--verbose`. Defaults are the values in §7.3 and D-9.

## 14. Testing

Offline, deterministic, under 15 s, no hardware.

| File | Cases |
|---|---|
| `test_dsp.py` | synthetic 15 bpm sine → RR within 1 bpm; 26 bpm → within 1; Hampel removes injected spikes; bandpass rejects 0.05 Hz and 2 Hz; best-Tx choice picks the higher-SNR stream; PLV ≈ 1 for identical phase, ≈ 0 for randomised phase |
| `test_station.py` | the state machine's allowed transitions; no capture before Start; Stop returns to idle; motion for 2 s forces `unclear`; result resets to idle after Done and after the timeout; a new session gets a new id |
| `test_rules.py` | each outcome boundary; low confidence forces `unclear`; apnea requires 10 s; one outcome per session; patient copy exists for all three |
| `test_probes.py` | ok / timeout / 5xx via `httpx.MockTransport`; retry once; cascade suppression marks descendants `unknown` with one root cause; verdict text per code |
| `test_contracts.py` | every endpoint validates against its model; CSV header exact; no identifier column; demo off keeps counters only |
| `test_store.py` | counter roundtrip, demo-row roundtrip, retention prune, WAL survives reopen |
| `test_sources.py` | simulator deterministic for a seed; replay parses the fixture; serial parser handles a fragmented and a malformed line |
| `test_templates.py` | every route 200 with the disclaimer where required; no external asset reference; the result page carries the outcome word and the staff link; the station page carries the no-camera caption |
| `test_accessibility.py` | status text present alongside every status dot; body copy at the minimum size; focus styles declared |

The JS canvas modules are verified by the demo script and a visual check, not by a JS test
runner: adding Node would reverse D-1. That is a conscious tradeoff, recorded here.

## 15. Acceptance criteria

| ID | Criterion | How it is checked |
|---|---|---|
| AC-101 | From a clean clone: `cd webapp && uv sync && uv run hinigram` serves `http://127.0.0.1:8765`. | Manual, then in the lane README |
| AC-102 | `/`, `/staff`, `/method`, `/staff/sessions`, `/staff/session/{id}` return 200 within 1 s of start. | `test_templates.py` |
| AC-103 | A simulator session with tachypnea yields `irregular`, rule `tachypnea`, RR within 1 bpm of the injected value, and evaluation latency ≤ 2 000 ms. | Scripted scenario test |
| AC-104 | An apnea scenario yields `irregular`, rule `apnea`; an injected motion burst yields `unclear`, never `regular`. | `test_station.py` + scenario |
| AC-105 | No session exists before Start, and the idle page performs no measurement. | `test_station.py` |
| AC-106 | No template references an external host. | `test_templates.py` |
| AC-107 | The CSV has the exact header of §6.5 and no identifier column. | `test_contracts.py` |
| AC-108 | The disclaimer appears on the idle screen, every result, and every staff route. | `test_templates.py` |
| AC-109 | `uv run pytest` in `webapp/` passes offline in under 15 s. | CI |
| AC-110 | `ruff format --check`, `ruff check` and `mypy` pass for `webapp/`. | CI |
| AC-111 | The Method page shows "evaluation pending" when the artifact is absent, and artifact values only when present. | `test_templates.py` |
| AC-112 | The torus renders 300 points at ≥ 30 fps, and the 2D twin's vector length equals the reported PLV within 0.01. | Manual + `test_contracts.py` |
| AC-113 | Root suite (`uv run pytest` at the repository root) still passes, with the placeholder test updated to the new lane shape. | CI |
| AC-114 | The station scene renders with no WebGL, rings `irregular`/`unclear`/`regular` distinctly, and carries the no-camera caption. | `test_templates.py` + manual |
| AC-115 | The patient result page contains no PLV value and no threshold; both appear only behind staff details. | `test_templates.py` |
| AC-116 | After a result, the next session starts with no state from the previous one (fresh id, fresh buffers, `idle`). | `test_station.py` |

## 16. Deviations from the proposal

Three, all of which the slide deck and the report must state.

1. **Dashboard: CLI → web.** The proposal specifies `rich` and `plotext`. The web application is
   the delivered interface; the CLI is retained only as a headless fallback if the browser
   fails during the demonstration. The requirement it serves is unchanged.
2. **Live detector: PyTorch → numpy RK4.** The proposal says "PyTorch solves this differential
   in real time". The live path integrates one oscillator, where numpy RK4 is sufficient and
   costs no 2 GB dependency; the torch `ResonanceNetwork` remains the research implementation
   and the source of the reported study. The station does not claim to run the trained bank.
3. **Product shape: multi-person monitoring → a single-person screening station.** The proposal's
   objective (3) promises to isolate up to three subjects and estimate each rate within
   2 bpm. The delivered product screens one person per session, because that is what a
   kiosk in a waiting area can actually do and demonstrate. Multi-subject separation remains
   an **offline** result on public CSI data (FastICA in the notebooks), and must be reported
   as such: not demonstrated by the application.

**Addition beyond the proposal.** The staff backend graph (§10.2) is new: the proposal asks
for a subject's waveform and distress alerts, not for service observability. It is justified
by the team's own debugging need — telling a dead ESP32 apart from a stalled analyzer — and
should be presented as an engineering aid, clearly separated from the patient surface.

## 17. Deferred decisions

| Deferred | Reopens when |
|---|---|
| Authentication and multi-operator sessions | A non-loopback deployment, or a second operator |
| Multi-subject screening (the proposal's objective 3) | A pilot with several people in the zone and a validated separation method |
| Multi-room / multi-receiver support | A second receiver node exists |
| HL7 FHIR or facility-system exchange | A facility asks, which is beyond the prototype |
| Real WebGL/Three.js scene | The canvas projection cannot carry the geometry needed (today it can) |
| Patient localisation / tracking | Never in this project: a kiosk with one person at a marked spot has no need, and the privacy cost is not justified |
| Persistent patient identity | Ethics approval and a consent process exist |
| Postgres or a time-series store | Event volume exceeds a day's retention |
| Evaluation artifact generator | The detector evaluation cell is written in the notebooks |

## 18. Risks and cut order

| Risk | Mitigation |
|---|---|
| No Rx firmware yet, so no live frames | The frame contract is the interface; simulator and replay exercise it identically. The serial path is one adapter, tested with a fake stream. |
| CSI payload differs from §6.1 | `v` field and a parser that rejects unknown versions loudly rather than silently mis-reading. |
| A kiosk reads as surveillance | REQ-105 (no capture before Start), no camera, abstract figure, aggregate-only storage, and the caption. This is the design's primary ethical constraint, not a footnote. |
| A false `regular` on a poorly positioned person | The quality gate and the SNR-based Tx choice force `unclear` rather than a confident number; REQ-122 is the check. |
| Station scene illegible at 1280 × 720 | The panel carries every fact in text; the scene adds orientation only. |
| Schedule: one week to submission | Cut order below; the demo spine never depends on a cut item. |

**Cut order when time runs short** (cut from the top): Method page → session CSV → staff
sessions page → torus interaction (keep the static render) → station figure animation (keep
the rings and tags) → the troika of axes/legend polish. **Never cut:** the Start gate, the
three outcomes, the quality gate, the staff verdict, the disclaimer, the source chip.

## 19. Open items for the maintainer

1. Confirm the demonstration date; the plan assumes a working demo by 2026-10-23.
2. Confirm the rig geometry: the three transmitter positions and the receiver position, in
   metres, for `station.js`.
3. Confirm whether the station will run on a tablet or a laptop; the layout assumes landscape
   at 1280 × 720 or larger, and the patient panel is readable at 768 px wide.
4. Confirm that the 30 s capture and 3 s settle suit the venue.

## References

Full APA 7th Edition entries are recorded in
[`docs/SOURCES.md`](../docs/SOURCES.md), under *Web application and detection sources*; that
file is authoritative.

- Cretikos et al. (2008) — respiratory rate as the neglected vital sign, the problem.
- Lachaux et al. (1999) — the phase-locking value, the detector's statistic in §7.2.
- Righetti, Buchli, & Ijspeert (2006) — adaptive Hopf oscillators, the model in §7.2.
- Hampel (1974) — the robust outlier filter in §7.1 step 3.
- Hyvärinen & Oja (2000) — FastICA, used offline for the multi-subject result, not on the live path.
- Wang et al. (2016); Liu et al. (2015); Soto et al. (2022) — CSI respiration sensing and its limits.
- W3C (2023) — WCAG 2.2 AA, the basis of REQ-112.
- The research notebook `D01_10-17_Gengineer.ipynb` — the Resonance Network study whose
  notation and PLV definition the Method page follows. It is a team artifact, not a
  publication, and is cited as such.
