# =============================================================================
# replicate.R -- Independent R reconciliation of the Python efficiency pipeline.
#
# Strategy: read the SAME panel the Python pipeline built (data/panel.csv,
# data/ddf_dmu.csv) so the DATA layer is identical, and re-estimate every
# quantity with established, peer-trusted R packages. If the numbers match
# recon_python.csv, the result is not an artifact of the hand-coded Python.
#
# Packages: Benchmarking (DEA/DDF), frontier (SFA), truncreg (Simar-Wilson
# 2007 second stage), sandwich + lmtest (clustered SEs); rDEA/FEAR optional
# for the Simar-Wilson 1998 bootstrap.
#
# Run from the nypd_eff/ directory:  Rscript R/replicate.R
# =============================================================================
suppressMessages({
  library(data.table); library(Benchmarking)
  library(sandwich);   library(lmtest)
})

P  <- fread("data/panel.csv")
DD <- fread("data/ddf_dmu.csv")

P[, av_raw := shoot_av_raw + viol_av_raw]
P[, av_net := shoot_av_net + viol_av_net]
P[, spike  := (shoot_l1 - shoot_m3) + (viol_l1 - viol_m3)]

out <- list()
add <- function(metric, value) out[[length(out) + 1]] <<-
  data.table(metric = metric, r_value = round(value, 4))

# ---- 1. DEA 2025, input-oriented, VRS, netted outputs -----------------------
# input = summer arrests; outputs = netted averted (translated >= 1, exactly
# as in Python). VRS input orientation is translation-invariant in outputs.
d25 <- P[yr == 2025]
X   <- matrix(pmax(d25$arr, 1), ncol = 1)
Y   <- as.matrix(d25[, .(shoot_av_net, viol_av_net)])
Y   <- sweep(Y, 2, apply(Y, 2, min)) + 1          # translate to >= 1

eff_vrs <- dea(X, Y, RTS = "vrs", ORIENTATION = "in")$eff
eff_crs <- dea(X, Y, RTS = "crs", ORIENTATION = "in")$eff
add("dea2025_mean_eff_vrs_net", mean(eff_vrs, na.rm = TRUE))
add("dea2025_crs_vrs_spearman", cor(eff_vrs, eff_crs, method = "spearman"))

# ---- 2. Netting removes the prior-year spike (OLS and Poisson) --------------
add("corr_spike_av_raw",     cor(P$spike, P$av_raw,  use = "complete.obs"))
add("corr_spike_av_net_ols", cor(P$spike, P$av_net,  use = "complete.obs"))

tr <- P[yr >= 2012 & yr <= 2022]
gp_s <- glm(shoot ~ shoot_l1 + shoot_m3, family = poisson, data = tr)
gp_v <- glm(viol  ~ viol_l1  + viol_m3,  family = poisson, data = tr)
P[, pred_shoot_pois := predict(gp_s, newdata = P, type = "response")]
P[, pred_viol_pois  := predict(gp_v, newdata = P, type = "response")]
P[, av_net_pois := (pred_shoot_pois - shoot) + (pred_viol_pois - viol)]
add("corr_spike_av_net_poisson", cor(P$spike, P$av_net_pois, use = "complete.obs"))

# ---- 3. Fingerprint with naive and precinct-clustered SEs -------------------
DD[, z := scale(spike)[, 1]]
fp <- function(ycol) {
  m  <- lm(DD[[ycol]] ~ DD$z)
  tn <- coef(m)[2] / sqrt(diag(vcov(m)))[2]
  Vc <- vcovCL(m, cluster = DD$pct)
  tc <- coef(m)[2] / sqrt(diag(Vc))[2]
  c(b = unname(coef(m)[2]), t_naive = unname(tn), t_clustered = unname(tc))
}
fr <- fp("b_raw"); fn <- fp("b_net")
add("fingerprint_raw_b", fr["b"]); add("fingerprint_raw_t_naive", fr["t_naive"])
add("fingerprint_raw_t_clustered", fr["t_clustered"])
add("fingerprint_net_b", fn["b"]); add("fingerprint_net_t_naive", fn["t_naive"])
add("fingerprint_net_t_clustered", fn["t_clustered"])

# ---- 4. Simar-Wilson 2007 truncated second stage (point estimates) ----------
# inefficiency (b_net_iv) >= 0, left-truncated at 0, on contextual variables.
if (requireNamespace("truncreg", quietly = TRUE)) {
  library(truncreg)
  S <- DD[is.finite(b_net_iv) & b_net_iv >= 0]
  S[, z_spike := scale(spike)[, 1]]
  S[, l_in := scale(log(pmax(arr_struct, 1)))[, 1]]
  tr2 <- truncreg(b_net_iv ~ zone_era + z_spike + l_in, data = S, point = 0,
                  direction = "left")
  add("sw2007_zone_era_coef", coef(tr2)["zone_era"])
}

# ---- 5. SFA cross-check (frontier) ------------------------------------------
if (requireNamespace("frontier", quietly = TRUE)) {
  library(frontier)
  d25[, lnY := log(shoot_av_net - min(shoot_av_net) + 1)]
  d25[, lnX := log(pmax(arr, 1))]
  sf <- tryCatch(sfa(lnY ~ lnX, data = d25), error = function(e) NULL)
  if (!is.null(sf)) add("sfa2025_slope_logarr", coef(sf)["lnX"])
}

# ---- 6. (optional) Simar-Wilson 1998 bias-corrected DEA via rDEA ------------
if (requireNamespace("rDEA", quietly = TRUE)) {
  library(rDEA)
  rb <- tryCatch(
    dea.robust(X = X, Y = Y, model = "output", RTS = "variable", B = 200),
    error = function(e) NULL)
  if (!is.null(rb)) add("dea2025_mean_eff_biascorrected", mean(1/rb$theta_hat_hat, na.rm=TRUE))
}

# ---- write reconciliation ---------------------------------------------------
recon_R <- rbindlist(out)
fwrite(recon_R, "data/recon_R.csv")

# merge with Python results for a side-by-side diff
if (file.exists("data/recon_python.csv")) {
  py <- fread("data/recon_python.csv")
  cmp <- merge(py, recon_R, by = "metric", all = TRUE)
  cmp[, abs_diff := abs(python_value - r_value)]
  fwrite(cmp, "data/reconciliation.csv")
  cat("\n================ PYTHON vs R RECONCILIATION ================\n")
  print(cmp)
  cat("\nMax abs diff on shared metrics:",
      round(max(cmp$abs_diff, na.rm = TRUE), 5), "\n")
  cat("All shared metrics agree within 0.01:",
      all(cmp$abs_diff < 0.01, na.rm = TRUE), "\n")
} else {
  print(recon_R)
}
