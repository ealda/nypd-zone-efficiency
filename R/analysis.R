# =============================================================================
# analysis.R -- R-native panel build + reconciliation (no Python dependency).
# Builds the precinct-by-summer panel from the NYC Open Data aggregates, nets
# out regression to the mean, runs the DEA (lpSolve), and reconciles the DEA
# and netting numbers against the Python results in data/recon_python.csv.
# (The current efficiency model lives in R/reciprocal_did.R; this file builds
# the shared panel and checks the core numbers. The DDF was dropped.)
#
#   micromamba run -p <env> Rscript R/analysis.R       # from nypd_eff/
# =============================================================================
suppressMessages({library(data.table); library(lpSolve); library(sandwich); library(lmtest)})

VALID <- c(1,5,6,7,9,10,13,14,17,18,19,20,22,23,24,25,26,28,30,32,33,34,40,41,42,
 43,44,45,46,47,48,49,50,52,60,61,62,63,66,67,68,69,70,71,72,73,75,76,77,78,79,
 81,83,84,88,90,94,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,
 115,120,121,122,123)

# ---- build panel from monthly aggregates ------------------------------------
load_monthly <- function(fn){
  d <- fread(file.path("data",fn)); d <- d[, .(pct=as.integer(pct),yr=as.integer(yr),
    mo=as.integer(mo), n=as.numeric(n))]
  d[pct %in% VALID & !is.na(pct)]
}
summer <- function(d, nm){ s <- d[mo>=6 & mo<=9, .(v=sum(n)), by=.(pct,yr)]; setnames(s,"v",nm); s }
sh <- summer(load_monthly("shootings_monthly.csv"),"shoot")
vi <- summer(load_monthly("violent_monthly.csv"),"viol")
ar <- fread("data/arrests_summer.csv")[, .(pct=as.integer(pct),yr=as.integer(yr),
        arr=as.numeric(arr),arr_fel=as.numeric(arr_fel))][pct %in% VALID]

pcts <- sort(Reduce(intersect, list(VALID, unique(sh$pct), unique(vi$pct), unique(ar$pct))))
grid <- CJ(pct=pcts, yr=2009:2025)
P <- Reduce(function(a,b) merge(a,b,by=c("pct","yr"),all.x=TRUE),
            list(grid, sh, vi, ar[, .(pct,yr,arr,arr_fel)]))
P[is.na(shoot), shoot:=0]; P[is.na(viol), viol:=0]
setorder(P, pct, yr)
lag <- function(x,k) shift(x,k)
for(c in c("shoot","viol")){
  P[, paste0(c,"_l1"):=lag(get(c),1), by=pct]
  P[, paste0(c,"_l2"):=lag(get(c),2), by=pct]
  P[, paste0(c,"_l3"):=lag(get(c),3), by=pct]
  P[, paste0(c,"_m3"):=rowMeans(.SD), .SDcols=paste0(c,c("_l1","_l2","_l3"))]
}
# RTM reversion model fit on no-zone era 2012-2022 (OLS, matches Python)
fit_pred <- function(col){
  tr <- P[yr>=2012 & yr<=2022 & !is.na(get(paste0(col,"_l1"))) & !is.na(get(paste0(col,"_m3")))]
  m <- lm(reformulate(paste0(col,c("_l1","_m3")), response=col), data=tr)
  predict(m, newdata=P)
}
P[, shoot_pred:=fit_pred("shoot")]; P[, viol_pred:=fit_pred("viol")]
P[, shoot_av_raw:=shoot_l1-shoot]; P[, shoot_av_net:=shoot_pred-shoot]
P[, viol_av_raw:=viol_l1-viol];   P[, viol_av_net:=viol_pred-viol]
P <- P[yr>=2012 & !is.na(shoot_pred) & !is.na(viol_pred) & !is.na(arr)]
P[, av_raw:=shoot_av_raw+viol_av_raw]; P[, av_net:=shoot_av_net+viol_av_net]
P[, crime:=shoot+viol]; P[, spike:=(shoot_l1-shoot_m3)+(viol_l1-viol_m3)]

# ---- DEA input-oriented (lpSolve); VRS or CRS -------------------------------
dea_in <- function(X, Y, rts="vrs"){
  n <- nrow(X); mI <- ncol(X); sO <- ncol(Y); th <- numeric(n)
  for(o in 1:n){
    # vars: theta, lambda_1..n
    obj <- c(1, rep(0,n))
    con <- matrix(0, 0, n+1); dir <- c(); rhs <- c()
    for(k in 1:mI){ con<-rbind(con, c(-X[o,k], X[,k])); dir<-c(dir,"<="); rhs<-c(rhs,0) }
    for(r in 1:sO){ con<-rbind(con, c(0, Y[,r]));        dir<-c(dir,">="); rhs<-c(rhs,Y[o,r]) }
    if(rts=="vrs"){ con<-rbind(con, c(0, rep(1,n))); dir<-c(dir,"="); rhs<-c(rhs,1) }
    s <- lp("min", obj, con, dir, rhs); th[o] <- if(s$status==0) s$objval else NA
  }
  th
}
tr_pos <- function(M){ sweep(M,2,apply(M,2,min)) + 1 }

d25 <- P[yr==2025]
X25 <- matrix(pmax(d25$arr,1),ncol=1)
Y25 <- tr_pos(as.matrix(d25[,.(shoot_av_net,viol_av_net)]))
eff_vrs <- dea_in(X25,Y25,"vrs"); eff_crs <- dea_in(X25,Y25,"crs")

# ---- netting robustness: OLS already (av_net); add Poisson ------------------
trp <- P[yr>=2012 & yr<=2022]
gs <- glm(shoot ~ shoot_l1 + shoot_m3, family=poisson, data=trp)
gv <- glm(viol  ~ viol_l1  + viol_m3,  family=poisson, data=trp)
P[, av_net_pois:=(predict(gs,P,type="response")-shoot)+(predict(gv,P,type="response")-viol)]

corr_raw  <- cor(P$spike, P$av_raw,      use="complete.obs")
corr_ols  <- cor(P$spike, P$av_net,      use="complete.obs")
corr_pois <- cor(P$spike, P$av_net_pois, use="complete.obs")

# ---- reconciliation (DEA + netting metrics) ---------------------------------
R <- data.table(metric=c(
  "dea2025_mean_eff_vrs_net","dea2025_crs_vrs_spearman",
  "corr_spike_av_raw","corr_spike_av_net_ols","corr_spike_av_net_poisson"),
  r_value=round(c(
  mean(eff_vrs,na.rm=TRUE), cor(eff_vrs,eff_crs,method="spearman"),
  corr_raw, corr_ols, corr_pois),4))
fwrite(R, "data/recon_R.csv")

if(file.exists("data/recon_python.csv")){
  py <- fread("data/recon_python.csv")
  cmp <- merge(py, R, by="metric", all=TRUE)
  cmp[, abs_diff:=abs(python_value-r_value)]
  fwrite(cmp, "data/reconciliation.csv")
  cat("\n===== PYTHON vs R RECONCILIATION =====\n"); print(cmp)
  cat("\nmax abs diff:", round(max(cmp$abs_diff,na.rm=TRUE),4),
      " | all within 0.02:", all(cmp$abs_diff<0.02,na.rm=TRUE), "\n")
}
fwrite(P, "data/panel_R.csv")
cat("\nR pipeline complete. Panel rows:", nrow(P), " precincts:", uniqueN(P$pct), "\n")
