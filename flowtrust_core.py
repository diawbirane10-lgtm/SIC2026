from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

CLASSES = ["conveyor_blockage","hopper_bridging","normal","spillage","unstable_feed","weighing_drift"]
FEATURE_NAMES = ["feeder_command_pct","belt_speed_command_mps","belt_speed_mps","speed_ratio","measured_mass_flow_tph","visual_flow_proxy_tph","flow_disagreement_ratio","visual_occupancy_pct","hopper_level_pct","hopper_level_rate_pct_min","mass_balance_residual_abs_pct","motor_current_a","motor_load_ratio","motor_torque_pct","vibration_mm_s","flow_cv_60s","motor_current_cv_60s","visual_accumulation_pct","visual_spillage_pct","speed_signal_quality","weigh_signal_quality","level_signal_quality","electrical_signal_quality","camera_quality","camera_connected"]

def _clip(x, lo=0.0, hi=100.0):
    return float(np.clip(x, lo, hi))

def make_synthetic_sample(label: str, rng: np.random.Generator) -> Dict[str, float]:
    feeder=rng.normal(70,7); cmd_speed=rng.normal(1.6,.08); speed=cmd_speed*rng.normal(.99,.015)
    flow=rng.normal(72,5); visual_flow=flow*rng.normal(1,.035); hopper=rng.normal(62,9); hopper_rate=rng.normal(0,.7)
    current=rng.normal(86,6); load=rng.normal(.70,.05); torque=rng.normal(69,5); vibration=rng.normal(2.2,.35)
    flow_cv=abs(rng.normal(.04,.012)); current_cv=abs(rng.normal(.035,.010)); accumulation=abs(rng.normal(4,2)); spillage=abs(rng.normal(1,.7))
    quality={k:_clip(rng.normal(.98,.015),0,1) for k in ["speed","weigh","level","electrical","camera"]}
    if label=="weighing_drift":
        flow*=rng.uniform(.55,.78); visual_flow=rng.normal(72,5); hopper_rate=rng.normal(-2.5,.7)
    elif label=="hopper_bridging":
        flow=rng.normal(28,6); visual_flow=rng.normal(30,7); hopper=rng.normal(88,5); hopper_rate=rng.normal(.2,.4); flow_cv=abs(rng.normal(.32,.06)); accumulation=rng.normal(48,8)
    elif label=="conveyor_blockage":
        speed=cmd_speed*rng.uniform(.18,.48); flow=rng.normal(18,6); visual_flow=rng.normal(15,6); current=rng.normal(126,8); load=rng.normal(1.03,.06); torque=rng.normal(108,7); vibration=rng.normal(6.5,.9); accumulation=rng.normal(78,7)
    elif label=="spillage":
        visual_flow=flow*rng.uniform(.62,.82); spillage=rng.normal(42,8); hopper_rate=rng.normal(-2.2,.8)
    elif label=="unstable_feed":
        flow_cv=abs(rng.normal(.30,.07)); current_cv=abs(rng.normal(.22,.05)); vibration=rng.normal(4.4,.7); flow*=rng.uniform(.72,1.08); visual_flow*=rng.uniform(.72,1.08)
    speed_ratio=speed/max(cmd_speed,1e-6); disagreement=abs(flow-visual_flow)/max(abs(visual_flow),1.0); residual=disagreement*100+abs(hopper_rate)*2.5+spillage*.18
    values=dict(feeder_command_pct=feeder,belt_speed_command_mps=cmd_speed,belt_speed_mps=speed,speed_ratio=speed_ratio,measured_mass_flow_tph=flow,visual_flow_proxy_tph=visual_flow,flow_disagreement_ratio=disagreement,visual_occupancy_pct=_clip(flow/1.05),hopper_level_pct=_clip(hopper),hopper_level_rate_pct_min=hopper_rate,mass_balance_residual_abs_pct=abs(residual),motor_current_a=max(current,0),motor_load_ratio=max(load,0),motor_torque_pct=max(torque,0),vibration_mm_s=max(vibration,0),flow_cv_60s=max(flow_cv,0),motor_current_cv_60s=max(current_cv,0),visual_accumulation_pct=_clip(accumulation),visual_spillage_pct=_clip(spillage),speed_signal_quality=quality["speed"],weigh_signal_quality=quality["weigh"],level_signal_quality=quality["level"],electrical_signal_quality=quality["electrical"],camera_quality=quality["camera"],camera_connected=1.0)
    return {k:float(values[k]) for k in FEATURE_NAMES}

def generate_dataset(samples_per_class:int=800,seed:int=2026)->Tuple[np.ndarray,np.ndarray]:
    rng=np.random.default_rng(seed); rows=[]; labels=[]
    for label in CLASSES:
        for _ in range(samples_per_class):
            s=make_synthetic_sample(label,rng); rows.append([s[n] for n in FEATURE_NAMES]); labels.append(label)
    return np.asarray(rows,dtype=np.float64),np.asarray(labels)

def observability_gate(x:Dict[str,float])->Tuple[bool,List[str]]:
    q=[x.get("speed_signal_quality",0),x.get("weigh_signal_quality",0),x.get("level_signal_quality",0),x.get("electrical_signal_quality",0)]
    camera_ok=x.get("camera_connected",0)>=.5 and x.get("camera_quality",0)>=.35; low=sum(v<.35 for v in q); evidence=[]
    if low>=2:evidence.append("Deux sources instrumentales ou plus sont de qualite insuffisante.")
    if not camera_ok:evidence.append("Vision indisponible ou qualite camera trop faible.")
    return (low<2 and (camera_ok or min(q)>=.70)),evidence

def physical_rules(x:Dict[str,float])->List[str]:
    e=[]
    if x.get("speed_ratio",1)<.55 and x.get("motor_load_ratio",0)>.9:e.append("Vitesse reelle faible sous forte charge: signature compatible avec un bourrage/entrainement contraint.")
    if x.get("hopper_level_pct",0)>80 and x.get("measured_mass_flow_tph",999)<40:e.append("Tremie chargee mais debit aval faible: pontage plausible.")
    if x.get("flow_disagreement_ratio",0)>.22:e.append("Desaccord significatif entre debit pese et proxy visuel.")
    if x.get("visual_spillage_pct",0)>25:e.append("La vision detecte une presence importante de matiere hors zone utile.")
    if x.get("flow_cv_60s",0)>.18 and x.get("motor_current_cv_60s",0)>.12:e.append("Debit et courant presentent une variabilite temporelle anormale.")
    return e

def operator_recommendation(label:str)->str:
    return {"normal":"Poursuivre la surveillance; aucune action automatique n'est autorisee.","weighing_drift":"Comparer le systeme de pesage aux indicateurs independants et planifier une verification/calibration.","hopper_bridging":"Verifier la tremie et l'alimentation amont en appliquant les procedures de securite du site.","conveyor_blockage":"Verifier le convoyeur, l'entrainement et l'accumulation avant toute remise en service.","spillage":"Inspecter la zone de transfert et confirmer l'origine de la perte de matiere.","unstable_feed":"Verifier la regularite de dosage, la qualite du combustible et les signaux de commande/charge.","unknown":"Ne pas conclure. Retablir l'observabilite ou demander une verification terrain."}[label]