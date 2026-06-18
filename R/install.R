# install.R -- packages needed for the R reconciliation.
# Run once:  Rscript R/install.R
pkgs <- c(
  "data.table",   # fast IO
  "Benchmarking", # DEA / directional distance (Bogetoft & Otto)
  "sandwich",     # clustered standard errors
  "lmtest",       # coeftest
  "truncreg",     # Simar-Wilson 2007 truncated regression
  "frontier"      # stochastic frontier (SFA) cross-check
)
# Optional but recommended for the gold-standard Simar-Wilson bootstrap:
optional <- c("rDEA", "FEAR")  # FEAR is Paul Wilson's own implementation

inst <- function(p) for (x in p)
  if (!requireNamespace(x, quietly = TRUE))
    tryCatch(install.packages(x, repos = "https://cloud.r-project.org"),
             error = function(e) message("could not install ", x, ": ", conditionMessage(e)))
inst(pkgs); inst(optional)
cat("done. core packages present:",
    all(sapply(pkgs, requireNamespace, quietly = TRUE)), "\n")
