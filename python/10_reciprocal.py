#!/usr/bin/env python3
"""
10_reciprocal.py -- efficiency with crime as a reciprocal (safety) output,
output-oriented (Lovell, Pastor & Turner 1995; Fare-Grosskopf undesirable-output
tradition). Safety = expected crime / observed crime, so the rebound is netted
in the numerator. >1 means a precinct came in safer than its own history predicts.

Outputs:
  adjusted safety (rebound-netted): (pred+1)/(obs+1)   [pred = reversion model]
  raw safety (contaminated):        (prior+1)/(obs+1)   [prior = last year]
Input: officers (arrests proxy). Output-oriented VRS DEA, inputs/outputs
divided by their means. Efficiency = 1/phi.
Writes: robustness_recip.csv (zone-era gap by proxy) and fingerprint_recip.csv.
"""
import numpy as np, pandas as pd
from scipy.optimize import linprog

P = pd.read_csv("data/panel.csv")
# spike-purged ("structural") input proxy: log(arr) ~ log(permanent crime) +
# precinct fixed effects. Computed here so nothing depends on the dropped DDF.
P["m3crime"] = P["shoot_m3"] + P["viol_m3"]
_d = P.dropna(subset=["m3crime","arr"]).copy(); _d = _d[_d.m3crime > 0]
_FE = pd.get_dummies(_d.pct, prefix="p").values.astype(float)
_X = np.column_stack([np.log(_d.m3crime.values), _FE])
_b, *_ = np.linalg.lstsq(_X, np.log(np.clip(_d.arr.values, 1, None)), rcond=None)
_d["arr_struct"] = np.exp(_X @ _b)
P = P.merge(_d[["pct","yr","arr_struct"]], on=["pct","yr"], how="left")
P["zone_era"] = (P.yr >= 2023).astype(int)
P["spike"] = (P.shoot_l1 - P.shoot_m3) + (P.viol_l1 - P.viol_m3)
# safety outputs (positive, no translation needed)
P["adj_s"] = (P.shoot_pred + 1) / (P.shoot + 1)
P["adj_v"] = (P.viol_pred  + 1) / (P.viol  + 1)
P["raw_s"] = (P.shoot_l1   + 1) / (P.shoot + 1)
P["raw_v"] = (P.viol_l1    + 1) / (P.viol  + 1)

def dea_out(X, Y):                       # output-oriented VRS, 1 input, >=1 outputs
    X = X / X.mean(); Y = Y / Y.mean(axis=0)
    n = len(X); sO = Y.shape[1]; eff = np.full(n, np.nan)
    for o in range(n):
        c = np.zeros(1+n); c[0] = -1.0           # max phi
        A=[]; b=[]
        r=np.zeros(1+n); r[1:]=X; A.append(r); b.append(X[o])             # input <=
        for q in range(sO):
            r=np.zeros(1+n); r[0]=Y[o,q]; r[1:]=-Y[:,q]; A.append(r); b.append(0.0)  # output
        Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                    bounds=[(0,None)]+[(0,None)]*n,method="highs")
        if res.success and res.x[0] >= 1e-9: eff[o]=1.0/res.x[0]
    return eff

def eff_panel(input_col, ycols):
    d = P.dropna(subset=[input_col,"adj_s","adj_v","raw_s","raw_v","spike"]).copy()
    out=[]
    for yr in range(2012,2026):
        dy=d[d.yr==yr]
        if len(dy)<20: continue
        X=np.clip(dy[input_col].values.astype(float),1,None)
        Y=dy[ycols].values.astype(float)
        t=dy[["pct","yr","zone_era","spike"]].copy(); t["eff"]=dea_out(X,Y); t["inp"]=X
        out.append(t)
    return pd.concat(out).dropna()

def zone_reg(A):
    A=A.copy(); A["z"]=(A.spike-A.spike.mean())/A.spike.std()
    A["li"]=np.log(np.clip(A.inp,1,None)); A["li"]=(A.li-A.li.mean())/A.li.std()
    X=np.column_stack([np.ones(len(A)),A.zone_era,A.z,A.li]); y=A.eff.values
    bb=np.linalg.lstsq(X,y,rcond=None)[0]; r=y-X@bb
    se=np.sqrt((r@r)/(len(A)-4)*np.linalg.inv(X.T@X)[1,1])
    return bb[1], bb[1]-1.96*se, bb[1]+1.96*se, np.nanmean(y)

# ---- Fig 2: zone-era gap by proxy, adjusted (rebound-netted) safety ---------
rows=[]
for col in ["arr","arr_fel","arr_struct"]:
    A=eff_panel(col,["adj_s","adj_v"]); c,lo,hi,me=zone_reg(A)
    rows.append(dict(input=col,mean_eff=round(me,3),zone_coef=round(c,4),
                     ci_lo=round(lo,4),ci_hi=round(hi,4),n=len(A)))
pd.DataFrame(rows).to_csv("data/robustness_recip.csv",index=False)

# ---- Fig 1: fingerprint, raw vs adjusted safety (input = arr) ---------------
Aa=eff_panel("arr",["adj_s","adj_v"]).rename(columns={"eff":"eff_adj"})[["pct","yr","spike","eff_adj"]]
Ar=eff_panel("arr",["raw_s","raw_v"]).rename(columns={"eff":"eff_raw"})[["pct","yr","eff_raw"]]
F=Aa.merge(Ar,on=["pct","yr"])
F["z"]=(F.spike-F.spike.mean())/F.spike.std()
F.to_csv("data/fingerprint_recip.csv",index=False)
def slope(y,z):
    X=np.column_stack([np.ones(len(z)),z]); bb=np.linalg.lstsq(X,y,rcond=None)[0]
    r=y-X@bb; se=np.sqrt((r@r)/(len(z)-2)/np.sum((z-z.mean())**2)); return bb[1],bb[1]/se
br=slope(F.eff_raw.values,F.z.values); ba=slope(F.eff_adj.values,F.z.values)

print("="*70); print("RECIPROCAL (safety) OUTPUT, OUTPUT-ORIENTED VRS"); print("="*70)
print("Zone-era gap by deployment proxy (adjusted safety):")
for r in rows:
    sig="*" if (r["ci_lo"]>0 or r["ci_hi"]<0) else " n.s."
    print(f"  {r['input']:10s}: coef={r['zone_coef']:+.4f}  CI[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}]{sig}  mean_eff={r['mean_eff']:.3f}")
print(f"\nFingerprint (efficiency vs prior-year spike):")
print(f"  raw safety     : slope={br[0]:+.4f}  t={br[1]:+.2f}")
print(f"  adjusted safety: slope={ba[0]:+.4f}  t={ba[1]:+.2f}")
