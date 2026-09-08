/* ==========================================================================
   Hufi — chat feature module.
   Renders into Hufi.mount.chat. Owns the message thread, mission polling,
   approval cards and result cards. Implements Hufi.chat.openAgent(id) for
   the sidebar (agents.js) to call.

   Nothing here talks to the backend except through Hufi.api(); nothing here
   touches app.js/app.css/index.html/agents.js/agents.css.
   ========================================================================== */
(function () {
  const Hufi = window.Hufi;
  const esc = Hufi.esc;

  const POLL_MS = 2500;
  const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'];

  const STARTERS = [
    'HufManager prüfen',
    'Website analysieren',
    'Tagesbericht',
    'Recherche starten',
    'neue Idee planen',
  ];

  // Plain-language labels for raw audit event_type values — shown only
  // inside the collapsed "Details" panel, never in the normal chat flow.
  const EVENT_LABELS = {
    mission_created: 'Mission erstellt',
    task_created: 'Aufgabe erstellt',
    project_bound: 'Projekt verbunden',
    agent_assigned: 'Agent zugewiesen',
    model_call: 'Modell angefragt',
    model_result: 'Modell hat geantwortet',
    tool_call: 'Werkzeug angefordert',
    tool_started: 'Werkzeug gestartet',
    tool_result: 'Werkzeug-Ergebnis',
    tool_reused: 'Ergebnis wiederverwendet',
    review: 'Prüfung durch Reviewer',
    approval_requested: 'Freigabe angefragt',
    approval_resolved: 'Freigabe entschieden',
    policy_blocked: 'Von Richtlinie blockiert',
    state_transition: 'Statuswechsel',
    recovery: 'Wiederherstellung nach Neustart',
    error: 'Fehler',
    executor_error: 'Ausführungsfehler',
    executor_interrupted: 'Ausführung unterbrochen',
    agent_registered: 'Agent registriert',
  };

  function eventDot(type) {
    if (['error', 'executor_error', 'policy_blocked'].includes(type)) return 'var(--bad)';
    if (['approval_requested', 'executor_interrupted', 'recovery', 'tool_call'].includes(type)) return 'var(--warn)';
    if (['tool_result', 'review', 'approval_resolved', 'state_transition'].includes(type)) return 'var(--ok)';
    return 'var(--idle)';
  }

  function eventNote(event) {
    const d = event.detail || {};
    switch (event.event_type) {
      case 'state_transition': return `${d.source ?? '?'} → ${d.target ?? '?'}${d.reason ? ' · ' + d.reason : ''}`;
      case 'tool_call': return `${d.tool ?? '?'}.${d.action ?? '?'}${d.target ? ' auf ' + d.target : ''}`;
      case 'tool_result': return `Status: ${d.status ?? '?'}`;
      case 'model_call': return d.provider ? `Anbieter: ${d.provider}` : '';
      case 'model_result': return d.provider ? `${d.provider}${d.model ? ' / ' + d.model : ''}` : '';
      case 'review': return d.verdict ? `Ergebnis: ${d.verdict}` : '';
      case 'approval_requested': return d.risk_class ? `Risiko: ${d.risk_class}` : '';
      case 'approval_resolved': return `${d.status ?? '?'} von ${event.actor ?? '?'}`;
      case 'policy_blocked': return d.decision ? `Entscheidung: ${d.decision}` : '';
      case 'error': case 'executor_error': return d.error ?? '';
      default: return '';
    }
  }

  function riskTone(risk) {
    switch (risk) {
      case 'R0': return 'idle';
      case 'R1': return 'ok';
      case 'R2': return 'accent';
      case 'R3': return 'warn';
      case 'R4': return 'bad';
      default: return 'idle';
    }
  }

  function statusLine(mission, taskCount) {
    switch (mission.status) {
      case 'queued': return 'Wird eingeplant …';
      case 'planning': return 'Hufi plant die nächsten Schritte …';
      case 'running':
        if (taskCount > 1) return `${taskCount} Agenten arbeiten daran …`;
        if (taskCount === 1) return 'Ein Agent arbeitet daran …';
        return 'Hufi arbeitet daran …';
      case 'retrying': return 'Ein Schritt wird noch einmal versucht …';
      case 'review': return 'Hufi prüft das Ergebnis …';
      case 'blocked': return 'Kommt gerade nicht weiter — Hufi sucht einen anderen Weg …';
      case 'waiting_approval': return 'Wartet auf deine Freigabe …';
      default: return '';
    }
  }

  // ---------- DOM refs (assigned in render()) ----------
  let threadEl, emptyEl, listEl, inputEl, sendBtn, micBtn;
  const state = { missions: new Map() };
  let currentAgentId = null;

  function scrollToBottom() {
    requestAnimationFrame(() => { threadEl.scrollTop = threadEl.scrollHeight; });
  }

  // ---------- Routine detection (MUSS 1) ----------
  // A recurring-sounding chat message ("Mach das jeden Montag um 8 Uhr.")
  // must never be silently run as a one-off mission -- the backend routine
  // grammar (hufiagents/workforce/routines.py) only understands
  // "every day at HH:MM" / "every <weekday> at HH:MM", so this detector's
  // only job is: recognise the small set of German phrasings that map onto
  // that exact grammar, and be honest (ask, or say "not supported yet")
  // about everything else rather than guessing. No cron syntax anywhere in
  // the UI; every "clear" result below is created through the real
  // POST /routines API, never faked client-side.
  const WEEKDAYS_DE_EN = {
    montag: 'monday', montags: 'monday',
    dienstag: 'tuesday', dienstags: 'tuesday',
    mittwoch: 'wednesday', mittwochs: 'wednesday',
    donnerstag: 'thursday', donnerstags: 'thursday',
    freitag: 'friday', freitags: 'friday',
    samstag: 'saturday', samstags: 'saturday',
    sonnabend: 'saturday', sonnabends: 'saturday',
    sonntag: 'sunday', sonntags: 'sunday',
  };
  const WEEKDAY_LABEL_DE = {
    monday: 'montags', tuesday: 'dienstags', wednesday: 'mittwochs',
    thursday: 'donnerstags', friday: 'freitags', saturday: 'samstags', sunday: 'sonntags',
  };

  function pad2(n) { return String(n).padStart(2, '0'); }

  function extractTimeDe(lower) {
    let m = lower.match(/\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:uhr)?\b/);
    if (m) return `${pad2(m[1])}:${m[2]}`;
    m = lower.match(/\b([01]?\d|2[0-3])\s*uhr\b/);
    if (m) return `${pad2(m[1])}:00`;
    m = lower.match(/\bum\s+([01]?\d|2[0-3])\b(?!\s*[:.]\d)/);
    if (m) return `${pad2(m[1])}:00`;
    return null;
  }

  function detectRoutineIntent(text) {
    const lower = text.toLowerCase();

    let weekdayEn = null;
    for (const word of Object.keys(WEEKDAYS_DE_EN)) {
      if (new RegExp(`\\b${word}\\b`).test(lower)) { weekdayEn = WEEKDAYS_DE_EN[word]; break; }
    }
    const dailySignal = /\b(t(ä|ae)glich|jeden tag|jeden morgen|jeden abend)\b/.test(lower);
    const weeklyVague = /\b(jede woche|w(ö|oe)chentlich)\b/.test(lower) && !weekdayEn;
    const monthlySignal = /\b(jeden monat|monatlich)\b/.test(lower);
    const tomorrowSignal = /\bmorgen\s+um\b/.test(lower) && !/\bjeden morgen\b/.test(lower);
    const time = extractTimeDe(lower);

    if (monthlySignal) {
      return { type: 'unsupported', message: 'Monatliche Routinen kann ich in dieser Version noch nicht einrichten — nur täglich oder an einem festen Wochentag. Sag mir gern einen festen Wochentag, zum Beispiel „jeden Montag um 8 Uhr“.' };
    }
    if (tomorrowSignal) {
      return { type: 'unsupported', message: 'Einzelne Aufträge kann ich aktuell nur sofort ausführen, noch nicht für einen späteren Zeitpunkt vormerken. Soll ich das gleich jetzt erledigen, oder meintest du eine wiederkehrende Routine, zum Beispiel „jeden Montag um 8 Uhr“?' };
    }
    if (weeklyVague) {
      return { type: 'clarify', question: 'Das klingt nach einer wiederkehrenden Aufgabe — an welchem Wochentag soll ich das erledigen? Zum Beispiel „jeden Montag um 8 Uhr“.' };
    }
    if (weekdayEn || dailySignal) {
      if (!time) {
        return { type: 'clarify', question: 'Gerne richte ich das als Routine ein — um wie viel Uhr soll ich das erledigen?' };
      }
      const schedule = weekdayEn ? `every ${weekdayEn} at ${time}` : `every day at ${time}`;
      const label = weekdayEn ? `${WEEKDAY_LABEL_DE[weekdayEn]} um ${time}` : `täglich um ${time}`;
      const cadence = weekdayEn ? 'wöchentliche' : 'tägliche';
      return { type: 'clear', schedule, label, cadence };
    }
    return null;
  }

  // ---------- Shell ----------
  function render() {
    Hufi.mount.chat.innerHTML = '';
    // Hufi.el() (app.js) returns only the string's first element, so the
    // thread and the input bar -- two sibling elements -- must be built and
    // appended separately rather than passed to one Hufi.el() call.
    Hufi.mount.chat.appendChild(Hufi.el(`
      <div class="chat-thread" id="chatThread">
        <div class="chat-col">
          <div class="chat-empty" id="chatEmpty">
            <div class="chat-empty__avatar avatar avatar--lg">H</div>
            <h1 class="chat-empty__title">Was soll ich für dich erledigen?</h1>
            <p class="chat-empty__sub muted">Sag mir dein Ziel. Ich kümmere mich um den Rest.</p>
            <div class="chat-chips" id="chatChips"></div>
          </div>
          <div class="chat-msglist" id="chatMsgList" hidden></div>
        </div>
      </div>
    `));
    Hufi.mount.chat.appendChild(Hufi.el(`
      <div class="chat-inputbar">
        <div class="chat-col">
          <button type="button" class="chat-mic" id="chatMic" title="Spracheingabe (bald verfügbar)" disabled>🎤</button>
          <textarea class="chat-input" id="chatInput" rows="1" placeholder="Was soll ich für dich erledigen?"></textarea>
          <button type="button" class="chat-send" id="chatSend" title="Senden">➤</button>
        </div>
      </div>
    `));

    threadEl = document.getElementById('chatThread');
    emptyEl = document.getElementById('chatEmpty');
    listEl = document.getElementById('chatMsgList');
    inputEl = document.getElementById('chatInput');
    sendBtn = document.getElementById('chatSend');
    micBtn = document.getElementById('chatMic');

    const chips = document.getElementById('chatChips');
    STARTERS.forEach((label) => {
      const chip = Hufi.el(`<button type="button" class="chip">${esc(label)}</button>`);
      chip.addEventListener('click', () => {
        inputEl.value = label;
        inputEl.focus();
      });
      chips.appendChild(chip);
    });

    sendBtn.addEventListener('click', handleSend);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    });

    Hufi.mount.topbarTitle.textContent = 'Hufi';
  }

  function handleSend() {
    const text = inputEl.value.trim();
    if (!text) return;
    const routine = detectRoutineIntent(text);
    if (routine && routine.type === 'clear') {
      inputEl.value = '';
      inputEl.style.height = 'auto';
      startRoutineTurn(text, routine);
      return;
    }
    if (routine && (routine.type === 'clarify' || routine.type === 'unsupported')) {
      inputEl.value = '';
      inputEl.style.height = 'auto';
      startClarifyTurn(text, routine.message || routine.question);
      return;
    }
    inputEl.value = '';
    inputEl.style.height = 'auto';
    startTurn(text);
  }

  function appendUserBubble(text) {
    if (!emptyEl.hidden) {
      emptyEl.hidden = true;
      listEl.hidden = false;
    }
    const turnEl = Hufi.el(`
      <div class="turn" data-fade-in>
        <div class="bubble bubble--user" data-fade-in></div>
        <div class="bubble bubble--hufi" data-fade-in></div>
      </div>
    `);
    turnEl.querySelector('.bubble--user').textContent = text;
    listEl.appendChild(turnEl);
    scrollToBottom();
    return turnEl;
  }

  // A routine-shaped message that is too ambiguous for the narrow backend
  // schedule grammar (weekly-without-a-day, monthly, "tomorrow at") gets an
  // honest Hufi reply instead of either a fake routine or a misinterpreted
  // one-off mission -- no mission or routine is created either way.
  function startClarifyTurn(text, message) {
    const turnEl = appendUserBubble(text);
    turnEl.querySelector('.bubble--hufi').textContent = message;
  }

  function startRoutineTurn(text, routine) {
    const turnEl = appendUserBubble(text);
    const hufiBubble = turnEl.querySelector('.bubble--hufi');
    hufiBubble.textContent = `Ich richte daraus eine ${routine.cadence} Routine ein: ${text} — ${routine.label}.`;

    const card = Hufi.el(`
      <div class="card routine-confirm" data-fade-in>
        <div class="row routine-confirm__actions">
          <button type="button" class="btn btn--primary" data-action="create">Erstellen</button>
          <button type="button" class="btn btn--ghost" data-action="change">Ändern</button>
          <button type="button" class="btn btn--ghost" data-action="cancel">Abbrechen</button>
        </div>
        <div class="routine-confirm__status" hidden></div>
      </div>
    `);
    turnEl.appendChild(card);
    scrollToBottom();

    const statusEl = card.querySelector('.routine-confirm__status');
    const actionsEl = card.querySelector('.routine-confirm__actions');

    card.querySelector('[data-action="create"]').addEventListener('click', async () => {
      actionsEl.querySelectorAll('button').forEach((b) => { b.disabled = true; });
      try {
        const created = await Hufi.api('/routines', {
          method: 'POST',
          body: JSON.stringify({
            owner_agent_id: currentAgentId || 'builder',
            mission_template: { outcome: text },
            schedule: routine.schedule,
            timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone) || 'Europe/Berlin',
          }),
        });
        actionsEl.hidden = true;
        statusEl.hidden = false;
        statusEl.textContent = created.next_run
          ? `Routine eingerichtet. Nächster Lauf: ${Hufi.fmtTime(created.next_run)}.`
          : 'Routine eingerichtet.';
      } catch (error) {
        actionsEl.querySelectorAll('button').forEach((b) => { b.disabled = false; });
        statusEl.hidden = false;
        statusEl.textContent = 'Die Routine konnte nicht eingerichtet werden: ' + error.message;
      }
    });

    card.querySelector('[data-action="change"]').addEventListener('click', () => {
      actionsEl.hidden = true;
      statusEl.hidden = false;
      statusEl.textContent = 'Kein Problem — passe den Text unten an und sende ihn erneut.';
      inputEl.value = text;
      inputEl.focus();
    });

    card.querySelector('[data-action="cancel"]').addEventListener('click', () => {
      actionsEl.hidden = true;
      statusEl.hidden = false;
      statusEl.textContent = 'Abgebrochen — nichts wurde eingerichtet.';
    });
  }

  // ---------- Turns (one per sent message / mission) ----------
  async function startTurn(text) {
    if (!emptyEl.hidden) {
      emptyEl.hidden = true;
      listEl.hidden = false;
    }

    const turnEl = Hufi.el(`
      <div class="turn" data-fade-in>
        <div class="bubble bubble--user" data-fade-in></div>
        <div class="bubble bubble--hufi" data-fade-in>Alles klar. Ich prüfe das mit meinem Team.</div>
        <div class="progress-lines"></div>
        <button type="button" class="details-toggle">Details anzeigen</button>
        <div class="details-panel" hidden><div class="details-timeline"><p class="empty-hint">Lädt …</p></div></div>
        <div class="approval-slot"></div>
        <div class="result-slot"></div>
      </div>
    `);
    turnEl.querySelector('.bubble--user').textContent = text;
    listEl.appendChild(turnEl);
    scrollToBottom();

    wireDetailsToggle(turnEl, null);

    let mission;
    try {
      // QA fix (MUSS 3): a hardcoded risk_ceiling here meant the frontend
      // was making a risk decision that belongs to the backend policy layer
      // (docs/product/PRODUCT-FLOW-FINDINGS.md). Omit it entirely and let
      // the server's own default (and, per task/agent, the real policy
      // engine) decide -- the approval card below already renders correctly
      // whenever the backend actually produces a waiting_approval mission.
      mission = await Hufi.api('/missions', {
        method: 'POST',
        body: JSON.stringify({ outcome: text }),
      });
    } catch (error) {
      const hufiBubble = turnEl.querySelector('.bubble--hufi');
      hufiBubble.textContent = 'Das hat leider nicht geklappt: ' + error.message;
      return;
    }

    wireDetailsToggle(turnEl, mission.id);
    trackMission(mission.id, turnEl);
  }

  function wireDetailsToggle(turnEl, missionId) {
    const toggle = turnEl.querySelector('.details-toggle');
    const panel = turnEl.querySelector('.details-panel');
    const timelineEl = panel.querySelector('.details-timeline');
    toggle.onclick = async () => {
      if (!missionId) return;
      const opening = panel.hidden;
      panel.hidden = !opening;
      toggle.textContent = opening ? 'Details verbergen' : 'Details anzeigen';
      if (!opening) return;
      timelineEl.innerHTML = '<p class="empty-hint">Lädt …</p>';
      try {
        const events = await Hufi.api(`/audit?mission_id=${encodeURIComponent(missionId)}&limit=100`);
        timelineEl.innerHTML = renderTimeline(events);
      } catch (error) {
        timelineEl.innerHTML = '<p class="empty-hint">Details gerade nicht verfügbar.</p>';
      }
      scrollToBottom();
    };
  }

  function renderTimeline(events) {
    if (!events.length) return '<p class="empty-hint">Noch keine Ereignisse.</p>';
    return '<ul class="audit-timeline">' + events.map((e) => {
      const label = EVENT_LABELS[e.event_type] || e.event_type;
      const note = eventNote(e);
      return `<li class="audit-timeline__item" style="--dot:${eventDot(e.event_type)}">
        <div class="audit-timeline__meta">${esc(Hufi.fmtTime(e.ts))} · ${esc(e.actor || '—')}</div>
        <div class="audit-timeline__label">${esc(label)}</div>
        ${note ? `<div class="audit-timeline__summary muted">${esc(note)}</div>` : ''}
        <details class="audit-timeline__raw"><summary>Rohdaten</summary><pre>${esc(JSON.stringify(e, null, 2))}</pre></details>
      </li>`;
    }).join('') + '</ul>';
  }

  // Honest, state-driven 3-line checklist (never mission-specific invented
  // steps, no UUIDs/status codes) for the normal in-progress path. Stage 1
  // is "done" the moment we're tracking a mission at all (it already
  // exists); stage 2/3 reflect the real, current mission.status.
  function progressChecklistHtml(taskCount, status) {
    const workLabel = taskCount > 1 ? `${taskCount} Agenten arbeiten daran` : 'Hufi arbeitet daran';
    const stage2 = status === 'review' ? 'done' : 'current';
    const stage3 = status === 'review' ? 'current' : 'pending';
    const mark = { done: '✓', current: '●', pending: '○' };
    const steps = [
      { label: 'Auftrag angenommen', state: 'done' },
      { label: workLabel, state: stage2 },
      { label: 'Ergebnis wird geprüft', state: stage3 },
    ];
    return '<div class="progress-checklist" data-fade-in>' + steps.map((s) => `
      <div class="progress-step progress-step--${s.state}"><span class="progress-step__mark">${mark[s.state]}</span><span>${esc(s.label)}</span></div>
    `).join('') + '</div>';
  }

  // ---------- Mission polling ----------
  function trackMission(missionId, turnEl) {
    const progressEl = turnEl.querySelector('.progress-lines');
    const approvalSlot = turnEl.querySelector('.approval-slot');
    const resultSlot = turnEl.querySelector('.result-slot');
    let lastHtml = null;
    let timer = null;
    let stopped = false;

    function setProgress(html) {
      if (html === lastHtml) return;
      lastHtml = html;
      progressEl.innerHTML = html;
    }

    async function tick() {
      if (stopped) return;
      let mission, tasks;
      try {
        mission = await Hufi.api(`/missions/${encodeURIComponent(missionId)}`);
        tasks = await Hufi.api(`/tasks?mission_id=${encodeURIComponent(missionId)}`).catch(() => []);
      } catch (error) {
        return; // transient network hiccup — keep polling silently
      }
      if (stopped) return;

      if (mission.status === 'waiting_approval') {
        setProgress(`<div class="progress-line" data-fade-in>${esc(statusLine(mission, tasks.length))}</div>`);
        await ensureApprovalCard(missionId, tasks, approvalSlot, turnEl);
      } else if (['blocked', 'retrying'].includes(mission.status)) {
        setProgress(`<div class="progress-line" data-fade-in>${esc(statusLine(mission, tasks.length))}</div>`);
      } else if (!TERMINAL_STATUSES.includes(mission.status)) {
        setProgress(progressChecklistHtml(tasks.length, mission.status));
      }

      if (TERMINAL_STATUSES.includes(mission.status)) {
        stopped = true;
        if (timer) clearInterval(timer);
        setProgress('');
        renderResult(resultSlot, mission);
        scrollToBottom();
      }
    }

    state.missions.set(missionId, { turnEl });
    tick();
    timer = setInterval(tick, POLL_MS);
  }

  async function ensureApprovalCard(missionId, tasks, approvalSlot, turnEl) {
    if (approvalSlot.dataset.rendered === '1') return;
    let approvals;
    try {
      approvals = await Hufi.api('/approvals?limit=20');
    } catch (error) {
      return;
    }
    const taskIds = new Set(tasks.map((t) => t.id));
    let approval = approvals.find((a) => a.status === 'pending' && taskIds.has(a.task_id));
    if (!approval) {
      // QA fix (MUSS 3): an ApprovalRequest is created against EITHER
      // task_id OR tool_call_id (never both -- see docs/ARCHITECTURE.md
      // Sec3.7), and a real R3 gate (e.g. a git push) is a *tool-call*-level
      // approval, so it only ever carries tool_call_id. Matching on
      // task_id alone silently never found these -- a real, reachable
      // approval would still never have rendered a card. Cross-reference
      // via the tracked tasks' own tool-calls as a second pass.
      const pending = approvals.filter((a) => a.status === 'pending' && a.tool_call_id);
      if (pending.length) {
        const callLists = await Promise.all(
          [...taskIds].map((id) => Hufi.api(`/tool-calls?task_id=${encodeURIComponent(id)}`).catch(() => []))
        );
        const ownToolCallIds = new Set(callLists.flat().map((c) => c.id));
        approval = pending.find((a) => ownToolCallIds.has(a.tool_call_id));
      }
    }
    if (!approval) return;
    approvalSlot.dataset.rendered = '1';
    renderApprovalCard(approvalSlot, approval);
    scrollToBottom();
  }

  function renderApprovalCard(container, approval) {
    const card = Hufi.el(`
      <div class="card approval-card" data-fade-in>
        <div class="approval-card__head">Hufi möchte etwas tun</div>
        <div class="approval-card__body">${esc(approval.summary || 'Ein Schritt braucht deine Zustimmung.')}</div>
        <details class="approval-card__details">
          <summary>Details</summary>
          <div class="approval-card__details-body">
            <span class="pill tone-${riskTone(approval.risk_class)}">${esc(approval.risk_class)}</span>
          </div>
        </details>
        <div class="approval-card__actions row">
          <button type="button" class="btn btn--primary approval-approve">Zulassen</button>
          <button type="button" class="btn btn--ghost approval-deny">Ablehnen</button>
        </div>
        <div class="approval-card__status" hidden></div>
      </div>
    `);
    container.appendChild(card);

    const approveBtn = card.querySelector('.approval-approve');
    const denyBtn = card.querySelector('.approval-deny');
    const statusEl = card.querySelector('.approval-card__status');
    const actionsEl = card.querySelector('.approval-card__actions');

    async function resolve(action, label) {
      approveBtn.disabled = true;
      denyBtn.disabled = true;
      try {
        await Hufi.api(`/approvals/${encodeURIComponent(approval.id)}/${action}`, {
          method: 'POST',
          body: JSON.stringify({ note: '' }),
        });
        actionsEl.hidden = true;
        statusEl.hidden = false;
        statusEl.textContent = label;
        statusEl.className = 'approval-card__status ' + (action === 'approve' ? 'muted' : 'muted');
      } catch (error) {
        statusEl.hidden = false;
        statusEl.textContent = 'Fehlgeschlagen: ' + error.message;
        approveBtn.disabled = false;
        denyBtn.disabled = false;
      }
    }

    approveBtn.addEventListener('click', () => resolve('approve', 'Freigegeben. Hufi macht weiter.'));
    denyBtn.addEventListener('click', () => resolve('deny', 'Abgelehnt. Hufi sucht einen anderen Weg.'));
  }

  function renderResult(resultSlot, mission) {
    const isFailed = mission.status === 'failed';
    const isCancelled = mission.status === 'cancelled';
    const title = isFailed ? 'Nicht geschafft' : isCancelled ? 'Abgebrochen' : 'Fertig';
    const mark = isFailed ? '✕' : isCancelled ? '○' : '✓';
    const tone = isFailed ? 'bad' : isCancelled ? 'idle' : 'ok';
    const raw = (mission.result || '').trim();
    const fallback = isFailed
      ? 'Es ist ein Fehler aufgetreten. Details siehe unten.'
      : isCancelled
        ? 'Die Mission wurde abgebrochen.'
        : 'Fertig.';
    const full = raw || fallback;
    const SHORT_LEN = 320;
    const isLong = full.length > SHORT_LEN;
    const short = isLong ? full.slice(0, SHORT_LEN).trim() + '…' : full;

    const card = Hufi.el(`
      <div class="card result-card" data-fade-in>
        <div class="row result-card__head">
          <span class="pill tone-${tone}">${mark} ${esc(title)}</span>
        </div>
        <div class="result-card__text"></div>
        <div class="row result-card__actions">
          <button type="button" class="btn btn--sm btn--primary result-continue">Weiterarbeiten</button>
          ${isLong ? '<button type="button" class="btn btn--sm btn--ghost result-expand">Bericht öffnen</button>' : ''}
          <button type="button" class="btn btn--sm btn--ghost result-dismiss">Später</button>
        </div>
      </div>
    `);
    const textEl = card.querySelector('.result-card__text');
    renderMarkdown(textEl, short);

    // "Weiterarbeiten": the natural next action after a result is to keep
    // talking to Hufi about it -- jumps straight to the composer.
    card.querySelector('.result-continue').addEventListener('click', () => {
      inputEl.focus();
      inputEl.scrollIntoView({ block: 'nearest' });
    });

    const expandBtn = card.querySelector('.result-expand');
    if (expandBtn) {
      let expanded = false;
      expandBtn.addEventListener('click', () => {
        expanded = !expanded;
        renderMarkdown(textEl, expanded ? full : short);
        expandBtn.textContent = expanded ? 'Weniger anzeigen' : 'Bericht öffnen';
      });
    }

    const mini = Hufi.el('<button type="button" class="result-mini" hidden>Ergebnis anzeigen</button>');
    const dismissBtn = card.querySelector('.result-dismiss');
    dismissBtn.addEventListener('click', () => {
      card.hidden = true;
      mini.hidden = false;
    });
    mini.addEventListener('click', () => {
      card.hidden = false;
      mini.hidden = true;
    });

    resultSlot.appendChild(card);
    resultSlot.appendChild(mini);
  }

  // Small safe Markdown subset. Text is always inserted through textContent;
  // links only accept http(s), so model output cannot introduce HTML/script.
  function renderMarkdown(target, source) {
    target.replaceChildren();
    const inline = (text) => {
      const span = document.createElement('span');
      const parts = text.split(/(`[^`]*`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]*\))/g);
      for (const part of parts) {
        if (/^`/.test(part)) { const code = document.createElement('code'); code.textContent = part.slice(1, -1); span.append(code); }
        else if (/^\*\*/.test(part)) { const strong = document.createElement('strong'); strong.textContent = part.slice(2, -2); span.append(strong); }
        else if (/^\*/.test(part)) { const em = document.createElement('em'); em.textContent = part.slice(1, -1); span.append(em); }
        else { const match = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/); if (match) { const link = document.createElement('a'); link.href = match[2]; link.textContent = match[1]; link.target = '_blank'; link.rel = 'noopener noreferrer'; span.append(link); } else span.append(document.createTextNode(part)); }
      }
      return span;
    };
    let list = null;
    for (const line of source.split('\n')) {
      const heading = line.match(/^(#{1,3})\s+(.+)/); const bullet = line.match(/^[-*]\s+(.+)/); const number = line.match(/^\d+\.\s+(.+)/);
      if (heading) { list = null; const node = document.createElement(`h${heading[1].length}`); node.append(inline(heading[2])); target.append(node); }
      else if (bullet || number) { const ordered = Boolean(number); if (!list || list.tagName !== (ordered ? 'OL' : 'UL')) { list = document.createElement(ordered ? 'ol' : 'ul'); target.append(list); } const item = document.createElement('li'); item.append(inline((bullet || number)[1])); list.append(item); }
      else if (line.trim()) { list = null; const p = document.createElement('p'); p.append(inline(line)); target.append(p); }
    }
  }

  // ---------- Public contract for the sidebar (agents.js) ----------
  Hufi.chat = {
    openAgent(agentId) {
      if (!threadEl) return;
      if (!agentId) return;
      currentAgentId = agentId;
      if (!emptyEl.hidden) {
        emptyEl.hidden = true;
        listEl.hidden = false;
      }
      // QA fix: this used to show the raw backend id ("builder") instead of
      // the display name already computed next to it in the sidebar
      // ("Builder") -- a small but real jargon leak into the normal flow.
      const displayName = (Hufi.agents && typeof Hufi.agents.humanizeId === 'function')
        ? Hufi.agents.humanizeId(agentId)
        : String(agentId);
      const note = Hufi.el(`<div class="system-note" data-fade-in></div>`);
      note.textContent = `Chat mit ${displayName}`;
      listEl.appendChild(note);
      Hufi.mount.topbarTitle.textContent = displayName;
      scrollToBottom();
      if (inputEl) inputEl.focus();
    },
  };

  Hufi.onReady(() => {
    render();
  });
})();
