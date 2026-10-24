"""Build Hinigram_v1_3_3_complete.ipynb: both notebooks in one file that runs on its own.

Its first code cell carries the bundle (code, data, trained models and saved results; not the notebooks, the figure
PNGs the notebook draws, or two bulky files whose summaries the notebooks show) as one gzip archive, checks its SHA-256, unpacks it into ./hinigram_files and moves there.
Part 1's cells follow, then a cell that moves into training/, then Part 2's cells. From the bundle folder:

    python development/build_complete_notebook.py <template: the v1.3.2 complete notebook> <output.ipynb>

The template supplies the unpacking cell's code and the two section headers; the cells themselves come from
Hinigram_v1_3_3.ipynb and training/Hinigram_training.ipynb. Outputs are cleared: run the result once (it needs nothing
but the file itself) before sharing it.
"""
import base64
import hashlib
import io
import os
import re
import sys
import tarfile

import nbformat as nbf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".ipynb_checkpoints", "figures", "mldata", "mldata_tmp", "hku"}
# kept in the bundle, but the notebooks only show summaries of them: per-window model predictions and the fallback's
# window table. The packed format sample stays in: the bench checks the notebook cites read it.
SKIP_FILES = ("_pred.npz", "fallback_window_table.csv.gz")


NOTE = ("This folder was unpacked by Hinigram_v1_3_3_complete.ipynb. To keep that file small it leaves out the two notebooks\n"
        "(their cells are in the complete notebook), the figure PNGs, the per-window model predictions (training/mlruns/*_pred.npz)\n"
        "and the fallback's window table (training/results/fallback_window_table.csv.gz). Everything the notebook runs, and the\n"
        "board's checks, work here. Rebuilding the Part 2 tables (run_ml_report.py, hinigram_schedule.py, hinigram_fallback.py)\n"
        "needs the full bundle, Hinigram_v1.3.3.zip; README.md describes that bundle.\n")


def archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tar:
        note = tarfile.TarInfo("hinigram_files/NOTE.txt")
        note.size, note.mode = len(NOTE.encode()), 0o644
        tar.addfile(note, io.BytesIO(NOTE.encode()))
        for root, dirs, files in os.walk(HERE):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                if f.endswith((".ipynb", ".pyc") + SKIP_FILES):
                    continue
                p = os.path.join(root, f)
                info = tar.gettarinfo(p, arcname=os.path.join("hinigram_files", os.path.relpath(p, HERE)))
                info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
                with open(p, "rb") as fh:
                    tar.addfile(info, fh)
    return buf.getvalue()


def clear(cells):
    for c in cells:
        if c.cell_type == "code":
            c.outputs, c.execution_count = [], None
    return cells


def main(template, out):
    tpl = nbf.read(template, as_version=4)
    p1 = nbf.read(os.path.join(HERE, "Hinigram_v1_3_3.ipynb"), as_version=4)
    p2 = nbf.read(os.path.join(HERE, "training", "Hinigram_training.ipynb"), as_version=4)
    raw = archive()
    sha = hashlib.sha256(raw).hexdigest()
    unpack = tpl.cells[1].source
    unpack = re.sub(r'ARCHIVE_SHA256 = "[0-9a-f]+"', f'ARCHIVE_SHA256 = "{sha}"', unpack)
    unpack = re.sub(r'_unpack\("[^"]*"\)', '_unpack("' + base64.b64encode(raw).decode() + '")', unpack)

    intro = p1.cells[0].source
    intro = intro.replace("This notebook replaces v1.2. It follows three questions from the audit:",
                          "This notebook replaces v1.2. It follows four questions from the audit:")
    intro = intro.replace("3. **Are the alerts clinically sensible and the display usable?** Sections 4 to 6.",
                          "3. **Are the alerts clinically sensible and the display usable?** Sections 4 to 6.\n"
                          "4. **Can a trained model read the rate better than the rules?** Part 2 trains ResoNet and two baselines, "
                          "tests them against v1.3.2, and follows up with the paper's training schedule, a fallback rule and real breathing references.")
    intro = intro.replace("(`training/Hinigram_training.ipynb`, Sections 7 to 10)", "(Part 2, Sections 7 to 10)")
    intro += ("\n\n> **This file runs on its own.** Run all cells in Jupyter, VS Code or Colab. The first code cell carries the code, "
              f"the data, the trained models and the saved results as one compressed archive ({len(raw) / 1e6:.0f} MB). It unpacks them into a "
              "folder named `hinigram_files` next to the notebook and works there. Every output below was produced that way, starting "
              "from an empty folder.\n>\n> Needs Python 3.10 or newer with numpy, scipy, pandas, matplotlib and scikit-learn. Retraining "
              "the learned models also needs jax and optax, and about 10 minutes on four cores to rebuild their training data.")

    setup1 = p1.cells[2].source
    setup1 = setup1.replace("# Setup. Keep this notebook in the same folder as the modules and data files that came with it.",
                            "# Setup. The first code cell unpacked the modules and data and moved into that folder.")
    setup1 = setup1.replace("Put the CSV from the receiver next to this notebook.", "Run the first code cell, which unpacks it.")
    p1.cells[2].source = setup1
    head2 = p2.cells[0].source.replace("# Hinigram: preprocessing and training a learned breathing-rate estimator",
                                       "# Part 2. Preprocessing and training a learned breathing-rate estimator")
    head2 = head2.replace("This notebook builds and tests", "This part builds and tests")
    p2.cells[0].source = head2
    setup2 = p2.cells[2].source.replace("# Setup. Keep this notebook in the training folder of the bundle.",
                                        "# Setup for Part 2, inside the unpacked training folder.")
    p2.cells[2].source = setup2

    nb = nbf.v4.new_notebook(metadata=tpl.metadata)
    nb.cells = clear([nbf.v4.new_markdown_cell(intro), nbf.v4.new_code_cell(unpack),
                      nbf.v4.new_markdown_cell("# Part 1. The v1.3.2 pipeline: audit, rebuild and validation")]
                     + p1.cells[1:]
                     + [p2.cells[0], nbf.v4.new_code_cell('# Part 2 works inside the training folder that the first code cell unpacked.\n'
                                                          'os.chdir(os.path.join(HINIGRAM_ROOT, "training"))')]
                     + p2.cells[1:])
    nbf.write(nb, out)
    print(f"{out}: {len(nb.cells)} cells, archive {len(raw) / 1e6:.1f} MB, sha256 {sha[:16]}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
