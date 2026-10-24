"""Pack the real format sample's packets for the board's injection bench (one gzip+base64 blob, about 1 MB).

The board's injection bench replays these packets in real time and adds known breathing to them in the browser, so it
needs the raw CSI rather than the processed readings in dashboard_data_room.json. Only the fields that vary in the
recording are stored: sensor, RSSI, sequence number, receiver timestamp and the 128 CSI values; the rest of each
CSI_DATA header is constant in this recording (rate 11, noise floor -96, channel 6, sig_len 47, first_word_invalid 1)
and is kept once in the blob's JSON header. From the bundle folder:
    python dashboard/pack_sample.py      (writes dashboard/sample_packets.b64, which build_dashboard.py embeds)

Layout (little-endian), gzip-compressed, then base64:
    b"HGS1", uint32 header length, header JSON (utf-8),
    uint8 sensor index[n], int8 rssi[n], uint32 seq[n], uint32 local_timestamp[n], int8 csi[n*128]
The host clock is not stored: the pipeline runs on the receiver clock, and the bench writes its own host times.
"""
import base64, gzip, hashlib, json, os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
sys.path.insert(0, B)
import hinigram_live as hl

SRC = os.path.join(B, "demo_20261019_024431.csv")
CONST = ["rate", "sig_mode", "mcs", "bandwidth", "smoothing", "not_sounding", "aggregation", "stbc", "fec_coding", "sgi",
         "noise_floor", "ampdu_cnt", "channel", "secondary_channel", "ant", "sig_len", "rx_state", "len", "first_word_invalid"]


def main(dst=os.path.join(HERE, "sample_packets.b64")):
    rows = []
    with open(SRC, encoding="utf-8") as f:
        for line in f:
            b = line.find("[")
            hdr = [x.strip() for x in line[:b].replace('"', "").rstrip(",").split(",")]
            vals = [int(v) for v in line[b + 1:line.rfind("]")].split(",")]
            if len(hdr) != 25 or hdr[1] != "CSI_DATA" or len(vals) != 128:
                sys.exit("unexpected line: " + line[:80])
            rows.append((hdr, vals))
    names = ["t_host", "type"] + hl.HEADER_FIELDS[1:]
    consts = {}
    for k in CONST:
        j = names.index(k)
        seen = {r[0][j] for r in rows}
        if len(seen) != 1:
            sys.exit(f"{k} varies in the recording; extend the packer")
        consts[k] = int(seen.pop())
    macs = sorted({r[0][3] for r in rows})
    n = len(rows)
    mi = np.array([macs.index(r[0][3]) for r in rows], np.uint8)
    rssi = np.array([int(r[0][4]) for r in rows], np.int8)
    seq = np.array([int(r[0][2]) for r in rows], np.uint32)
    ts = np.array([int(r[0][19]) for r in rows], np.uint32)
    csi = np.array([r[1] for r in rows], np.int8)
    head = json.dumps({"file": os.path.basename(SRC), "n": n, "macs": macs, "const": consts, "t_host0": float(rows[0][0][0]),
                       "sha256": hashlib.sha256(open(SRC, "rb").read()).hexdigest()}).encode()
    blob = (b"HGS1" + struct.pack("<I", len(head)) + head + mi.tobytes() + rssi.tobytes() + seq.astype("<u4").tobytes()
            + ts.astype("<u4").tobytes() + csi.tobytes())
    out = base64.b64encode(gzip.compress(blob, 9, mtime=0)).decode()
    open(dst, "w").write(out)
    print(f"wrote {dst}: {n} packets, {len(macs)} sensors, {len(out) / 1e6:.2f} MB base64")


if __name__ == "__main__":
    main(*sys.argv[1:])
