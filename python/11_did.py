#!/usr/bin/env python3
"""
11_did.py -- separate the zone program from the citywide post-2022 decline.
Instead of a time-only 'zone era' dummy, compare the precincts a spike-based
program TARGETS (top tercile by pre-zone shootings) against the rest, within
the same years (difference-in-differences). The common citywide trend cancels;
the treated x post interaction is the proxy zone effect. A placebo with a fake
cutoff inside the pre-zone era checks the jump is specific to the zone era.
Efficiency = reciprocal (safety) output, output-oriented VRS, input = arrests.
"""
import numpy as np, pandas as pd
from scipy.optimize import linprog

P=pd.read_csv("data/panel.csv")
P["adj_s"]=(P.shoot_pred+1)/(P.shoot+1); P["adj_v"]=(P.viol_pred+1)/(P.viol+1)

def dea_out(X,Y):
    X=X/X.mean(); Y=Y/Y.mean(axis=0); n=len(X); sO=Y.shape[1]; eff=np.full(n,np.nan)
    for o in range(n):
        c=np.zeros(1+n); c[0]=-1.0; A=[]; b=[]
        r=np.zeros(1+n); r[1:]=X; A.append(r); b.append(X[o])
        for q in range(sO):
            r=np.zeros(1+n); r[0]=Y[o,q]; r[1:]=-Y[:,q]; A.append(r); b.append(0.0)
        Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                    bounds=[(0,None)]*(1+n),method="highs")
        if res.success and res.x[0]>=1e-9: eff[o]=1/res.x[0]
    return eff

rows=[]
d=P.dropna(subset=["arr","adj_s","adj_v"])
for yr in range(2012,2026):
    dy=d[d.yr==yr]
    if len(dy)<20: continue
    t=dy[["pct","yr","shoot"]].copy(); t["eff"]=dea_out(np.clip(dy["arr"].values.astype(float),1,None),
                                                         dy[["adj_s","adj_v"]].values.astype(float))
    rows.append(t)
E=pd.concat(rows).dropna()

# fixed treated group = top tercile by mean PRE-zone (2012-2022) shootings
pre=E[E.yr<=2022].groupby("pct")["shoot"].mean()
treated=set(pre[pre>=pre.quantile(2/3)].index)
E["treated"]=E.pct.isin(treated).astype(int)

def did(df, cutoff):
    df=df.copy(); df["post"]=(df.yr>=cutoff).astype(int)
    X=np.column_stack([np.ones(len(df)),df.treated,df.post,df.treated*df.post]); y=df.eff.values
    bb=np.linalg.lstsq(X,y,rcond=None)[0]; r=y-X@bb
    V=(r@r)/(len(df)-4)*np.linalg.inv(X.T@X); se=np.sqrt(np.diag(V))
    return bb[3], bb[3]-1.96*se[3], bb[3]+1.96*se[3], bb[3]/se[3]

real=did(E,2023)                          # zone era
plac=did(E[E.yr<=2022],2018)              # placebo: fake cutoff in pre-zone era

print("="*68); print("DIFFERENCE-IN-DIFFERENCES (targeted vs rest, within year)"); print("="*68)
print(f"treated precincts (top tercile pre-zone shootings): {len(treated)}")
print(f"\nReal (post=2023, zone era):")
print(f"  treated x post = {real[0]:+.4f}  95% CI [{real[1]:+.4f}, {real[2]:+.4f}]  t={real[3]:+.2f}"
      f"  {'*' if (real[1]>0 or real[2]<0) else 'n.s.'}")
print(f"Placebo (pre-zone only, fake post=2018):")
print(f"  treated x post = {plac[0]:+.4f}  95% CI [{plac[1]:+.4f}, {plac[2]:+.4f}]  t={plac[3]:+.2f}"
      f"  {'*' if (plac[1]>0 or plac[2]<0) else 'n.s.'}")
print("\nReading: the time-only zone-era gap was ~+0.12. If the DiD interaction is")
print("near zero, that gap was the citywide decline, not the program. If it is")
print("positive (and the placebo is null), targeted precincts gained beyond trend.")
pd.DataFrame([dict(spec="real_2023",coef=real[0],lo=real[1],hi=real[2]),
              dict(spec="placebo_2018",coef=plac[0],lo=plac[1],hi=plac[2])]).to_csv("data/did_results.csv",index=False)
