"""Rewrite a CSI log that was saved with tabs or semicolons (for example re-saved from a spreadsheet) into the receiver's
own comma-separated layout, which hinigram_live.py, the notebooks and hinigram_paced.py read. The board reads either.
Header rows (pc_time,type,id,mac,...) and other non-CSI lines are dropped; every CSI_DATA field is kept as it was.

    python firmware/tools/to_receiver_csv.py my_log.tsv            (writes my_log_receiver.csv next to it)
    python firmware/tools/to_receiver_csv.py my_log.tsv out.csv
"""
import os, re, sys


def convert(src, dst=None):
    dst = dst or os.path.splitext(src)[0] + "_receiver.csv"
    if os.path.exists(dst):
        sys.exit(f"{dst} exists; choose another name (recordings are never overwritten)")
    kept = skipped = 0
    with open(src, encoding="utf-8", errors="replace") as fin, open(dst, "x", encoding="utf-8") as fout:
        for line in fin:
            s = line.strip()
            b, e = s.find("["), s.rfind("]")
            if "CSI_DATA" not in s or b < 0 or e < b:
                skipped += 1
                continue
            head = [x.strip() for x in re.split(r"[,\t;]", s[:b].replace('"', "").rstrip(",\t; "))]
            vals = [v.strip() for v in s[b + 1:e].split(",")]
            fout.write(",".join(head) + ',"[' + ",".join(vals) + ']"\n')
            kept += 1
    print(f"{dst}: {kept} CSI_DATA lines written, {skipped} other lines dropped")
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    convert(*sys.argv[1:3])
