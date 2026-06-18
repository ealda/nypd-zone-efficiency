# robustness.R -- Does the zone-era efficiency gap depend on the input proxy?
# Re-runs input-oriented VRS DEA (netted outputs) with three deployment proxies
# and regresses efficiency on zone-era + controls. Writes data/robustness_R.csv
# and reconciles against the Python data/robustness_inputs.csv.
suppressMessages({library(data.table); library(lpSolve)})

P <- fread(if (file.exists("data/panel_R.csv")) "data/panel_R.csv" else "data/panel.csv")
P[, zone_era := as.integer(yr >= 2023)]
P[, spike := (shoot_l1 - shoot_m3) + (viol_l1 - viol_m3)]
P[, m3crime := shoot_m3 + viol_m3]

# spike-purged input: log(arr) ~ log(permanent crime) + precinct fixed effects
d <- P[is.finite(m3crime) & m3crime > 0 & is.finite(arr)]
X <- model.matrix(~ log(m3crime) + factor(pct), data = d)
b <- qr.solve(X, log(pmax(d$arr, 1)))
d[, arr_struct := exp(as.vector(X %*% b))]
P <- merge(P, d[, .(pct, yr, arr_struct)], by = c("pct","yr"), all.x = TRUE)

dea_in <- function(x, Y){                    # input-oriented VRS, 1 input, >=1 outputs
  n <- length(x); th <- numeric(n)
  x <- x / mean(x)                            # mean-normalize input
  Yt <- sweep(Y, 2, apply(Y, 2, min)) + 1
  Yt <- sweep(Yt, 2, colMeans(Yt), "/")       # mean-normalize each output
  for (o in 1:n){
    obj <- c(1, rep(0, n))
    con <- rbind(c(-x[o], x))                 # input
    dir <- "<="; rhs <- 0
    for (q in 1:ncol(Yt)){ con <- rbind(con, c(0, Yt[, q])); dir <- c(dir, ">="); rhs <- c(rhs, Yt[o, q]) }
    con <- rbind(con, c(0, rep(1, n))); dir <- c(dir, "="); rhs <- c(rhs, 1)
    s <- lp("min", obj, con, dir, rhs); th[o] <- if (s$status == 0) s$objval else NA
  }
  th
}

run <- function(col){
  d <- P[is.finite(get(col)) & is.finite(shoot_av_net) & is.finite(viol_av_net) & is.finite(spike)]
  rows <- list()
  for (y in 2012:2025){
    dy <- d[yr == y]; if (nrow(dy) < 20) next
    x <- pmax(dy[[col]], 1)
    Y <- as.matrix(dy[, .(shoot_av_net, viol_av_net)])
    t <- dy[, .(pct, yr, zone_era, spike)]; t[, eff := dea_in(x, Y)]; t[, inp := x]
    rows[[length(rows)+1]] <- t
  }
  A <- rbindlist(rows)[is.finite(eff)]
  A[, z := scale(spike)[,1]]; A[, li := scale(log(pmax(inp,1)))[,1]]
  m <- lm(eff ~ zone_era + z + li, data = A)
  ci <- confint(m)["zone_era", ]
  data.table(input = col, mean_eff = round(mean(A$eff), 3),
             zone_coef = round(coef(m)["zone_era"], 4),
             ci_lo = round(ci[1], 4), ci_hi = round(ci[2], 4), n = nrow(A))
}

R <- rbindlist(lapply(c("arr","arr_fel","arr_struct"), run))
fwrite(R, "data/robustness_R.csv")
cat("\n==== ZONE-ERA EFFICIENCY GAP BY INPUT PROXY (R) ====\n"); print(R)

if (file.exists("data/robustness_inputs.csv")){
  py <- fread("data/robustness_inputs.csv")[, .(input, py_coef = zone_coef, py_lo = ci_lo, py_hi = ci_hi)]
  cmp <- merge(py, R[, .(input, r_coef = zone_coef, r_lo = ci_lo, r_hi = ci_hi)], by = "input")
  cmp[, coef_absdiff := abs(py_coef - r_coef)]
  cat("\n==== PYTHON vs R ====\n"); print(cmp)
  cat("\nmax coef abs diff:", round(max(cmp$coef_absdiff), 4),
      " | signs and significance agree:",
      all(sign(cmp$py_coef) == sign(cmp$r_coef)), "\n")
}
