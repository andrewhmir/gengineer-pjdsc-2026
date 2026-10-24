"""Record Hinigram receivers to CSV files, with a host timestamp in front of every line.

That is the format the notebook (hinigram_live.load_csi_session) and the board's "Open a CSV file" read. One file per
receiver; the HINIGRAM_RX status lines are kept (the readers skip them) so each file records the chip and settings.

    pip install pyserial
    python log_serial.py COM5                      (Windows)
    python log_serial.py /dev/ttyUSB0 /dev/ttyUSB1 --baud 921600 --out recordings
Stop with Ctrl+C.
"""
import argparse
import datetime
import os
import threading
import time

import serial


def record(port, baud, path, stop):
    with serial.Serial(port, baud, timeout=0.5) as s, open(path, "a", encoding="ascii", errors="replace", newline="") as f:
        buf = b""
        while not stop.is_set():
            chunk = s.read(8192)
            if not chunk:
                continue
            t = time.time()
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for raw in lines:
                txt = raw.decode("ascii", "replace").strip()
                if txt.startswith("CSI_DATA") or txt.startswith("HINIGRAM_RX"):
                    f.write(f"{t:.6f},{txt}\n")
            f.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="+")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--out", default="recordings")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stop, threads = threading.Event(), []
    for i, port in enumerate(a.ports):
        path = os.path.join(a.out, f"hinigram_rx{i + 1}_{stamp}.csv")
        th = threading.Thread(target=record, args=(port, a.baud, path, stop), daemon=True)
        th.start()
        threads.append(th)
        print("recording", port, "to", path)
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop.set()
        for t in threads:
            t.join(timeout=2)
        print("stopped")


if __name__ == "__main__":
    main()
