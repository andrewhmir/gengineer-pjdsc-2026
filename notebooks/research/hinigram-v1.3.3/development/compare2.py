import pandas as pd, numpy as np, sys
pd.set_option('display.width',220)
PAUSEF=['pause','short7','short9','pause11','pause13','dev_child_pause','dev_adult_pause_early','dev_adult_pause_late']
def summ(f):
    d=pd.read_pickle(f); d['pmin']=np.where(d.prof=='adult',10.0,20.0)
    br=d[~d.any_pause&~d.mot]; lp=d[d.silence>=d.pmin]; mp=d[(d.silence>=6)&(d.silence<d.pmin)]
    pf=lambda x:(x.status=='urgent')&x.reason.str.startswith('Possible breathing pause')
    rs=lambda x:x.status.isin(['typical','watch'])|((x.status=='urgent')&~x.reason.str.startswith('Possible breathing pause'))
    nop=d[~d.name.isin(PAUSEF)]
    return dict(breathing_shown=br.rel.mean(), breathing_rate_state=rs(br).mean(), long_rate_state=rs(lp).mean(), long_flag=pf(lp).mean(),
                long_noread=(lp.status=='no_reading').mean(), mid_rate_state=rs(mp).mean(), false_pause_nopause_files=int(pf(nop).sum()), n_nop=len(nop))
files=[(k,f) for k,f in [(a.split('=')[0],a.split('=')[1]) for a in sys.argv[1:]]]
r=pd.DataFrame([dict(run=k,**summ(f)) for k,f in files]); print(r.round(3).to_string())
a=pd.read_pickle(files[0][1]); b=pd.read_pickle(files[-1][1])
m=a.merge(b,on=['file','mac','t'],suffixes=('_0','_g'))
print(m[m.status_0!=m.status_g].groupby(['status_0','status_g']).size().to_string())
P={'pause':(125,142),'pause11':(35,46),'pause13':(145,158),'dev_child_pause':(118,143),'dev_adult_pause_early':(36,54),'dev_adult_pause_late':(122,138),'short7':(140,147),'short9':(40,49)}
rows=[]
for (f,mac),g in m.groupby(['file','mac']):
    nm=g.name_0.iloc[0]
    if nm not in P: continue
    a0,b0=P[nm]
    for suf in ('_0','_g'):
        hit=g[(g.t>=a0)&(g.t<=b0+30)&(g['status'+suf]=='urgent')&g['reason'+suf].str.startswith('Possible breathing pause')]
        rs=g[(g.t>=a0+(10 if g.prof_0.iloc[0]=='adult' else 20))&(g.t<=b0)&g['status'+suf].isin(['typical','watch'])]
        rows.append(dict(file=f,mac=mac,depth=g.depth_0.iloc[0],ver=suf,lat=(hit.t.min()-a0) if len(hit) else np.nan, reassure=len(rs)))
R=pd.DataFrame(rows).pivot_table(index=['file','mac','depth'],columns='ver',values=['lat','reassure'],aggfunc='first')
print(R.to_string())
