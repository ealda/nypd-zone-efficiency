# validate_benchmarking.R -- confirm the hand-coded output-oriented VRS DEA
# (lpSolve / scipy) matches the field-standard Benchmarking package.
# Requires: Benchmarking, data.table  (Benchmarking depends on lpSolveAPI,
# quadprog, ucminf). data/dea2025_scores.csv is written by 12_validate_dea.py.
suppressMessages({library(Benchmarking); library(data.table)})

d <- fread("data/dea2025_scores.csv")     # pct, arr, y1, y2, eff(hand-coded, =1/phi)
X <- matrix(d$arr, ncol = 1)              # DEA is units-invariant
Y <- as.matrix(d[, .(y1, y2)])

E <- dea(X, Y, RTS = "vrs", ORIENTATION = "out")$eff   # Benchmarking, >= 1
bench <- 1 / E                            # put on the same (0,1] scale as ours
mine  <- d$eff

cat("output-oriented VRS, 2025 reciprocal outputs, n =", nrow(d), "\n")
cat("max |hand-coded - Benchmarking| =", signif(max(abs(mine - bench)), 3), "\n")
cat("correlation                     =", round(cor(mine, bench), 6), "\n")
cat("mean hand-coded =", round(mean(mine),4), " mean Benchmarking =", round(mean(bench),4), "\n")
cat("on frontier: hand-coded =", sum(mine > 0.999), " Benchmarking =", sum(bench > 0.999), "\n")
cat("\nPASS:", isTRUE(max(abs(mine - bench)) < 1e-4), "\n")
