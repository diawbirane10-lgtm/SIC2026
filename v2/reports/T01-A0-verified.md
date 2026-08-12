# T01-A0 scene-gate bootstrap — verified result

- Workflow: `FLOWTRUST T01-A CPU bootstrap`
- Run: `31641959644`
- Commit: `4998e809033fcbcfa01a5a5600c33ca11fa89bca`
- Artifact: `FLOWTRUST_T01A0_CPU_4998e809033fcbcfa01a5a5600c33ca11fa89bca`
- Model: `facebook/dinov2-large`, frozen backbone, 304,368,640 parameters
- Head: logistic regression on frozen embeddings
- Calibration: sigmoid on group-disjoint validation
- Device/tier: CPU exploratory bootstrap

## Closed-test evidence

The artifact contains 111 train images, 19 validation images and 12 closed-test images. The closed test contains **12 conveyor-applicable positives and zero non-industrial negatives**.

Reported metrics from `metrics.json`:

- macro-F1: `1.0`
- ECE: `0.07858528647215629`
- false conveyor accept rate: `null`
- statistical gate passed: `false`
- integration gate passed: `false`

The confusion matrix is `[[12, 0], [0, 0]]`, so the apparent perfect F1 only proves recall/classification on the positive-only closed test. It does **not** evaluate the required false-conveyor-accept gate because there are no negative examples in that test fold.

## Gate verdict

**NO-GO / statistically unevaluable for the required scene gate.** The configured gate is `false_conveyor_accept_rate <= 0.02`, and the artifact explicitly records `false_conveyor_accept_rate = null` and `statistical_gate_passed = false`.

The artifact also explicitly blocks integration because this is an exploratory CPU bootstrap and requires the unchanged closed-test protocol to be rerun on GPU before HMI integration. No production or main-branch promotion is justified by this run.
