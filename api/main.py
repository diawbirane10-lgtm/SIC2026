from pathlib import Path
from typing import Dict
import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from flowtrust_core import FEATURE_NAMES, observability_gate, physical_rules, operator_recommendation

ROOT=Path(__file__).resolve().parents[1]
MODELS=ROOT/'models'
app=FastAPI(title='FLOWTRUST-AFR',version='0.2.0',docs_url=None,redoc_url=None,openapi_url=None)

class Payload(BaseModel):
    features: Dict[str,float]

_cache={}
def load_models():
    if not _cache:
        _cache['rf']=joblib.load(MODELS/'afr_rf_diagnostic_v1.joblib')
        _cache['ood']=joblib.load(MODELS/'afr_isolation_known_domain_v1.joblib')
    return _cache

@app.get('/api/health')
def health():
    return {'status':'ok','version':'0.2.0','mode':'advisory_read_only','automatic_control_allowed':False,'model_id':'afr-rf-diagnostic-v1','training_strategy':'synthetic_reproducible_public_snapshot'}

@app.post('/api/diagnose')
def diagnose(payload:Payload):
    x=payload.features
    ok,gate_evidence=observability_gate(x)
    vector=np.asarray([[float(x.get(f,np.nan)) for f in FEATURE_NAMES]],dtype=float)
    missing=float(np.isnan(vector).mean())
    if missing>0.20 or not ok:
        return {'diagnostic':'unknown','confidence':0.0,'abstained':True,'evidence':gate_evidence+[f'Missing fraction={missing:.1%}'],'recommendation':operator_recommendation('unknown'),'automatic_control_allowed':False}
    if np.isnan(vector).any():
        vector=np.nan_to_num(vector,nan=0.0)
    models=load_models(); rf=models['rf']['model']; iso=models['ood']['model']
    if iso.predict(vector)[0] < 0:
        return {'diagnostic':'unknown','confidence':0.0,'abstained':True,'evidence':['Point hors enveloppe connue selon IsolationForest.'],'recommendation':operator_recommendation('unknown'),'automatic_control_allowed':False}
    proba=rf.predict_proba(vector)[0]; idx=int(np.argmax(proba)); label=str(rf.classes_[idx]); confidence=float(proba[idx]); evidence=physical_rules(x)
    if confidence<0.58:
        return {'diagnostic':'unknown','confidence':confidence,'abstained':True,'evidence':evidence+['Confiance modele insuffisante.'],'recommendation':operator_recommendation('unknown'),'automatic_control_allowed':False}
    return {'diagnostic':label,'confidence':confidence,'abstained':False,'evidence':evidence,'recommendation':operator_recommendation(label),'automatic_control_allowed':False}