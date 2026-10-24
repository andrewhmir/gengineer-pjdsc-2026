#!/usr/bin/env python3
"""Search for status-colour triads that pass WCAG contrast AND stay separable under CVD simulation.
Re-uses the functions from palette_check.py (loaded with runpy; its __main__ block is not executed)."""
import itertools
import runpy

ns = runpy.run_path('/tmp/claude-0/-home-claude/938d17eb-6f55-59cc-8791-ffef3bc972f4/scratchpad/palette_check.py',
                    run_name='lib')
contrast, simulate, hex2lab, de2000 = ns['contrast'], ns['simulate'], ns['hex2lab'], ns['de2000']
KINDS = ['normal', 'protan', 'deutan', 'tritan']
INK, WHITE, PAPER, DARK, DARK_SURF = '#1F1B16', '#FFFFFF', '#FAF7F2', '#171513', '#23201C'


def set_stats(cols):
    out = {}
    for k in KINDS:
        labs = [hex2lab(simulate(c, k)) for c in cols]
        out[k] = min(de2000(labs[i], labs[j]) for i, j in itertools.combinations(range(len(cols)), 2))
    return out


def show(label, cols):
    s = set_stats(cols)
    Ls = [round(hex2lab(c)[0], 1) for c in cols]
    print(f'{label:34s} {cols} L*={Ls} ' + ' '.join(f'{k}={v:5.1f}' for k, v in s.items())
          + f' | min={min(s.values()):5.1f}')


# ---------------- light theme search ----------------
ok_c = ['#0F766E', '#0E7490', '#0B6E8A', '#1D6FA3', '#0072B2', '#00796B', '#0B6B66', '#1A7A55', '#14708A',
        '#00687F', '#0A6C99', '#22668D']
watch_c = ['#F4C152', '#F2B544', '#F0B429', '#FFC233', '#E69F00', '#F5C451', '#FFCB47', '#F6BE3B', '#F7D070']
urg_c = ['#B42318', '#C2410C', '#B3261E', '#C0392B', '#A1260D', '#D55E00', '#B83A1C', '#9F1D14', '#C4321F',
         '#B5302A', '#A8201A']
rows = []
for o, w, u in itertools.product(ok_c, watch_c, urg_c):
    if contrast(o, WHITE) < 4.5 or contrast(u, WHITE) < 4.5 or contrast(o, PAPER) < 4.5 or contrast(u, PAPER) < 4.5:
        continue
    if contrast(INK, w) < 7:
        continue
    s = set_stats([o, w, u])
    rows.append((min(s.values()), o, w, u, s))
rows.sort(reverse=True)
print('LIGHT THEME: top triads (ok, watch_fill, urgent); ok/urgent >= 4.5:1 on white and paper; ink on watch >= 7:1')
for m, o, w, u, s in rows[:10]:
    print(f'  min={m:5.1f}  ok={o} watch={w} urgent={u}  ' + ' '.join(f'{k}={v:5.1f}' for k, v in s.items())
          + f'  cr(ok,white)={contrast(o, WHITE):.2f} cr(urg,white)={contrast(u, WHITE):.2f} cr(ink,watch)={contrast(INK, w):.2f}')

# ---------------- dark theme search ----------------
ok_d = ['#4FB8C9', '#5BB8E0', '#56B4E9', '#4FB8AE', '#6DB7EE', '#5CC197', '#57C0D6', '#7FC8F8', '#62B6CB']
watch_d = ['#F2B84B', '#F0C04A', '#FFD166', '#F5C46A', '#FFC94D', '#EDB74A', '#F7D27A']
urg_d = ['#FF7E6E', '#FF6B5B', '#F26D5B', '#F0614F', '#EF5A48', '#FF8A80', '#F87060', '#E8604C', '#F2705E',
         '#E86A5A']
rows = []
for o, w, u in itertools.product(ok_d, watch_d, urg_d):
    if min(contrast(c, DARK_SURF) for c in (o, w, u)) < 4.5:
        continue
    s = set_stats([o, w, u])
    rows.append((min(s.values()), o, w, u, s))
rows.sort(reverse=True)
print('\nDARK THEME: top triads (ok, watch, urgent); each >= 4.5:1 on #23201C surface (and thus on #171513)')
for m, o, w, u, s in rows[:10]:
    print(f'  min={m:5.1f}  ok={o} watch={w} urgent={u}  ' + ' '.join(f'{k}={v:5.1f}' for k, v in s.items())
          + f'  cr vs #171513: {contrast(o, DARK):.2f}/{contrast(w, DARK):.2f}/{contrast(u, DARK):.2f}')

# ---------------- hand-picked final candidates ----------------
print('\nHAND-PICKED SETS (including a neutral "no reading / low signal" grey)')
show('current tailwind dark', ['#22C55E', '#FACC15', '#EF4444'])
show('proposal L: teal-blue/amber/red', ['#0E7490', '#F4C152', '#B42318'])
show('proposal L + grey', ['#0E7490', '#F4C152', '#B42318', '#6B6560'])
show('proposal L alt OI-blue', ['#0072B2', '#F4C152', '#B42318'])
show('proposal D: sky/amber/coral', ['#56B4E9', '#F2B84B', '#F0614F'])
show('proposal D + grey', ['#56B4E9', '#F2B84B', '#F0614F', '#A39B91'])
for c in ['#0E7490', '#0072B2', '#B42318', '#C2410C', '#6B6560', '#8A5300', '#7A4A00', '#A15C00']:
    print(f'  {c}: vs white {contrast(c, WHITE):.2f}, vs paper {contrast(c, PAPER):.2f}, vs sand #F2EDE4 {contrast(c, "#F2EDE4"):.2f}')
for c in ['#56B4E9', '#F2B84B', '#F0614F', '#EF5A48', '#A39B91']:
    print(f'  {c}: vs #171513 {contrast(c, DARK):.2f}, vs #23201C {contrast(c, DARK_SURF):.2f}, white text on it {contrast("#FFFFFF", c):.2f}, #171513 text on it {contrast(DARK, c):.2f}')
