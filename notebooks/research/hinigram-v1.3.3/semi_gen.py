import numpy as np, os, json, time
import hinigram_live as hl
SRC=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo_20261019_024431.csv')
MACS=['1a:00:00:00:00:01','1a:00:00:00:00:02','1a:00:00:00:00:03']
# Scenario segments (t_start, t_end, breaths/min); 0 = pause. Designed around the real recording's
# movement episodes (~0-18 s on Sensor 3, ~64-109 s on all links) so that each event lands in a quiet stretch.
SCEN={
 'normal_to_fast': [(0,90,14),(90,180,28)],
 'fast_watch':     [(0,180,22)],
 'pause':          [(0,125,16),(125,142,0),(142,180,16)],
 'slow':           [(0,180,7.5)],
 'child_fast':     [(0,180,46)],
}
PROFILE={'child_fast':'child_1_5y'}
DEPTHS=[0.06,0.035,0.02]   # per-link sensitivity (near / mid / far)
def make(name, seed, depths=DEPTHS, tag=''):
    scs={m: hl.BreathingScenario(SCEN[name], depth=d, phase_depth=d, seed=seed*10+i, name=name)
         for i,(m,d) in enumerate(zip(MACS,depths))}
    dst=f'semi/{name}_s{seed}{tag}.csv'
    if not os.path.exists(dst):
        os.makedirs('semi', exist_ok=True)
        hl.inject_breathing(SRC,dst,scs)
    return dst, scs
DEMO={  # dashboard demo: one scenario per link, all at good sensitivity
 MACS[0]: ('normal_to_fast', 0.05, 'adult'),
 MACS[1]: ('pause', 0.05, 'adult'),
 MACS[2]: ('child_fast', 0.05, 'child_1_5y'),
}
def make_demo(path='semi/demo_semisynthetic.csv'):
    scs={m: hl.BreathingScenario(SCEN[n], depth=d, phase_depth=d, seed=77+i, name=n) for i,(m,(n,d,p)) in enumerate(DEMO.items())}
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        hl.inject_breathing(SRC,path,scs)
    return path, scs, {m:p for m,(n,d,p) in DEMO.items()}
if __name__=='__main__':
    t=time.time()
    for seed in [1,2]:
        for name in SCEN:
            make(name,seed)
    make_demo()
    print('generated in %.1fs'%(time.time()-t))
