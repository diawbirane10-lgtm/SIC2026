# T01-D1 temporal challenger — verified result

- Workflow: `FLOWTRUST T01-D1 temporal challenger`
- Run: `31641782137`
- Commit: `6f8b4f6b7e949790cacf7e1db5314ed45fa08857`
- Artifact: `FLOWTRUST_T01D1_6f8b4f6b7e949790cacf7e1db5314ed45fa08857`
- Dataset: UCI Condition monitoring of hydraulic systems, ID 447, CC BY 4.0
- DOI: `10.24432/C5CW21`
- Task: multichannel short-horizon forecast on stable physical cycles
- Channels: PS1 pressure, PS2 pressure, EPS1 motor power
- Split: group-disjoint 70/15/15 by physical source cycle; model selection on validation only
- Context / horizon: 64 / 16
- Physical groups: 240 total, 36 closed-test groups

## Validation selection

Validation MAE versus persistence MAE `0.0687068924`:

- Ridge: `10.7106885910` MAE; relative error `154.8896x`
- Extra Trees: `1.6490930682` MAE; relative error `23.0019x`
- Random Forest: `1.6911373029` MAE; relative error `23.6138x`

Extra Trees was selected using validation only.

## Closed-test result

- Extra Trees MAE: `1.8153702378`
- Persistence MAE: `0.05998016521`
- Relative error versus persistence: `29.26617602x`
- Gate: closed-test normalized MAE <= 95% of persistence normalized MAE
- Gate passed: `false`

## Verdict

**NO-GO.** The challenger is dramatically worse than simple persistence on the closed test and must not be promoted. This remains an off-domain temporal competence benchmark on a physical hydraulic rig, not a cement-plant performance claim.

The artifact contains a large `temporal_head.joblib`; it is intentionally not committed to the repository. Only metrics and provenance are recorded here.
