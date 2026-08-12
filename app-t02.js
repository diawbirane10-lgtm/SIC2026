(() => {
  const LABELS = {
    normal: 'ALIMENTATION STABLE',
    weighing_drift: 'DÉRIVE DE PESAGE PROBABLE',
    hopper_bridging: 'PONTAGE DE TRÉMIE PROBABLE',
    conveyor_blockage: 'BOURRAGE CONVOYEUR PROBABLE',
    spillage: 'DÉVERSEMENT PROBABLE',
    unstable_feed: 'ALIMENTATION INSTABLE',
    unknown: 'ABSTENTION — OBSERVABILITÉ / COHÉRENCE INSUFFISANTE'
  };

  const MODALITY_LABELS = {
    process: 'Procédé',
    electromechanical: 'Électromécanique',
    vision: 'Vision'
  };

  const META = {
    nominal: { hopperRate: 0.0, flowCv: 0.04, currentCv: 0.035, accumulation: 4, spillage: 1 },
    weighing_drift: { hopperRate: -2.5, flowCv: 0.05, currentCv: 0.04, accumulation: 5, spillage: 1 },
    hopper_bridging: { hopperRate: 0.2, flowCv: 0.32, currentCv: 0.07, accumulation: 48, spillage: 2 },
    conveyor_blockage: { hopperRate: 1.3, flowCv: 0.10, currentCv: 0.10, accumulation: 78, spillage: 4 },
    spillage: { hopperRate: -2.2, flowCv: 0.06, currentCv: 0.05, accumulation: 10, spillage: 42 },
    unstable_feed: { hopperRate: 1.9, flowCv: 0.30, currentCv: 0.22, accumulation: 8, spillage: 3 },
    camera_loss: { hopperRate: 0.0, flowCv: 0.04, currentCv: 0.035, accumulation: 4, spillage: 1 },
    sensor_stuck: { hopperRate: 0.0, flowCv: 0.00, currentCv: 0.035, accumulation: 4, spillage: 1 },
    desync: { hopperRate: 0.5, flowCv: 0.15, currentCv: 0.12, accumulation: 15, spillage: 3 },
    missing_data: { hopperRate: 0.0, flowCv: 0.0, currentCv: 0.0, accumulation: 0, spillage: 0 }
  };

  let backendState = 'pending';
  let backendDecision = null;
  let inFlight = false;
  let requestSeq = 0;
  let latestAppliedSeq = 0;
  let lastBackendNotice = '';

  function ensureBackendTag() {
    if (document.getElementById('fusionBackendTag')) return;
    const head = document.querySelector('#diagnosisPanel .panel-head');
    if (!head) return;
    const right = document.createElement('div');
    right.style.display = 'flex';
    right.style.gap = '.45rem';
    right.style.alignItems = 'center';
    right.innerHTML = '<span class="tag" id="fusionBackendTag">T02 · connexion…</span>';
    head.appendChild(right);
  }

  function setBackendTag(text, kind = '') {
    ensureBackendTag();
    const tag = document.getElementById('fusionBackendTag');
    if (!tag) return;
    tag.textContent = text;
    tag.className = `tag ${kind}`.trim();
  }

  function featurePayload() {
    const v = state.values;
    const meta = META[state.activeScenario] || META.nominal;
    const cameraQualityFromCv = state.cameraMetrics?.quality != null ? state.cameraMetrics.quality / 100 : null;
    const simulatedCameraQuality = clamp((v.cameraQuality ?? 0) / 100, 0, 1);
    let cameraQuality = cameraQualityFromCv ?? simulatedCameraQuality;
    let cameraConnected = 1.0;

    let speedQuality = 0.98;
    let weighQuality = 0.98;
    let levelQuality = 0.98;
    let electricalQuality = 0.98;

    if (state.activeScenario === 'camera_loss') {
      cameraQuality = 0.05;
      cameraConnected = 0.0;
    }
    if (state.activeScenario === 'sensor_stuck') {
      weighQuality = 0.10;
      levelQuality = 0.45;
    }
    if (state.activeScenario === 'desync') {
      speedQuality = 0.28;
      weighQuality = 0.28;
      levelQuality = 0.28;
      electricalQuality = 0.28;
    }
    if (state.activeScenario === 'missing_data') {
      speedQuality = 0.10;
      weighQuality = 0.10;
      levelQuality = 0.10;
      electricalQuality = 0.10;
      cameraQuality = 0.10;
      cameraConnected = 0.0;
    }

    const speedCommand = 1.6;
    const visualFlow = Math.max(0, Number(v.visualFlow) || 0);
    const measuredFlow = Math.max(0, Number(v.flow) || 0);
    const disagreement = Math.abs(measuredFlow - visualFlow) / Math.max(Math.abs(visualFlow), 1.0);
    const residual = disagreement * 100 + Math.abs(meta.hopperRate) * 2.5 + meta.spillage * 0.18;

    return {
      feeder_command_pct: Number(v.feeder) || 0,
      belt_speed_command_mps: speedCommand,
      belt_speed_mps: Number(v.speed) || 0,
      speed_ratio: (Number(v.speed) || 0) / speedCommand,
      measured_mass_flow_tph: measuredFlow,
      visual_flow_proxy_tph: visualFlow,
      flow_disagreement_ratio: disagreement,
      visual_occupancy_pct: clamp(visualFlow / 1.05, 0, 100),
      hopper_level_pct: clamp(Number(v.hopper) || 0, 0, 100),
      hopper_level_rate_pct_min: meta.hopperRate,
      mass_balance_residual_abs_pct: Math.abs(residual),
      motor_current_a: Math.max(0, Number(v.current) || 0),
      motor_load_ratio: clamp((Number(v.current) || 0) / 123.0, 0, 1.35),
      motor_torque_pct: Math.max(0, Number(v.torque) || 0),
      vibration_mm_s: Math.max(0, Number(v.vibration) || 0),
      flow_cv_60s: meta.flowCv,
      motor_current_cv_60s: meta.currentCv,
      visual_accumulation_pct: clamp(meta.accumulation, 0, 100),
      visual_spillage_pct: clamp(meta.spillage, 0, 100),
      speed_signal_quality: speedQuality,
      weigh_signal_quality: weighQuality,
      level_signal_quality: levelQuality,
      electrical_signal_quality: electricalQuality,
      camera_quality: cameraQuality,
      camera_connected: cameraConnected
    };
  }

  function severityFromDecision(decision) {
    if (!decision || decision.abstained || decision.diagnostic === 'unknown') return 'ood';
    if (['conveyor_blockage', 'hopper_bridging', 'spillage'].includes(decision.diagnostic)) return 'critical';
    if (['weighing_drift', 'unstable_feed'].includes(decision.diagnostic)) return 'warn';
    return 'ok';
  }

  function decisionTitle(decision) {
    return LABELS[decision?.diagnostic] || LABELS.unknown;
  }

  function backendIsT02() {
    return backendState === 'online' && backendDecision?.fusion?.version === 't02-v1';
  }

  function applyT02Decision() {
    if (!backendIsT02()) return;
    const d = backendDecision;
    const fusion = d.fusion;
    const severity = severityFromDecision(d);
    const sevLabel = severity === 'ok' ? 'ÉTAT NOMINAL' : severity === 'critical' ? 'ALARME CRITIQUE' : severity === 'warn' ? 'À VÉRIFIER' : 'ABSTENTION';
    const title = decisionTitle(d);
    const confidencePct = Math.round(clamp(Number(d.confidence) || 0, 0, 1) * 100);

    const stateBox = document.getElementById('diagnosisState');
    if (stateBox) {
      const explanation = d.abstained
        ? (fusion.abstention_reasons?.[0] || 'FLOWTRUST refuse de conclure avec les évidences disponibles.')
        : `Fusion T02 : ${fusion.active_modalities.length} modalités actives, accord ${(fusion.agreement * 100).toFixed(0)} %, marge ${(fusion.margin * 100).toFixed(0)} %.`;
      stateBox.innerHTML = `<div class="severity sev-${severity}">${sevLabel}</div><div class="diag-label">${title}</div><p>${explanation}</p>`;
    }

    const confidence = document.getElementById('confidencePill');
    if (confidence) confidence.textContent = d.abstained ? `Abstention · ${confidencePct} %` : `Confiance T02 ${confidencePct} %`;

    const sourceHealth = document.getElementById('sourceHealth');
    if (sourceHealth && fusion.modalities) {
      sourceHealth.innerHTML = Object.entries(fusion.modalities).map(([name, details]) => {
        const active = Boolean(details.active);
        const rel = Math.round((Number(details.reliability) || 0) * 100);
        const label = MODALITY_LABELS[name] || name;
        return `<span class="source ${active ? 'ok' : 'bad'}">${active ? '✓' : '×'} ${label} ${rel}%</span>`;
      }).join('');
    }

    const evidence = document.getElementById('evidenceList');
    if (evidence) {
      const rows = Array.isArray(d.evidence) && d.evidence.length
        ? d.evidence
        : (fusion.abstention_reasons || []);
      evidence.innerHTML = rows.slice(0, 6).map(item => `<li>${item}</li>`).join('');
    }

    const recommendation = document.getElementById('recommendation');
    if (recommendation) {
      recommendation.innerHTML = `<b>Suggestion opérateur</b><p>${d.recommendation || 'Vérification opérateur recommandée.'}</p><small>T02 · Conseil uniquement — aucune commande machine.</small>`;
    }

    const panel = document.getElementById('diagnosisPanel');
    if (panel) panel.className = `panel diagnosis-panel ${severity === 'critical' ? 'critical-panel' : ''}`;

    setBackendTag('T02 · API v0.3', 'ok');
  }

  async function requestT02Diagnosis() {
    if (inFlight) return;
    inFlight = true;
    const seq = ++requestSeq;
    const scenarioAtRequest = state.activeScenario;
    try {
      const response = await fetch('/api/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features: featurePayload() })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (seq < latestAppliedSeq || scenarioAtRequest !== state.activeScenario) return;
      latestAppliedSeq = seq;

      if (data?.fusion?.version === 't02-v1') {
        backendState = 'online';
        backendDecision = data;
        if (lastBackendNotice !== 't02') {
          addEvent('info', 'T02 connecté : diagnostic HMI piloté par la fusion procédé / électromécanique / vision.');
          lastBackendNotice = 't02';
        }
        applyT02Decision();
      } else {
        backendState = 'legacy';
        backendDecision = data;
        setBackendTag('API v0.2 · T02 non déployé', 'warn');
        if (lastBackendNotice !== 'legacy') {
          addEvent('warn', 'Backend accessible mais sans T02 : l’HMI conserve le moteur de démonstration local.');
          lastBackendNotice = 'legacy';
        }
      }
    } catch (error) {
      backendState = 'offline';
      backendDecision = null;
      setBackendTag('API indisponible · fallback local', 'warn');
      if (lastBackendNotice !== 'offline') {
        addEvent('warn', 'API diagnostic indisponible : maintien du replay local, sans revendiquer T02.');
        lastBackendNotice = 'offline';
      }
    } finally {
      inFlight = false;
    }
  }

  function installRenderOverlay() {
    if (typeof renderLive !== 'function') return;
    const baseRenderLive = renderLive;
    renderLive = function patchedRenderLive() {
      baseRenderLive();
      applyT02Decision();
    };
  }

  function installAlarmGate() {
    if (typeof updateAlarm !== 'function') return;
    const baseUpdateAlarm = updateAlarm;
    updateAlarm = function patchedUpdateAlarm() {
      if (!backendIsT02()) {
        baseUpdateAlarm();
        return;
      }

      const severity = severityFromDecision(backendDecision);
      const banner = document.getElementById('alarmBanner');
      const shouldAlarm = severity === 'critical' && !backendDecision.abstained && state.progress > 0.35;
      if (shouldAlarm) {
        banner?.classList.add('show');
        document.body.classList.add('alarm-active');
        const title = document.getElementById('alarmTitle');
        const message = document.getElementById('alarmMessage');
        if (title) title.textContent = state.alarmAck ? 'ALARME ACQUITTÉE' : 'ALARME CRITIQUE';
        if (message) message.textContent = `${decisionTitle(backendDecision)} — confirmé par T02`;
        if (!state.alarmAck) startBuzzer();
      } else {
        banner?.classList.remove('show');
        document.body.classList.remove('alarm-active');
        stopBuzzer();
      }
    };
  }

  function enhanceCoherenceTest() {
    if (typeof runTest !== 'function') return;
    const baseRunTest = runTest;
    runTest = function patchedRunTest(kind) {
      if (kind !== 'coherence' || !backendIsT02()) {
        return baseRunTest(kind);
      }

      const fusion = backendDecision.fusion;
      const rows = Object.entries(fusion.modalities).map(([name, details]) => {
        const rel = Math.round((Number(details.reliability) || 0) * 100);
        const vote = LABELS[details.vote] || details.vote;
        return `<div><span>${MODALITY_LABELS[name] || name}</span><span>${vote}</span><strong class="${details.active ? 'good-text' : 'bad-text'}">${details.active ? rel + ' %' : 'EXCLUE'}</strong></div>`;
      }).join('');
      const abstention = backendDecision.abstained
        ? (fusion.abstention_reasons || []).join(' ')
        : `Accord ${(fusion.agreement * 100).toFixed(0)} %, marge ${(fusion.margin * 100).toFixed(0)} %.`;

      document.getElementById('testResultTitle').textContent = 'Test FLOWTRUST — cohérence multimodale T02';
      document.getElementById('testResultStatus').textContent = backendDecision.abstained ? 'ABSTENTION' : 'TERMINÉ';
      document.getElementById('testResultBody').innerHTML = `<div class="coherence-table"><div><b>Modalité</b><b>Vote</b><b>Fiabilité</b></div>${rows}</div><div class="result-callout ${backendDecision.abstained ? 'warn' : ''}">${abstention}</div>`;
      addEvent('info', 'Test guidé : cohérence multimodale T02.');
    };
  }

  ensureBackendTag();
  installRenderOverlay();
  installAlarmGate();
  enhanceCoherenceTest();
  setBackendTag('T02 · connexion…');
  setTimeout(requestT02Diagnosis, 450);
  setInterval(requestT02Diagnosis, 1600);
})();
