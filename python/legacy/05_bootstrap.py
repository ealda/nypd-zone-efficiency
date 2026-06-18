#!/usr/bin/env python3
"""
05_bootstrap.py -- Simar-Wilson inference.

(A) SW-2007 Algorithm 1: truncated regression of DDF inefficiency (beta>=0,
    left-truncated at 0) on contextual variables, with a parametric bootstrap
    giving confidence intervals that account for estimated efficiencies.
(B) SW-1998 homogeneous bootstrap: bias-correct the 2025 input-oriented DEA
    efficiency scores and report bias-corrected mean + 95% CI.
"""
import numpy as np, pandas as pd
from scipy.optimize import linprog, minimize
from scipy.stats import truncnorm, norm
rng=np.random.default_rng(11)

# ============================================================ (A) SW-2007 alg1
dmu=pd.read_csv("data/ddf_dmu.csv").dropna(subset=["b_net_iv","spike","arr_struct"]).copy()
dmu=dmu[dmu.b_net_iv>=0]
y=dmu["b_net_iv"].values                                   # inefficiency >=0
z_spike=(dmu.spike-dmu.spike.mean())/dmu.spike.std()
l_in=np.log(np.clip(dmu.arr_struct,1,None)); l_in=(l_in-l_in.mean())/l_in.std()
Z=np.column_stack([np.ones(len(dmu)), dmu.zone_era.values, z_spike.values, l_in.values])
names=["const","zone_era","prior_spike","log_struct_input"]

def trunc_reg_ll(p, Z, y):                                 # left-trunc normal at 0
    k=Z.shape[1]; b=p[:k]; s=np.exp(p[k])
    mu=Z@b; e=(y-mu)/s
    ll=norm.logpdf(e)-np.log(s)-norm.logsf((0-mu)/s)       # density / P(y>0)
    return -np.sum(ll)

def fit_trunc(Z,y,p0=None):
    k=Z.shape[1]
    if p0 is None:
        ols=np.linalg.lstsq(Z,y,rcond=None)[0]
        p0=np.concatenate([ols,[np.log(np.std(y-Z@ols)+1e-3)]])
    r=minimize(trunc_reg_ll,p0,args=(Z,y),method="L-BFGS-B",
               options={"maxiter":300})
    return r.x[:k], np.exp(r.x[k]), r.x

bhat,shat,phat=fit_trunc(Z,y)
B=500; draws=np.zeros((B,Z.shape[1]))
mu=Z@bhat
a=(0-mu)/shat                                              # lower trunc point (std)
for bi in range(B):
    ystar=truncnorm.rvs(a, np.inf, loc=mu, scale=shat, random_state=rng)
    bb,_,_=fit_trunc(Z,ystar,p0=phat); draws[bi]=bb
lo=np.percentile(draws,2.5,axis=0); hi=np.percentile(draws,97.5,axis=0)

# write part A immediately (so a slow part B never loses it)
with open("data/bootstrap_findings.txt","w") as f:
    def wa(*x): print(*x,file=f); print(*x)
    wa("="*70); wa("SIMAR-WILSON BOOTSTRAP INFERENCE"); wa("="*70)
    wa(f"(A) Truncated second stage on DDF inefficiency (n={len(dmu)}, B={B})")
    wa(f"    sigma={shat:.3f}")
    wa(f"    {'variable':18s} {'coef':>8s} {'95% CI':>22s}   sign")
    for i,nm in enumerate(names):
        sig="*" if (lo[i]>0 or hi[i]<0) else " (n.s.)"
        wa(f"    {nm:18s} {bhat[i]:+8.4f}   [{lo[i]:+.4f}, {hi[i]:+.4f}]{sig}")
    wa("    (positive coef => MORE inefficiency; zone_era>0 would mean zones LESS efficient)")
    wa("")

# ============================================================ (B) SW-1998 boot
pan=pd.read_csv("data/panel.csv")
d25=pan[pan.yr==2025].dropna(subset=["arr"]).copy()
d25["av_net"]=(d25.shoot_pred-d25.shoot)+(d25.viol_pred-d25.viol)
Xin=np.clip(d25["arr"].values.astype(float),1,None).reshape(-1,1)
Yo=d25["av_net"].values.astype(float); Yo=(Yo-Yo.min()+1.0).reshape(-1,1)

def dea_out(X,Y,Xref=None,Yref=None):
    Xr=X if Xref is None else Xref; Yr=Y if Yref is None else Yref
    nref=Xr.shape[0]; n=X.shape[0]; mI=X.shape[1]; sO=Y.shape[1]; th=np.zeros(n)
    for o in range(n):
        c=np.zeros(1+nref); c[0]=-1.0                      # output-oriented: max phi
        A=[]; b=[]
        for k in range(mI):
            r=np.zeros(1+nref); r[1:]=Xr[:,k]; A.append(r); b.append(X[o,k])
        for q in range(sO):
            r=np.zeros(1+nref); r[0]=Y[o,q]; r[1:]=-Yr[:,q]; A.append(r); b.append(0.0)
        Ae=[np.concatenate([[0.0],np.ones(nref)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                    bounds=[(None,None)]+[(0,None)]*nref,method="highs")
        th[o]=res.x[0] if res.success else np.nan
    return th                                              # phi>=1 ; eff=1/phi

phi=dea_out(Xin,Yo)                                        # phi>=1
theta=1.0/phi                                              # theta in (0,1]
n=len(theta)
# Simar-Wilson 1998 homogeneous smoothed bootstrap WITH reflection at 1.
Bd=120
sig=np.std(theta); h=max(1.06*sig*n**(-0.2),1e-3)
def draw_thetastar():
    samp=rng.choice(theta,size=n,replace=True)
    eps=rng.normal(size=n)
    ts=samp+h*eps
    ts=np.where(ts>1.0, 2.0-ts, ts)                        # reflect at upper bound 1
    mbar=samp.mean()
    ts=mbar+(ts-mbar)/np.sqrt(1+h**2/sig**2)               # variance correction
    ts=np.where(ts>1.0, 2.0-ts, ts)                        # reflect again
    return np.clip(ts, theta.min()*0.5, 1.0)
boot_phi=np.zeros((Bd,n))
for bi in range(Bd):
    ts=draw_thetastar()
    # pseudo outputs Y*_i = Y_i * phi_i/phi*_i = Y_i * (ts_i/theta_i)
    Yref=Yo*(ts/theta).reshape(-1,1)
    boot_phi[bi]=dea_out(Xin,Yo,Xref=Xin,Yref=Yref)
boot_theta=1.0/boot_phi                                    # efficiency space (0,1]
bias=boot_theta.mean(axis=0)-theta                         # naive theta biased UP
eff_bc=theta-bias                                          # bias-corrected efficiency
lo_e=np.percentile(boot_theta,2.5,axis=0); hi_e=np.percentile(boot_theta,97.5,axis=0)
eff=theta

with open("data/bootstrap_findings.txt","a") as f:
    def w(*a): print(*a,file=f); print(*a)
    w(f"(B) Bias-corrected 2025 DEA efficiency (output-oriented, netted; Bd={Bd})")
    w(f"    naive mean efficiency (theta)  = {eff.mean():.3f}")
    w(f"    bias-corrected mean efficiency = {np.nanmean(eff_bc):.3f}")
    w(f"    mean upward bias removed       = {np.nanmean(bias):.3f}")
    w(f"    median 95% CI width            = {np.nanmedian(hi_e-lo_e):.3f}")
    w(f"    n on naive frontier (eff=1)    = {int(np.sum(eff>0.999))}")
    w("")
    w("Reading: the truncated regression with bootstrap CIs is the inferential test")
    w("of whether zone-era precincts are more/less efficient net of selection; the")
    w("bias correction shows DEA's optimistic small-sample bias in the 2025 scores.")
print("\nwrote bootstrap_findings.txt")
