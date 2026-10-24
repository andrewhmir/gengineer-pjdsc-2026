# Hinigram v1.3.3 bundle

Breathing screening from ESP32 Wi-Fi CSI for a waiting room, audited and rebuilt.

**v1.3.3 in one line:** the board gains an injection bench (known breathing added to Wi-Fi packets while they stream),
three board fixes, the learned estimator's follow-up studies, a real-breathing route and a placement guide. The pipeline
itself is unchanged: `hinigram_live.py` is still the frozen v1.3.2 (`frozen_hash_v132.txt`). Details in `CHANGES.md`.

## Start here

| I want to... | Open |
|---|---|
| Read the whole story with every table and figure | `Hinigram_v1_3_3.ipynb` (Part 1), then `training/Hinigram_training.ipynb` (Part 2). Both have been run once, so nothing needs running |
| See the waiting-room board | `dashboard/Hinigram_dashboard_standalone.html` in Chrome or Edge |
| Run the hackathon demo | `DEMO.md`: setup, a five-minute script, what to do if something fails, likely questions |
| Check the room and boards in 2 minutes | The board's **Injection bench** with *Your receiver, live over USB* and the **Quick check** (`firmware/PLACEMENT.md`) |
| Test the board with known breathing, live | The board's **Injection bench** source (Part 1, Section 6b) |
| Read a receiver live | The board's **Connect receiver**, with **Serial speed** set to the receiver's (opened as a local file on the computer plugged into the receiver) |
| Check accuracy on a real person without a belt | The board's **Check accuracy with paced breathing** panel (Part 1, Section 6) |
| Place the boards in the room | `firmware/PLACEMENT.md` |
| Flash the boards | `firmware/README.md` |
| See what changed since v1.3.2 | `CHANGES.md` |
| See the literature behind the audit | `audit/Hinigram algorithm literature audit.md` |

Both notebooks also come as one self-contained file, `Hinigram_v1_3_3_complete.ipynb`, delivered next to this bundle:
its first cell unpacks the code, data, trained models and results it needs into a `hinigram_files` folder beside it.

Python 3.10 or newer with numpy, scipy, pandas and matplotlib runs both notebooks. Retraining the learned models also
needs `jax` and `optax` (CPU versions); the notebooks only read saved predictions. `legacy_v12.py` (the v1.2 functions,
for comparisons) also needs scikit-learn. The bench's checks need Node.js 18 or newer. Figure fonts are in `fonts/`
(SIL Open Font License); without them the figures fall back to DejaVu Sans.

## Folder map

**Notebooks and documents**

| Path | What it is |
|---|---|
| `Hinigram_v1_3_3.ipynb` | Part 1: the real format sample, the pipeline, held-out validation, screening rules, the retired v1.2 stages, the room, the board, the injection bench (6b) and the board fixes (6c) |
| `training/Hinigram_training.ipynb` | Part 2: the learned estimator (ResoNet and baselines) against v1.3.2, plus the v1.3.3 follow-up: the longer schedule (7), the fallback rule tested once on set 6 (8), real breathing from the HKU dataset (9), training on your own recordings (10) and several people on one link (11) |
| `README.md`, `CHANGES.md`, `DEMO.md` | This map, what changed since v1.3.2 with the checks behind each change, and the demo runbook |

**The pipeline and its validation** (top level, so the notebooks can import them)

| Path | What it is |
|---|---|
| `hinigram_live.py` | The v1.3.2 pipeline, frozen (SHA-256 in `frozen_hash_v132.txt`) |
| `hinigram_eval.py`, `validate_heldout.py`, `validate_heldout4.py`, `validate_pipelines.py`, `semi_gen.py` | Validation metrics, held-out scenarios, the semi-synthetic generator; `validate_heldout4.py` regenerates set 4 (15 to 25 minutes) |
| `heldout4_rows.json` | Held-out set 4 (seeds 41, 42), frozen v1.3.2: the reported results |
| `heldout2_rows.json`, `heldout3_rows.json`, `v132_on_heldout3_rows.json` | Earlier held-out sets and a diagnostic re-run, kept to show the problems each version fixed |
| `hinigram_paced.py`, `paced_check/` | Scoring for the paced-breathing check, and a rehearsal recording with its pacer log |
| `hinigram_style.py`, `hinigram_figures.py`, `figures/`, `fonts/` | Shared colours and type, the figure functions, the notebook figures as PNG, the fonts |
| `legacy_v12.py` | The v1.2 functions, unchanged, for comparisons only |
| `demo_20261019_024431.csv` | The real 173 s format sample from three ESP32 nodes (read-only) |

**The board** (`dashboard/`)

| Path | What it is |
|---|---|
| `Hinigram_dashboard_standalone.html` | The board as one file: demo room, format sample, CSV files, live receiver, paced-breathing check, injection bench |
| `hinigram_dsp.js` | The pipeline in JavaScript (gives the same states and rates as `hinigram_live.py`) |
| `hinigram_inject.js` | The injection bench's engine: breathing model, simulated movement, background player |
| `template_*.html`, `template_*.js`, `build_dashboard.py` | The board's sources and the script that assembles the HTML file |
| `dashboard_data_*.json`, `export_*.py`, `export_dashboard_js.js` | The demo room's data and the scripts that rebuild it |
| `sample_packets.b64`, `pack_sample.py` | The format sample's raw packets for the bench (1.1 MB), and the script that packs them |
| `check_inject_bench.js`, `check_inject_bench.py`, `check_dsp_parity.js`, `bench_check/` | The bench's checks, the cross-check with the frozen Python v1.3.2, the JavaScript parity check, and their saved outputs |

**The learned estimator** (`training/`)

| Path | What it is |
|---|---|
| `hinigram_dataset.py` | Builds the semi-synthetic training, validation and held-out data (`all`, or `test6` for set 6) |
| `hinigram_resonet.py`, `ml_driver.py` | The models and training loop; the driver that trains every arm, fold and seed |
| `hinigram_ml_eval.py`, `hinigram_ml_report.py`, `run_ml_report.py` | Evaluation through the same state machine, and the Part 2 tables and figures |
| `hinigram_schedule.py` | v1.3.3: the Section 7 tables (80 epochs against 40, on set 5) |
| `hinigram_fallback.py` | v1.3.3: the fallback rule (choose on validation, freeze, test once on set 6) |
| `hinigram_realdata.py` | v1.3.3: v1.3.2, the model and the fallback against a real breathing reference (HKU belt, or a paced-breathing log) |
| `hku_adapter.py`, `hku_shrink.py` | v1.3.3: the HKU dataset as ESP32 receiver logs; and a script that shrinks it for sharing |
| `hinigram_finetune.py` | v1.3.3: a small fine-tune on the HKU belt rates, one recording held out at a time |
| `hinigram_multiperson.py` | v1.3.3: 1 to 4 simulated people on one link: v1.3.2, spectral peaks and ICA, and pauses (Section 11) |
| `mlruns/` | Every trained run: weights, predictions, logs, summaries (`lin_sync-e80_*` are the 80-epoch runs) |
| `results/` | Result tables and figures, including `fallback_rule.json` (frozen, with its hash) and the set 6 and schedule results |

**Hardware** (`firmware/`): `hinigram_node` (one per chair) and `hinigram_receiver` (one per front corner) for the original ESP32,
`tools/log_serial.py` (record receivers to CSV), `tools/to_receiver_csv.py` (rewrite a tab- or semicolon-separated log),
`README.md` (build, flash, bring-up), `PLACEMENT.md` (where each board goes). Compiled with ESP-IDF 5.3.2 (the v1.3.3 receiver
change, LLTF capture only, sets two flags and was not rebuilt); not yet run on hardware.

**Background**: `audit/` (the literature review and its check scripts), `development/` (development-only scripts),
`history/` (the frozen v1.3.0 and v1.3.1 pipelines, the v1.3.2 JavaScript pipeline, and the script behind set 3).

## Rebuilding

**The board.** From this folder: `python dashboard/export_dashboard.py`, `node dashboard/export_dashboard_js.js` (checks
the JavaScript pipeline against Python update by update), `python dashboard/export_room_demo.py`, `python dashboard/pack_sample.py`,
then `python dashboard/build_dashboard.py`. Checks: `node dashboard/check_dsp_parity.js` and `node dashboard/check_inject_bench.js <folder>`,
then `python dashboard/check_inject_bench.py <folder> bench_injected.csv bench_truth.json <table.csv>` (the last argument writes
the comparison table, as in `dashboard/bench_check/python_crosscheck.csv`; the `.txt` files there are the two checks' printed output).

**The learned models.** From `training/`: `HINIGRAM_WORKERS=4 python hinigram_dataset.py all` (about 10 minutes on four
cores, about 17 with the default two workers; about 460 MB in `mldata/`, 580 MB once set 6 is built; the builder runs one
maths thread per worker, without which the workers fight over the cores and the build runs many times slower). `python ml_driver.py shallow,shallow-p0,lin_power,lin_power-p0,lin_surrogate,lin_randphase,lin_sync 0,1`
trains every original arm; `python ml_driver.py lin_sync-e80 0,1 "--epochs 80 --patience 15"` the 80-epoch runs. Existing runs
are skipped. `python run_ml_report.py` recomputes the tables and figures of Sections 1 to 6, `python hinigram_schedule.py` those
of Section 7. The fallback study: `python hinigram_fallback.py choose`,
`freeze`, `test` (the rule in `results/` is already frozen and set 6 already scored; `test` refuses to score it twice).
Real data (Section 9): `python hku_adapter.py <folder or hku_small.npz>`, `python hinigram_realdata.py hku`, then optionally `python hinigram_finetune.py hku` and `python hinigram_multiperson.py hku`. The converted recordings (`training/hku/`) are not in the bundle; the results are, in `training/results/`.

## How the evidence was produced

Breathing of a known rate was added to every packet of the real format sample, keeping its loss, timing jitter and gain
steps. Development files (seeds 1 to 6) were used for building and calibrating. Each frozen version was then tested once
on a fresh held-out set: v1.3.0 on set 2, v1.3.1 on set 3, v1.3.2 on set 4 (set 1 was looked at during tuning and is not
reported). The learned models were trained on separate files (seeds 1000 to 1149, validation 2000 to 2029), always leaving
the test sensor out, and compared with v1.3.2 once on set 5 (seeds 51, 52). The fallback rule was chosen on validation,
frozen with a hash, and tested once on set 6 (seeds 61, 62).

## What the evidence does and does not show

The format sample is real but has no breathing reference, so it tests how the hardware is read, not accuracy. Accuracy
comes from semi-synthetic files: a fair engineering test, not a clinical one (one room, one recording, three fixed links,
simulated breathing). Three failure modes are open: a pause can sit under *no breathing concern* on a weak link; a child's
breathing can be read as a slow component right after movement; and an empty chair can raise a pause alert when faded
periodic movement in the background arms the pause test (Part 1, Section 6b). The learned estimator's best use so far,
the fallback rule, adds correct readings but makes the first failure more frequent, so the board does not use it.
Before anyone relies on the board it needs a study against a reference sensor on real people, review of the thresholds by
Filipino emergency clinicians, and the privacy and device-regulation steps at the end of Part 1.
