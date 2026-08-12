const SCENARIOS = {
  nominal: {
    label: 'Fonctionnement nominal', short: 'Nominal', severity: 'ok', confidence: 94,
    diag: 'ALIMENTATION STABLE',
    values: { flow:72, visualFlow:71, current:86, speed:1.58, hopper:62, feeder:70, torque:69, vibration:2.2, cameraQuality:95 },
    evidence: ['Débit pesé et proxy visuel cohérents.', 'Vitesse réelle proche de la consigne.', 'Charge moteur et niveau de trémie compatibles avec le flux observé.'],
    rec: 'Poursuivre la surveillance. Aucune action automatique n’est autorisée.',
    checks: ['Continuer la surveillance des tendances.', 'Aucune vérification terrain urgente.']
  },
  weighing_drift: {
    label: 'Dérive du système de pesage', short: 'Dérive pesage', severity: 'warn', confidence: 88,
    diag: 'DÉRIVE DE PESAGE PROBABLE',
    values: { flow:43, visualFlow:69, current:84, speed:1.57, hopper:57, feeder:70, torque:68, vibration:2.3, cameraQuality:94 },
    evidence: ['Le débit pesé chute alors que le flux visuel reste élevé.', 'La charge moteur reste compatible avec un flux proche du nominal.', 'La baisse de niveau de trémie est incompatible avec le débit affiché.'],
    rec: 'Comparer le système de pesage aux indicateurs indépendants puis planifier une vérification/calibration.',
    checks: ['Contrôler zéro et étalonnage du pesage.', 'Inspecter l’état mécanique du doseur/peseur.', 'Comparer avec historique et bilan de trémie.']
  },
  hopper_bridging: {
    label: 'Pontage de trémie', short: 'Pontage trémie', severity: 'critical', confidence: 91,
    diag: 'PONTAGE DE TRÉMIE PROBABLE',
    values: { flow:28, visualFlow:30, current:78, speed:1.56, hopper:89, feeder:72, torque:74, vibration:4.1, cameraQuality:93 },
    evidence: ['Trémie fortement chargée mais débit aval faible.', 'Flux visuel intermittent malgré la demande d’alimentation.', 'La vitesse convoyeur reste disponible : le défaut paraît plus amont que convoyeur.'],
    rec: 'Vérifier la trémie et l’alimentation amont selon les procédures de sécurité du site.',
    checks: ['Confirmer le niveau réel de trémie.', 'Inspecter la zone de sortie sans intervention dangereuse.', 'Comparer commande doseur et débit réellement obtenu.']
  },
  conveyor_blockage: {
    label: 'Bourrage convoyeur', short: 'Bourrage', severity: 'critical', confidence: 93,
    diag: 'BOURRAGE CONVOYEUR PROBABLE',
    values: { flow:18, visualFlow:15, current:128, speed:0.72, hopper:81, feeder:70, torque:109, vibration:6.4, cameraQuality:92 },
    evidence: ['Vitesse réelle fortement inférieure à la consigne.', 'Courant et couple moteur augmentent simultanément.', 'Accumulation matière cohérente avec un blocage mécanique.'],
    rec: 'Demander une vérification du convoyeur, de l’entraînement et de la zone d’accumulation avant toute remise en service.',
    checks: ['Comparer vitesse commandée et vitesse mesurée.', 'Consulter les alarmes du variateur.', 'Inspecter la zone d’accumulation selon la procédure de consignation.']
  },
  spillage: {
    label: 'Déversement de matière', short: 'Déversement', severity: 'critical', confidence: 89,
    diag: 'DÉVERSEMENT PROBABLE',
    values: { flow:66, visualFlow:45, current:82, speed:1.56, hopper:51, feeder:70, torque:67, vibration:3.0, cameraQuality:93 },
    evidence: ['Le bilan matière devient incohérent.', 'Le proxy visuel utile baisse alors que la matière quitte la trémie.', 'La signature électrique reste compatible avec un convoyage actif.'],
    rec: 'Inspecter la zone de transfert et confirmer l’origine de la perte de matière.',
    checks: ['Vérifier bavettes et zone de transfert.', 'Confirmer l’accumulation hors bande.', 'Comparer pertes visuelles et bilan matière.']
  },
  unstable_feed: {
    label: 'Alimentation instable', short: 'Flux instable', severity: 'warn', confidence: 86,
    diag: 'ALIMENTATION INSTABLE',
    values: { flow:49, visualFlow:52, current:97, speed:1.50, hopper:66, feeder:73, torque:81, vibration:4.5, cameraQuality:91 },
    evidence: ['Débit et courant oscillent sur plusieurs fenêtres.', 'La vitesse reste globalement disponible.', 'La variabilité est persistante et non limitée à un pic isolé.'],
    rec: 'Vérifier la régularité du dosage, la disponibilité matière et les signaux de commande/charge.',
    checks: ['Comparer consigne doseur et réponse réelle.', 'Contrôler hétérogénéité du combustible.', 'Rechercher des cycles d’alimentation intermittente.']
  },
  camera_loss: {
    label: 'Perte / forte dégradation caméra', short: 'Perte caméra', severity: 'ood', confidence: 0,
    diag: 'ABSTENTION — VISION INDISPONIBLE',
    values: { flow:70, visualFlow:0, current:85, speed:1.57, hopper:61, feeder:70, torque:69, vibration:2.4, cameraQuality:5 },
    evidence: ['Qualité ou disponibilité caméra insuffisante.', 'La branche vision est exclue de la fusion.', 'FLOWTRUST refuse d’inventer une preuve visuelle.'],
    rec: 'Rétablir la caméra ou poursuivre temporairement avec les seules sources suffisamment fiables.',
    checks: ['Vérifier connexion et alimentation caméra.', 'Nettoyer l’optique.', 'Contrôler le cadrage et l’éclairage.']
  },
  sensor_stuck: {
    label: 'Capteur bloqué (stuck-at)', short: 'Capteur bloqué', severity: 'ood', confidence: 0,
    diag: 'ABSTENTION — CAPTEUR SUSPECT',
    values: { flow:55, visualFlow:70, current:86, speed:1.58, hopper:62, feeder:70, torque:69, vibration:2.2, cameraQuality:94 },
    evidence: ['Une variable reste artificiellement constante pendant que les autres évoluent.', 'La cohérence temporelle du capteur n’est plus crédible.', 'Le signal suspect est retiré du diagnostic.'],
    rec: 'Tester le capteur concerné et rétablir une source fiable avant de conclure.',
    checks: ['Vérifier alimentation et communication du transmetteur.', 'Comparer avec une source indépendante.', 'Contrôler historique des variations.']
  },
  desync: {
    label: 'Désynchronisation des sources', short: 'Désynchronisation', severity: 'ood', confidence: 0,
    diag: 'ABSTENTION — SOURCES DÉSYNCHRONISÉES',
    values: { flow:58, visualFlow:72, current:101, speed:1.21, hopper:64, feeder:70, torque:83, vibration:3.9, cameraQuality:92 },
    evidence: ['Les réponses des différentes sources sont décalées dans le temps.', 'La relation cause-effet débit/charge/vitesse devient ambiguë.', 'Le diagnostic est suspendu pour éviter une conclusion erronée.'],
    rec: 'Vérifier horodatage, acquisition et synchronisation des sources avant nouvelle analyse.',
    checks: ['Comparer timestamps PLC, edge et caméra.', 'Contrôler latence réseau.', 'Rejouer la fenêtre après resynchronisation.']
  },
  missing_data: {
    label: 'Rafale de données manquantes', short: 'Données manquantes', severity: 'ood', confidence: 0,
    diag: 'OBSERVABILITÉ INSUFFISANTE',
    values: { flow:0, visualFlow:0, current:0, speed:0, hopper:62, feeder:70, torque:0, vibration:0, cameraQuality:20 },
    evidence: ['Plusieurs sources deviennent simultanément indisponibles.', 'Le seuil minimal d’observabilité n’est plus atteint.', 'FLOWTRUST s’abstient volontairement.'],
    rec: 'Rétablir les flux de données ou demander une vérification terrain. Aucun diagnostic n’est forcé.',
    checks: ['Vérifier acquisition OPC UA/historian.', 'Contrôler réseau et compte de service.', 'Confirmer l’état réel auprès de l’opérateur.']
  }
};

const FAULT_ORDER = ['weighing_drift','hopper_bridging','conveyor_blockage','spillage','unstable_feed','camera_loss','sensor_stuck','desync','missing_data'];
const state = {
  activeScenario: 'nominal',
  values: {...SCENARIOS.nominal.values},
  target: {...SCENARIOS.nominal.values},
  progress: 1,
  events: [],
  history: [],
  cameraStream: null,
  facingMode: 'environment',
  cameraMetrics: null,
  audioCtx: null,
  buzzerTimer: null,
  alarmAck: false,
  replayTimer: null
};

const $ = id => document.getElementById(id);
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
const nowTime = () => new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
const scenario = () => SCENARIOS[state.activeScenario];

function initAudio(){
  if(!state.audioCtx){
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if(Ctx) state.audioCtx = new Ctx();
  }
  if(state.audioCtx?.state === 'suspended') state.audioCtx.resume().catch(()=>{});
}
function beep(){
  if(!$('audioAlarmToggle')?.checked || !state.audioCtx) return;
  const o = state.audioCtx.createOscillator();
  const g = state.audioCtx.createGain();
  o.type = 'square'; o.frequency.value = 760;
  g.gain.setValueAtTime(0.0001,state.audioCtx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.12,state.audioCtx.currentTime+0.02);
  g.gain.exponentialRampToValueAtTime(0.0001,state.audioCtx.currentTime+0.28);
  o.connect(g); g.connect(state.audioCtx.destination); o.start(); o.stop(state.audioCtx.currentTime+0.3);
}
function startBuzzer(){
  initAudio();
  if(state.buzzerTimer || state.alarmAck) return;
  beep(); state.buzzerTimer = setInterval(beep,1700);
}
function stopBuzzer(){ if(state.buzzerTimer){ clearInterval(state.buzzerTimer); state.buzzerTimer=null; } }

function addEvent(type,message){
  state.events.unshift({time:nowTime(),type,message});
  state.events = state.events.slice(0,40);
  renderEvents();
}
function renderEvents(){
  const box=$('eventLog'); if(!box) return;
  if(!state.events.length){ box.innerHTML='<div class="empty-event">Aucun événement enregistré.</div>'; return; }
  box.innerHTML=state.events.map(e=>`<div class="event ${e.type}"><time>${e.time}</time><span class="event-dot"></span><p>${e.message}</p></div>`).join('');
}

function setScenario(key,source='injection'){
  if(!SCENARIOS[key]) return;
  initAudio();
  state.activeScenario=key; state.target={...SCENARIOS[key].values}; state.progress=0; state.alarmAck=false;
  const s=SCENARIOS[key];
  addEvent(s.severity==='critical'?'critical':s.severity==='warn'?'warn':s.severity==='ood'?'ood':'info', `${source==='replay'?'Replay':'Injection'} : ${s.label}`);
  updateAlarm(); renderScenarioButtons();
  document.querySelector('[data-view="supervision"]')?.click();
}
function restoreNominal(){
  stopBuzzer(); state.alarmAck=false; setScenario('nominal','reset');
}

function updateAlarm(){
  const s=scenario(); const banner=$('alarmBanner');
  const shouldAlarm=s.severity==='critical' && state.progress>0.35;
  if(shouldAlarm){
    banner.classList.add('show'); document.body.classList.add('alarm-active');
    $('alarmTitle').textContent=state.alarmAck?'ALARME ACQUITTÉE':'ALARME CRITIQUE';
    $('alarmMessage').textContent=`${s.label} — ${s.diag}`;
    if(!state.alarmAck) startBuzzer();
  } else {
    banner.classList.remove('show'); document.body.classList.remove('alarm-active'); stopBuzzer();
  }
}

function liveTick(){
  const s=scenario();
  state.progress=clamp(state.progress+0.055,0,1);
  Object.keys(state.values).forEach(k=>{
    const target=state.target[k] ?? state.values[k];
    const noise = ['flow','visualFlow','current','hopper','torque'].includes(k) ? (Math.random()-.5)*0.8 : ['speed','vibration'].includes(k)?(Math.random()-.5)*0.03:0;
    state.values[k] += (target-state.values[k])*0.13 + noise;
  });
  if(state.activeScenario==='unstable_feed'){
    const wave=Math.sin(Date.now()/700);
    state.values.flow += wave*3.2; state.values.current += wave*2.6; state.values.vibration += Math.abs(wave)*0.25;
  }
  if(state.activeScenario==='sensor_stuck') state.values.flow=55;
  if(state.activeScenario==='missing_data' && state.progress>.55){ state.values.flow=0; state.values.current=0; state.values.speed=0; }
  state.history.push({flow:state.values.flow,current:state.values.current,speed:state.values.speed*50});
  if(state.history.length>70) state.history.shift();
  renderLive(); drawTrend(); updateAlarm();
}

function metricCard(label,value,unit,status='normal'){
  return `<div class="metric-card ${status}"><small>${label}</small><b>${value}</b><span>${unit}</span></div>`;
}
function renderLive(){
  const v=state.values, s=scenario();
  $('synHopper').textContent=`${Math.round(v.hopper)} %`; $('synFeeder').textContent=`${Math.round(v.feeder)} %`; $('synSpeed').textContent=`${v.speed.toFixed(2)} m/s`; $('synFlow').textContent=`${Math.round(v.flow)} t/h`;
  const flowStatus=v.flow<30?'danger':v.flow<50?'warn':'normal';
  const currentStatus=v.current>115?'danger':v.current>100?'warn':'normal';
  const speedStatus=v.speed<0.9?'danger':v.speed<1.3?'warn':'normal';
  const vibStatus=v.vibration>5.5?'danger':v.vibration>4?'warn':'normal';
  $('metricGrid').innerHTML=[
    metricCard('Débit AFR',v.flow.toFixed(1),'t/h',flowStatus), metricCard('Flux visuel',v.visualFlow.toFixed(1),'t/h',Math.abs(v.visualFlow-v.flow)>18?'warn':'normal'),
    metricCard('Courant moteur',Math.round(v.current),'A',currentStatus), metricCard('Vitesse réelle',v.speed.toFixed(2),'m/s',speedStatus),
    metricCard('Niveau trémie',Math.round(v.hopper),'%',v.hopper>85?'warn':'normal'), metricCard('Vibration',v.vibration.toFixed(1),'mm/s',vibStatus)
  ].join('');

  const sevLabel=s.severity==='ok'?'ÉTAT NOMINAL':s.severity==='critical'?'ALARME CRITIQUE':s.severity==='warn'?'À VÉRIFIER':'ABSTENTION';
  $('diagnosisState').innerHTML=`<div class="severity sev-${s.severity}">${sevLabel}</div><div class="diag-label">${s.diag}</div><p>${s.severity==='ood'?'FLOWTRUST ne dispose pas de preuves suffisamment fiables pour conclure.':'Fusion des variables procédé, électriques et visuelles avec contrôle de cohérence.'}</p>`;
  $('confidencePill').textContent=s.severity==='ood'?'Confiance insuffisante':`Confiance ${Math.round(s.confidence*state.progress + (1-state.progress)*94)} %`;
  const health = s.severity==='ood' ? ['Procédé','Électrique','Niveau','Vision'].map((x,i)=>({x,ok:!(state.activeScenario==='missing_data'||(state.activeScenario==='camera_loss'&&i===3)||(state.activeScenario==='sensor_stuck'&&i===0)||(state.activeScenario==='desync'&&i<3))})) : ['Procédé','Électrique','Niveau','Vision'].map(x=>({x,ok:true}));
  $('sourceHealth').innerHTML=health.map(h=>`<span class="source ${h.ok?'ok':'bad'}">${h.ok?'✓':'×'} ${h.x}</span>`).join('');
  $('evidenceList').innerHTML=s.evidence.map(x=>`<li>${x}</li>`).join('');
  $('recommendation').innerHTML=`<b>Suggestion opérateur</b><p>${s.rec}</p><small>Conseil uniquement — aucune commande machine.</small>`;
  $('diagnosisPanel').className=`panel diagnosis-panel ${s.severity==='critical'?'critical-panel':''}`;
}

function drawTrend(){
  const c=$('trendCanvas'); if(!c) return; const rect=c.getBoundingClientRect(); const dpr=window.devicePixelRatio||1;
  c.width=Math.max(320,rect.width*dpr); c.height=210*dpr; const ctx=c.getContext('2d'); ctx.scale(dpr,dpr); const w=rect.width,h=210;
  ctx.clearRect(0,0,w,h); ctx.strokeStyle='rgba(130,160,180,.16)'; ctx.lineWidth=1;
  for(let i=1;i<5;i++){ctx.beginPath();ctx.moveTo(0,i*h/5);ctx.lineTo(w,i*h/5);ctx.stroke();}
  const series=[['flow','#42d6c8',0,140],['current','#ffbf69',0,150],['speed','#5ab3ff',0,100]];
  series.forEach(([key,color,min,max])=>{ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();state.history.forEach((p,i)=>{const x=i/Math.max(1,state.history.length-1)*w;const y=h-((p[key]-min)/(max-min))*h; i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();});
}

function renderFaultGrid(){
  const box=$('faultGrid'); if(!box) return;
  box.innerHTML=FAULT_ORDER.map(k=>{const s=SCENARIOS[k];const icon=s.severity==='critical'?'⚠':s.severity==='warn'?'△':'◇';return `<button class="fault-card ${s.severity}" data-fault="${k}"><span class="fault-icon">${icon}</span><div><b>${s.label}</b><small>${s.diag}</small></div></button>`}).join('');
  box.querySelectorAll('[data-fault]').forEach(b=>b.addEventListener('click',()=>setScenario(b.dataset.fault)));
}
function renderScenarioButtons(){
  const box=$('scenarioButtons'); if(!box) return;
  box.innerHTML=Object.entries(SCENARIOS).map(([k,s])=>`<button class="scenario-btn ${k===state.activeScenario?'active':''}" data-scenario="${k}"><b>${s.short}</b><span>${s.severity==='critical'?'Critique':s.severity==='warn'?'Attention':s.severity==='ood'?'Abstention':'Normal'}</span></button>`).join('');
  box.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>{state.activeScenario=b.dataset.scenario;state.target={...SCENARIOS[b.dataset.scenario].values};renderScenarioButtons();}));
}

function switchView(name){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active')); document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  $(`view-${name}`)?.classList.add('active'); document.querySelector(`[data-view="${name}"]`)?.classList.add('active');
  if(name==='supervision') setTimeout(drawTrend,80);
}

async function startCamera(){
  initAudio();
  if(!navigator.mediaDevices?.getUserMedia){ cameraError('Caméra non prise en charge par ce navigateur.'); return; }
  stopCamera(false);
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:state.facingMode},width:{ideal:1280},height:{ideal:720}}});
    state.cameraStream=stream; $('cameraVideo').srcObject=stream; await $('cameraVideo').play();
    $('cameraPlaceholder').classList.add('hidden'); $('roiOverlay').classList.add('show'); $('cameraStatusTag').textContent='LIVE'; $('cameraStatusTag').classList.add('ok');
    $('runCvBtn').disabled=false; $('stopCameraBtn').disabled=false; $('switchCameraBtn').disabled=false; $('startCameraBtn').textContent='Caméra active';
    const track=stream.getVideoTracks()[0]; const settings=track.getSettings(); $('cameraResolution').textContent=`${settings.width||'--'}×${settings.height||'--'}`; $('cameraFps').textContent=`FPS ${Math.round(settings.frameRate||30)}`;
    addEvent('info','Caméra locale activée avec autorisation utilisateur.');
  }catch(err){
    cameraError(err.name==='NotAllowedError'?'Autorisation caméra refusée. Tu peux la réactiver dans les permissions du navigateur.':`Impossible d'activer la caméra : ${err.message}`);
  }
}
function stopCamera(log=true){
  if(state.cameraStream){state.cameraStream.getTracks().forEach(t=>t.stop());state.cameraStream=null;}
  if($('cameraVideo')) $('cameraVideo').srcObject=null; $('cameraPlaceholder')?.classList.remove('hidden'); $('roiOverlay')?.classList.remove('show');
  if($('cameraStatusTag')){$('cameraStatusTag').textContent='NON ACTIVÉE';$('cameraStatusTag').classList.remove('ok','bad');}
  ['runCvBtn','stopCameraBtn','switchCameraBtn'].forEach(id=>{if($(id))$(id).disabled=true}); if($('startCameraBtn'))$('startCameraBtn').textContent='Activer la caméra';
  if(log) addEvent('info','Caméra locale coupée.');
}
function cameraError(msg){ $('cameraStatusTag').textContent='ERREUR'; $('cameraStatusTag').classList.add('bad'); $('cameraPlaceholder').innerHTML=`<span>!</span><b>Caméra indisponible</b><p>${msg}</p>`; addEvent('warn',msg); }
async function switchCamera(){ state.facingMode=state.facingMode==='environment'?'user':'environment'; await startCamera(); }

function analyzeCamera(){
  const video=$('cameraVideo'); if(!state.cameraStream || !video.videoWidth){ cameraError('Aucune image caméra disponible.'); return; }
  const canvas=$('cameraCanvas'); canvas.width=160; canvas.height=90; const ctx=canvas.getContext('2d',{willReadFrequently:true}); ctx.drawImage(video,0,0,160,90);
  const data=ctx.getImageData(0,0,160,90).data; const gray=new Float32Array(160*90); let sum=0;
  for(let i=0,j=0;i<data.length;i+=4,j++){const y=.2126*data[i]+.7152*data[i+1]+.0722*data[i+2];gray[j]=y;sum+=y;}
  const mean=sum/gray.length; let variance=0,edge=0,count=0;
  for(let y=1;y<89;y++)for(let x=1;x<159;x++){const i=y*160+x;variance+=(gray[i]-mean)**2;edge+=Math.abs(gray[i]-gray[i-1])+Math.abs(gray[i]-gray[i-160]);count++;}
  const contrast=Math.sqrt(variance/gray.length); const sharp=edge/Math.max(1,count*2);
  const brightnessScore=clamp(100-Math.abs(mean-128)*0.9,0,100); const contrastScore=clamp(contrast*3.1,0,100); const sharpScore=clamp(sharp*8.5,0,100); const quality=Math.round(.35*brightnessScore+.30*contrastScore+.35*sharpScore);
  state.cameraMetrics={brightness:mean,contrast,sharpness:sharp,quality};
  $('cvQuality').textContent=`${quality}/100`; $('cvBrightness').textContent=`${Math.round(mean)}/255`; $('cvContrast').textContent=contrast.toFixed(1); $('cvSharpness').textContent=sharp.toFixed(1);
  $('cameraStatusTag').textContent=quality>=65?'CV OK':quality>=45?'CV À VÉRIFIER':'CV INSUFFISANT'; $('cameraStatusTag').className=`tag ${quality>=65?'ok':quality>=45?'warn':'bad'}`;
  addEvent(quality<45?'warn':'info',`Test caméra/CV local : qualité ${quality}/100, luminosité ${Math.round(mean)}, contraste ${contrast.toFixed(1)}, netteté ${sharp.toFixed(1)}.`);
  return state.cameraMetrics;
}

function runTest(kind){
  initAudio(); const s=scenario(),v=state.values; let title='',status='TERMINÉ',html='';
  if(kind==='sensor'){
    title='Test d’intégrité capteur — débit massique';
    const disagreement=Math.abs(v.flow-v.visualFlow)/Math.max(1,v.visualFlow);
    html=`<div class="result-score"><b>${state.activeScenario==='sensor_stuck'?42:state.activeScenario==='weighing_drift'?61:94}/100</b><span>Santé du signal</span></div><div class="check-list"><p><span>Disponibilité</span><b>${state.activeScenario==='missing_data'?'Dégradée':'OK'}</b></p><p><span>Stuck-at</span><b>${state.activeScenario==='sensor_stuck'?'SUSPECT':'Non détecté'}</b></p><p><span>Dérive</span><b>${state.activeScenario==='weighing_drift'?'SUSPECTE':'Non détectée'}</b></p><p><span>Cohérence vision</span><b>${Math.round(disagreement*100)} % d'écart</b></p></div><div class="result-callout">${state.activeScenario==='weighing_drift'?'La charge moteur, la vision et le bilan de trémie suggèrent que la chute du débit pesé n’est probablement pas une chute réelle du flux.':'Aucune incohérence majeure du capteur sélectionné dans l’état courant.'}</div>`;
  } else if(kind==='camera'){
    title='Test caméra / Computer Vision'; const m=analyzeCamera(); if(!m){status='CAMÉRA REQUISE';html='<p>Active la caméra puis relance le test. L’analyse de qualité est effectuée localement sur ta tablette.</p>';} else html=`<div class="result-score"><b>${m.quality}/100</b><span>Qualité exploitable</span></div><div class="check-list"><p><span>Luminosité</span><b>${Math.round(m.brightness)}/255</b></p><p><span>Contraste</span><b>${m.contrast.toFixed(1)}</b></p><p><span>Netteté</span><b>${m.sharpness.toFixed(1)}</b></p><p><span>Décision</span><b>${m.quality>=65?'Vision autorisée':m.quality>=45?'Vision à faible autorité':'Vision exclue'}</b></p></div>`;
  } else if(kind==='drive'){
    title='Diagnostic entraînement convoyeur'; const ratio=v.speed/1.6; const bad=ratio<.65&&v.current>110;
    html=`<div class="check-list"><p><span>Vitesse réelle / commande</span><b>${Math.round(ratio*100)} %</b></p><p><span>Courant moteur</span><b>${Math.round(v.current)} A</b></p><p><span>Couple</span><b>${Math.round(v.torque)} %</b></p><p><span>Vibration</span><b>${v.vibration.toFixed(1)} mm/s</b></p></div><div class="result-callout ${bad?'danger':''}">${bad?'Signature électromécanique compatible avec un convoyeur contraint ou bourré. Inspection recommandée.':'Aucune signature critique de l’entraînement dans l’état courant.'}</div>`;
  } else if(kind==='coherence'){
    title='Test FLOWTRUST — cohérence multimodale'; const dis=Math.abs(v.flow-v.visualFlow); const mismatch=dis>15;
    html=`<div class="coherence-table"><div><b>Source</b><b>Observation</b><b>Confiance</b></div><div><span>Pesage</span><span>${v.flow.toFixed(1)} t/h</span><strong class="${mismatch?'bad-text':'good-text'}">${mismatch?'CONFLIT':'OK'}</strong></div><div><span>Vision</span><span>${v.visualFlow.toFixed(1)} t/h</span><strong class="${state.activeScenario==='camera_loss'?'bad-text':'good-text'}">${state.activeScenario==='camera_loss'?'INDISPONIBLE':'OK'}</strong></div><div><span>Électrique</span><span>${Math.round(v.current)} A</span><strong class="good-text">ANALYSÉ</strong></div><div><span>Stock</span><span>${Math.round(v.hopper)} %</span><strong class="good-text">ANALYSÉ</strong></div></div><div class="result-callout ${mismatch?'warn':''}">${mismatch?`Les sources ne racontent pas la même histoire : ${dis.toFixed(1)} t/h d'écart entre pesage et vision. ${s.diag}.`:'Les quatre familles de preuves sont globalement cohérentes.'}</div>`;
  } else if(kind==='observability'){
    title='Test d’observabilité'; const abstain=s.severity==='ood';
    html=`<div class="result-score"><b>${abstain?'INSUFF.':'OK'}</b><span>Capacité à conclure</span></div><div class="result-callout ${abstain?'danger':''}">${abstain?'FLOWTRUST s’abstient : une ou plusieurs sources critiques sont indisponibles, suspectes ou désynchronisées.':'Les sources minimales nécessaires au diagnostic sont disponibles.'}</div>`;
  } else if(kind==='incident'){
    title='Injection de défaut'; status='CHOISISSEZ UN DÉFAUT'; html='<p>Utilise le laboratoire d’injection juste au-dessus. Les défauts critiques déclenchent la chaîne complète d’alarme : rouge + journal + buzzer + message opérateur.</p>';
    $('faultGrid')?.scrollIntoView({behavior:'smooth',block:'center'});
  }
  $('testResultTitle').textContent=title; $('testResultStatus').textContent=status; $('testResultBody').innerHTML=html; addEvent('info',`Test guidé : ${title}`);
}

function explainCurrent(){
  const s=scenario(); $('testResultTitle').textContent=`Pourquoi : ${s.diag}`; $('testResultStatus').textContent=s.severity==='ood'?'ABSTENTION':'EXPLICATION';
  $('testResultBody').innerHTML=`<ol class="explain-list">${s.evidence.map((x,i)=>`<li><b>${i+1}</b><span>${x}</span></li>`).join('')}</ol><div class="result-callout"><b>Conclusion</b><br>${s.diag}. Le système confronte plusieurs sources ; aucune preuve unique ne commande le procédé.</div>`; switchView('tests');
}
function showNextChecks(){
  const s=scenario(); $('testResultTitle').textContent='Prochaines vérifications suggérées'; $('testResultStatus').textContent='OPÉRATEUR'; $('testResultBody').innerHTML=`<ol class="next-list">${s.checks.map(x=>`<li>${x}</li>`).join('')}</ol><p class="privacy-note">Ces éléments sont des suggestions de vérification. FLOWTRUST ne déclenche aucune action sur la machine.</p>`; switchView('tests');
}

function startReplay(){
  initAudio(); if(state.replayTimer) clearInterval(state.replayTimer); const key=state.activeScenario==='nominal'?'conveyor_blockage':state.activeScenario;
  state.activeScenario='nominal'; state.target={...SCENARIOS.nominal.values}; state.progress=1; let step=0; const timeline=$('replayTimeline'); timeline.innerHTML='';
  const phases=[['T+00 s','État nominal — toutes les sources sont cohérentes.'],['T+10 s','Première dérive faible détectée sur les tendances.'],['T+20 s','Concordance de plusieurs sources : anomalie en cours de confirmation.'],['T+30 s',`Diagnostic consolidé : ${SCENARIOS[key].diag}.`]];
  state.replayTimer=setInterval(()=>{if(step===1)setScenario(key,'replay'); if(step<phases.length){timeline.insertAdjacentHTML('beforeend',`<div class="timeline-row"><b>${phases[step][0]}</b><span>${phases[step][1]}</span></div>`);step++;}else{clearInterval(state.replayTimer);state.replayTimer=null;}},1800);
}

function bind(){
  document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>switchView(t.dataset.view)));
  document.querySelectorAll('.test-card').forEach(t=>t.addEventListener('click',()=>runTest(t.dataset.test)));
  $('startCameraBtn').addEventListener('click',startCamera); $('switchCameraBtn').addEventListener('click',switchCamera); $('runCvBtn').addEventListener('click',analyzeCamera); $('stopCameraBtn').addEventListener('click',()=>stopCamera(true));
  $('restoreNominalBtn').addEventListener('click',restoreNominal); $('resetBtn').addEventListener('click',restoreNominal); $('replayBtn').addEventListener('click',startReplay);
  $('explainBtn').addEventListener('click',explainCurrent); $('nextChecksBtn').addEventListener('click',showNextChecks);
  $('clearEventsBtn').addEventListener('click',()=>{state.events=[];renderEvents();});
  $('muteAlarmBtn').addEventListener('click',()=>{stopBuzzer();addEvent('info','Buzzer coupé par l’opérateur.');});
  $('ackAlarmBtn').addEventListener('click',()=>{state.alarmAck=true;stopBuzzer();updateAlarm();addEvent('info','Alarme acquittée par l’opérateur — défaut toujours surveillé.');});
  $('audioAlarmToggle').addEventListener('change',e=>{initAudio();if(!e.target.checked)stopBuzzer();else updateAlarm();});
  window.addEventListener('resize',drawTrend);
}

function init(){
  bind(); renderFaultGrid(); renderScenarioButtons(); renderEvents(); renderLive();
  addEvent('info','FLOWTRUST-AFR démarré en LIVE SIMULATION / READ-ONLY.');
  setInterval(()=>{$('clock').textContent=nowTime();},1000); $('clock').textContent=nowTime();
  setInterval(liveTick,800);
}
init();
