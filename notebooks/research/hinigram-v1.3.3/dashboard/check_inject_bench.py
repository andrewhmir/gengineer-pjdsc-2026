"""Cross-check of the injection bench with the frozen Python v1.3.2, from the bundle folder:
    node dashboard/check_inject_bench.js inject_check        (writes the injected stream and its truth log)
    python dashboard/check_inject_bench.py inject_check
    python dashboard/check_inject_bench.py inject_check bench_injected.csv bench_truth.json table.csv   (also writes the table)

It reads the injected packets exactly as the board saw them, runs hinigram_live.analyze_session (the frozen reference)
on them, and scores both pipelines against the injected truth with the notebook's rule (30 s windows that breathing
fills at least 80% of; within +/-2 per minute). The board runs the streaming version of the pipeline (75 s buffer,
running medians for the movement index) and the reference runs on the whole file, so a few windows near movement and
at the start can differ; the comparison reports how many.
Also works on a log saved from the board's bench (Download the truth log + Download the injected packets).
Alert times are listed in full as episodes (updates under 3 s apart): "152-200 s (25 updates)". For an empty chair it
also lists every rate shown and every concern raised, by either pipeline.
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hinigram_live as hl


def window_truth(t, bpm, t_end, win=30.0):
    m = (t > t_end - win) & (t <= t_end)
    if m.sum() < win * 2:
        return None
    v = bpm[m]
    pres = np.array([x is not None and x > 0 for x in v])
    if pres.mean() < 0.8:
        return None
    return float(np.mean([x for x in v if x is not None and x > 0]))


def episodes(ts):
    out = []
    for t in ts:
        if out and t - out[-1][1] < 3:
            out[-1][1] = t
            out[-1][2] += 1
        else:
            out.append([t, t, 1])
    return ", ".join(f"{a:.0f}-{b:.0f} s ({n} update{'s' if n > 1 else ''})" for a, b, n in out) or "none"


def main(d, csv_name="bench_injected.csv", log_name="bench_truth.json", out_csv=None):
    log = json.load(open(os.path.join(d, log_name)))
    S = hl.load_csi_session(os.path.join(d, csv_name))
    # the reference runs one profile per chair: the one each chair started with (a board log keeps it as profile_start)
    profiles = {c["mac"]: c.get("profile_start", c["profile"]) for c in log["chairs"]}
    for c in log["chairs"]:
        changes = [e for e in c.get("events", []) if e.get("kind") == "profile"]
        if changes:
            when = ", ".join(f"{e['t']:.0f} s" for e in changes)
            print(f"note: {c['seat']} changed profile at {when}; the reference keeps "
                  f"{profiles[c['mac']]} throughout, so compare that chair only before the first change")
    tracks = hl.analyze_session(S, hl.RRConfig(profile="adult"), profiles)
    print(f"{os.path.join(d, csv_name)}: {sum(len(S.links[m].t) for m in S.macs)} packets, {len(S.macs)} chairs, {S.duration_s:.0f} s")
    print(f"{'seat':5} {'profile':13} {'full':>5} | {'board shown':>11} {'within 2':>8} | {'python shown':>12} {'within 2':>8} | {'same state':>10}  pause alerts (python)")
    table, empty_notes = [], []
    for c in log["chairs"]:
        T = tracks.get(c["mac"])
        if T is None:
            print(c["seat"], "no reference track (too short)")
            continue
        tt = np.array(c["truth"]["t"], float)
        tb = np.array(c["truth"]["bpm"], dtype=object)
        jt = np.array([h["t"] for h in c["js"]], float)
        full = bs = bo = ps = po = same = both = 0
        alerts = []
        for k, t in enumerate(T.t):
            w = window_truth(tt, tb, t)
            # the board's live updates and the reference's file updates fall on different 2 s grids: pair each
            # reference update with the board update nearest in time (within 1 s)
            j = int(np.argmin(np.abs(jt - t))) if len(jt) else -1
            h = c["js"][j] if j >= 0 and abs(jt[j] - t) <= 1.0 else None
            if h is not None:
                both += 1
                same += h["status"] == T.status[k]
            if T.status[k] == "urgent" and "pause" in T.reason[k].lower():
                alerts.append(float(t))
            if w is None:
                continue
            full += 1
            if T.reliable[k]:
                ps += 1
                po += abs(T.bpm[k] - w) <= 2
            if h is not None and h["reliable"]:
                bs += 1
                bo += abs(h["bpm"] - w) <= 2
        al = episodes(alerts)
        if c.get("empty"):
            js = c["js"]
            for who, ts, st, rel in (("board", [h["t"] for h in js], [h["status"] for h in js], [h["reliable"] for h in js]),
                                     ("python", list(T.t), list(T.status), list(T.reliable))):
                empty_notes.append(f"{c['seat']} (empty chair), {who}: rate shown in {sum(map(bool, rel))} of {len(ts)} updates; "
                                   + "; ".join(f"{s_} {episodes([t for t, s in zip(ts, st) if s == s_])}" for s_ in ("urgent", "watch", "typical")))
        print(f"{c['seat']:5} {c['profile']:13} {full:5d} | {bs:11d} {bo:8d} | {ps:12d} {po:8d} | {same:4d}/{both:<5d}  {al}")
        table.append(dict(seat=c["seat"], profile=c["profile"], scenario=json.dumps(c.get("script")) if c.get("script") else ("empty chair" if c.get("empty") else ""),
                          windows_full=full, board_shown=bs, board_within2=bo, python_shown=ps, python_within2=po, same_state=same, paired_updates=both,
                          python_pause_alerts_s=al))
    for n in empty_notes:
        print(n)
    if out_csv:
        import pandas as pd
        pd.DataFrame(table).to_csv(out_csv, index=False)


if __name__ == "__main__":
    main(*sys.argv[1:])
