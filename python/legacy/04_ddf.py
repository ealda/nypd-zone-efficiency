#!/usr/bin/env python3
# DROPPED. The directional-distance (DDF) model was removed from the analysis.
#
# Reason: the DDF is not units-invariant (its score depends on the chosen
# direction vector and on variable magnitudes), and the version here used the
# crime LEVEL as the bad output, so it did not net the rebound. The analysis
# instead measures efficiency with crime entered as a reciprocal (safety),
# output-oriented VRS, which is radial/units-invariant and nets the rebound
# cleanly (see 10_reciprocal.py).
#
# The spike-purged input proxy that this script used to produce is now computed
# inline in 10_reciprocal.py, so nothing depends on this file.
raise SystemExit("04_ddf.py is deprecated; the DDF model was dropped. See 10_reciprocal.py.")
