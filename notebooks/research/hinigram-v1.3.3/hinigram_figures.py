"""
hinigram_figures.py  (Hinigram v1.3.2)
====================================
Figures built from the live format sample and from the audit/validation runs.
Every function returns the matplotlib Figure; nothing here invents data.
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.lines import Line2D

import hinigram_style as hs
import hinigram_live as hl


def _sensor_index(S, mac):
    return S.macs.index(mac) + 1


def _rolling_mean(x, n):
    n = max(1, int(n))
    c = np.cumsum(np.r_[0.0, np.asarray(x, float)])
    out = np.empty(len(x))
    for i in range(len(x)):
        lo = max(0, i - n + 1)
        out[i] = (c[i + 1] - c[lo]) / (i + 1 - lo)
    return out


def _motion_spans(t, flag, min_len=0.5):
    spans, start = [], None
    for ti, f in zip(t, flag):
        if f and start is None:
            start = ti
        elif not f and start is not None:
            if ti - start >= min_len:
                spans.append((start, ti))
            start = None
    if start is not None:
        spans.append((start, t[-1]))
    return spans


# --------------------------------------------------------------------------- #
# L1. Stream health of the live format sample
# --------------------------------------------------------------------------- #
def fig_live_health(S, health=None, fs=10.0):
    health = health or hl.session_health(S)
    t_end = min(float(L.t[-1]) for L in S.links.values())
    tg = np.arange(5.0, t_end, 0.5)
    fig, axes = plt.subplots(4, 1, figsize=(11.5, 9.2), sharex=True,
                             gridspec_kw=dict(height_ratios=[1, 1.1, 0.9, 0.9], hspace=0.42))
    feats = {}
    for mac in S.macs:
        k = _sensor_index(S, mac)
        L = S.links[mac]
        col = hs.SENSOR[k]
        rate = hl.rolling_rate(L, tg, 5.0)
        axes[0].plot(tg, rate, color=col, lw=1.8)
        # RSSI: 1 s rolling mean on the receiver clock
        F = hl.link_features(L, fs=fs, t_end=t_end)
        feats[mac] = F
        axes[1].plot(F.t, _rolling_mean(F.rssi, fs), color=col, lw=1.6)
        # gain steps: share of packets whose RMS amplitude jumps > 1.5 dB from the previous packet
        amp = np.abs(L.H[:, hl.valid_slots(bool(L.first_word_invalid[0]))])
        mdb = 20 * np.log10(np.sqrt(np.mean(amp ** 2, axis=1)) + 1e-9)
        step = np.r_[0, np.abs(np.diff(mdb)) > 1.5].astype(float)
        lo = np.searchsorted(L.t, tg - 5.0); hi = np.searchsorted(L.t, tg)
        cs = np.cumsum(np.r_[0, step])
        share = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1) * 100
        axes[2].plot(tg, share, color=col, lw=1.6)
        axes[3].plot(F.t, F.activity, color=col, lw=1.2)
    # motion episodes (any sensor above threshold), shaded on every panel
    tt = feats[S.macs[0]].t
    act = np.max(np.vstack([np.interp(tt, feats[m].t, feats[m].activity) for m in S.macs]), axis=0)
    spans = _motion_spans(tt, act > 1.0, min_len=1.0)
    for ax in axes:
        for a, b in spans:
            hs.status_patch(ax, a, b, "moving", alpha=0.9)
    axes[3].axhline(1.0, color=hs.INK_3, lw=1.0)
    hs.hand(axes[3], t_end, 1.15, "movement threshold", va="bottom", ha="right", size=10, color=hs.INK_2)
    axes[3].set_yscale("log")
    axes[3].set_ylim(0.05, max(30, float(np.nanmax(act)) * 1.3))
    axes[0].set_ylim(0, 36)
    axes[0].set_ylabel("Packets / s")
    hs.hand(axes[0], t_end, 4, "v1.2 assumed 100 packets/s per link;\nthe nodes deliver about 28.5",
            va="bottom", ha="right", size=10.5, color=hs.STATUS["urgent"]["text"], linespacing=1.15)
    axes[1].set_ylabel("RSSI (dBm)")
    axes[2].set_ylabel("Gain steps\n(% of packets)")
    axes[2].set_ylim(0, 100)
    axes[3].set_ylabel("Movement index\n(log scale)")
    axes[3].set_xlabel("Time in recording (s, receiver clock)")
    titles = ["A  Packet rate per sensor (5 s window)", "B  Received signal strength",
              "C  Automatic-gain steps in the CSI scale", "D  Movement index (shaded = movement detected)"]
    for ax, ti in zip(axes, titles):
        ax.set_title(ti, fontsize=10.5)
    handles = [Line2D([0], [0], color=hs.SENSOR[k], lw=2.2, marker=hs.SENSOR_MARKER[k], ms=5,
                      label=f"{hs.SENSOR_NAME[k]} ({S.macs[k - 1][-5:]})") for k in (1, 2, 3)]
    handles.append(mpl.patches.Patch(facecolor=hs.STATUS["moving"]["tint"], hatch="\\\\\\\\",
                                     edgecolor=hs.STATUS["moving"]["edge"], label="Movement detected"))
    axes[0].legend(handles=handles, ncol=4, loc="lower left", bbox_to_anchor=(-0.01, 1.16), fontsize=8.5)
    hs.suptitle(fig, "What the three sensors actually delivered",
                f"Live format sample {S.path.split('/')[-1]}: {S.duration_s:.0f} s, "
                f"{sum(h['packets'] for h in health):,} packets, channel {health[0]['channel']}, "
                f"{health[0]['valid_subcarriers']} usable subcarriers per packet", y=0.985)
    hs.source_note(fig, "Rates use the receiver's own clock (local_timestamp). Movement index combines RSSI spread "
                        "and change in the CSI shape; above 1 means movement.", y=0.045)
    return fig


# --------------------------------------------------------------------------- #
# L2. CSI payload layout (what is valid in the 128-byte LLTF block)
# --------------------------------------------------------------------------- #
def fig_payload_layout(S, legacy_mask=None):
    mac = S.macs[0]
    L = S.links[mac]
    amp = np.abs(L.H)
    mean_amp = np.nanmean(np.where(np.isfinite(amp), amp, np.nan), axis=0)
    mean_amp = np.nan_to_num(mean_amp, nan=0.0)
    valid = np.zeros(64, bool); valid[hl.valid_slots(True)] = True
    corrupt = np.zeros(64, bool); corrupt[[0, 1]] = True
    fig = plt.figure(figsize=(11.5, 7.6))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 0.22, 1.25], hspace=0.62, top=0.86)
    ax = fig.add_subplot(gs[0]); axm = fig.add_subplot(gs[1], sharex=ax); axh = fig.add_subplot(gs[2])
    x = np.arange(64)
    cols = np.where(valid, hs.BRAND, np.where(corrupt, hs.STATUS["no_reading"]["fill"], hs.SUNKEN))
    ax.bar(x, np.where(corrupt, np.nanmax(mean_amp) * 0.15, mean_amp), width=0.78, color=cols,
           edgecolor=np.where(valid, "none", hs.LINE_UI), linewidth=np.where(valid, 0, 0.6))
    for i in np.where(corrupt)[0]:
        ax.bar(i, np.nanmax(mean_amp) * 0.15, width=0.78, color="none", edgecolor=hs.LINE_UI, hatch="////", lw=0.6)
    ax.set_xlim(-1, 64)
    ax.set_ylabel("Mean |CSI| (int8 units)")
    ax.set_title("A  Mean amplitude in each of the 64 slots (Sensor 1)", fontsize=10.5)
    hs.hand(ax, 32, np.nanmax(mean_amp) * 0.42, "guard and null\nslots 27 to 37", ha="center", size=10.5, color=hs.INK_2)
    leg = [mpl.patches.Patch(color=hs.BRAND, label="Valid data subcarrier"),
           mpl.patches.Patch(facecolor=hs.SUNKEN, edgecolor=hs.LINE_UI, label="Guard / null"),
           mpl.patches.Patch(facecolor=hs.STATUS["no_reading"]["fill"], edgecolor=hs.LINE_UI, hatch="////",
                             label="Corrupt first word")]
    ax.legend(handles=leg, ncol=3, loc="lower right", bbox_to_anchor=(1.0, 1.0), fontsize=8.5)
    ax.set_xticks([0, 2, 14, 26, 32, 38, 50, 63])
    ax.set_xticklabels(["slot 0\nDC", "2\n+2", "14\n+14", "26\n+26", "32\n-32", "38\n-26", "50\n-14", "63\n-1"])
    # mask strip: which slots each version reads
    axm.set_ylim(-0.6, 1.6); axm.set_yticks([0, 1]); axm.set_yticklabels(["v1.3 reads", "v1.2 reads"])
    axm.grid(False)
    for spine in axm.spines.values():
        spine.set_visible(False)
    axm.tick_params(axis="x", labelbottom=False)
    v13 = valid
    for i in range(64):
        if v13[i]:
            axm.add_patch(mpl.patches.Rectangle((i - 0.39, -0.35), 0.78, 0.7, color=hs.BRAND))
        if legacy_mask is not None and legacy_mask[i]:
            bad = not valid[i]
            axm.add_patch(mpl.patches.Rectangle((i - 0.39, 0.65), 0.78, 0.7,
                                                facecolor=hs.STATUS["urgent"]["fill"] if bad else hs.LINE_UI,
                                                edgecolor="none"))
    if legacy_mask is not None:
        n_bad = int(np.sum(legacy_mask & ~valid)); n_miss = int(np.sum(valid & ~legacy_mask))
        axm.text(64.5, 1.0, f"{n_bad} null slots read (red), {n_miss} valid slots skipped", va="center",
                 fontsize=8.5, color=hs.STATUS["urgent"]["text"])
        axm.text(64.5, 0.0, f"{int(valid.sum())} valid subcarriers", va="center", fontsize=8.5, color=hs.INK_2)
    # heatmap of amplitude shape over time, frequency order
    slots = hl.valid_slots(True)
    sc = hl.ESP32_SLOT_TO_SUBCARRIER[slots]
    shape, _, _ = hl.sanitize_packets(L.H, True)
    tg = np.arange(L.t[0], L.t[-1], 0.25)
    Z = np.stack([np.interp(tg, L.t, shape[:, j]) for j in range(shape.shape[1])])
    im = axh.imshow(Z, aspect="auto", origin="lower", cmap="hinigram_teal",
                    extent=[tg[0], tg[-1], 0, len(sc)], vmin=0.6, vmax=1.35, interpolation="nearest")
    yt = [0, 13, 38, 50]
    axh.set_yticks(np.array(yt) + 0.5)
    axh.set_yticklabels([f"{sc[i]:+d}" for i in yt])
    axh.axhline(26, color=hs.FIG_BG, lw=1.2)
    axh.text(tg[0] + 1, 26.6, "DC gap", fontsize=7.5, color=hs.INK, va="bottom")
    axh.grid(False)
    axh.set_ylabel("Subcarrier index")
    axh.set_xlabel("Time in recording (s)")
    axh.set_title("B  Gain-normalised amplitude per subcarrier over time (Sensor 1)", fontsize=10.5)
    cb = fig.colorbar(im, ax=axh, pad=0.01, fraction=0.025)
    cb.set_label("|H| / packet RMS", color=hs.INK_2)
    cb.outline.set_visible(False)
    hs.suptitle(fig, "The CSI payload: 64 slots, 51 carry data",
                "ESP32 reports the legacy long training field as slots [0..31, -32..-1], imaginary part first. "
                "Slots 0 to 1 are corrupt when first_word_invalid = 1.", y=0.955)
    return fig


# --------------------------------------------------------------------------- #
# L3. Automatic gain control steps
# --------------------------------------------------------------------------- #
def fig_gain_steps(S, mac=None, t_zoom=(125.0, 135.0)):
    mac = mac or S.macs[1]
    k = _sensor_index(S, mac)
    L = S.links[mac]
    amp = np.abs(L.H[:, hl.valid_slots(True)])
    mdb = 20 * np.log10(np.sqrt(np.mean(amp ** 2, axis=1)) + 1e-9)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), gridspec_kw=dict(width_ratios=[2.1, 1, 1.1], wspace=0.38))
    m = (L.t >= t_zoom[0]) & (L.t < t_zoom[1])
    axes[0].plot(L.t[m], mdb[m], color=hs.SENSOR[k], lw=0.9, alpha=0.55)
    axes[0].plot(L.t[m], mdb[m], ls="none", marker=hs.SENSOR_MARKER[k], ms=3.2, color=hs.SENSOR[k])
    axes[0].set_xlabel("Time in recording (s)")
    axes[0].set_ylabel("Packet RMS amplitude (dB)")
    axes[0].set_title(f"A  {hs.SENSOR_NAME[k]}: consecutive packets", fontsize=10.5)
    q = (L.t >= 110) & (L.t <= 173)
    axes[1].hist(mdb[q], bins=60, color=hs.SENSOR[k], alpha=0.85, orientation="horizontal")
    axes[1].set_ylim(axes[0].get_ylim())
    axes[1].set_xlabel("Packets")
    axes[1].set_title("B  Fixed gain levels (110 to 173 s)", fontsize=10.5)
    axes[1].grid(axis="y", visible=False)
    rs = L.rssi[q].astype(float)
    jit = (np.random.default_rng(0).random(rs.size) - 0.5) * 0.6
    axes[2].plot(rs + jit, mdb[q], ls="none", marker="o", ms=2.2, alpha=0.35, color=hs.SENSOR[k])
    axes[2].set_xlabel("RSSI (dBm, jittered)")
    axes[2].set_ylabel("Packet RMS amplitude (dB)")
    axes[2].set_title("C  Same RSSI, different scale", fontsize=10.5)
    hs.suptitle(fig, "Gain steps: the CSI scale jumps between fixed levels from packet to packet",
                "Breathing changes the amplitude by well under 1 dB; these steps are 3 to 9 dB and do not follow RSSI. "
                "v1.3 divides each packet by its own RMS; the firmware fix is to lock the receiver gain.", y=1.06)
    return fig


# --------------------------------------------------------------------------- #
# V1. Same raw format sample, two pipelines (no breathing reference)
# --------------------------------------------------------------------------- #
STATUS_SHORT = {"urgent": "Needs help now", "watch": "Watch", "typical": "No concern",
                "no_reading": "No reading", "moving": "Moving"}


def _status_ribbon(ax, t, status, hop=2.0, y0=0.0, y1=1.0):
    for ti, st in zip(t, status):
        hs.status_patch(ax, ti - hop, ti, st, y0=y0, y1=y1)


def fig_raw_sample_two_pipelines(rows_null, macs):
    """rows_null: list of dicts (validation rows for the raw sample) with legacy_* and new_* fields."""
    import pandas as pd
    d = pd.DataFrame(rows_null)
    fig = plt.figure(figsize=(11.5, 6.4))
    gs = fig.add_gridspec(len(macs), 2, width_ratios=[3.2, 1], hspace=0.55, wspace=0.18, top=0.83)
    for i, mac in enumerate(macs):
        k = i + 1
        g = d[d.mac == mac].sort_values("t")
        ax = fig.add_subplot(gs[i, 0])
        ax.set_ylim(0, 40)
        _status_ribbon(ax, g.t.values, g.new_status.values, y0=0.0, y1=0.13)
        ax.plot(g.t, g.legacy_bpm, ls="none", marker="s", ms=4.2, color=hs.V12, label="v1.2 reported rate")
        rel = g[g.new_reliable]
        ax.plot(rel.t, rel.new_bpm, ls="none", marker="o", ms=5.5, color=hs.V13, label="v1.3 reported rate")
        ax.set_title(f"{hs.SENSOR_NAME[k]}", fontsize=10.5)
        ax.set_ylabel("Breaths / min")
        if i == len(macs) - 1:
            ax.set_xlabel("Window end time (s)")
        n_leg = int(np.isfinite(g.legacy_bpm).sum()); n_new = int(g.new_reliable.sum())
        ax.text(1.0, 1.04, f"v1.2 gave a rate in {n_leg} of {len(g)} windows; v1.3 in {n_new}",
                transform=ax.transAxes, ha="right", fontsize=8.5, color=hs.INK_2)
    axp = fig.add_subplot(gs[:, 1])
    plv = d.legacy_plv.dropna().values
    axp.hist(plv, bins=np.linspace(0, 1, 26), color=hs.V12, alpha=0.9, orientation="horizontal")
    axp.axhline(0.15, color=hs.STATUS["urgent"]["fill"], lw=1.4)
    axp.axhline(0.60, color=hs.STATUS["watch"]["edge"], lw=1.4)
    axp.text(axp.get_xlim()[1] * 0.98 if axp.get_xlim()[1] else 1, 0.17, "v1.2 RED cut 0.15", ha="right", fontsize=8, color=hs.STATUS["urgent"]["text"])
    axp.text(axp.get_xlim()[1] * 0.98 if axp.get_xlim()[1] else 1, 0.62, "v1.2 YELLOW cut 0.60", ha="right", fontsize=8, color=hs.STATUS["watch"]["text"])
    axp.set_ylim(0, 1.02)
    axp.set_ylabel("v1.2 coherence (PLV)")
    axp.set_xlabel("Windows")
    axp.set_title(f"v1.2 coherence, median {np.median(plv):.2f}", fontsize=10.5)
    handles = [Line2D([0], [0], ls="none", marker="s", ms=6, color=hs.V12, label="v1.2 reported rate"),
               Line2D([0], [0], ls="none", marker="o", ms=6, color=hs.V13, label="v1.3 reported rate (only when reliable)")]
    for st in ("no_reading", "moving"):
        s = hs.STATUS[st]
        handles.append(mpl.patches.Patch(facecolor=s["tint"], edgecolor=s["edge"], hatch="////" if st == "no_reading" else "\\\\\\\\",
                                         label=f"v1.3 status: {STATUS_SHORT[st]}"))
    fig.legend(handles=handles, ncol=4, loc="upper left", bbox_to_anchor=(0.01, 0.905), fontsize=8.5)
    hs.suptitle(fig, "Same recording, two pipelines: v1.2 always finds a breathing rate",
                "The live format sample has no breathing reference. v1.2 still reports a normal-looking rate with high coherence; "
                "v1.3 says it cannot read breathing.", y=0.985)
    return fig


# --------------------------------------------------------------------------- #
# V2. Rate tracking against known truth (held-out semi-synthetic examples)
# --------------------------------------------------------------------------- #
def fig_tracking_examples(rows, examples, truth_fn=None):
    """examples: list of (scenario, seed, mac, title). rows: held-out validation rows."""
    import pandas as pd
    d = pd.DataFrame(rows)
    n = len(examples)
    fig, axes = plt.subplots(n, 1, figsize=(11.5, 2.9 * n + 0.8), sharex=True,
                             gridspec_kw=dict(hspace=0.55, top=0.86))
    axes = np.atleast_1d(axes)
    for ax, (scen, seed, mac, title, truth_curve) in zip(axes, examples):
        g = d[(d.scenario == scen) & (d.seed == seed) & (d.mac == mac)].sort_values("t")
        ymax = max(40, np.nanmax(np.r_[g.truth.values, g.new_bpm.values, g.legacy_bpm.values]) * 1.15)
        ax.set_ylim(0, ymax)
        _status_ribbon(ax, g.t.values, g.new_status.values, y0=0.0, y1=0.10)
        tt, tb = truth_curve[0], truth_curve[1]
        pauses = truth_curve[2] if len(truth_curve) > 2 else []
        tb = np.where(tb > 0, tb, np.nan)
        for a, b in pauses:
            ax.axvspan(a, b, color=hs.STATUS["urgent"]["tint"], lw=0, zorder=0)
            hs.hand(ax, (a + b) / 2, ymax * 0.95, f"programmed\n{b - a:.0f} s pause", ha="center", va="top",
                    size=10, color=hs.INK_2)
            tb = np.where((tt > a - 2.5) & (tt < b + 2.5), np.nan, tb)
        ax.plot(tt, tb, label="Programmed breathing rate", **hs.REF_STYLE)
        ax.plot(g.t, g.legacy_bpm, ls="none", marker="s", ms=4, color=hs.V12, label="v1.2")
        rel = g[g.new_reliable]
        ax.plot(rel.t, rel.new_bpm, ls="none", marker="o", ms=5.2, color=hs.V13, label="v1.3 (reliable windows)")
        ax.set_title(title, fontsize=10.5)
        ax.set_ylabel("Breaths / min")
        e = (rel.new_bpm - rel.truth).abs()
        el = (g.legacy_bpm - g.truth).abs()
        ax.text(1.0, 1.04, f"v1.3 MAE {e.mean():.1f} on {len(rel)} windows | v1.2 MAE {el.mean():.1f} on {el.notna().sum()}",
                transform=ax.transAxes, ha="right", fontsize=8.5, color=hs.INK_2)
    axes[-1].set_xlabel("Window end time (s)")
    handles = [Line2D([0], [0], label="Programmed rate (truth)", **hs.REF_STYLE),
               Line2D([0], [0], ls="none", marker="o", ms=6, color=hs.V13, label="v1.3, reliable windows"),
               Line2D([0], [0], ls="none", marker="s", ms=6, color=hs.V12, label="v1.2")]
    for st in ("typical", "watch", "urgent", "no_reading", "moving"):
        s = hs.STATUS[st]
        hatch = "////" if st == "no_reading" else ("\\\\\\\\" if st == "moving" else None)
        handles.append(mpl.patches.Patch(facecolor=s["tint"], edgecolor=s["edge"] if hatch else "none", hatch=hatch,
                                         label=f"v1.3: {STATUS_SHORT[st]}"))
    fig.legend(handles=handles, ncol=4, loc="upper left", bbox_to_anchor=(0.01, 0.935), fontsize=8.5)
    hs.suptitle(fig, "Known breathing on real packets: tracking and screening status",
                "Held-out semi-synthetic test: the live format sample with breathing of known rate modulated onto every packet "
                "(real loss, timing and gain steps kept). Ribbon = v1.3 status.", y=0.985)
    return fig


# --------------------------------------------------------------------------- #
# V3. Accuracy summary on held-out data
# --------------------------------------------------------------------------- #
def fig_accuracy_summary(rows):
    import pandas as pd
    d = pd.DataFrame(rows)
    d = d[d.scenario != "raw_sample_null"]
    dd = d[np.isfinite(d.truth)]
    depths = sorted(dd.depth.unique())
    fig = plt.figure(figsize=(12, 8.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.15], hspace=0.68, wspace=0.42, top=0.86)
    # A coverage
    ax = fig.add_subplot(gs[0, 0])
    cov13 = [dd[dd.depth == x].new_reliable.mean() * 100 for x in depths]
    cov12 = [np.isfinite(dd[dd.depth == x].legacy_bpm).mean() * 100 for x in depths]
    xs = np.arange(len(depths))
    ax.bar(xs - 0.17, cov12, width=0.3, color=hs.V12, label="v1.2")
    ax.bar(xs + 0.17, cov13, width=0.3, color=hs.V13, label="v1.3")
    for x, v in zip(xs + 0.17, cov13):
        ax.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8.5, color=hs.INK_2)
    ax.set_xticks(xs); ax.set_xticklabels([f"{x * 100:.1f}%" for x in depths])
    ax.set_xlabel("Breathing modulation depth")
    ax.set_ylabel("Windows with a rate (%)")
    ax.set_title("A  How often a rate is shown", fontsize=10.5)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=2, fontsize=8.5)
    ax.set_ylim(0, 125)
    # B within 2 bpm among shown
    ax = fig.add_subplot(gs[0, 1])
    w13, w12 = [], []
    for x in depths:
        g = dd[dd.depth == x]
        e13 = (g.new_bpm - g.truth).abs()[g.new_reliable]
        e12 = (g.legacy_bpm - g.truth).abs().dropna()
        w13.append((e13 <= 2).mean() * 100 if len(e13) else np.nan)
        w12.append((e12 <= 2).mean() * 100)
    ax.bar(xs - 0.17, w12, width=0.3, color=hs.V12)
    ax.bar(xs + 0.17, np.nan_to_num(w13), width=0.3, color=hs.V13)
    for x, v, g in zip(xs + 0.17, w13, depths):
        n = int(dd[dd.depth == g].new_reliable.sum())
        lab = f"{v:.0f}%\nn={n}" if np.isfinite(v) else "n=0"
        ax.text(x, (v if np.isfinite(v) else 0) + 2, lab, ha="center", fontsize=8, color=hs.INK_2)
    ax.set_xticks(xs); ax.set_xticklabels([f"{x * 100:.1f}%" for x in depths])
    ax.set_xlabel("Breathing modulation depth")
    ax.set_ylabel("Shown rates within ±2 /min (%)")
    ax.set_ylim(0, 125)
    ax.set_title("B  When a rate is shown, is it right?", fontsize=10.5)
    # C Bland-Altman for v1.3 (reliable windows, depth >= 3%)
    ax = fig.add_subplot(gs[0, 2])
    g = dd[dd.new_reliable & (dd.depth >= 0.03)]
    mean = (g.new_bpm + g.truth) / 2; diff = g.new_bpm - g.truth
    bias, sd = diff.mean(), diff.std(ddof=1)
    lo, hi = bias - 1.96 * sd, bias + 1.96 * sd
    # windows overlap (30 s windows, 2 s hop), so the CIs use an effective n of one window per 30 s
    n = len(g); n_eff = max(2, n * 2.0 / 30.0)
    se_b = sd / np.sqrt(n_eff); se_l = sd * np.sqrt(3.0 / n_eff)
    tq = 1.96
    for yv, se in ((bias, se_b), (lo, se_l), (hi, se_l)):
        ax.axhspan(yv - tq * se, yv + tq * se, color=hs.GRID_MAJOR, alpha=0.55, lw=0, zorder=0)
    ax.plot(mean, diff, ls="none", marker="o", ms=3, alpha=0.55, color=hs.V13, zorder=2)
    lim = 1.15 * max(diff.abs().max(), abs(lo - tq * se_l), abs(hi + tq * se_l))
    ax.set_ylim(-lim, lim)
    x_left = float(mean.min())
    for yv in (bias, lo, hi):
        ax.axhline(yv, color=hs.INK if yv == bias else hs.INK_2, lw=1.2, ls="-" if yv == bias else (0, (5, 3)), zorder=3)
    nz = lambda v: 0.0 if abs(v) < 0.005 else v      # no "-0.00"
    ax.text(0.98, 0.97, f"bias (solid) {nz(bias):+.2f}\nlimits (dashed) {nz(lo):+.2f} to {nz(hi):+.2f}\nshaded: 95% CI, effective n = {n_eff:.0f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=hs.INK_2, linespacing=1.35)
    ax.set_xlabel("Mean of v1.3 and truth (/min)")
    ax.set_ylabel("v1.3 minus truth (/min)")
    ax.set_title(f"C  Agreement, depth ≥ 3% (n = {n})", fontsize=10.5)
    out = g[diff.abs() > 5]
    if len(out):
        hs.hand(ax, float(mean[diff.abs() > 5].mean()) + 3, float(diff[diff.abs() > 5].mean()) + 0.35 * lim,
                f"{len(out)} {'window' if len(out) == 1 else 'windows'} locked onto\na slow component", va="center", ha="left", size=9.5, color=hs.STATUS["urgent"]["text"])

    # D/E status confusion matrices
    order = ["typical", "watch", "urgent"]
    outs = ["typical", "watch", "urgent", "no_reading", "moving"]
    x = d[d.truth_status.isin(order)]
    for j, (col, name) in enumerate((("legacy_status", "v1.2"), ("new_status", "v1.3"))):
        ax = fig.add_subplot(gs[1, j if j == 0 else 1:3] if j == 1 else gs[1, 0])
        M = np.zeros((len(order), len(outs)))
        for a, ts in enumerate(order):
            row = x[x.truth_status == ts][col].value_counts()
            tot = max(1, (x.truth_status == ts).sum())
            for b, o in enumerate(outs):
                M[a, b] = row.get(o, 0) / tot * 100
        use_outs = outs if name == "v1.3" else ["typical", "watch", "urgent"]
        Mu = M[:, [outs.index(o) for o in use_outs]]
        im = ax.imshow(Mu, cmap="hinigram_teal", vmin=0, vmax=100, aspect="auto")
        for a in range(Mu.shape[0]):
            for b in range(Mu.shape[1]):
                v = Mu[a, b]
                ax.text(b, a, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                        color="#FFFFFF" if v > 55 else hs.INK)
        ax.set_xticks(range(len(use_outs)))
        ax.set_xticklabels([f"{hs.STATUS[o]['icon']} {STATUS_SHORT[o]}".replace("Needs help now", "Needs\nhelp now") for o in use_outs], fontsize=8.5)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([f"{hs.STATUS[o]['icon']} {STATUS_SHORT[o]}" for o in order], fontsize=8.5)
        ax.grid(False)
        ax.set_xlabel(f"{name} output")
        ax.set_ylabel("True status")
        under = (x[x.truth_status == "urgent"][col] == "typical").mean() * 100
        ax.set_title(f"{'D' if name == 'v1.2' else 'E'}  {name} output vs true status", fontsize=10.5, pad=34)
        msg = (f"True 'needs help now' shown as\n'no concern' in {under:.0f}% of windows" if name == "v1.2" else
               f"True 'needs help now' shown as 'no concern' in {under:.0f}% of windows.\n"
               "No reading and Moving are abstentions, not answers.")
        ax.text(0.0, 1.02, msg, transform=ax.transAxes, fontsize=8.5, color=hs.INK_2, va="bottom")
        if name == "v1.3":
            ax.set_yticklabels([])
            ax.set_ylabel("")
    hs.suptitle(fig, "Held-out accuracy: fewer readings, but the readings shown are right",
                "Semi-synthetic held-out set (new seeds, rates, ages and pause timings, frozen thresholds). "
                "Rows = true status from the programmed breathing; columns = what each version showed.", y=0.985)
    return fig
