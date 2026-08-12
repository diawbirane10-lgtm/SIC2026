# FLOWTRUST V2 — T01-F1 verified result

- GitHub Actions run: `31641667209`
- Head SHA: `524ad320272bea2a68d14e08cadaf0b83e5d8d8f`
- Dataset: UCI Condition monitoring of hydraulic systems, 600 physical source cycles, controlled sensor corruptions
- Samples: 5,400 = 600 per class across 9 classes
- Split: group-disjoint 70/15/15 by physical source cycle; validation used for model selection only
- Selected validation model: HistGradientBoosting
- Closed-test samples: 810 from 90 unseen physical cycles
- Closed-test macro-F1: `0.8835646823`
- Closed-test balanced accuracy: `0.8827160494`
- Closed-test mean confidence: `0.9342093635`
- Gate: macro-F1 >= 0.90 AND balanced accuracy >= 0.90
- Gate result: **FAIL**
- Strong classes: dropout F1 `1.0000`, noise_burst `0.9945`, bias `0.9780`, drift `0.9773`, spike `0.9724`
- Weak classes: normal `0.6768`, clipping `0.6746`, timestamp_shift `0.8000`, stuck_at `0.8786`
- Evidence artifact: `FLOWTRUST_T01F1_524ad320272bea2a68d14e08cadaf0b83e5d8d8f`, artifact ID `9159120600`, ZIP SHA-256 `f4529dac242ce449f67ee684d5196bed9cf9bce2fb820b6811c2133e615d60a5`

This benchmark tests sensor-integrity classification on controlled corruptions of real physical UCI hydraulic cycles. It is not a cement-process diagnostic performance claim. The model is not promoted into FLOWTRUST V2 because the closed-test gate failed.
