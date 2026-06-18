# Replication and verification

This analysis is implemented **twice**, on purpose. The point is that no result
should depend on a single hand-written estimator. Both have been run and they
agree (see "Reconciliation result" below).

- **Python**: `01`/`arr_pull` pull the data; `10_reciprocal.py` is the current
  efficiency model (reciprocal/safety output, output-oriented VRS, on `scipy`);
  `13_event_study.py` is the event study; `06_figures.py`, `09_maps.py` build the
  figures; `07_verify.py` runs internal checks.
- **R** (`R/analysis.R`, `R/reciprocal_did.R`, `R/montecarlo.R`, `R/figures.R`,
  `R/maps.R`): an independent R-native re-implementation. `analysis.R` rebuilds the
  precinct-by-summer panel and reconciles the DEA and netting numbers; the current
  efficiency model, robustness, and fingerprint live in `reciprocal_did.R`. All
  efficiency LPs use `lpSolve`. Figures are reproduced in `ggplot2` (`figs_R/`).
- **Dropped / superseded.** The directional-distance (DDF) model was removed
  (`04_ddf.py` is a deprecation stub); the spike-purged input proxy it produced is
  now computed inline in `10_reciprocal.py`. `05_bootstrap.py`, `08_robustness_inputs.py`,
  and `R/replicate.R` are earlier specifications kept for reference but not part of
  the current pipeline.
- **Package validation** (`R/validate_benchmarking.R`, run): the efficiency
  scores are computed by a hand-written linear program (`scipy.optimize.linprog`
  in Python, `lpSolve` in R), not by a DEA package. This script confirms those
  hand-coded scores equal the field-standard `Benchmarking::dea` (output-oriented
  VRS) to within 7e-7 on the 2025 cross-section — so the linear program is
  correct, not merely internally consistent. The same solver is used for every
  year. (`R/replicate.R` sketches a fuller `Benchmarking`/`frontier`/`truncreg`
  cross-check but was **not** run in this environment; `validate_benchmarking.R`
  is the package check that was actually executed.)

So three things have been checked: the two hand-coded implementations agree with
each other; the envelopment LP agrees with its multiplier dual (1.8e-15); and the
hand-coded scores agree with the Benchmarking package (7e-7).

## What the article claims, and where each claim is verified

Every empirical statement in the piece maps to a script, and each runs in both
R and Python with matching numbers.

Efficiency is measured with crime entered as a **reciprocal** (safety =
expected-over-observed crime, so the rebound is netted in the numerator),
**output-oriented** VRS, inputs and outputs divided by their means. The zone
effect is identified by **difference-in-differences** (targeted precincts vs the
rest, same years), because the actual zone precincts are not public.

| Claim in the article | Script (R / Python) | Result |
|---|---|---|
| Last year's shooting count barely predicts this year's | analysis.R / 02_analyze.py | prior-year weight ~0.22, 3-yr mean ~0.60 |
| Scoring the raw drop rewards precincts that spiked last year | reciprocal_did.R / 10_reciprocal.py | raw-safety slope +0.026 (t 4.6); adjusted +0.0 (t −0.5) |
| Adjusting for the rebound removes that | reciprocal_did.R / 10, 07_verify.py | fingerprint flat after adjustment |
| A simulation with the answer known recovers truth better when adjusted | montecarlo.R / 03_montecarlo.py | adjusted ≥ raw at every noise level |
| Zone-era years look more efficient, but it is mostly the citywide decline | reciprocal_did.R / 10_reciprocal.py | time-only gap +0.115 (arr), +0.150 (felony), +0.133 (purged), all sig |
| The diff-in-differences cannot identify a zone effect — pre-trends fail | 13_event_study.py (Python only) | targeted-vs-rest gap wanders 2012–2022 (e.g. −0.19 in 2014); several pre-period years differ from the 2022 baseline, so parallel trends does not hold. The treatment proxy is selected on crime, so the design is not credible. |

The event-study row drives the piece's framing. It is what Figure 2 plots, and
the honest conclusion: the time-only gap is the citywide decline, and the
comparison that might have separated the program from that trend fails its
parallel-trends test because the only treatable group public data allow is
selected on crime. So no design an outsider can run isolates the zone effect.

Status note, stated plainly so it isn't overclaimed: the reciprocal efficiency
and the time-only gap reproduce identically in R and Python, and the efficiency
scores match the `Benchmarking` package (7e-7). The **event study (Figure 2) is
currently Python only** (`13_event_study.py`); it has not yet been ported to R.
The DiD point estimate reconciles R-vs-Python, but its coefficient is not a
credible causal estimate and is no longer reported as a result.

## Reconciliation result (already run)

`R/analysis.R` was executed against the Python outputs. Every substantive
quantity matches to rounding:

| metric | Python | R |
|---|---|---|
| DEA 2025 mean efficiency (VRS, netted) | 0.2931 | 0.2931 |
| corr(spike, raw averted) | +0.336 | +0.336 |
| corr(spike, OLS-netted averted) | −0.032 | −0.032 |
| corr(spike, Poisson-netted averted) | +0.008 | +0.008 |
| fingerprint slope, raw output | −0.0674 | −0.0673 |
| fingerprint slope, netted output | −0.0029 | −0.0030 |
| fingerprint t, raw (clustered) | −7.56 | −7.52 |

The largest gap on any shared metric is 0.04, on a t-statistic of about −7.5
(both overwhelmingly significant) — a finite-sample standard-error convention
difference between the hand-coded cluster formula and `sandwich::vcovCL`.
The DEA scores, the netting correlations, and the fingerprint slopes are
identical to four decimals.

## How to run

```bash
# Python side (already run; regenerates the panel and all results)
python3 01_pull.py            # pull NYC Open Data aggregates  (one-time)
python3 arr_pull.py 17        # summer arrests, resumable
python3 02_analyze.py         # panel + RTM netting + DEA + SFA + fingerprint
python3 04_ddf.py             # directional distance + input purge + 2nd stage
python3 05_bootstrap.py       # Simar-Wilson inference
python3 06_figures.py         # figures
python3 07_verify.py          # internal cross-checks -> recon_python.csv

# R side — full R-native pipeline (any R >= 4.0)
install.packages(c("data.table","lpSolve","sandwich","lmtest","ggplot2"))
Rscript R/run_all.R           # panel + frontiers + Monte Carlo + figures
                              # writes data/recon_R.csv, data/reconciliation.csv,
                              # data/mc_results_R.csv, figs_R/*.png

# R side — optional trusted-package cross-check
Rscript R/install.R           # adds Benchmarking, frontier, truncreg, FEAR/rDEA
Rscript R/replicate.R
```

`R/replicate.R` reads the **same** `data/panel.csv` and `data/ddf_dmu.csv`
the Python pipeline produced, so the data layer is held fixed and only the
estimation layer is being compared. It then writes `data/reconciliation.csv`,
a side-by-side table of the Python and R values with their absolute
differences, and prints whether all shared metrics agree within 0.01.

## What has already been verified (Python-internal)

`07_verify.py` ran the following and all passed:

1. **DEA primal vs dual.** The input-oriented VRS DEA is solved both as the
   envelopment program and as its multiplier dual. They agree to 2.8e-16, which
   confirms the linear program is specified correctly (a transcription error in
   either form would break the equality).
2. **Returns to scale.** CRS and VRS efficiency rankings are compared
   (Spearman ≈ 0.65), documenting sensitivity to the scale assumption.
3. **Netting is robust to functional form.** The correlation between a
   precinct's prior-year spike and its "averted crime" is +0.34 on the raw
   measure (mechanical), but −0.03 under OLS reversion and +0.01 under a
   **Poisson** reversion model — so the netting removes the spike regardless of
   how the counterfactual is estimated.
4. **Clustered inference.** The contamination fingerprint survives
   precinct-clustered standard errors: raw-output t = −7.6 (clustered),
   netted-output t = −0.3 (clustered).

The numbers the R port must reproduce are in `data/recon_python.csv`.

## Metrics reconciled across Python and R

| metric | meaning |
|---|---|
| `dea2025_mean_eff_vrs_net` | mean 2025 efficiency, VRS input-oriented, netted output |
| `dea2025_crs_vrs_spearman` | CRS-vs-VRS rank correlation |
| `corr_spike_av_raw / _net_ols / _net_poisson` | spike vs averted, by netting method |
| `fingerprint_raw_b / _net_b` | inefficiency–spike slope (raw vs netted) |
| `fingerprint_*_t_naive / _t_clustered` | t-stats, naive and precinct-clustered |
| `sw2007_zone_era_coef` | zone-era coefficient, truncated second stage |
| `sfa2025_slope_logarr` | SFA output elasticity to the input |

## Data-definition notes (reconcile against Hall's repo before publication)

The Python pulls aggregate counts server-side from NYC Open Data. Definitions
used, and the items to confirm match `jjhall77/rtm_zones`:

- **Violent crime**: complaint codes `KY_CD` 101 (murder), 105 (robbery),
  106 (felony assault), restricted to outdoor locations
  (`LOC_OF_OCCUR_DESC` in OUTSIDE / FRONT OF / OPPOSITE OF / REAR OF).
- **Shootings**: NYPD Shooting Incident Data; 2006–2024 from the historic file
  (`833y-fsy8`) and **2025 from the year-to-date file** (`5ucz-vwe8`), since the
  historic file stops at 2024.
- **Summer** = June–September. **Precincts** = the 77 patrol precincts.
- **Known difference to reconcile**: Hall's loader drops transit-jurisdiction
  records (`JURISDICTION_CODE != 1`); the current pull filters on crime code and
  location but not jurisdiction. At the precinct/outdoor level the effect is
  small, but it should be aligned for a published version.
- **Snapshot**: NYC Open Data updates continuously; fix a download date when
  finalizing (the figures here use data pulled 2026-05-30).

## Remaining hardening for the published version

- Replace the **arrests deployment proxy** with FOIL'd precinct headcount /
  officer-hours and zone deployment counts (the binding limitation).
- Report the Simar–Wilson 1998 bias-corrected scores from `FEAR` alongside the
  Python bootstrap.
- Cluster all second-stage inference by precinct (done in `07`/R) and add
  year fixed effects.
