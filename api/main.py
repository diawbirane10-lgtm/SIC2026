from typing import Dict
import math
from fastapi import FastAPI
from pydantic import BaseModel

VERSION = '0.3.1'
FUSION_VERSION = 't02-edge-v1'
FEATURE_NAMES=['feeder_command_pct','belt_speed_command_mps','belt_speed_mps','speed_ratio','measured_mass_flow_tph','visual_flow_proxy_tph','flow_disagreement_ratio','visual_occupancy_pct','hopper_level_pct','hopper_level_rate_pct_min','mass_balance_residual_abs_pct','motor_current_a','motor_load_ratio','motor_torque_pct','vibration_mm_s','flow_cv_60s','motor_current_cv_60s','visual_accumulation_pct','visual_spillage_pct','speed_signal_quality','weigh_signal_quality','level_signal_quality','electrical_signal_quality','camera_quality','camera_connected']
CLASSES=['conveyor_blockage','hopper_bridging','normal','spillage','unstable_feed','weighing_drift']
MEAN=[70.0477000608,1.5998520831,1.410256286,0.881447898,50.3980066623,51.0370166824,0.3238588758,47.9981015832,66.2763437492,-0.7637033213,36.6211169879,92.7044645488,0.7558100057,75.5388098344,3.2815903062,0.1299214479,0.0658168444,23.5873990387,7.9264225089,0.9792436452,0.9792624149,0.9791760978,0.9790392839,0.9792980636,1.0]
SCALE=[7.0786957877,0.0800328321,0.4011149547,0.2465617688,22.2066132038,22.5989293893,0.8495121483,21.1491554322,12.9333902657,1.3273152476,85.2241333938,16.3197849165,0.1339057761,15.5739774142,1.7507149772,0.1328829303,0.0714088356,29.3944512899,15.7283180112,0.0138210015,0.0138980807,0.0138173351,0.0138527404,0.0138920358,1.0]
COEF=[[-0.0292661415,0.0377864276,-0.7301167986,-0.7500210718,-0.3818706368,-0.4768610746,0.4142870124,-0.3818706368,-0.1751812209,0.1392665343,0.4082720945,0.6648515739,0.6789362289,0.6880893014,0.6501966371,-0.2434546405,-0.0486316126,0.5529386764,-0.0365729901,0.0011424077,0.0030415877,0.0081842384,0.0339571771,0.0058371561,0.0],[0.0027310285,-0.1001471546,0.2764099379,0.3009685745,-1.006046102,-0.9618968856,0.0593527431,-1.006046102,1.2563020682,0.5352165324,0.0356135135,-0.2452310163,-0.2823583139,-0.2637879361,-0.5129371983,1.1994985929,-0.4097490745,0.9734529646,-0.1439531079,-0.0415432607,0.0777978482,0.0683629554,-0.005749756,-0.0417470945,0.0],[-0.0271750027,0.261674296,-0.098253043,-0.1570344861,2.094775502,0.062062834,-1.2741042895,2.094775502,-0.2027130374,1.6904716261,-1.3996833293,-0.1480973106,-0.1622839911,0.0625980322,-0.6638846984,-1.3862577008,-1.2319289445,0.0685430311,-1.6082990358,0.0623508674,-0.0677634385,-0.0390154812,0.0127679537,-0.134137014,0.0],[0.116402804,-0.0043182993,0.1038034227,0.105630021,0.8994350093,-0.9836136144,0.4246666727,0.8994350093,-0.1243394816,-0.8130688591,0.5555507015,-0.2102414487,-0.1200060438,-0.1290672973,-0.2097261936,-0.2286240492,-0.1505654161,-0.1730961114,3.1453883985,-0.1500427971,-0.1664717483,0.0024711367,0.1206859352,0.0650411138,0.0],[-0.0825319278,0.0023485418,0.2061056625,0.2093991931,0.521695696,0.3675293616,-0.1043670822,0.521695696,-0.3638745586,0.8400560613,-0.1214108265,-0.1745528851,-0.0477066338,-0.1344897585,1.2514228634,1.7771177144,2.4659787434,-0.5219817167,-0.2105905079,0.2167851509,0.0233786908,-0.1474143737,-0.1323898742,0.0805995272,0.0],[0.0198392393,-0.1973438114,0.2420508184,0.2910577692,-2.1279894685,1.9927793791,0.4801649436,-2.1279894685,-0.3901937698,-2.391941895,0.5216578464,0.1132710868,-0.0665812463,-0.2233423417,-0.5150714103,-1.1182799168,-0.6251036956,-0.8998568441,-1.1459727567,-0.0886923681,0.1300170602,0.1074115243,-0.0292714358,0.0244063114,0.0]]
INTERCEPT=[-0.2530001419,0.2243300318,-0.7923094871,-0.0090450843,0.2955122952,0.5345123862]

app=FastAPI(title='FLOWTRUST-AFR',version=VERSION,docs_url=None,redoc_url=None,openapi_url=None)
class Payload(BaseModel): features: Dict[str,float]

def clip(x): return max(0.0,min(1.0,float(x)))
def hi(v,t,w):
    z=max(-60.0,min(60.0,(float(v)-t)/max(w,1e-9))); return 1.0/(1.0+math.exp(-z))
def lo(v,t,w): return 1-hi(v,t,w)
def softmax(logits):
    m=max(logits); vals=[math.exp(x-m) for x in logits]; s=sum(vals) or 1.0; return [x/s for x in vals]
def prior(x):
    vals=[float(x.get(k,0.0)) for k in FEATURE_NAMES]
    z=[(vals[i]-MEAN[i])/(SCALE[i] or 1.0) for i in range(len(vals))]
    logits=[INTERCEPT[c]+sum(COEF[c][i]*z[i] for i in range(len(z))) for c in range(len(CLASSES))]
    p=softmax(logits); return {CLASSES[i]:p[i] for i in range(len(CLASSES))},z
def reliabilities(x):
    return {'process':(clip(x.get('weigh_signal_quality',0))+clip(x.get('level_signal_quality',0)))/2,'electromechanical':(clip(x.get('speed_signal_quality',0))+clip(x.get('electrical_signal_quality',0)))/2,'vision':clip(x.get('camera_quality',0)) if float(x.get('camera_connected',0))>=.5 else 0.0}
def blank(): return {k:.02 for k in CLASSES}
def modality_scores(x):
    flow=float(x.get('measured_mass_flow_tph',0)); visual=float(x.get('visual_flow_proxy_tph',0)); hopper=float(x.get('hopper_level_pct',0)); hr=float(x.get('hopper_level_rate_pct_min',0)); residual=float(x.get('mass_balance_residual_abs_pct',0)); fcv=float(x.get('flow_cv_60s',0)); sr=float(x.get('speed_ratio',1)); current=float(x.get('motor_current_a',0)); load=float(x.get('motor_load_ratio',0)); torque=float(x.get('motor_torque_pct',0)); vib=float(x.get('vibration_mm_s',0)); ccv=float(x.get('motor_current_cv_60s',0)); acc=float(x.get('visual_accumulation_pct',0)); spill=float(x.get('visual_spillage_pct',0)); dis=float(x.get('flow_disagreement_ratio',0));p=blank();e=blank();v=blank()
    p['normal']=.55*lo(fcv,.14,.035)+.25*lo(residual,12,4)+.20*lo(hopper,82,4);p['hopper_bridging']=.50*hi(hopper,80,4)+.35*lo(flow,42,7)+.15*lo(abs(hr),1,.4);p['unstable_feed']=.72*hi(fcv,.17,.04)+.18*hi(abs(hr),1.8,.6)+.10*hi(residual,15,5);p['conveyor_blockage']=.50*lo(flow,35,7)+.25*hi(hopper,72,6)+.25*hi(residual,15,5);p['weighing_drift']=.45*hi(residual,18,5)+.30*lo(flow,52,8)+.25*hi(abs(hr),1.6,.5);p['spillage']=.35*hi(residual,18,5)+.25*hi(abs(hr),1.6,.5)+.10
    e['normal']=.40*hi(sr,.80,.06)+.25*lo(load,.88,.05)+.20*lo(ccv,.10,.03)+.15*lo(vib,3.6,.6);e['conveyor_blockage']=.30*lo(sr,.62,.07)+.25*hi(load,.90,.05)+.15*hi(current,105,8)+.15*hi(torque,92,6)+.15*hi(vib,4.2,.7);e['unstable_feed']=.45*hi(ccv,.12,.03)+.30*hi(vib,3.6,.6)+.15*hi(load,.82,.07)+.10*hi(current,98,8);e['hopper_bridging']=.20*lo(load,.82,.08)+.15*hi(sr,.82,.06);e['weighing_drift']=.25*hi(sr,.82,.06)+.20*lo(ccv,.10,.03);e['spillage']=.20*hi(sr,.82,.06)+.10*lo(ccv,.10,.03)
    v['normal']=.35*hi(visual,48,8)+.30*lo(acc,20,6)+.30*lo(spill,10,4);v['spillage']=.70*hi(spill,22,6)+.20*hi(dis,.16,.05)+.10*lo(acc,50,10);v['conveyor_blockage']=.45*hi(acc,58,8)+.35*lo(visual,36,7)+.20*hi(dis,.12,.05);v['hopper_bridging']=.40*hi(acc,30,8)+.35*lo(visual,42,8)+.15*lo(spill,12,4);v['weighing_drift']=.35*hi(visual,52,8)+.50*hi(dis,.18,.05)+.10*lo(spill,12,4);v['unstable_feed']=.15*hi(dis,.10,.04)+.10
    for s in (p,e,v):
        for k in CLASSES:s[k]=clip(s[k])
    return {'process':p,'electromechanical':e,'vision':v}
def fuse(x,rfp):
    r=reliabilities(x);sc=modality_scores(x);active=[n for n in r if r[n]>=.35];details={}
    for n in sc:
        vote=max(sc[n],key=sc[n].get);details[n]={'reliability':r[n],'active':n in active,'vote':vote,'strength':float(sc[n][vote])}
    if len(active)<2:return {'version':FUSION_VERSION,'diagnostic':'unknown','confidence':0.0,'abstained':True,'abstention_reasons':['Moins de deux modalités indépendantes sont suffisamment fiables.'],'active_modalities':active,'modalities':details,'consensus':0.0,'margin':0.0}
    tr=sum(r[n] for n in active);fs={k:.78*sum(r[n]*sc[n][k] for n in active)/tr+.22*rfp.get(k,0.0) for k in CLASSES};tot=sum(fs.values()) or 1.0;fs={k:v/tot for k,v in fs.items()};ordered=sorted(CLASSES,key=lambda k:fs[k],reverse=True);cand,runner=ordered[0],ordered[1];margin=fs[cand]-fs[runner];support=[n for n in active if details[n]['vote']==cand and details[n]['strength']>=.30];cons=sum(r[n] for n in support)/tr;strong=[details[n]['vote'] for n in active if details[n]['strength']>=.45];reasons=[]
    if fs[cand]<.28:reasons.append('Support fusionné insuffisant.')
    prior_strength=rfp.get(cand,0.0)
    if margin<.04 and not (prior_strength>.65 and cons>.55):reasons.append('Marge trop faible entre les deux hypothèses principales.')
    if cand!='normal' and cons<.30 and not (prior_strength>.92 and any(details[n]['vote']==cand and details[n]['strength']>.75 for n in active)):reasons.append("Le défaut n'est pas soutenu par assez de modalités indépendantes.")
    if len(strong)>=3 and len(set(strong))==len(strong) and prior_strength<.85:reasons.append('Contradiction forte entre les modalités actives.')
    abst=bool(reasons);confidence=0.0 if abst else min(.96,clip(.55*min(1.0,fs[cand]*2.0)+.45*cons));return {'version':FUSION_VERSION,'diagnostic':'unknown' if abst else cand,'candidate':cand,'confidence':confidence,'abstained':abst,'abstention_reasons':reasons,'active_modalities':active,'modalities':details,'fused_scores':fs,'consensus':cons,'margin':margin}
def physical_rules(x):
    e=[]
    if float(x.get('speed_ratio',1))<.55 and float(x.get('motor_load_ratio',0))>.9:e.append('Vitesse réelle faible sous forte charge : signature compatible avec un bourrage/entraînement contraint.')
    if float(x.get('hopper_level_pct',0))>80 and float(x.get('measured_mass_flow_tph',999))<40:e.append('Trémie chargée mais débit aval faible : pontage plausible.')
    if float(x.get('flow_disagreement_ratio',0))>.22:e.append('Désaccord significatif entre débit pesé et proxy visuel.')
    if float(x.get('visual_spillage_pct',0))>25:e.append('La vision indique une présence importante de matière hors zone utile.')
    if float(x.get('flow_cv_60s',0))>.18 and float(x.get('motor_current_cv_60s',0))>.12:e.append('Débit et courant présentent une variabilité temporelle anormale.')
    return e
def recommendation(label):
    return {'normal':'Poursuivre la surveillance ; aucune action automatique n’est autorisée.','weighing_drift':'Comparer le système de pesage aux indicateurs indépendants et planifier une vérification/calibration.','hopper_bridging':'Vérifier la trémie et l’alimentation amont selon les procédures de sécurité du site.','conveyor_blockage':'Vérifier le convoyeur, l’entraînement et la zone d’accumulation avant toute remise en service.','spillage':'Inspecter la zone de transfert et confirmer l’origine de la perte de matière.','unstable_feed':'Vérifier la régularité du dosage et les signaux de commande/charge.','unknown':'Ne pas conclure. Rétablir l’observabilité ou demander une vérification terrain.'}[label]
def unknown(evidence,fusion=None):return {'diagnostic':'unknown','confidence':0.0,'abstained':True,'evidence':evidence,'recommendation':recommendation('unknown'),'fusion':fusion,'fusion_version':FUSION_VERSION,'automatic_control_allowed':False}
@app.get('/api/health')
def health():return {'status':'ok','version':VERSION,'mode':'advisory_read_only','automatic_control_allowed':False,'model_id':'flowtrust-linear-prior-v1','fusion_version':FUSION_VERSION,'model_origin':'distilled_linear_prior_from_sil_20260812','training_strategy':'offline_trained_linear_prior_plus_t02_fusion'}
@app.post('/api/diagnose')
def diagnose(payload:Payload):
    x=payload.features
    if any(k not in x for k in FEATURE_NAMES):return unknown(['Caractéristiques requises manquantes dans la requête.'])
    r=reliabilities(x);active=sum(v>=.35 for v in r.values())
    if active<2:return unknown(['Observabilité insuffisante : moins de deux modalités fiables.'])
    if float(x.get('weigh_signal_quality',1))<.20:return unknown(['Capteur de pesage suspect ou bloqué : source exclue et vérification requise.'])
    if float(x.get('speed_signal_quality',1))<.35 and float(x.get('weigh_signal_quality',1))<.35 and float(x.get('electrical_signal_quality',1))<.35:return unknown(['Sources principales désynchronisées ou de qualité insuffisante.'])
    prior_x=dict(x)
    if float(x.get('camera_connected',0))<.5:
        prior_x['visual_flow_proxy_tph']=float(x.get('measured_mass_flow_tph',0));prior_x['flow_disagreement_ratio']=0.0;prior_x['visual_occupancy_pct']=max(0.0,min(100.0,float(x.get('measured_mass_flow_tph',0))/1.05));prior_x['visual_accumulation_pct']=0.0;prior_x['visual_spillage_pct']=0.0;prior_x['camera_quality']=.98;prior_x['camera_connected']=1.0
    rfp,z=prior(prior_x)
    core_idx=[0,1,2,3,4,8,9,11,12,13,14,15,16]
    if max(abs(z[i]) for i in core_idx)>12:return unknown(['Point très éloigné de l’enveloppe SIL connue : abstention OOD.'])
    fu=fuse(x,rfp);ev=physical_rules(x)
    if fu['abstained']:ev.extend(fu['abstention_reasons']);return unknown(ev,fu)
    label=fu['diagnostic']
    for n,d in fu['modalities'].items():
        if d['active']:ev.append(f"{n}: vote={d['vote']}, support={d['strength']:.2f}, fiabilité={d['reliability']:.2f}")
    if not ev:ev.append('Aucune incohérence physique majeure détectée dans la fenêtre courante.')
    return {'diagnostic':label,'confidence':fu['confidence'],'abstained':False,'evidence':ev,'recommendation':recommendation(label),'fusion':fu,'fusion_version':FUSION_VERSION,'model_origin':'distilled_linear_prior_from_sil_20260812','automatic_control_allowed':False}
