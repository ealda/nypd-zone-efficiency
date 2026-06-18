#!/usr/bin/env python3
"""
08_robustness_inputs.py -- Does the zone-era null survive different input
proxies? Re-run input-oriented VRS DEA (netted outputs) with three deployment
proxies and regress efficiency on zone-era + controls each time.
  arr        total summer arrests
  arr_fel    felony summer arrests (less driven by low-level proactive stops)
  arr_struct arrests purged of the prior-year spike (selection-instrumented)
"""
import numpy as np, pandas as pd
from scipy.optimize import linprog

P = pd.read_csv("data/panel.csv")
DD = pd.read_csv("data/ddf_dmu.csv")[["pct","yr","arr_struct"]]
P = P.merge(DD, on=["pct","yr"], how="left")
P["zone_era"] = (P.yr >= 2023).astype(int)
P["spike"] = (P.shoot_l1 - P.shoot_m3) + (P.viol_l1 - P.viol_m3)

def dea_vrs_in(X, Y):
    n = len(X); th = np.zeros(n)
    X = X / np.mean(X)                          # mean-normalize input
    Yt = Y - Y.min(axis=0) + 1.0
    Yt = Yt / Yt.mean(axis=0)                   # mean-normalize each output
    for o in range(n):
        c = np.zeros(1+n); c[0] = 1.0
        A=[]; b=[]
        r=np.zeros(1+n); r[0]=-X[o]; r[1:]=X; A.append(r); b.append(0.0)
        for q in range(Yt.shape[1]):
            r=np.zeros(1+n); r[1:]=-Yt[:,q]; A.append(r); b.append(-Yt[o,q])
        Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                    bounds=[(None,None)]+[(0,None)]*n,method="highs")
        th[o]=res.x[0] if res.success else np.nan
    return th

def run(input_col):
    rows=[]
    d = P.dropna(subset=[input_col,"shoot_av_net","viol_av_net","spike"]).copy()
    for yr in range(2012,2026):
        dy = d[d.yr==yr]
        if len(dy) < 20: continue
        X = np.clip(dy[input_col].values.astype(float),1,None)
        Y = dy[["shoot_av_net","viol_av_net"]].values.astype(float)
        eff = dea_vrs_in(X, Y)
        t = dy[["pct","yr","zone_era","spike"]].copy(); t["eff"]=eff; t["inp"]=X
        rows.append(t)
    A = pd.concat(rows).dropna()
    A["z"]=(A.spike-A.spike.mean())/A.spike.std()
    A["li"]=np.log(np.clip(A.inp,1,None)); A["li"]=(A.li-A.li.mean())/A.li.std()
    Xm=np.column_stack([np.ones(len(A)),A.zone_era,A.z,A.li]); y=A.eff.values
    bb=np.linalg.lstsq(Xm,y,rcond=None)[0]; res=y-Xm@bb
    s2=(res@res)/(len(A)-Xm.shape[1]); V=s2*np.linalg.inv(Xm.T@Xm); se=np.sqrt(np.diag(V))
    zc, zse = bb[1], se[1]
    return dict(input=input_col, mean_eff=round(np.nanmean(y),3),
                zone_coef=round(zc,4), zone_t=round(zc/zse,2),
                ci_lo=round(zc-1.96*zse,4), ci_hi=round(zc+1.96*zse,4),
                n=len(A))

res=[run(c) for c in ["arr","arr_fel","arr_struct"]]
R=pd.DataFrame(res); R.to_csv("data/robustness_inputs.csv",index=False)
print("="*72)
print("ZONE-ERA EFFECT ON EFFICIENCY UNDER THREE DEPLOYMENT PROXIES")
print("(efficiency regressed on zone_era + prior-spike + log input)")
print("="*72)
for r in res:
    sig = "*" if (r["ci_lo"]>0 or r["ci_hi"]<0) else "  n.s."
    print(f"  {r['input']:10s}: zone-era coef={r['zone_coef']:+.4f}  "
          f"95% CI [{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}]{sig}   "
          f"mean eff={r['mean_eff']:.3f}  n={r['n']}")
print("\nIf every CI straddles zero, the 'no zone edge' result does not depend")
print("on which arrests-based proxy is used for deployment.")
