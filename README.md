# FLOWTRUST-AFR

**FLOWTRUST-AFR** is a read-only decision-support prototype for multimodal monitoring and diagnosis of **Alternative Fuels and Raw Materials (AFR)** feed chains in a cement-plant context.

It fuses automation/process variables, electrical signatures and visual indicators to detect incoherent flow conditions and suggest an operator check. **The application never sends a control command; the final decision remains with the operator.**

## What the public MVP demonstrates

- multimodal fusion of process, electrical and visual features;
- Random Forest classification for feed-chain dynamics;
- Random Forest visual anomaly detection;
- out-of-domain (OOD) abstention;
- robust temporal evidence: Hampel, Theil–Sen, Student-t, CUSUM, Welch spectrum and cross-correlation;
- physical-coherence rules for starvation, bridging/blockage, slippage and spillage;
- operator-facing evidence and recommendation panel;
- synthetic replay scenarios, explicitly separated from real SOCOCIM data.

## Safety / scope

This repository is a hackathon MVP, not a plant protection layer and not a closed-loop controller. The intended pilot path is **read-only OPC UA → shadow mode → operator advice**. No automatic actuator command is part of the MVP.

Public demonstration data are synthetic. Site-specific performance, savings or failure probabilities must not be claimed before calibration and validation on industrial data.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000/index.html`.

## API

- `GET /api/health`
- `GET /api/schema`
- `GET /api/demo?scenario=nominal|bridging|starvation|slippage|camera_degraded`
- `POST /api/diagnose`

## Model artifacts

The deployment artifacts are gzip-compressed joblib files and remain losslessly reloadable:

- `models/dynamics_public.joblib.gz`
- `models/vision_synthetic.joblib.gz`
- `models/fusion_ood_synthetic.joblib.gz`

`model_report.json` records the deterministic rebuild seed, validation metrics and exact artifact sizes.

## Pilot infrastructure target

The intended pilot is read-only and modest: one 24–27 inch operator display, an industrial PC or Jetson-class edge computer, a read-only OPC UA connection, and one fixed PoE industrial camera (IP67/IK10, WDR, 1080p or 4 MP) overlooking the selected AFR transfer point. Camera placement and final sensor list must be confirmed on site after a field survey.

## Provenance

The project direction uses public references/datasets discussed during development, including UCI Hydraulic Systems, an openly licensed cement-furnace dataset and an iron-ore conveyor dataset. Public datasets are validation references; they are not presented as SOCOCIM measurements.

## License

Code: MIT. Dataset licenses remain those of their respective sources.
