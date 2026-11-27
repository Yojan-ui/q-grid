"""Ablation study: which design change removes how much of the gap to the central optimum.

Factors (each on/off, 16 combinations, identical days/data/objective):
  A  horizon 1 h (v1 cost-to-go as terminal value)  ->  24 h rolling horizon
  B  discretised kW (full-power battery / diesel / cable levels)  ->  continuous LP dispatch
  C  binary ADMM (each building solves its whole mixed-integer problem inside every negotiation round)
       ->  consensus ADMM on the convex LP with binaries fixed locally
  D  perfect forecast  ->  realistic gradient-boosting forecasts of solar and load
Objective everywhere = model.settle() objective (energy + diesel fuel + value of lost load + terminal value), the
same as the central MILP B4, so gap-to-optimum is exact. Master problems are solved exactly (HiGHS branch and bound).
"""
