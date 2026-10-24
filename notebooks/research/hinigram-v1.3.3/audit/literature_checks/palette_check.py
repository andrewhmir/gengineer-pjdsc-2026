#!/usr/bin/env python3
"""WCAG 2.x contrast + colour-vision-deficiency (CVD) checks for Hinigram palette research.

- Contrast: WCAG relative luminance (sRGB, threshold 0.04045) and (L1+0.05)/(L2+0.05).
- CVD simulation: Machado, Oliveira & Fernandes (2009) matrices, severity 1.0, applied in linear RGB.
- Colour difference: CIEDE2000 on CIELAB (D65).
- Viewing-distance table: character height for a given visual angle (arcmin).
"""
import math
import itertools


def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def l2s(c):
    c = min(max(c, 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rel_lum(h):
    r, g, b = (s2l(c) for c in hex2rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


MACHADO = {
    'protan': [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    'deutan': [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    'tritan': [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def simulate(h, kind):
    if kind == 'normal':
        return h.upper()
    lin = [s2l(c) for c in hex2rgb(h)]
    m = MACHADO[kind]
    out = [sum(m[i][j] * lin[j] for j in range(3)) for i in range(3)]
    return '#%02X%02X%02X' % tuple(round(l2s(c) * 255) for c in out)


def hex2lab(h):
    r, g, b = (s2l(c) for c in hex2rgb(h))
    X = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    Y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    Z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883

    def f(t):
        d = 6 / 29
        return t ** (1 / 3) if t > d ** 3 else t / (3 * d * d) + 4 / 29

    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
        dhp = dh
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dth = 30 * math.exp(-((hbp - 275) / 25) ** 2)
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# ---- sanity checks -------------------------------------------------------
assert abs(contrast('#000000', '#FFFFFF') - 21.0) < 1e-9
assert abs(contrast('#767676', '#FFFFFF') - 4.54) < 0.01
assert abs(de2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) - 2.0425) < 1e-3  # Sharma et al. 2005 pair 1
assert abs(de2000((50.0, 2.5, 0.0), (73.0, 25.0, -18.0)) - 27.1492) < 1e-3          # Sharma pair 24

BGS = {
    'white': '#FFFFFF',
    'warm_paper': '#FAF7F2',
    'sand': '#F2EDE4',
    'slate900(current)': '#0F172A',
    'slate800(current)': '#1E293B',
    'warm_dark': '#171513',
    'warm_dark_surface': '#23201C',
}

PALETTES = {
    'okabe_ito': {'black': '#000000', 'orange': '#E69F00', 'sky_blue': '#56B4E9', 'bluish_green': '#009E73',
                  'yellow': '#F0E442', 'blue': '#0072B2', 'vermillion': '#D55E00', 'reddish_purple': '#CC79A7'},
    'ibm_cvd': {'ultramarine': '#648FFF', 'indigo': '#785EF0', 'magenta': '#DC267F', 'orange': '#FE6100', 'gold': '#FFB000'},
    'tol_bright': {'blue': '#4477AA', 'cyan': '#66CCEE', 'green': '#228833', 'yellow': '#CCBB44', 'red': '#EE6677',
                   'purple': '#AA3377', 'grey': '#BBBBBB'},
    'tol_high_contrast': {'blue': '#004488', 'yellow': '#DDAA33', 'red': '#BB5566'},
    'tol_vibrant': {'blue': '#0077BB', 'cyan': '#33BBEE', 'teal': '#009988', 'orange': '#EE7733', 'red': '#CC3311',
                    'magenta': '#EE3377', 'grey': '#BBBBBB'},
    'nhs_frontend': {'blue': '#005EB8', 'text_black': '#212B32', 'secondary_text_grey1': '#4C6272', 'red': '#D5281B',
                     'warm_yellow': '#FFB81C', 'green': '#007F3B', 'dark_blue': '#003087', 'focus_yellow': '#FFEB3B',
                     'grey5_bg': '#F0F4F5'},
    'tailwind_current': {'slate400_text': '#94A3B8', 'slate500_text': '#64748B', 'red500': '#EF4444',
                         'yellow400': '#FACC15', 'green500': '#22C55E', 'cyan400': '#22D3EE', 'emerald400': '#34D399'},
    # Proposed Hinigram light theme (text-safe "ink" shades + soft tints for fills)
    'hinigram_light': {
        'ink_text': '#1F1B16', 'ink_secondary': '#5A534A', 'ink_tertiary': '#6B645B', 'border_ui': '#8A8176',
        'brand_teal': '#0B6B66', 'brand_teal_hover': '#08524E', 'accent_mango_deco': '#E3A13B',
        'ok_strong': '#1A7A55', 'ok_tint': '#E4F2EA', 'ok_on_tint_text': '#0E4F37',
        'watch_strong': '#A85D00', 'watch_fill': '#F4C152', 'watch_tint': '#FCF0D2', 'watch_on_tint_text': '#5E3A00',
        'urgent_strong': '#B42318', 'urgent_tint': '#FBE7E4', 'urgent_on_tint_text': '#7A1610',
        'info_strong': '#0B66A8', 'info_tint': '#E3EFF8',
        'unknown_strong': '#6B6560', 'unknown_tint': '#EDEBE8',
    },
    # Proposed Hinigram dark (night / dim nurse station) theme on warm_dark #171513
    'hinigram_dark': {
        'text': '#F4EFE6', 'text_secondary': '#BDB4A7', 'border_ui': '#7D756A',
        'brand_teal': '#4FB8AE', 'ok': '#5CC197', 'watch': '#F2B84B', 'urgent': '#FF7E6E', 'info': '#6DB7EE',
        'unknown': '#A39B91',
    },
}

TRIADS = {
    'current tailwind (green500/yellow400/red500)': ['#22C55E', '#FACC15', '#EF4444'],
    'classic RAG (#00A651/#FFC000/#E00000)': ['#00A651', '#FFC000', '#E00000'],
    'NHS green/warm-yellow/red': ['#007F3B', '#FFB81C', '#D5281B'],
    'Okabe-Ito bluish-green/orange/vermillion': ['#009E73', '#E69F00', '#D55E00'],
    'Okabe-Ito blue/orange/vermillion': ['#0072B2', '#E69F00', '#D55E00'],
    'Okabe-Ito blue/yellow/vermillion': ['#0072B2', '#F0E442', '#D55E00'],
    'Tol high-contrast blue/yellow/red': ['#004488', '#DDAA33', '#BB5566'],
    'IBM ultramarine/gold/magenta': ['#648FFF', '#FFB000', '#DC267F'],
    'Hinigram light strong (ok/watch/urgent)': ['#1A7A55', '#A85D00', '#B42318'],
    'Hinigram light fills (ok/watch_fill/urgent)': ['#1A7A55', '#F4C152', '#B42318'],
    'Hinigram dark (ok/watch/urgent)': ['#5CC197', '#F2B84B', '#FF7E6E'],
}


def report_palettes():
    print('=' * 100)
    print('WCAG CONTRAST RATIOS (colour vs background)')
    print('=' * 100)
    cols = ['white', 'warm_paper', 'sand', 'slate900(current)', 'warm_dark']
    for pname, pal in PALETTES.items():
        print(f'\n## {pname}')
        print(f"{'token':24s} {'hex':8s} {'L*':>5s} " + ' '.join(f'{c[:17]:>17s}' for c in cols))
        for name, hx in pal.items():
            L = hex2lab(hx)[0]
            print(f'{name:24s} {hx:8s} {L:5.1f} ' + ' '.join(f'{contrast(hx, BGS[c]):17.2f}' for c in cols))


def report_pairs():
    print('\n' + '=' * 100)
    print('SPECIFIC FOREGROUND/BACKGROUND PAIRS')
    print('=' * 100)
    pairs = [
        ('current: slate400 text on slate900', '#94A3B8', '#0F172A'),
        ('current: slate500 text on slate800', '#64748B', '#1E293B'),
        ('current: red500 text on slate900', '#EF4444', '#0F172A'),
        ('current: green500 text on slate900', '#22C55E', '#0F172A'),
        ('current: yellow400 text on slate900', '#FACC15', '#0F172A'),
        ('white text on red500 badge', '#FFFFFF', '#EF4444'),
        ('white text on green500 badge', '#FFFFFF', '#22C55E'),
        ('black text on yellow400 badge', '#000000', '#FACC15'),
        ('HL ink_text on warm_paper', '#1F1B16', '#FAF7F2'),
        ('HL ink_secondary on warm_paper', '#5A534A', '#FAF7F2'),
        ('HL ink_secondary on sand', '#5A534A', '#F2EDE4'),
        ('HL ink_tertiary on white', '#6B645B', '#FFFFFF'),
        ('HL ink_tertiary on warm_paper', '#6B645B', '#FAF7F2'),
        ('HL border_ui on white', '#8A8176', '#FFFFFF'),
        ('HL border_ui on warm_paper', '#8A8176', '#FAF7F2'),
        ('HL white text on brand_teal button', '#FFFFFF', '#0B6B66'),
        ('HL brand_teal link on warm_paper', '#0B6B66', '#FAF7F2'),
        ('HL white text on ok_strong', '#FFFFFF', '#1A7A55'),
        ('HL white text on urgent_strong', '#FFFFFF', '#B42318'),
        ('HL white text on watch_strong', '#FFFFFF', '#A85D00'),
        ('HL ink_text on watch_fill', '#1F1B16', '#F4C152'),
        ('HL ok_on_tint_text on ok_tint', '#0E4F37', '#E4F2EA'),
        ('HL watch_on_tint_text on watch_tint', '#5E3A00', '#FCF0D2'),
        ('HL urgent_on_tint_text on urgent_tint', '#7A1610', '#FBE7E4'),
        ('HL ok_strong border vs ok_tint', '#1A7A55', '#E4F2EA'),
        ('HL watch_strong border vs watch_tint', '#A85D00', '#FCF0D2'),
        ('HL urgent_strong border vs urgent_tint', '#B42318', '#FBE7E4'),
        ('HL ok_strong vs white (icon/border)', '#1A7A55', '#FFFFFF'),
        ('HL watch_strong vs white (icon/border)', '#A85D00', '#FFFFFF'),
        ('HL urgent_strong vs white (icon/border)', '#B42318', '#FFFFFF'),
        ('HL info_strong vs white', '#0B66A8', '#FFFFFF'),
        ('HL unknown_strong vs white', '#6B6560', '#FFFFFF'),
        ('HD text on warm_dark', '#F4EFE6', '#171513'),
        ('HD text_secondary on warm_dark', '#BDB4A7', '#171513'),
        ('HD text_secondary on warm_dark_surface', '#BDB4A7', '#23201C'),
        ('HD border_ui on warm_dark', '#7D756A', '#171513'),
        ('HD ok on warm_dark', '#5CC197', '#171513'),
        ('HD watch on warm_dark', '#F2B84B', '#171513'),
        ('HD urgent on warm_dark', '#FF7E6E', '#171513'),
        ('HD info on warm_dark', '#6DB7EE', '#171513'),
        ('HD unknown on warm_dark', '#A39B91', '#171513'),
        ('HD ok on warm_dark_surface', '#5CC197', '#23201C'),
        ('HD urgent on warm_dark_surface', '#FF7E6E', '#23201C'),
        ('HD dark text #171513 on HD urgent fill', '#171513', '#FF7E6E'),
        ('HD dark text #171513 on HD watch fill', '#171513', '#F2B84B'),
        ('HD dark text #171513 on HD ok fill', '#171513', '#5CC197'),
        ('fig: #222222 text on white', '#222222', '#FFFFFF'),
        ('fig: #595959 axis grey on white', '#595959', '#FFFFFF'),
        ('fig: #BFBFBF gridline on white', '#BFBFBF', '#FFFFFF'),
    ]
    for label, fg, bg in pairs:
        cr = contrast(fg, bg)
        tag = 'AAA' if cr >= 7 else ('AA' if cr >= 4.5 else ('AA-large/UI' if cr >= 3 else 'FAIL'))
        print(f'{label:45s} {fg} on {bg}: {cr:5.2f}:1  [{tag}]')


def report_triads():
    print('\n' + '=' * 100)
    print('STATUS TRIADS UNDER CVD SIMULATION (Machado 2009, severity 1.0)')
    print('min pairwise CIEDE2000 (higher = more distinct); L* order; luminance-contrast between neighbours')
    print('=' * 100)
    for tname, cols in TRIADS.items():
        print(f'\n## {tname}: {cols}')
        for kind in ['normal', 'protan', 'deutan', 'tritan']:
            sim = [simulate(c, kind) for c in cols]
            labs = [hex2lab(c) for c in sim]
            des = {f'{i}-{j}': de2000(labs[i], labs[j]) for i, j in itertools.combinations(range(3), 2)}
            Ls = [lab[0] for lab in labs]
            print(f'  {kind:7s} sim={sim} L*={[round(x, 1) for x in Ls]} '
                  f"dE00(ok-watch)={des['0-1']:5.1f} dE00(ok-urgent)={des['0-2']:5.1f} "
                  f"dE00(watch-urgent)={des['1-2']:5.1f} min={min(des.values()):5.1f}")
        print(f'  luminance contrast ok:urgent={contrast(cols[0], cols[2]):.2f}  watch:urgent={contrast(cols[1], cols[2]):.2f}'
              f'  ok:watch={contrast(cols[0], cols[1]):.2f}')


def report_okabe_pairs():
    print('\n' + '=' * 100)
    print('OKABE-ITO: worst pairs under each CVD type (CIEDE2000)')
    print('=' * 100)
    pal = PALETTES['okabe_ito']
    names = list(pal)
    for kind in ['normal', 'protan', 'deutan', 'tritan']:
        res = []
        for a, b in itertools.combinations(names, 2):
            d = de2000(hex2lab(simulate(pal[a], kind)), hex2lab(simulate(pal[b], kind)))
            res.append((d, a, b))
        res.sort()
        print(f'  {kind:7s} worst 3: ' + '; '.join(f'{a}/{b}={d:.1f}' for d, a, b in res[:3]))


def report_viewing_distance():
    print('\n' + '=' * 100)
    print('CHARACTER (CAP) HEIGHT FOR VISUAL ANGLE, and approximate font-size in device px')
    print('assumes cap height = 0.72 em; displays: 24in 1080p (0.2767 mm/px), 43in 1080p (0.4958 mm/px), 55in 1080p (0.6342 mm/px)')
    print('=' * 100)
    displays = {'24in-1080p': 0.2767, '43in-1080p': 0.4958, '55in-1080p': 0.6342}
    cap_ratio = 0.72
    for dist in [0.5, 0.7, 1.0, 2.0, 3.0, 4.0, 5.0]:
        row = []
        for arc in [16, 20, 22]:
            h = 2 * dist * 1000 * math.tan(math.radians(arc / 60) / 2)
            row.append(f'{arc}arcmin cap={h:5.1f}mm')
        px = []
        h20 = 2 * dist * 1000 * math.tan(math.radians(20 / 60) / 2)
        h16 = 2 * dist * 1000 * math.tan(math.radians(16 / 60) / 2)
        for dname, pitch in displays.items():
            px.append(f'{dname}: font>={h16 / pitch / cap_ratio:5.0f}px(16\') pref~{h20 / pitch / cap_ratio:5.0f}px(20\')')
        print(f'{dist:4.1f} m | ' + ' | '.join(row) + ' || ' + ' | '.join(px))
    # CSS reference pixel: 1/96 in at 28 in (711.2 mm) => visual angle
    ref_arcmin = math.degrees(math.atan((25.4 / 96) / 711.2)) * 60
    print(f'\nCSS reference pixel visual angle ~ {ref_arcmin:.3f} arcmin ({ref_arcmin / 60:.4f} deg)')
    for fs in [9.5, 11.5, 14, 16, 18, 20, 24]:
        cap_arc = fs * cap_ratio * ref_arcmin
        print(f'  font-size {fs:5.1f} CSS px at the reference viewing distance -> cap height ~ {cap_arc:4.1f} arcmin')


if __name__ == '__main__':
    report_palettes()
    report_pairs()
    report_triads()
    report_okabe_pairs()
    report_viewing_distance()
