"""Assemble the dashboard: one self-contained page (artifact body) plus a standalone .html file."""
import json, os, re, sys
D = os.path.dirname(os.path.abspath(__file__))
rd = lambda n: open(os.path.join(D, n), encoding="utf-8").read()
head, body = rd("template_head.html"), rd("template_body.html")
dsp, inj, wrk, app = rd("hinigram_dsp.js"), rd("hinigram_inject.js"), rd("template_worker.js"), rd("template_app.js")
# the format sample's raw packets for the injection bench (pack_sample.py); about 1.1 MB of base64
sample = rd("sample_packets.b64").strip() if os.path.exists(os.path.join(D, "sample_packets.b64")) else ""
data = json.loads(rd("dashboard_data_room.json" if os.path.exists(os.path.join(D, "dashboard_data_room.json")) else "dashboard_data_final.json"))
data["version"] = "Hinigram v1.3.3 (pipeline v1.3.2)"     # the board changed in v1.3.3; hinigram_live.py did not
for name, js in (("dsp", dsp), ("inject", inj), ("worker", wrk), ("app", app)):
    if re.search(r"</script", js, re.I) or "<!--" in js:
        sys.exit(f"{name} contains a sequence that would end the script block")
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
scripts = (
    f'<script id="dsp-src">\n{dsp}\n</script>\n'
    f'<script id="inject-src">\n{inj}\n</script>\n'
    f'<script id="worker-src" type="text/plain">\n{wrk}\n</script>\n'
    f'<script id="sample-packets" type="text/plain">{sample}</script>\n'
    f'<script type="application/json" id="hinigram-data">{blob}</script>\n'
    f'<script>\n{app}\n</script>\n'
)
artifact = head + "\n" + body + "\n" + scripts
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              + head + '\n</head>\n<body>\n' + body + '\n' + scripts + '</body>\n</html>\n')
for fn, txt in (("hinigram_dashboard.html", artifact), ("Hinigram_dashboard_standalone.html", standalone)):
    open(os.path.join(D, fn), "w", encoding="utf-8").write(txt)
    print(fn, f"{len(txt.encode('utf-8')) / 1024:.0f} KB")
for bad in ("—",):
    for fn, txt in (("artifact", artifact),):
        if bad in txt:
            print("WARNING: em dash found in", fn)
