/* FLOWTRUST-AFR v0.3 — runtime bridge between the live HMI and T02 trust fusion. */
(() => {
  const LABELS = {
    normal: 'ALIMENTATION STABLE',
    weighing_drift: 'DÉRIVE DE PESAGE PROBABLE',
    hopper_bridging: 'PONTAGE DE TRÉMIE PROBABLE',
    conveyor_blockage: 'BOURRAGE CONVOYEUR PROBABLE',
    spillage: 'DÉVERSEMENT PROBABLE',
    unstable_feed: 'ALIMENTATION INSTABLE',
    unknown: 'ABSTENTION — OBSERVABILITÉ / CONFIANCE INSUFFISANTE'
  };

  const criticalLabels = new Set(['conveyor_blockage','hopper_bridging','spillage']);
  let latest = null;
  let busy = false;
  let lastAt = 0;
  let previousDiagnostic = null;

  function profile() {
    const key = state.activeScenario;
    const base = {
      hopperRate: 0, accumulation: 4, spillage: 1, flowCv: .04, currentCv: .035,
      speedQ: .99, weighQ: .99, levelQ: .99, electricalQ: .99,
      cameraQ: Math.max(.01, Math.min(1, (state.values.cameraQuality || 95) / (state.values.cameraQuality > 1 ? 100 : 1))),
      cameraConnected: 1
    };
    if (key === 'weighing_drift') Object.assign(base,{hopperRate:-2.5,weighQ:.72});
    if (key === 'hopper_bridging') Object.assign(base,{hopperRate:.2,accumulation:48,flowCv:.32,currentCv:.09});
    if (key === 'conveyor_blockage') Object.assign(base,{hopperRate:.8,accumulation:78,spillage:3,flowCv:.11,currentCv:.14});
    if (key === 'spillage') Object.assign(base,{hopperRate:-2.2,accumulation:10,spillage:42,flowCv:.07,currentCv:.05});
    if (key === 'unstable_feed') Object.assign(base,{hopperRate:1.3,accumulation:16,spillage:4,flowCv:.30,currentCv:.22});
    if (key === 'camera_loss') Object.assign(base,{cameraQ:.05,cameraConnected:0});
    if (key === 'sensor_stuck') Object.assign(base,{flowCv:0,weighQ:.12});
    if (key === 'desync') Object.assign(base,{flowCv:.14,currentCv:.14,speedQ:.28,weighQ:.28,electricalQ:.28});
    if (key === 'missing_data') Object.assign(base,{flowCv:0,currentCv:0,speedQ:.05,weighQ:.05,levelQ:.70,electricalQ:.05,cameraQ:.20,cameraConnected:0});
    return base;
  }

  function buildFeatures() {
    const v = state.values;
    const p = profile();
    const visual = Number(v.visualFlow || 0);
    const flow = Number(v.flow || 0);
    const disagreement = Math.abs(flow - visual) / Math.max(1, Math.abs(visual));
    const residual = disagreement * 100 + Math.abs(p.hopperRate) * 2.5 + p.spillage * .18;
    return {
      feeder_command_pct: Number(v.feeder || 0),
      belt_speed_command_mps: 1.6,
      belt_speed_mps: Number(v.speed || 0),
      speed_ratio: Number(v.speed || 0) / 1.6,
      measured_mass_flow_tph: flow,
      visual_flow_proxy_tph: visual,
      flow_disagreement_ratio: disagreement,
      visual_occupancy_pct: Math.max(0, Math.min(100, visual / 1.05)),
      hopper_level_pct: Number(v.hopper || 0),
      hopper_level_rate_pct_min: p.hopperRate,
      mass_balance_residual_abs_pct: Math.abs(residual),
      motor_current_a: Number(v.current || 0),
      motor_load_ratio: Math.max(.05, Number(v.current || 0) / 123),
      motor_torque_pct: Number(v.torque || 0),
      vibration_mm_s: Number(v.vibration || 0),
      flow_cv_60s: p.flowCv,
      motor_current_cv_60s: p.currentCv,
      visual_accumulation_pct: p.accumulation,
      visual_spillage_pct: p.spillage,
      speed_signal_quality: p.speedQ,
      weigh_signal_quality: p.weighQ,
      level_signal_quality: p.levelQ,
      electrical_signal_quality: p.electricalQ,
      camera_quality: p.cameraQ,
      camera_connected: p.cameraConnected
    };
  }

  async function requestDiagnosis(force=false) {
    const now = Date.now();
    if (busy || (!force && now - lastAt < 1300)) return;
    busy = true; lastAt = now;
    try {
      const response = await fetch('/api/diagnose', {
        method: 'POST',
        headers: {'content-type':'application/json'},
        body: JSON.stringify({features: buildFeatures()})
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      latest = data;
      if (previousDiagnostic && previousDiagnostic !== data.diagnostic) {
        addEvent(data.abstained ? 'ood' : data.diagnostic === 'normal' ? 'info' : criticalLabels.has(data.diagnostic) ? 'critical' : 'warn',
          `T02 : ${LABELS[data.diagnostic] || data.diagnostic} — confiance ${Math.round((data.confidence || 0) * 100)} %`);
      }
      previousDiagnostic = data.diagnostic;
      renderT02();
    } catch (error) {
      latest = {
        diagnostic:'unknown', confidence:0, abstained:true,
        evidence:[`Backend T02 indisponible : ${error.message}`],
        recommendation:'Vérifier la connexion au moteur de diagnostic avant de conclure.',
        fusion:null, automatic_control_allowed:false
      };
      renderT02();
    } finally { busy = false; }
  }

  function severity() {
    if (!latest) return 'pending';
    if (latest.abstained) return 'ood';
    if (latest.diagnostic === 'normal') return 'ok';
    return criticalLabels.has(latest.diagnostic) ? 'critical' : 'warn';
  }

  function renderT02() {
    if (!latest || !$('diagnosisState')) return;
    const sev = severity();
    const title = latest.abstained ? 'ABSTENTION' : sev === 'ok' ? 'ÉTAT NOMINAL' : sev === 'critical' ? 'ALARME CRITIQUE' : 'À VÉRIFIER';
    $('diagnosisState').innerHTML = `<div class="severity sev-${sev === 'pending' ? 'ood' : sev}">${title}</div><div class="diag-label">${LABELS[latest.diagnostic] || latest.diagnostic}</div><p>${latest.abstained ? 'FLOWTRUST refuse de forcer un diagnostic lorsque les preuves sont insuffisantes ou contradictoires.' : 'Verdict calculé par l’arbitre T02 à partir des preuves procédé, électromécaniques et visuelles.'}</p>`;
    $('confidencePill').textContent = latest.abstained ? 'Confiance insuffisante' : `Confiance ${Math.round((latest.confidence || 0) * 100)} %`;

    const modalities = latest.fusion?.modalities || {};
    const names = {process:'Procédé', electromechanical:'Électrique', vision:'Vision'};
    $('sourceHealth').innerHTML = Object.entries(names).map(([key,label]) => {
      const m = modalities[key];
      const active = m ? m.active : false;
      return `<span class="source ${active ? 'ok' : 'bad'}">${active ? '✓' : '×'} ${label}${m ? ` ${Math.round(m.reliability * 100)}%` : ''}</span>`;
    }).join('');

    $('evidenceList').innerHTML = (latest.evidence || []).slice(0,6).map(item => `<li>${item}</li>`).join('');
    $('recommendation').innerHTML = `<b>Suggestion opérateur</b><p>${latest.recommendation || 'Vérification opérateur recommandée.'}</p><small>Conseil uniquement — aucune commande machine.</small>`;
    $('diagnosisPanel').className = `panel diagnosis-panel ${sev === 'critical' ? 'critical-panel' : ''}`;
    updateT02Alarm();
  }

  function updateT02Alarm() {
    const banner = $('alarmBanner');
    if (!banner) return;
    const shouldAlarm = severity() === 'critical' && state.progress > .35;
    if (shouldAlarm) {
      banner.classList.add('show'); document.body.classList.add('alarm-active');
      $('alarmTitle').textContent = state.alarmAck ? 'ALARME ACQUITTÉE' : 'ALARME CRITIQUE';
      $('alarmMessage').textContent = LABELS[latest?.diagnostic] || 'Anomalie critique détectée';
      if (!state.alarmAck) startBuzzer();
    } else {
      banner.classList.remove('show'); document.body.classList.remove('alarm-active'); stopBuzzer();
    }
  }

  const legacyRenderLive = renderLive;
  renderLive = function() { legacyRenderLive(); renderT02(); };
  updateAlarm = updateT02Alarm;

  function rewriteCameraCopy() {
    const cameraPanel = document.querySelector('.camera-panel');
    if (cameraPanel) {
      const h2 = cameraPanel.querySelector('h2');
      if (h2) h2.textContent = 'Caméra / diagnostic image';
      const note = cameraPanel.querySelector('.privacy-note');
      if (note) note.textContent = 'Le test local mesure uniquement luminosité, contraste et netteté. Il ne reconnaît pas encore à lui seul une scène convoyeur/AFR et aucune image n’est envoyée au backend.';
    }
    const notice = document.querySelector('.notice');
    if (notice) notice.innerHTML = '<b>LIVE SIMULATION — T02.</b> Les variables procédé sont synthétiques et alimentent réellement le moteur de fusion T02. La caméra locale sert ici au diagnostic technique d’image ; elle n’est pas présentée comme une preuve AFR tant que le scene-gate industriel V2 n’est pas validé.';
    const validation = document.querySelector('#view-validation .validation-grid');
    if (validation) {
      const first = validation.querySelector('.panel');
      if (first) first.innerHTML = '<small>ARBITRE PRINCIPAL</small><h2>T02 — fusion multimodale de confiance</h2><p>Le Random Forest (RF, forêt aléatoire) reste un prior statistique. Le verdict final confronte séparément les preuves procédé, électromécaniques et vision, pondérées par leur fiabilité. En cas de contradiction ou d’observabilité insuffisante, FLOWTRUST s’abstient.</p>';
    }
  }

  function correctCameraResult() {
    setTimeout(() => {
      if (!$('testResultTitle') || !$('testResultBody')) return;
      if ($('testResultTitle').textContent.includes('caméra')) {
        const m = state.cameraMetrics;
        $('testResultTitle').textContent = 'Diagnostic technique caméra';
        if (m) $('testResultBody').insertAdjacentHTML('beforeend','<div class="result-callout warn"><b>Important :</b> ce score contrôle la qualité de l’image uniquement. Il ne signifie pas « convoyeur reconnu » ni « défaut AFR détecté ».</div>');
      }
    },0);
  }

  document.querySelector('[data-test="camera"]')?.addEventListener('click', correctCameraResult);
  $('runCvBtn')?.addEventListener('click', () => setTimeout(() => {
    if ($('cameraStatusTag') && state.cameraMetrics) {
      $('cameraStatusTag').textContent = state.cameraMetrics.quality >= 65 ? 'IMAGE TECHNIQUEMENT NETTE' : state.cameraMetrics.quality >= 45 ? 'IMAGE À VÉRIFIER' : 'IMAGE INSUFFISANTE';
      addEvent('info','Le score caméra affiché évalue la qualité technique de l’image, pas son contenu industriel.');
    }
  },0));

  const oldCoherenceCard = document.querySelector('[data-test="coherence"]');
  oldCoherenceCard?.addEventListener('click', () => setTimeout(() => {
    if (!latest || !$('testResultBody')) return;
    const mods = latest.fusion?.modalities || {};
    $('testResultTitle').textContent = 'Test FLOWTRUST — cohérence multimodale T02';
    $('testResultStatus').textContent = latest.abstained ? 'ABSTENTION' : 'T02 ACTIF';
    $('testResultBody').innerHTML = `<div class="coherence-table"><div><b>Source</b><b>Vote</b><b>Fiabilité</b></div>${['process','electromechanical','vision'].map(key => { const m=mods[key]; const label=key==='process'?'Procédé':key==='electromechanical'?'Électromécanique':'Vision'; return `<div><span>${label}</span><span>${m?.vote || '--'}</span><strong class="${m?.active ? 'good-text':'bad-text'}">${m ? Math.round(m.reliability*100)+' %':'--'}</strong></div>`; }).join('')}</div><div class="result-callout ${latest.abstained?'warn':''}">${latest.abstained ? 'Les preuves ne permettent pas une conclusion robuste : FLOWTRUST s’abstient.' : `Consensus T02 : ${LABELS[latest.diagnostic] || latest.diagnostic}, confiance ${Math.round((latest.confidence||0)*100)} %.`}</div>`;
  },20));

  rewriteCameraCopy();
  addEvent('info','Couche T02 connectée : le diagnostic live est calculé par /api/diagnose.');
  requestDiagnosis(true);
  setInterval(() => requestDiagnosis(false), 1400);
})();
