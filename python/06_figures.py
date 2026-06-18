#!/usr/bin/env python3
"""06_figures.py -- three figures for the Vital City piece, house palette."""
import numpy as np, pandas as pd, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

RED="#A8322B"; BLUE="#244E78"; GOLD="#C7A24A"; GREY="#666666"; LIGHT="#EFEAE0"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,
    "axes.edgecolor":GREY,"axes.linewidth":0.6,"figure.dpi":130})
FIG="figures"; os.makedirs(FIG,exist_ok=True)   # run from repo root

def style(ax,title,sub=None,src=None,ylab=None,xlab=None):
    ax.set_title(title,loc="left",fontsize=12.5,fontweight="bold",color="#1A1A1A",pad=34)
    if sub: ax.text(0,1.015,sub,transform=ax.transAxes,fontsize=8.8,color="#4A4A4A",va="bottom")
    ax.grid(axis="y",color="#E5E5E5",lw=0.5); ax.set_axisbelow(True)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    if ylab: ax.set_ylabel(ylab,fontsize=10,color="#4A4A4A")
    if xlab: ax.set_xlabel(xlab,fontsize=10,color="#4A4A4A")
    if src: ax.figure.text(0.012,0.012,src,fontsize=7.5,color="#999999")

# ============================================================ FIG 1 fingerprint
d=pd.read_csv("data/fingerprint_recip.csv").dropna(subset=["eff_raw","eff_adj","z"]).copy()
d=d[np.abs(d.z)<3.0]
bins=np.linspace(d.z.min(),d.z.max(),11); d["bin"]=pd.cut(d.z,bins)
g=d.groupby("bin",observed=True).agg(z=("z","mean"),er=("eff_raw","mean"),en=("eff_adj","mean")).dropna()
def fit(x,y): b=np.polyfit(x,y,1); return b
fr=fit(d.z,d.eff_raw); fn=fit(d.z,d.eff_adj)
xs=np.linspace(d.z.min(),d.z.max(),50)
fig,ax=plt.subplots(figsize=(8.6,5.2))
ax.scatter(g.z,g.er,s=42,color=RED,zorder=3,label="Raw year-over-year drop")
ax.scatter(g.z,g.en,s=42,color=BLUE,zorder=3,label="Adjusted for the rebound")
ax.plot(xs,np.polyval(fr,xs),color=RED,lw=2)
ax.plot(xs,np.polyval(fn,xs),color=BLUE,lw=2,ls="--")
style(ax,"Precinct efficiency versus the prior-year crime spike",
      sub="Efficiency score by how far above its own trend the precinct ran the prior year (binned means, 77 precincts, 2012–2025).",
      src="NYPD complaint + shooting data via NYC Open Data. Calculation by author.",
      ylab="Efficiency score (higher = more efficient)",xlab="Prior-year crime spike (standard deviations above precinct trend)")
ax.legend(frameon=False,loc="upper left",fontsize=10)
fig.tight_layout(rect=[0,0.03,1,1]); fig.savefig(f"{FIG}/fig1_fingerprint.png",bbox_inches="tight"); plt.close(fig)

# ============================================================ FIG 2 proxy range
rr=pd.read_csv("data/robustness_recip.csv"); didf=pd.read_csv("data/did_results.csv")
to=rr[rr.input=="arr"].iloc[0]
dr=didf[didf.spec=="real_2023"].iloc[0]; dp=didf[didf.spec=="placebo_2018"].iloc[0]
rowsf=[("Zone era vs earlier years", to.zone_coef, to.ci_lo, to.ci_hi),
       ("Targeted precincts vs the rest,\nsame years", dr.coef, dr.lo, dr.hi),
       ("An earlier decline (a check)", dp.coef, dp.lo, dp.hi)]
fig,ax=plt.subplots(figsize=(9.0,3.8)); y=np.arange(len(rowsf))[::-1]
for yi,(lab,co,lo,hi) in zip(y,rowsf):
    col=GREY if (lo<=0<=hi) else BLUE
    ax.plot([lo,hi],[yi,yi],color=col,lw=3,solid_capstyle="round",zorder=2)
    ax.scatter([co],[yi],s=70,color=col,zorder=3,edgecolor="white",linewidth=1.2)
ax.axvline(0,color="#1A1A1A",lw=1.0,zorder=1)
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rowsf],fontsize=9.5)
style(ax,"The zone-era efficiency gap, before and after removing the citywide decline",
      sub="Estimated efficiency gap with 95% intervals. Comparing targeted precincts with the rest in the same years removes the citywide drop; a placebo checks an earlier decline.",
      src="Output-oriented VRS, reciprocal (safety) output. Calculation by author.",
      xlab="Effect on efficiency  (0 = no difference,  right = more efficient)")
ax.grid(axis="y",visible=False)
fig.tight_layout(rect=[0,0.04,1,1]); fig.savefig(f"{FIG}/fig2_zone_effect.png",bbox_inches="tight"); plt.close(fig)

# ============================================================ FIG 3 monte carlo
mc=pd.read_csv("data/mc_results_v2.csv")
fig,ax=plt.subplots(figsize=(8.6,5.0))
ax.plot(mc.sigma,mc.rec_net,"-o",color=BLUE,lw=2,label="Adjusted for the rebound")
ax.plot(mc.sigma,mc.rec_raw,"--o",color=RED,lw=2,label="Raw year-over-year drop")
style(ax,"Recovery of true efficiency, by year-to-year volatility",
      sub="Simulated precincts, deployment sent to last year's hot spots; correlation of each method's score with the true efficiency.",
      src="Monte Carlo, 25 replications per point. Calculation by author.",
      ylab="Correlation with true efficiency",xlab="Year-to-year crime volatility (transitory s.d.)")
ax.legend(frameon=False,loc="upper right",fontsize=10)
ax.set_ylim(0,0.7)
fig.tight_layout(rect=[0,0.03,1,1]); fig.savefig(f"{FIG}/fig3_montecarlo.png",bbox_inches="tight"); plt.close(fig)

print("wrote figs/fig1_fingerprint.png, fig2_zone_effect.png, fig3_montecarlo.png")
for f in ("fig1_fingerprint","fig2_zone_effect","fig3_montecarlo"):
    print(f, os.path.getsize(f"{FIG}/{f}.png"),"bytes")
