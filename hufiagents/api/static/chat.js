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

  function scrollToBottom() {
    requestAnimationFrame(() => { threadEl.scrollTop = threadEl.scrollHeight; });
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
            <p class="chat-empty__sub muted">Ich bin Hufi. Sag mir dein Ziel — ich hole mir das passende Team und melde mich mit dem Ergebnis.</p>
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
    inputEl.value = '';
    inputEl.style.height = 'auto';
    startTurn(text);
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
      mission = await Hufi.api('/missions', {
        method: 'POST',
        body: JSON.stringify({ outcome: text, risk_ceiling: 'R1' }),
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

  // ---------- Mission polling ----------
  function trackMission(missionId, turnEl) {
    const progressEl = turnEl.querySelector('.progress-lines');
    const approvalSlot = turnEl.querySelector('.approval-slot');
    const resultSlot = turnEl.querySelector('.result-slot');
    let lastLine = null;
    let timer = null;
    let stopped = false;

    function setLine(text) {
      if (text === lastLine) return;
      lastLine = text;
      progressEl.innerHTML = text ? `<div class="progress-line" data-fade-in>${esc(text)}</div>` : '';
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
        setLine(statusLine(mission, tasks.length));
        await ensureApprovalCard(missionId, tasks, approvalSlot, turnEl);
      } else {
        setLine(statusLine(mission, tasks.length));
      }

      if (TERMINAL_STATUSES.includes(mission.status)) {
        stopped = true;
        if (timer) clearInterval(timer);
        setLine('');
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
    const approval = approvals.find((a) => a.status === 'pending' && taskIds.has(a.task_id));
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
          <span class="pill tone-${tone}">${esc(title)}</span>
        </div>
        <div class="result-card__text"></div>
        <div class="row result-card__actions">
          ${isLong ? '<button type="button" class="btn btn--sm btn--ghost result-expand">Bericht öffnen</button>' : ''}
          <button type="button" class="btn btn--sm btn--ghost result-dismiss">Später</button>
        </div>
      </div>
    `);
    const textEl = card.querySelector('.result-card__text');
    textEl.textContent = short;

    const expandBtn = card.querySelector('.result-expand');
    if (expandBtn) {
      let expanded = false;
      expandBtn.addEventListener('click', () => {
        expanded = !expanded;
        textEl.textContent = expanded ? full : short;
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

  // ---------- Public contract for the sidebar (agents.js) ----------
  Hufi.chat = {
    openAgent(agentId) {
      if (!threadEl) return;
      if (!agentId) return;
      if (!emptyEl.hidden) {
        emptyEl.hidden = true;
        listEl.hidden = false;
      }
      const note = Hufi.el(`<div class="system-note" data-fade-in></div>`);
      note.textContent = `Chat mit ${agentId}`;
      listEl.appendChild(note);
      Hufi.mount.topbarTitle.textContent = String(agentId);
      scrollToBottom();
      if (inputEl) inputEl.focus();
    },
  };

  Hufi.onReady(() => {
    render();
  });
})();
