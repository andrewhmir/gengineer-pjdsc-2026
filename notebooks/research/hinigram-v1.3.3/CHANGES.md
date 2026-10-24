# Changes in v1.3.3

The pipeline is unchanged: `hinigram_live.py` is the frozen v1.3.2 (SHA-256 `e90a0ce7...ff6` in `frozen_hash_v132.txt`),
and every result reported for v1.3.2 stands. Everything below is new or fixed around it.

## The board

**Injection bench (new).** A fifth data source adds breathing of a known rate to Wi-Fi packets while they stream and
scores the board against it (Part 1, Section 6b).

* Sources: the format sample (all of it, or its quiet stretch), a CSV from your receiver, or your receiver live over USB.
  With the receiver, breathing is added only to the chairs you switch on, before the pipeline sees the packets.
* 3 chairs in one row facing one corner receiver, or 8 or 12 in rows facing two corner receivers, numbered so each
  receiver takes one continuous range of node IDs.
* Per chair, while it runs: breathing added or not, who sits there, breathing rate, how strongly breathing moves the
  signal, hold breath, shift in seat (simulated movement), empty the chair. Six scenarios, including the eleven held-out
  scenarios (taken in turn over runs, with the depths rotating over the sensors as in sets 4 to 6) and a null test.
* A table of every chair (the rate set now, what the board reads and says, and whether that is right against the 30 s it
  scores), a score panel (rates; every breath-hold with its alert time, judged with the profile of whoever sat there when
  it began; pause alerts when nobody held their breath, with those on a chair that had no breathing in it counted apart),
  the injected truth on each seat's chart, TEST notes in the log, and downloads: truth log, injected packets (receiver
  format) and scores.
* A striped TEST band across the room whenever the bench is shown, and a TEST mark on every seat card, the seat's sheet,
  the logbook and the screen-reader announcements. The packets download starts with a line marking it as test data, and
  the board shows the TEST band when it opens such a file. Leaving the bench switches added breathing off.
* Engine: `dashboard/hinigram_inject.js` (the breathing model of `hinigram_live.inject_breathing`, run forward in time).
  The format sample's raw packets are embedded in the board (`dashboard/sample_packets.b64`, 1.1 MB), so it works offline.
* Checks: `check_inject_bench.js` (five chairs, six minutes, through the board's own live pipeline: rates, an 18 s hold
  flagged after 12 s, an 8 s hold not flagged, movement detected, an empty chair that shows a rate on 3 of 165 updates and
  raises a pause alert, reported as a known open failure) and `check_inject_bench.py` (the frozen Python v1.3.2 on the
  same packets: the same state in 91 to 99% of paired updates on the chairs with breathing). Both list every alert as an
  episode (first and last update, and how many).

**Fixes.**

| Problem in v1.3.2 | Fix | Check |
|---|---|---|
| On screens with more than one device pixel per CSS pixel (phones, most laptops) every chart doubled its height on every redraw; within seconds the page ran at about one frame a second | The chart's designed height is read once (`setupCanvas`) | Phone-sized screen in headless Chromium: 61 frames a second at pixel ratio 2 (v1.3.2: 1); charts keep their designed size at ratios 2 and 3 |
| The Hampel filter sorted a new array twice per sample and channel: about 70% of the live pipeline's time | Stable insertion sort into a reused buffer; same median | `check_dsp_parity.js`: bit-identical to v1.3.2 (`history/hinigram_dsp_v132.js`) on features, whole files and a live stream; about 3.6 to 3.7 times faster |
| A log re-saved with tabs or semicolons gave "no CSI_DATA lines" | The board's parser accepts commas, tabs and semicolons; `firmware/tools/to_receiver_csv.py` rewrites such a log for the Python tools | A tab-separated line parses to the same packet |

**The bench runs itself on your receiver.** The scenarios now work with *Your receiver, live over USB* too: each node
gets its scenario as soon as it is heard, timed from that moment, with nothing to set by hand ("Nothing added" keeps
the old way: you switch chairs on yourself). Two new scenarios check a room before anyone sits down: the **Quick check**
(2 minutes: 15 a minute, an 18 s breath-hold, a shift in the seat; the default for the receiver) and the **Setup
check** (4 minutes, two rates). At the end each chair gets a verdict (*Ready*, *Repeat* if the room moved, *Check*
with the reason), its added breathing switches off, and the verdicts go into the scores download. Windows in which
the board saw movement are not held against the link. Each routine starts at the node's first packet; its verdict is
fixed when it ends and names the node; a node that stops sending, a pause alert while the chair breathes, or a change
made by hand during the routine is reported as such; the schedule follows the stream, so it keeps time in a background
tab; and the live board gets back each node's adult or child setting afterwards. Tested in headless Chromium with a simulated receiver: three
empty chairs on the format sample's quiet stretch were all *Ready* (rates 100% right, the hold flagged after 10 to 12 s,
the shift seen) in both checks; on its busy stretch the Quick check said *Repeat* for all three. The thresholds are
suggestions, not validated.

**Also new.** A **Serial speed** choice next to **Connect receiver** (921,600 or 2,000,000 baud; the bench uses the same
setting, and the browser remembers it). Without it the board could read a receiver only at 921,600 baud.

**Bench fixes after review.** A new run never takes in messages still queued from the previous one (each run is
numbered), and a run stopped while it is still starting does not go on streaming out of sight; chair changes made while
a run starts are applied when it begins; changing who sits in a chair keeps that seat's history; the rate slider follows
the scenario, also after a drag released where it began; chairs in the null test get an on/off switch and their knobs
wait until it is on; switching a chair off, or pressing *Breathe again* during a scripted hold, ends its scenario there
instead of scoring a hold that never happened or splitting one in two; a browser without Web Serial no longer leaves the
bench's Start needing two presses; the chair table wraps its headers on phones so the check stays on screen; the
playback clock never shows more than the total.

**After a test on your receiver, the live board starts afresh.** Readings made from added breathing stayed in the
pipeline's 30 s windows and in the seats' history, so *Connect receiver* could show them, unmarked, after the test. When
a receiver test with added breathing ends, the live board now starts a new session (readings return after about 30 s)
and says so; the serial speed cannot change while a port is open.

The board's footer now reads "Hinigram v1.3.3 (pipeline v1.3.2)".

## The learned estimator (Part 2, Sections 7 to 10)

* **The paper's training schedule** (80 epochs, patience 15) for the sync arm, both seeds, three folds (`lin_sync-e80`):
  +3.3 points of correct readings on set 5 (95% CI 2.4 to 4.2), the same share within ±2/min, readings off by more than
  5/min roughly doubled (1.1 to 1.2% against 0.5 to 0.8%), and 42.9% against 40.5% coverage on validation
  (`hinigram_schedule.py` writes the tables).
* **The fallback rule** (v1.3.2 first, the model only where v1.3.2 abstains), chosen on validation, frozen with a hash
  (`results/fallback_rule.json`), then tested once on a fresh held-out set 6 (`hinigram_fallback.py`): correct readings
  30.6% to 37.4% of windows at the same precision, but *no breathing concern* in 6 to 8 of 162 pause windows against 2.
  The board does not use it.
* **Real breathing references:** `hku_adapter.py` turns the HKU lab dataset (Intel AX200, respiration belt) into ESP32
  receiver logs; `hinigram_realdata.py` scores v1.3.2, the model and the fallback against a belt or a paced-breathing log.
  HKU results (Section 9; another radio, one office, about eight minutes): on the steady recordings every rate v1.3.2
  showed was within 2/min of the belt; breathing reached receive antenna 1 and barely antenna 0, where v1.3.2 abstained;
  the model, trained only on simulation, gave a correct rate in 43% of one-person windows against v1.3.2's 23%, as
  precisely (95% against 94% of shown rates within 2/min); in the empty office, no rate and no alert on any link. The
  dataset's subcarrier index puts its channel at 5.50 GHz, not the stated 5.57 GHz; the adapter now says so. `hku_shrink.py` cuts the dataset to the 52 ESP32-frequency
  subcarriers for sharing; its first version read none of them (it expected one subcarrier-index convention), so both
  scripts now work out the convention from the index (tone numbers, positions, FFT bins, frequencies, or none), read the
  microsecond timestamps across their 2^32 wrap, keep two minutes of the empty office (only its samples shaped like the
  recordings', as the dataset's lab notebook does: the file mixes packet types), and store what they found.
  Checked on stand-ins in eight index layouts. `hinigram_finetune.py` fine-tunes each model's last head
  layer and batch-norm scales and shifts on the belt rates, one recording held out at a time (a method check on the six
  one-person recordings, about six minutes, not evidence for new people). It did not help: 57% of held-out windows within
  2/min against 63% before, so the models stay as trained.
* **Several people on one link** (`hinigram_multiperson.py`, Section 11; `hku` mode for the two real two-person
  recordings, where spectral peaks found both rates in 92% and 39% of windows and ICA in 33% and 7%): 1 to 4 simulated people on one real link. ICA
  found 79 to 83% of people's rates with 2 to 4 people (v1.3.2, one rate per link: 20 to 36%), an upper bound since the
  simulated people are independent; but v1.3.2's pause alert fell from about 61% of runs with one person to 32% with two
  and 15 to 17% with three, and almost never fired when the person who stopped was the weaker one. One transmitter per
  seat stays the design.
* `hinigram_resonet.py` gains `--patience` and `--suffix` (a variant's files never replace the arm's); `ml_driver.py`
  passes extra arguments; `hinigram_dataset.py` builds set 6 (`test6`) and runs one maths thread per worker.

## Firmware

* The corner receiver captures the legacy long training field only (`htltf_en` and `stbc_htltf2_en` off), so every line
  carries the 128 values the pipeline and the board read. With HT-LTF on, the nodes' HT20 packets would give 256 values
  and the board would skip every line. The change sets two flags and was not rebuilt or run on hardware here.

## Documents

* `firmware/PLACEMENT.md`: where the nodes and receivers go, how to number them for two receivers, capacity, what to keep
  out of the links, a first one-chair test (including `len` 128 and the sample's signal strengths), and tests before
  trusting the layout.
* `README.md`: a task-based start, and a folder map by purpose.
* `DEMO.md`: a runbook for showing the system with three transmitters and one receiver.
* `firmware/PLACEMENT.md` adds the three-chair layout and the Quick check.
* Part 1 notebook renamed `Hinigram_v1_3_3.ipynb`; new Sections 6b and 6c; Section 7 updated.

## Findings worth knowing

* **An empty chair can raise *needs help now*.** On the bench, a chair with nothing added gave a breathing-pause alert,
  in the board's pipeline (2:34 to 2:44) and in the frozen Python v1.3.2 (2:32 to 3:20) alike, each followed by about 30 s
  of *watch: breathing resumed*. A window whose earlier seconds held periodic background
  movement that then faded counts as "breathing seen" (`recent_gated`), which arms the pause test. Needs presence
  detection, or arming only after a shown rate (Part 1, Sections 6b and 7).
* **The fallback's extra false reassurance** comes from v1.3.2's rule that holds a rate-based state for up to 20 s after
  the last reading: readings the model added let the board reach *no breathing concern* sooner, and the hold carried
  that state into a pause (all on the 3% link).
