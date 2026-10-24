"""
hinigram_style.py  (Hinigram v1.3)
==================================
One set of design tokens for every figure and the dashboard, so a colour means the
same thing everywhere.

Design intent: Hinigram = hininga + "-gram", a record of breathing. Figures read like
a clinical printout: paper ground, blue-black ink, a pale teal chart-paper grid, pencil
for reference lines, handwritten marks for annotations, and colour reserved for meaning.

* Sensors (identity, 3 series): Okabe-Ito blue / vermillion / bluish green. Validated
  with the dataviz six-check validator on the paper surface, all pairs: worst CVD dE 11.0
  (deutan), normal-vision dE 18.7, every colour >= 3:1 against paper.
* Status (meaning, fixed, always shipped with an icon and words): urgent red, watch
  yellow with a brown text tone, typical ballpoint blue, no-reading graphite (hatched so it
  never looks like a patient state). Text tones meet 4.5:1 on paper and on their tints.
* Method comparison: v1.3 blue, v1.2 vermillion, programmed truth as a dashed pencil line.

Typefaces: Atkinson Hyperlegible Next for all text (Braille Institute legibility face) and
Kalam for handwritten annotations. ``use_style()`` registers local copies when present
(``fonts/`` next to this file, ``$HINIGRAM_FONT_DIR`` or ``~/.cache/hinigram_fonts``) and can
fetch them from the Google Fonts repository; without them the figures fall back to DejaVu Sans.
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

# --------------------------------------------------------------------------- #
# Tokens (identical to the dashboard's CSS custom properties)
# --------------------------------------------------------------------------- #
PAPER = "#FAFBF8"        # page and figure ground
FIG_BG = PAPER
SURFACE = PAPER          # axes sit on the same paper
SUNKEN = "#EEF2EE"
INK = "#1B2836"          # blue-black ink, 14:1 on paper
INK_2 = "#475563"        # 7.6:1
INK_3 = "#66727E"        # 4.7:1
LINE_UI = "#66727E"
TRACE = "#23324A"        # pen colour for waveforms
PENCIL = "#8A857E"       # reference and truth lines
GRID = "#E3EEEA"         # chart-paper minor grid
GRID_MAJOR = "#BCD8CF"   # chart-paper major grid
BASELINE = INK
BRAND = "#0B6B66"        # deep teal
BRAND_TINT = "#DCEFEC"
STAMP = "#5B3F9E"        # stamp-pad violet, used only for "checked by staff"
MANGO = "#E3A13B"        # kept for backward compatibility; not used for meaning

SENSOR = {1: "#0072B2", 2: "#D55E00", 3: "#009E73"}
SENSOR_MARKER = {1: "o", 2: "s", 3: "D"}
SENSOR_NAME = {1: "Sensor 1", 2: "Sensor 2", 3: "Sensor 3"}

# comparison roles (figures that compare methods, not sensors)
REFERENCE = PENCIL
REF_STYLE = dict(color=PENCIL, lw=1.8, ls=(0, (6, 4)))
V13 = "#0072B2"          # audited pipeline
V12 = "#D55E00"          # legacy pipeline

STATUS = {
    "urgent":     dict(fill="#B42318", tint="#FBE9E7", text="#9A1C12", edge="#B42318",
                       en="Needs help now", fil="Kailangan ng tulong ngayon", icon="!"),
    "watch":      dict(fill="#F5B700", tint="#FFF4CC", text="#7A5200", edge="#7A5200",
                       en="Watch", fil="Bantayan", icon="◆"),
    "typical":    dict(fill="#1F4FA8", tint="#E8EEF9", text="#1F4FA8", edge="#1F4FA8",
                       en="No breathing concern", fil="Walang nakitang problema sa paghinga", icon="✓"),
    "no_reading": dict(fill="#6E6A64", tint="#EEEDEA", text="#57534D", edge="#8A857E",
                       en="No reliable reading", fil="Hindi mabasa", icon="?"),
    "moving":     dict(fill="#6E6A64", tint="#EEEDEA", text="#57534D", edge="#8A857E",
                       en="Moving, reading paused", fil="Gumagalaw, hinto muna ang pagbasa", icon="↔"),
}
STATUS_ORDER = ["urgent", "watch", "typical", "no_reading", "moving"]

# single-hue sequential ramp (paper -> deep teal) for spectrograms and heatmaps
TEAL_RAMP = LinearSegmentedColormap.from_list(
    "hinigram_teal", ["#FAFBF8", "#D9ECE7", "#9FD0C6", "#4FA79C", "#0B6B66", "#063F3C"])
# diverging (signed error): ballpoint blue <-> red with a neutral paper-grey midpoint
DIVERGING = LinearSegmentedColormap.from_list(
    "hinigram_div", ["#1F4FA8", "#93AEDD", "#EEF0EC", "#E7A39B", "#B42318"])

# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
_FONT_FILES = {
    "Kalam-Regular.ttf": _GF + "kalam/Kalam-Regular.ttf",
    "Kalam-Bold.ttf": _GF + "kalam/Kalam-Bold.ttf",
    "AtkinsonHyperlegibleNext[wght].ttf": _GF + "atkinsonhyperlegiblenext/AtkinsonHyperlegibleNext%5Bwght%5D.ttf",
}
_STATIC_WEIGHTS = {400: "Regular", 600: "SemiBold", 700: "Bold", 800: "ExtraBold"}
TEXT_FONT = "DejaVu Sans"
HAND_FONT = "DejaVu Sans"


def _font_dirs():
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    dirs = [Path(os.environ["HINIGRAM_FONT_DIR"])] if os.environ.get("HINIGRAM_FONT_DIR") else []
    return dirs + [here / "fonts", Path.cwd() / "fonts", Path.home() / ".cache" / "hinigram_fonts"]


def _instantiate_static(var_path: Path):
    """Make static weights from the variable font (matplotlib cannot pick weights from a variable font)."""
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
    except ImportError:
        return
    for w, sub in _STATIC_WEIGHTS.items():
        out = var_path.parent / f"AtkinsonHyperlegibleNext-{sub}.ttf"
        if out.exists():
            continue
        try:
            inst = instancer.instantiateVariableFont(TTFont(var_path), {"wght": w}, updateFontNames=True)
            inst["OS/2"].usWeightClass = w
            inst.save(out)
        except Exception:
            return


def ensure_fonts(download: bool = True, timeout: float = 8.0) -> tuple:
    """Register Atkinson Hyperlegible Next and Kalam with matplotlib; download them once if allowed."""
    global TEXT_FONT, HAND_FONT
    found = []
    for d in _font_dirs():
        if d.is_dir():
            found += [p for p in d.glob("*.ttf")]
    names = {p.name for p in found}
    if download and not {"Kalam-Regular.ttf", "AtkinsonHyperlegibleNext-Regular.ttf"} <= names:
        cache = Path.home() / ".cache" / "hinigram_fonts"
        try:
            cache.mkdir(parents=True, exist_ok=True)
            for fn, url in _FONT_FILES.items():
                dst = cache / fn
                if not dst.exists():
                    with urllib.request.urlopen(url, timeout=timeout) as r:
                        dst.write_bytes(r.read())
            _instantiate_static(cache / "AtkinsonHyperlegibleNext[wght].ttf")
            found += list(cache.glob("*.ttf"))
        except Exception:
            pass  # offline: keep the default font, figures still render
    for p in found:
        if "[wght]" in p.name:
            continue  # use the static instances
        try:
            font_manager.fontManager.addfont(str(p))
        except Exception:
            pass
    avail = {f.name for f in font_manager.fontManager.ttflist}
    TEXT_FONT = next((n for n in ("Atkinson Hyperlegible Next", "Atkinson Hyperlegible", "DejaVu Sans") if n in avail), "sans-serif")
    HAND_FONT = "Kalam" if "Kalam" in avail else TEXT_FONT
    return TEXT_FONT, HAND_FONT


def use_style(download_fonts: bool = True):
    """Apply the Hinigram figure style globally (call once per notebook). Returns the text font in use."""
    fam, _ = ensure_fonts(download=download_fonts)
    mpl.rcParams.update({
        "figure.facecolor": FIG_BG,
        "savefig.facecolor": FIG_BG,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": INK,
        "axes.linewidth": 1.0,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 11,
        "axes.titlelocation": "left",
        "axes.titlepad": 8,
        "axes.labelsize": 9.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID_MAJOR,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "xtick.color": INK_3,
        "ytick.color": INK_3,
        "xtick.labelcolor": INK_3,
        "ytick.labelcolor": INK_3,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "xtick.major.size": 3,
        "ytick.major.size": 0,
        "xtick.major.width": 1.0,
        "font.family": [fam, "DejaVu Sans"],   # DejaVu fills symbols the text face lacks (check, diamond, arrows)
        "font.size": 9.5,
        "text.color": INK,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "legend.labelcolor": INK_2,
        "lines.linewidth": 1.8,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "patch.linewidth": 0,
        "hatch.color": PENCIL,
        "hatch.linewidth": 0.8,
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "image.cmap": "hinigram_teal",
    })
    for cm in (TEAL_RAMP, DIVERGING):
        try:
            mpl.colormaps.register(cm)
        except ValueError:
            pass
    return fam


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def suptitle(fig, title, subtitle=None, y=1.0):
    """Left-aligned figure title + optional plain-language subtitle."""
    fig.text(0.01, y, title, ha="left", va="bottom", fontsize=14, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.01, y - 0.005, subtitle, ha="left", va="top", fontsize=9.5, color=INK_2)


def panel_label(ax, letter):
    ax.text(-0.02, 1.02, letter, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=11, fontweight="bold", color=BRAND)


def source_note(fig, text, y=-0.02):
    fig.text(0.01, y, text, ha="left", va="top", fontsize=7.8, color=INK_3)


def hand(ax, x, y, text, color=INK_2, size=10.5, **kw):
    """A handwritten nurse-style annotation (Kalam when installed)."""
    return ax.text(x, y, text, fontfamily=HAND_FONT, fontsize=size, color=color, fontweight="bold", **kw)


def chart_paper(ax, x_minor=None, x_major=None, y_minor=None, y_major=None):
    """Strip-chart grid: pale teal minor squares under darker major lines."""
    from matplotlib.ticker import MultipleLocator
    ax.grid(False)
    if x_minor:
        ax.xaxis.set_minor_locator(MultipleLocator(x_minor))
    if x_major:
        ax.xaxis.set_major_locator(MultipleLocator(x_major))
    if y_minor:
        ax.yaxis.set_minor_locator(MultipleLocator(y_minor))
    if y_major:
        ax.yaxis.set_major_locator(MultipleLocator(y_major))
    ax.grid(True, which="minor", color=GRID, lw=0.6)
    ax.grid(True, which="major", color=GRID_MAJOR, lw=0.8)
    ax.tick_params(which="minor", length=0)


def status_patch(ax, x0, x1, status, y0=0, y1=1, transform=None, alpha=1.0):
    """Shade a time span with a status tint (pencil-hatched for technical states)."""
    s = STATUS[status]
    hatch = "////" if status == "no_reading" else ("\\\\\\\\" if status == "moving" else None)
    kw = dict(facecolor=s["tint"], edgecolor=s["edge"] if hatch else "none", linewidth=0,
              hatch=hatch, alpha=alpha)
    if transform is None:
        transform = ax.get_xaxis_transform()
    return ax.add_patch(mpl.patches.Rectangle((x0, y0), x1 - x0, y1 - y0, transform=transform, **kw))


def direct_label(ax, x, y, text, color=INK_2, **kw):
    """Text label in ink tokens (never the series colour)."""
    return ax.annotate(text, (x, y), xytext=(4, 0), textcoords="offset points",
                       va="center", ha="left", fontsize=8.5, color=color, **kw)
