#!/usr/bin/env python3
"""
03_montecarlo.py -- RTM-propagation identification under KNOWN truth.

DGP per precinct i:
  permanent level   mu_i        (lognormal)
  true efficiency   e_i in (0,1] (how well deployment averts crime)
  pre-period (no deployment): c = mu * exp(N(0,sigma))  -> used to FIT the
       reversion model, exactly as the real pipeline fits on the no-zone era.
  treatment year:
       c_prev = mu*exp(eps_prev)              transitory spike/dip
       deploy d = k * c_prev                  SELECTION: officers go to spikes
       a_true  = e_i * d^alpha                 real averted crime (the target)
       c_now   = mu*exp(eps_now) - a_true
  raw_av = c_prev - c_now      (contaminated by reversion of eps_prev, which
                                is correlated with d via selection)
  net_av = pred  - c_now       (pred = reversion-model counterfactual)

We run input-oriented VRS DEA with input d and a single output, three times:
  output = a_true  -> eff_true  (what DEA gives with a clean output)
  output = raw_av  -> eff_raw
  output = net_av  -> eff_net
and ask how well eff_raw / eff_net recover eff_true and the true e_i, as the
transitory variance (sigma) grows. Writes data/mc_results.csv incrementally.
"""
import numpy as np, csv, os
from scipy.optimize import linprog
from scipy.stats import spearmanr

rng = np.random.default_rng(7)
N=60; REPS=25; ALPHA=0.5; K=0.8
SIGMAS=[0.10,0.25,0.45,0.70]
PATH="data/mc_results_v2.csv"

def dea_vrs_input_single(x, y):
    x=np.clip(x,1e-6,None); y=y - y.min() + 1.0
    n=len(x); th=np.zeros(n)
    for o in range(n):
        c=np.zeros(1+n); c[0]=1.0
        A=[]; b=[]
        r=np.zeros(1+n); r[0]=-x[o]; r[1:]=x; A.append(r); b.append(0.0)      # input
        r=np.zeros(1+n); r[1:]=-y; A.append(r); b.append(-y[o])               # output
        Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
        res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),
                    b_eq=np.array(be),bounds=[(None,None)]+[(0,None)]*n,method="highs")
        th[o]=res.x[0] if res.success else np.nan
    return th

def one_rep(sigma):
    mu=np.exp(rng.normal(2.0,0.6,N))            # permanent crime level
    e =rng.uniform(0.3,1.0,N)                    # true efficiency
    # pre-period (no deployment): 4 years, fit reversion c_t ~ c_{t-1}+mean3
    pre=np.array([mu*np.exp(rng.normal(0,sigma,N)) for _ in range(4)])  # (4,N)
    ct=pre[3]; c1=pre[2]; m3=pre[:3].mean(axis=0)
    X=np.column_stack([np.ones(N),c1,m3]); beta,*_=np.linalg.lstsq(X,ct,rcond=None)
    # treatment year
    eps_prev=rng.normal(0,sigma,N); eps_now=rng.normal(0,sigma,N)
    c_prev=mu*np.exp(eps_prev); m3t=mu  # 3yr mean ~ permanent
    d=K*c_prev
    a_true=e*np.power(d,ALPHA)
    c_now=mu*np.exp(eps_now)-a_true
    pred=np.column_stack([np.ones(N),c_prev,m3t])@beta
    raw_av=c_prev-c_now; net_av=pred-c_now
    eff_true=dea_vrs_input_single(d,a_true)
    eff_raw =dea_vrs_input_single(d,raw_av)
    eff_net =dea_vrs_input_single(d,net_av)
    def sp(a,b):
        m=np.isfinite(a)&np.isfinite(b); return spearmanr(a[m],b[m]).correlation
    # contamination signature: does measured efficiency track the prior-yr shock?
    # recovery: how well does measured efficiency track clean-output DEA?
    return (sp(eff_raw,eps_prev), sp(eff_net,eps_prev),
            sp(eff_raw,eff_true), sp(eff_net,eff_true))

new=not os.path.exists(PATH)
with open(PATH,"a",newline="") as f:
    w=csv.writer(f)
    if new: w.writerow(["sigma","reps","sig_raw","sig_net","rec_raw","rec_net"])
    for sigma in SIGMAS:
        acc=np.array([one_rep(sigma) for _ in range(REPS)])
        mean=np.nanmean(acc,axis=0)
        w.writerow([sigma,REPS]+[round(v,3) for v in mean]); f.flush()
        print(f"sigma={sigma:.2f} | contamination corr(eff,prior-shock): "
              f"RAW={mean[0]:+.3f} NET={mean[1]:+.3f}  | recovery corr(eff,clean): "
              f"RAW={mean[2]:.3f} NET={mean[3]:.3f}",flush=True)
print("done -> data/mc_results.csv")
print("EXPECT: RAW contamination >0 and grows with sigma; NET ~0. "
      "NET recovery >= RAW at every sigma.")
