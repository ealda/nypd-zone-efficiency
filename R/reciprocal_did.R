# reciprocal_did.R -- R twin of 10_reciprocal.py + 11_did.py.
# Efficiency with crime as a reciprocal (safety) output, output-oriented VRS,
# inputs/outputs mean-normalized. (1) time-only zone-era gap by proxy;
# (2) difference-in-differences, targeted precincts vs the rest, same years,
# plus a placebo. Reconciles against the Python CSVs.
suppressMessages({library(data.table); library(lpSolve)})

P <- fread(if (file.exists("data/panel_R.csv")) "data/panel_R.csv" else "data/panel.csv")
P[, zone_era := as.integer(yr >= 2023)]
P[, spike := (shoot_l1 - shoot_m3) + (viol_l1 - viol_m3)]
P[, adj_s := (shoot_pred + 1)/(shoot + 1)]
P[, adj_v := (viol_pred  + 1)/(viol  + 1)]
# spike-purged input
d <- P[is.finite(shoot_m3+viol_m3) & (shoot_m3+viol_m3)>0 & is.finite(arr)]
X <- model.matrix(~ log(shoot_m3+viol_m3) + factor(pct), data=d)
b <- qr.solve(X, log(pmax(d$arr,1))); d[, arr_struct := exp(as.vector(X %*% b))]
P <- merge(P, d[,.(pct,yr,arr_struct)], by=c("pct","yr"), all.x=TRUE)

dea_out <- function(x, Y){                 # output-oriented VRS, mean-normalized
  x <- x/mean(x); Y <- sweep(Y, 2, colMeans(Y), "/")
  n <- length(x); sO <- ncol(Y); eff <- rep(NA_real_, n)
  for (o in 1:n){
    con <- rbind(c(0, x)); dir <- "<="; rhs <- x[o]          # input
    for (q in 1:sO){ con <- rbind(con, c(Y[o,q], -Y[,q])); dir <- c(dir,"<="); rhs <- c(rhs,0) }
    con <- rbind(con, c(0, rep(1,n))); dir <- c(dir,"="); rhs <- c(rhs,1)
    s <- lp("max", c(1, rep(0,n)), con, dir, rhs)
    if (s$status==0 && s$objval>=1e-9) eff[o] <- 1/s$objval
  }
  eff
}
eff_panel <- function(input_col){
  d <- P[is.finite(get(input_col)) & is.finite(adj_s) & is.finite(adj_v) & is.finite(spike)]
  rows <- list()
  for (y in 2012:2025){ dy <- d[yr==y]; if (nrow(dy)<20) next
    t <- dy[,.(pct,yr,zone_era,spike,shoot)]; t[, eff := dea_out(pmax(dy[[input_col]],1), as.matrix(dy[,.(adj_s,adj_v)]))]
    t[, inp := pmax(dy[[input_col]],1)]; rows[[length(rows)+1]] <- t }
  rbindlist(rows)[is.finite(eff)]
}
zone_reg <- function(A){
  A[, z:=scale(spike)[,1]]; A[, li:=scale(log(pmax(inp,1)))[,1]]
  m <- lm(eff ~ zone_era + z + li, data=A); ci <- confint(m)["zone_era",]
  c(coef(m)["zone_era"], ci[1], ci[2])
}

# (1) time-only gap by proxy
R1 <- rbindlist(lapply(c("arr","arr_fel","arr_struct"), function(c){
  v <- zone_reg(eff_panel(c)); data.table(input=c, zone_coef=round(v[1],4), ci_lo=round(v[2],4), ci_hi=round(v[3],4))}))
# (2) DiD on the arr efficiency panel
E <- eff_panel("arr")
pre <- E[yr<=2022, .(m=mean(shoot)), by=pct]; treated <- pre[m>=quantile(m,2/3), pct]
E[, treated := as.integer(pct %in% treated)]
did <- function(df, cut){ df[, post:=as.integer(yr>=cut)]
  m <- lm(eff ~ treated*post, data=df); ci <- confint(m)["treated:post",]
  c(coef(m)["treated:post"], ci[1], ci[2]) }
real <- did(copy(E), 2023); plac <- did(copy(E[yr<=2022]), 2018)

# write R result CSVs so the R figures are self-contained
fwrite(R1, "data/robustness_recip_R.csv")
fwrite(data.table(spec=c("real_2023","placebo_2018"), coef=c(real[1],plac[1]),
                  lo=c(real[2],plac[2]), hi=c(real[3],plac[3])), "data/did_R.csv")
# fingerprint: raw vs adjusted safety, input = arr
P[, raw_s := (shoot_l1+1)/(shoot+1)]; P[, raw_v := (viol_l1+1)/(viol+1)]
dr2 <- P[is.finite(arr)&is.finite(raw_s)&is.finite(raw_v)&is.finite(spike)]
fr <- list()
for (y in 2012:2025){ dy <- dr2[yr==y]; if (nrow(dy)<20) next
  t <- dy[,.(pct,yr,spike)]; t[, eff_raw := dea_out(pmax(dy$arr,1), as.matrix(dy[,.(raw_s,raw_v)]))]; fr[[length(fr)+1]] <- t }
FP <- merge(rbindlist(fr), E[,.(pct,yr,eff_adj=eff)], by=c("pct","yr"))
FP <- FP[is.finite(eff_raw)&is.finite(eff_adj)]; FP[, z := scale(spike)[,1]]
fwrite(FP[,.(pct,yr,spike,eff_raw,eff_adj,z)], "data/fingerprint_recip_R.csv")

cat("\n==== TIME-ONLY ZONE GAP BY PROXY (R, reciprocal/output-oriented) ====\n"); print(R1)
cat(sprintf("\nDiD real (2023):    %+.4f  [%+.4f, %+.4f]\n", real[1], real[2], real[3]))
cat(sprintf("DiD placebo (2018): %+.4f  [%+.4f, %+.4f]\n", plac[1], plac[2], plac[3]))

if (file.exists("data/robustness_recip.csv") && file.exists("data/did_results.csv")){
  py1 <- fread("data/robustness_recip.csv")[, .(input, py=zone_coef)]
  cmp1 <- merge(py1, R1[, .(input, r=zone_coef)], by="input"); cmp1[, d:=abs(py-r)]
  pyd <- fread("data/did_results.csv")
  cat("\n==== PYTHON vs R ====\n"); print(cmp1)
  cat(sprintf("DiD real: py %+.4f vs r %+.4f | placebo: py %+.4f vs r %+.4f\n",
      pyd[spec=="real_2023",coef], real[1], pyd[spec=="placebo_2018",coef], plac[1]))
  cat("time-only max diff:", round(max(cmp1$d),4),
      "| DiD real diff:", round(abs(pyd[spec=="real_2023",coef]-real[1]),4), "\n")
}
