# FLOWTRUST V2 — Training 01 bootstrap results

Date: 2026-08-12

This report records only metrics proven by completed GitHub Actions runs. It does not claim production readiness or cement-plant performance.

## T01-F0 — MOMENT sensor-integrity bootstrap

GitHub Actions run: `31636473365`
Artifact: `FLOWTRUST_T01F0_CPU_3317a3e61a0116aac3bf46b7c9d7a4068835dd57` (artifact ID `9157322366`)
Dataset source: UCI Condition Monitoring of Hydraulic Systems, with controlled sensor corruptions injected on real physical cycles.
Split: group-disjoint 70/15/15 by physical source cycle.
Foundation: `AutonLab/MOMENT-1-large`.
Measured foundation encoder parameters: `341,231,104`.
Training mode: calibrated linear probe on frozen foundation embeddings.
Closed test: 54 samples across 9 balanced fault classes.

- MOMENT macro-F1: `0.4138996481`
- MOMENT balanced accuracy: `0.4259259259`
- Statistical baseline macro-F1: `0.6037037037`
- Statistical baseline balanced accuracy: `0.6111111111`
- MOMENT minus baseline macro-F1: `-0.1898040556`
- Closed-test mean confidence: `0.3263577262`
- Bootstrap gate: MOMENT macro-F1 and balanced accuracy must both be at least the statistical baseline.
- **Gate result: FAIL**

Notable per-class F1 on the six-sample-per-class closed test: spike `1.0000`, noise burst `0.9091`, bias `0.5714`, drift `0.3636`, normal `0.3158`, clipping `0.2500`, stuck-at `0.1818`, dropout `0.1333`, timestamp shift `0.0000`.

Interpretation: the frozen MOMENT embedding plus linear probe does not justify replacing the engineered statistical detector. The next candidate should target the weak classes explicitly and must be re-evaluated on a larger group-disjoint closed test before integration.

## T01-D0 — Chronos-2 temporal bootstrap

GitHub Actions run: `31636625165`
Artifact: `FLOWTRUST_T01D0_CPU_024809465f36bbb8f3355356bfc698b3a094e8a9` (artifact ID `9157227799`)
Dataset source: UCI Condition Monitoring of Hydraulic Systems, DOI `10.24432/C5CW21`.
Channels: PS1 pressure, PS2 pressure, EPS1 motor power.
Mode: zero-shot multivariate CPU.
Measured model parameters: `119,477,664`.
Context length: 256; prediction length: 32; stable physical cycles evaluated: 12.

- Chronos normalized MAE mean: `0.2335146012`
- Persistence normalized MAE mean: `0.2320911434`
- Relative error vs persistence: `+0.0061331845` (~0.61% worse)
- Mean q10–q90 coverage: `0.7421875`
- Bootstrap gate: Chronos normalized MAE must be <= 95% of persistence normalized MAE.
- **Gate result: FAIL**

Interpretation: Chronos-2 zero-shot does not clear the required 5% improvement over persistence on this bootstrap. Several cycles improve, but aggregate performance is slightly worse because of difficult cycles/outliers. LoRA adaptation or a different temporal model must earn its place against the persistence baseline rather than being integrated by default.

## T01-A — scene gate

Run `31634655983` remains in progress at the time of this report. No metric or gate result is recorded here until the workflow completes and produces evidence.
