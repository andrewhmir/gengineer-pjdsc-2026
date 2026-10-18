# `research/` — the research record, not the executed analysis lane

These are the team's two research notebooks, committed so the work that produced the
Pa-Hinga (`CSI-YASAT`) method and the Resonance Network study is readable, citable, and
reviewable in the repository rather than living off-repository. They are **records**, not
part of the executed analysis narrative: the CI `Execute notebooks` job runs the direct
children of [`notebooks/`](../) and excludes this directory by path. The rule and its
reasoning are in the lane [`README.md`](../README.md#execution-how-notebooks-are-selected-and-run).

## The two notebooks

### `CSI_YASAT_PaHinga_All_In_One_Master_v2_1.ipynb`

The all-in-one master (v2.1): the 136-byte Slotted-TDMA frame and its unpacking, the causal
DSP chain (CSCR, cyclostationary filtering), the cold-start Stuart–Landau Hopf resonator with
an RK4 solver, the `ResonanceNetwork` / `FastResonanceNetwork` / `HopfProbe` ablation, the
two-stage 3D room calibration and Fresnel localizer, the embedded 3D waiting-room triage UI,
and the three-thread host runtime with its latency profiler and Bland–Altman validation.
Runs in Google Colab, or on a local machine with a GPU.

### `D01_10-17_Gengineer.ipynb`

The Resonance Network study on the High-Gamma Dataset: readout ablation (`power` / `sync` /
`sync_imag` / `both`), dynamics ablation (nonlinear-coupled vs linear FFT bank), EEGNet and
ShallowConvNet baselines, paired statistics against the sample-size threshold, and the Hopf
probe. Runs on a GPU machine; the data steps expect the per-subject cache and dataset access
described below.

Both filenames are kept exactly as the work was recorded. `D01_10-17_Gengineer.ipynb` is
cited by that name in [`specs/2026-10-17-webapp-design.md`](../../specs/2026-10-17-webapp-design.md)
(the Method page follows its notation and PLV definition), and `specs/` is frozen.

## Why they are not in the executed lane

The notebooks lane executes every direct child of `notebooks/` through `nbmake` against the
locked root environment, offline, with committed synthetic fixtures only. These notebooks
need `torch`, `scipy`, `scikit-learn`, `wfdb` and `kagglehub`, and they download real
datasets (several gigabytes, some behind PhysioNet credentialing). The root project
deliberately does not install a 2 GB torch dependency — see §16 of the design record — so
executing them in CI would fail on the first import, not on anything about the analysis.
That is the whole reason for the path exclusion; nothing here excuses a broken notebook.

## How to run them

**Master.** Open it in Google Colab (the notebook's own instructions assume Colab), choose a
GPU runtime, and run top to bottom. It synthesises its own CSI streams for the DSP, Hopf and
runtime sections, so it needs no downloaded dataset for those parts; the `wfdb` and
scikit-learn imports are used by the dataset-loader definitions. Running it writes
`csi_yasat_3d_room_triage_ui.html` and `firmware_esp32_v2/*.cpp` into the working directory.

**D01.** Three things must exist before the study cells run:

1. `subj_cache/subj_<N>.npz` — the per-subject High-Gamma windows (`X_tr`, `y_tr`, `X_te`,
   `y_te`), derived from the High-Gamma Dataset; the notebook's own header says the raw store
   is `.edf` and that the cache is what it reads.
2. Kaggle credentials for `kagglehub.dataset_download("guozhenjennzhu/csi-bench")`.
3. PhysioNet access for `wfdb.get_record_list("mimic3wdb")`.

The data-setup cells write to `/content/drive/MyDrive/RESEARCH` — the Google Drive mount a
Colab runtime provides. That absolute path is Colab-specific on purpose: this notebook is not
a clean-clone notebook, and it is not offered as one. Adjust the path if you run it elsewhere.

The study's two input roots are **not** hard-coded. They come from `RN_CACHE_DIR` and
`RN_DATA_DIR`, defaulting to the notebook-relative `subj_cache/` and
`data/eeg_data/mne_data_backup/`. The committed file carries no machine-specific path: the
two absolute Windows paths the original run used were replaced with those environment
lookups before the commit, so a different machine changes two environment variables rather
than editing the notebook.

Both notebooks set seed `42` (`torch.manual_seed` / `np.random.seed`) for every split,
initialisation and sampling step, so a re-run on the same data reproduces the numbers.

## Provenance and state

- The master is the **v2.1 all-in-one consolidation** of the Pa-Hinga backend library
  (`csi_yasat_resonet.py`), the pre-executed PJDSC-Gengineer experiments, and the 3D
  waiting-room digital twin. It was produced outside this repository, on Colab.
- D01 is the 17 October 2026 Resonance Network study. Its section 11 is deliberately an
  "honest conclusion": the notebook records the small-N caveat and expects the strong
  band-power baseline to lead, because the contribution is the controlled isolation, not a
  superiority claim.
- **Outputs were stripped before the commit** (`nbstripout`), so the committed files carry no
  stored outputs of any kind: no executed results, no embedded tables, no plots or base64
  imagery from a run. What a reader sees is code and prose only; re-running reproduces the
  numbers. The same pass normalises cell ids, so
  `uv run nbstripout --verify notebooks/research/<name>.ipynb` exits 0.

## Data and privacy

No data is committed here. Everything these notebooks read is retrieved at run time, and
every dataset is cited in [`docs/SOURCES.md`](../../docs/SOURCES.md) before it appears:

- MIMIC-III Waveform Database (PhysioNet) — de-identified ICU waveforms.
- CSI-Bench (Kaggle) — WiFi CSI sensing benchmark.
- High-Gamma Dataset (Schirrmeister et al., 2017) — 128-channel EEG.

MIMIC-III is de-identified and openly accessible, but it is still patient-derived data: it
stays outside the repository, and the Data Privacy Act rule in
[`docs/DATA.md`](../../docs/DATA.md) applies to anything derived from it. Nothing
person-identifying appears in these notebooks or in their committed outputs — the outputs are
gone entirely.

## Not a place for new work

`research/` holds finished records. An unfinished notebook does not belong here either: no
job executes this directory, so nothing would catch it. New analysis that should run in CI
belongs one directory up, as `notebooks/NN-topic.ipynb`, where the lane's hygiene tests and
the `nbmake` job both see it.
