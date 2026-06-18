#!/usr/bin/env python3
"""
09_maps.py -- precinct choropleths, before (2022) vs after (2025).
Top: summer shootings per square mile. Bottom: efficiency score (diverging
scale around the citywide median). Bold outline = precincts a spike-based
program would target (top third by the prior year's shootings); the actual
zone precincts are not public.
"""
import json, numpy as np, pandas as pd, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.collections import PatchCollection
from matplotlib.colors import TwoSlopeNorm
from scipy.optimize import linprog

FIG="figures"; os.makedirs(FIG,exist_ok=True)   # run from repo root
BEFORE, AFTER = 2022, 2025
SQFT_PER_SQMI=27878400.0

gj=json.load(open("data/precincts.geojson"))
shapes={}; area_sqmi={}
for ft in gj["features"]:
    pc=int(ft["properties"]["precinct"]); g=ft["geometry"]
    area_sqmi[pc]=float(ft["properties"]["shape_area"])/SQFT_PER_SQMI
    polys=g["coordinates"] if g["type"]=="MultiPolygon" else [g["coordinates"]]
    shapes.setdefault(pc,[]).extend([np.array(p[0]) for p in polys])

P=pd.read_csv("data/panel.csv")
def shoot_density(yr):
    s=P[P.yr==yr]; return {pc:(c/area_sqmi[pc]) for pc,c in zip(s.pct,s.shoot) if pc in area_sqmi}
def dea_eff(yr):
    # reciprocal (safety) output, output-oriented VRS, mean-normalized
    d=P[P.yr==yr].dropna(subset=["arr","shoot_pred","viol_pred"]).copy()
    X=np.clip(d["arr"].values.astype(float),1,None); X=X/X.mean()
    ys=(d["shoot_pred"].values+1)/(d["shoot"].values+1)
    yv=(d["viol_pred"].values+1)/(d["viol"].values+1)
    Y=np.column_stack([ys,yv]); Y=Y/Y.mean(axis=0)
    n=len(d); eff=np.full(n,np.nan)
    for o in range(n):
        c=np.zeros(1+n); c[0]=-1.0; A=[]; b=[]
        r=np.zeros(1+n); r[1:]=X; A.append(r); b.append(X[o])
        for q in range(2):
            r=np.zeros(1+n); r[0]=Y[o,q]; r[1:]=-Y[:,q]; A.append(r); b.append(0.0)
        Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                    bounds=[(0,None)]*(1+n),method="highs")
        if res.success and res.x[0]>=1e-9: eff[o]=1.0/res.x[0]
    return dict(zip(d.pct,eff))

sd_b, sd_a = shoot_density(BEFORE), shoot_density(AFTER)
ef_b, ef_a = dea_eff(BEFORE), dea_eff(AFTER)

# targeted precincts: top third by the PRIOR year's (2022) summer shootings
s22=dict(zip(P[P.yr==BEFORE].pct, P[P.yr==BEFORE].shoot))
thr=np.quantile(list(s22.values()),2/3)
targeted={pc for pc,v in s22.items() if v>=thr}

ASPECT=1/np.cos(np.radians(40.7))
allpts=np.vstack([r for rings in shapes.values() for r in rings])
def panel(ax, vmap, cmap, norm, title):
    patches=[]; cvals=[]
    for pc,rings in shapes.items():
        v=vmap.get(pc,np.nan)
        for ring in rings: patches.append(MplPoly(ring,closed=True)); cvals.append(v)
    coll=PatchCollection(patches,cmap=cmap,edgecolor="white",linewidth=0.25,norm=norm)
    coll.set_array(np.array(cvals)); ax.add_collection(coll)
    for pc in targeted:                       # bold outline for targeted precincts
        for ring in shapes.get(pc,[]):
            ax.plot(ring[:,0],ring[:,1],color="#1A1A1A",lw=0.9,zorder=5)
    ax.set_xlim(allpts[:,0].min(),allpts[:,0].max()); ax.set_ylim(allpts[:,1].min(),allpts[:,1].max())
    ax.set_aspect(ASPECT); ax.axis("off")
    ax.set_title(title,fontsize=12,fontweight="bold",color="#1A1A1A")
    return coll

plt.rcParams.update({"font.family":"DejaVu Sans"})
fig,axs=plt.subplots(2,2,figsize=(10,11.2))

smax=max(max(sd_b.values()),max(sd_a.values()))
from matplotlib.colors import Normalize
sn=Normalize(0,smax)
panel(axs[0,0],sd_b,"Reds",sn,f"Shootings per square mile, {BEFORE}")
ps=panel(axs[0,1],sd_a,"Reds",sn,f"Shootings per square mile, {AFTER}")
cb=fig.colorbar(ps,ax=axs[0,:],fraction=0.046,pad=0.02,shrink=0.8); cb.set_label("summer shootings per sq mi",fontsize=9)

alleff=np.array(list(ef_b.values())+list(ef_a.values()))
med=float(np.nanmedian(alleff)); lo=float(np.nanmin(alleff))
en=TwoSlopeNorm(vmin=lo, vcenter=med, vmax=1.0)
panel(axs[1,0],ef_b,"RdBu",en,f"Efficiency, {BEFORE}")
pe=panel(axs[1,1],ef_a,"RdBu",en,f"Efficiency, {AFTER}")
cb2=fig.colorbar(pe,ax=axs[1,:],fraction=0.046,pad=0.02,shrink=0.8)
cb2.set_label(f"efficiency (red below median {med:.2f}, blue above)",fontsize=9)

fig.suptitle("New York City precincts, before the zones (2022) and now (2025)",
             fontsize=15,fontweight="bold",y=0.975)
fig.text(0.5,0.945,"Bold outline marks the precincts a spike-based program targets (top third by 2022 shootings). The actual zone precincts are not public.",
         ha="center",fontsize=9,color="#4A4A4A")
fig.text(0.01,0.008,"NYPD shooting, complaint, arrest data via NYC Open Data; precinct boundaries DCP. Calculation by author.",
         fontsize=7.5,color="#999999")
fig.savefig(f"{FIG}/fig4_maps.png",dpi=130,bbox_inches="tight"); plt.close(fig)

# per-precinct values for the R reconciliation
mv=pd.DataFrame({"pct":sorted(shapes)})
mv["sd_before"]=mv.pct.map(sd_b); mv["sd_after"]=mv.pct.map(sd_a)
mv["eff_before"]=mv.pct.map(ef_b); mv["eff_after"]=mv.pct.map(ef_a)
mv["targeted"]=mv.pct.isin(targeted).astype(int)
mv.round(5).to_csv("data/maps_values.csv",index=False)
print("wrote figs/fig4_maps.png and data/maps_values.csv | targeted:",len(targeted),
      "| median eff:",round(med,3))
