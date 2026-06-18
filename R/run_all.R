# run_all.R -- R-native pipeline, end to end. Run from nypd_eff/:
#   Rscript R/run_all.R
# Requires: data.table, lpSolve, sandwich, lmtest, ggplot2, jsonlite
# (install once: install.packages(c("data.table","lpSolve","sandwich","lmtest","ggplot2")))
# Inputs are the aggregate CSVs in data/ produced by the Python pull
# (01_pull.py / arr_pull.py); the R code does the rest natively.
source("R/analysis.R")        # panel + netting + DEA reconciliation
source("R/reciprocal_did.R")  # reciprocal/output-oriented efficiency + diff-in-diff (primary)
source("R/montecarlo.R")      # RTM-propagation simulation
source("R/figures.R")         # ggplot2 figures 1-3 -> figs_R/
source("R/maps.R")            # precinct choropleths (needs jsonlite) -> figs_R/fig4_*
cat("\nAll R steps complete.\n")
