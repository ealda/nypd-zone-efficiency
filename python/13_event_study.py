#!/usr/bin/env python3
"""
13_event_study.py -- event study behind the diff-in-differences.
Efficiency gap between targeted precincts (top third by mean 2012-2022
shootings) and the rest, estimated year by year, relative to 2022 (the year
before the zones launched). Flat pre-2023 coefficients support the parallel-
trends assumption the DiD needs; post-2023 coefficients show the program window.
Cluster-robust SEs by precinct. Writes figs/fig5_eventstudy.png + data CSV.
"""
import numpy as np, pandas as pd, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import linprog
RED="#A8322B"; BLUE="#244E78"; GREY="#666666"
FIG="figures"; os.makedirs(FIG,exist_ok=True)   # run from repo root

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
    t=dy[["pct","yr","shoot"]].copy()
    t["eff"]=dea_out(np.clip(dy["arr"].values.astype(float),1,None), dy[["adj_s","adj_v"]].values.astype(float))
    rows.append(t)
E=pd.concat(rows).dropna()
pre=E[E.yr<=2022].groupby("pct")["shoot"].mean()
treated=set(pre[pre>=pre.quantile(2/3)].index)
E["treated"]=E.pct.isin(treated).astype(int)

years=sorted(E.yr.unique()); REF=2022
# design: const, treated, year FE (drop first year), treated x year (drop REF)
cols=["const","treated"]; M={"const":np.ones(len(E)),"treated":E.treated.values}
for y in years[1:]:
    M[f"yr{y}"]=(E.yr==y).astype(float).values; cols.append(f"yr{y}")
for y in years:
    if y==REF: continue
    M[f"tx{y}"]=((E.yr==y)&(E.treated==1)).astype(float).values; cols.append(f"tx{y}")
X=np.column_stack([M[c] for c in cols]); y=E.eff.values
beta=np.linalg.lstsq(X,y,rcond=None)[0]
e=y-X@beta
# cluster-robust by precinct
XtXinv=np.linalg.inv(X.T@X); meat=np.zeros((X.shape[1],X.shape[1]))
for g in E.pct.unique():
    m=(E.pct.values==g); Xg=X[m]; eg=e[m]; s=Xg.T@eg; meat+=np.outer(s,s)
V=XtXinv@meat@XtXinv; se=np.sqrt(np.diag(V))
bdict=dict(zip(cols,beta)); sdict=dict(zip(cols,se))

ys=[]; bs=[]; los=[]; his=[]
for yr in years:
    if yr==REF: b=0.0; s=0.0
    else: b=bdict[f"tx{yr}"]; s=sdict[f"tx{yr}"]
    ys.append(yr); bs.append(b); los.append(b-1.96*s); his.append(b+1.96*s)
out=pd.DataFrame({"year":ys,"coef":np.round(bs,4),"lo":np.round(los,4),"hi":np.round(his,4)})
out.to_csv("data/event_study.csv",index=False)

plt.rcParams.update({"font.family":"DejaVu Sans"})
fig,ax=plt.subplots(figsize=(8.8,4.8))
ax.axhline(0,color=GREY,lw=0.8); ax.axvline(2022.5,color=RED,ls="--",lw=1.2)
ax.errorbar(ys,bs,yerr=[np.array(bs)-np.array(los),np.array(his)-np.array(bs)],
            fmt="o",color=BLUE,ecolor=BLUE,capsize=3,lw=1.5,ms=6)
ax.text(2022.5,ax.get_ylim()[1],"zones launch",color=RED,fontsize=9,ha="right",va="top")
ax.set_title("Event study: efficiency gap, targeted precincts vs the rest, by year",
             loc="left",fontsize=13,fontweight="bold",color="#1A1A1A",pad=30)
ax.text(0,1.03,"Difference relative to 2022, the year before the zones. If the zones were the cause, the points would sit flat before 2023. They do not.",
        transform=ax.transAxes,fontsize=9,color="#4A4A4A")
ax.set_xlabel("year"); ax.set_ylabel("efficiency gap vs 2022")
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.grid(axis="y",color="#E5E5E5",lw=0.5); ax.set_axisbelow(True)
fig.text(0.012,0.012,"Output-oriented VRS, reciprocal output; cluster-robust SEs by precinct. Calculation by author.",fontsize=7.5,color="#999999")
fig.tight_layout(rect=[0,0.03,1,1]); fig.savefig(f"{FIG}/fig5_eventstudy.png",bbox_inches="tight"); plt.close(fig)
print(out.to_string(index=False))
pre_yrs=out[out.year<2023]; print("\nmax |pre-2023 coef| =",round(pre_yrs.coef.abs().max(),4),
      "| any pre-2023 CI excludes 0:",bool(((pre_yrs.lo>0)|(pre_yrs.hi<0)).any()))
