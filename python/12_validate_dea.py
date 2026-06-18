#!/usr/bin/env python3
"""
12_validate_dea.py -- validate the hand-coded output-oriented VRS DEA two ways:
(1) envelopment (primal) vs multiplier (dual) -- must agree if the LP is right;
(2) print scores for 2025 so they can be checked against a package.
"""
import numpy as np, pandas as pd
from scipy.optimize import linprog

P=pd.read_csv("data/panel.csv")
d=P[P.yr==2025].dropna(subset=["arr","shoot_pred","viol_pred"]).copy()
X=np.clip(d["arr"].values.astype(float),1,None); X=X/X.mean()
Y=np.column_stack([(d.shoot_pred.values+1)/(d.shoot.values+1),
                   (d.viol_pred.values+1)/(d.viol.values+1)])
Y=Y/Y.mean(axis=0)
n=len(X)

def out_primal(o):
    # max phi : sum lam x<=x_o ; sum lam y >= phi y_o ; sum lam=1
    c=np.zeros(1+n); c[0]=-1.0; A=[]; b=[]
    r=np.zeros(1+n); r[1:]=X; A.append(r); b.append(X[o])
    for q in range(Y.shape[1]):
        r=np.zeros(1+n); r[0]=Y[o,q]; r[1:]=-Y[:,q]; A.append(r); b.append(0.0)
    Ae=[np.concatenate([[0.0],np.ones(n)])]; be=[1.0]
    res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                bounds=[(0,None)]*(1+n),method="highs")
    return -res.fun

def out_dual(o):
    # min v'x_o + v0 : u'y_o=1 ; v'x_j - u'y_j + v0 >=0 ; u,v>=0 ; v0 free
    mI=1; sO=Y.shape[1]; nv=mI+sO+1   # [v(1), u(sO), v0]
    c=np.zeros(nv); c[0]=X[o]; c[-1]=1.0
    A=[]; b=[]                          # -(v'x_j - u'y_j + v0) <= 0
    for j in range(n):
        r=np.zeros(nv); r[0]=-X[j]; r[1:1+sO]=Y[j,:]; r[-1]=-1.0; A.append(r); b.append(0.0)
    Ae=[np.zeros(nv)]; Ae[0][1:1+sO]=Y[o,:]; be=[1.0]
    bounds=[(0,None)]*(mI+sO)+[(None,None)]
    res=linprog(c,A_ub=np.array(A),b_ub=np.array(b),A_eq=np.array(Ae),b_eq=np.array(be),
                bounds=bounds,method="highs")
    return res.fun

prim=np.array([out_primal(o) for o in range(n)])
dual=np.array([out_dual(o)  for o in range(n)])
gap=np.nanmax(np.abs(prim-dual))
print("output-oriented VRS, 2025, reciprocal outputs")
print(f"  max |primal phi - dual phi| = {gap:.2e}   ({'AGREE' if gap<1e-6 else 'MISMATCH'})")
print(f"  mean efficiency (1/phi)     = {np.nanmean(1/prim):.4f}")
print(f"  n efficient (phi==1)        = {int(np.sum(prim<1+1e-6))} of {n}")
# dump scores for an external package check
pd.DataFrame({"pct":d.pct.values,"arr":d.arr.values,
              "y1":Y[:,0],"y2":Y[:,1],"eff":1/prim}).round(6).to_csv("data/dea2025_scores.csv",index=False)
print("wrote data/dea2025_scores.csv")
