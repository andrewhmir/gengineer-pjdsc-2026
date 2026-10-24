"""Demo room for the ESP32-only build: 12 chairs in three rows, each chair with its own ESP32 node on the backrest and
its link to one of two receivers in the front corners. There are only three real links in the recording, so each
chair reuses the packets of one real sensor (loss, timing jitter, gain steps and movement kept) with its own
simulated breathing added. From the bundle folder, after export_dashboard.py and export_dashboard_js.js:
    python dashboard/export_room_demo.py      (writes dashboard/dashboard_data_room.json, which build_dashboard.py reads)"""
import json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)                      # the bundle folder
sys.path[:0] = [B, HERE]
os.chdir(B)
import hinigram_live as hl
import semi_gen
import export_dashboard as ex

SCEN = dict(semi_gen.SCEN, normal15=[(0, 180, 15)], normal13=[(0, 180, 13)], normal17=[(0, 180, 17)], normal16=[(0, 180, 16)],
            normal19=[(0, 180, 19)], child30=[(0, 180, 30)], infant38=[(0, 180, 38)])
# seat: (scenario, modulation depth, age profile). Chairs 1-2 of each row link to receiver 1 (front-left corner),
# chairs 3-4 to receiver 2 (front-right corner).
SEATS = [("A1", "normal15", 0.05, "adult"), ("A2", "normal_to_fast", 0.05, "adult"), ("A3", "child30", 0.05, "child_1_5y"),
         ("A4", "normal17", 0.015, "adult"), ("B1", "fast_watch", 0.05, "adult"), ("B2", "normal13", 0.04, "adult"),
         ("B3", "pause", 0.05, "adult"), ("B4", "infant38", 0.05, "infant_2_12m"), ("C1", "child_fast", 0.05, "child_1_5y"),
         ("C2", "normal16", 0.035, "adult"), ("C3", "slow", 0.05, "adult"), ("C4", "normal19", 0.045, "adult")]
os.makedirs("semi", exist_ok=True)
sensors, packets, dur = [], 0, None
for k in range(4):
    group = SEATS[3 * k:3 * k + 3]
    scs = {m: hl.BreathingScenario(SCEN[n], depth=d, phase_depth=d, seed=300 + 3 * k + j, name=n)
           for j, (m, (_, n, d, _)) in enumerate(zip(semi_gen.MACS, group))}
    path = os.path.join("semi", f"room_demo_{k}.csv")
    if not os.path.exists(path):
        hl.inject_breathing(semi_gen.SRC, path, scs)
    out = ex.export(path, {m: p for m, (_, _, _, p) in zip(semi_gen.MACS, group)}, scs)
    packets += out["packets"]; dur = out["duration"] if dur is None else min(dur, out["duration"])
    for j, (s, (seat, n, d, p)) in enumerate(zip(out["sensors"], group)):
        col = int(seat[1:])
        s.update(seat=seat, label=f"Node {seat}", mac=f"1a:00:00:00:{k + 1:02d}:{j + 1:02d}", row=seat[0], col=col,
                 rx=1 if col <= 2 else 2, reuse=j + 1)
        s["health"]["sensor"] = f"Node {seat} (packets of sensor {j + 1})"
        sensors.append(s)
sensors.sort(key=lambda s: s["seat"])
room = dict(file="demo_20261019_024431.csv", title="Demo room", duration=dur, packets=packets, start=out["start"], sensors=sensors,
            receivers=[dict(id=1, label="Receiver 1", corner="front-left"), dict(id=2, label="Receiver 2", corner="front-right")],
            note="12 chairs; each reuses the packets of one of the three real sensors, with simulated breathing added.")
data = json.load(open(os.path.join(HERE, "dashboard_data_final.json")))
data["sources"]["demo"] = room
data["generated"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dashboard_data_room.json")
json.dump(data, open(dst, "w"), separators=(",", ":"))
print("wrote", dst, os.path.getsize(dst), "bytes;", len(sensors), "chairs")
for s in sensors:
    h = s["hops"]; i = max(j for j, t in enumerate(h["t"]) if t <= 131)
    print(s["seat"], s["profile"], h["status"][i], h["bpm"][i], h["reason"][i])
