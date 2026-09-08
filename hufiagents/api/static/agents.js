/* ==========================================================================
   Hufi — Agent Experience module (sidebar contact list + agent detail pane).
   Owned by this feature module. Builds on the Hufi.* contract from app.js;
   never touches app.js/app.css/index.html/chat.js/chat.css.

   Backend contract: agents and routines are durable REST resources. The UI
   refreshes its own state after a mutation; it never fakes success.
     - GET /audit          REQUIRES `mission_id` as a query param (verified
                            live: GET /audit?limit=5 -> 422 "mission_id ...
                            Field required"). There is NO way to fetch "all
                            recent audit events across missions" in one call,
                            despite what the brief assumed. This module works
                            around that by pulling recent missions and
                            fetching each mission's audit trail, then merging
                            + filtering client-side by actor. See
                            fetchAggregatedAudit() below.
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});

  // ---------- Local state ----------
  let agentsCache = [];
  let auditAggCache = null; // { ts, data }

  // ---------- Friendly copy helpers ----------

  function humanizeId(id) {
    return String(id || '')
      .replace(/[_-]+/g, ' ')
      .trim()
      .split(' ')
      .filter(Boolean)
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ') || String(id || '');
  }

  // Known registry roles get a warm German one-liner. Anything unrecognised
  // falls back to the raw backend text rather than inventing capabilities.
  const ROLE_TRANSLATIONS = {
    'Bounded workspace builder':
      'Arbeitet eigenständig in einer abgesicherten Umgebung.',
    'Independent mechanical acceptance reviewer':
      'Prüft Ergebnisse unabhängig, bevor sie freigegeben werden.',
    'Bounded git push / draft-PR workflow':
      'Reicht Änderungen kontrolliert per Git ein.',
    'Mission intake, prioritisation, coordination':
      'Nimmt neue Aufgaben an, priorisiert und koordiniert.',
    'Per-project coordination across HufiAgents/HufManager':
      'Koordiniert projektübergreifend zwischen deinen Projekten.',
  };

  function friendlyRole(role) {
    if (ROLE_TRANSLATIONS[role]) return ROLE_TRANSLATIONS[role];
    // Strip trailing "(path/to/file.py, ...)" implementation-detail asides
    // that some registry roles carry — those are jargon, not a persona.
    const stripped = String(role || '').replace(/\s*\([^)]*\.py[^)]*\)\s*$/, '');
    return stripped || 'Noch keine Rollenbeschreibung.';
  }

  const STATUS_LABEL = { active: 'Aktiv', disabled: 'Deaktiviert' };
  function statusTone(status) {
    return status === 'active' ? 'tone-ok' : 'tone-idle';
  }

  // Friendly, non-technical labels for audit event_type — never surface the
  // raw event_type, risk codes, provider ids or JSON here (that's reserved
  // for the Details/System view).
  const EVENT_LABELS = {
    mission_created: 'Neue Aufgabe gestartet',
    task_created: 'Teilaufgabe angelegt',
    project_bound: 'Projekt verknüpft',
    agent_assigned: 'Wurde zugewiesen',
    model_call: 'Denkt nach …',
    model_result: 'Antwort erhalten',
    tool_call: 'Aktion angefragt',
    tool_started: 'Aktion gestartet',
    tool_result: 'Aktion abgeschlossen',
    tool_reused: 'Ergebnis wiederverwendet',
    review: 'Ergebnis geprüft',
    approval_requested: 'Freigabe angefragt',
    approval_resolved: 'Freigabe entschieden',
    policy_blocked: 'Von Richtlinie gestoppt',
    state_transition: 'Status geändert',
    recovery: 'Nach Neustart wiederhergestellt',
    error: 'Fehler aufgetreten',
    executor_error: 'Ausführungsfehler',
    executor_interrupted: 'Ausführung unterbrochen',
    agent_registered: 'Wurde registriert',
  };
  function eventLabel(type) {
    return EVENT_LABELS[type] || 'Aktivität';
  }
  function eventTone(type) {
    if (['error', 'executor_error', 'policy_blocked'].includes(type)) return 'tone-bad';
    if (['approval_requested', 'executor_interrupted', 'recovery'].includes(type)) return 'tone-warn';
    if (['tool_result', 'review', 'approval_resolved', 'state_transition'].includes(type)) return 'tone-ok';
    return 'tone-idle';
  }

  // ---------- Avatar helpers ----------

  function hashHue(str) {
    let h = 0;
    const s = String(str || '');
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % 360;
  }

  function avatarColor(id) {
    return `hsl(${hashHue(id)}, 58%, 42%)`;
  }

  function initials(name) {
    const words = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[1][0]).toUpperCase();
  }

  function avatarHtml(agent, sizeClass) {
    const name = humanizeId(agent.id);
    const color = avatarColor(agent.id);
    return `<span class="avatar ${sizeClass}" style="background:${color};color:#fff;">${Hufi.esc(initials(name))}</span>`;
  }

  // ---------- Aggregated audit (works around /audit requiring mission_id) ----------

  async function fetchAggregatedAudit({ missionsLimit = 25, perMissionLimit = 50, maxAgeMs = 15000 } = {}) {
    const now = Date.now();
    if (auditAggCache && now - auditAggCache.ts < maxAgeMs) return auditAggCache.data;
    let missions = [];
    try {
      missions = await Hufi.api(`/missions?limit=${missionsLimit}`);
    } catch (e) {
      missions = [];
    }
    const chunks = await Promise.all(
      missions.map((m) =>
        Hufi.api(`/audit?mission_id=${encodeURIComponent(m.id)}&limit=${perMissionLimit}`).catch(() => [])
      )
    );
    const merged = chunks.flat();
    merged.sort((a, b) => new Date(b.ts) - new Date(a.ts));
    auditAggCache = { ts: now, data: merged };
    return merged;
  }

  // ---------- Sidebar list ----------

  function agentRowHtml(agent) {
    const name = humanizeId(agent.id);
    const tone = statusTone(agent.status);
    const label = STATUS_LABEL[agent.status] || agent.status;
    return `
      <button type="button" class="agent-row" data-id="${Hufi.esc(agent.id)}" data-fade-in>
        ${avatarHtml(agent, 'avatar--sm')}
        <span class="agent-row-main">
          <span class="agent-row-name">${Hufi.esc(name)}</span>
          <span class="agent-row-role muted">${Hufi.esc(friendlyRole(agent.role))}</span>
        </span>
        <span class="pill ${tone}">${Hufi.esc(label)}</span>
      </button>`;
  }

  function renderSidebar(agents) {
    const list = Hufi.mount.sidebarList;
    list.innerHTML = '';
    if (!agents.length) {
      list.appendChild(Hufi.el('<p class="empty-hint">Keine Hufis gefunden.</p>'));
      return;
    }
    for (const agent of agents) {
      const row = Hufi.el(agentRowHtml(agent));
      row.addEventListener('click', () => selectAgent(agent));
      list.appendChild(row);
    }
  }

  function selectAgent(agent) {
    if (Hufi.chat && typeof Hufi.chat.openAgent === 'function') {
      Hufi.chat.openAgent(agent.id);
    }
    Hufi.rightPane.show(humanizeId(agent.id), (container) => renderAgentDetail(container, agent));
    if (typeof Hufi.closeSidebar === 'function') Hufi.closeSidebar();
  }

  function wireSearch() {
    const input = document.getElementById('sidebarSearch');
    if (!input) return;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      if (!q) return renderSidebar(agentsCache);
      const filtered = agentsCache.filter((a) => {
        const name = humanizeId(a.id).toLowerCase();
        const role = friendlyRole(a.role).toLowerCase();
        return name.includes(q) || role.includes(q);
      });
      renderSidebar(filtered);
    });
  }

  async function loadSidebar() {
    try {
      agentsCache = await Hufi.api('/agents');
      renderSidebar(agentsCache);
    } catch (e) {
      Hufi.mount.sidebarList.innerHTML = '';
      Hufi.mount.sidebarList.appendChild(
        Hufi.el(`<p class="empty-hint">Hufis konnten nicht geladen werden: ${Hufi.esc(e.message)}</p>`)
      );
    }
  }

  // ---------- Agent detail (right pane) ----------

  function renderAgentDetail(container, agent) {
    const name = humanizeId(agent.id);
    const tools = (agent.capabilities && agent.capabilities.tools) || [];

    container.appendChild(Hufi.el(`
      <div class="agent-profile" data-fade-in>
        <div class="agent-profile-header">
          ${avatarHtml(agent, 'avatar--lg')}
          <div class="agent-profile-heading">
            <h2 class="agent-profile-name">${Hufi.esc(name)}</h2>
            <p class="muted agent-profile-role">${Hufi.esc(friendlyRole(agent.role))}</p>
            <span class="pill ${statusTone(agent.status)}">${Hufi.esc(STATUS_LABEL[agent.status] || agent.status)}</span>
          </div>
        </div>

        <div class="card agent-computer">
          <div class="row">
            <span class="agent-computer-icon" aria-hidden="true">🖥️</span>
            <div>
              <div class="agent-computer-title">Computer</div>
              <div class="faint">Noch nicht verbunden</div>
            </div>
          </div>
        </div>

        <section class="agent-section">
          <h3>Live-Aktivität</h3>
          <div id="agentActivity"><p class="empty-hint">Lädt …</p></div>
        </section>

        <section class="agent-section">
          <h3>Routinen</h3>
          <div id="agentRoutines" class="card routine-card"><p class="empty-hint">Lädt …</p></div>
        </section>

        <details class="agent-registry">
          <summary>Weitere Informationen</summary>
          <dl class="kv-list">
            <dt>Rollenbeschreibung</dt><dd>${Hufi.esc(agent.role)}</dd>
            <dt>Risikodecke</dt><dd>${Hufi.esc(agent.default_risk_ceiling || '—')}</dd>
          </dl>
          <div class="tag-list-label muted">Werkzeuge</div>
          <div class="tag-list">
            ${tools.length ? tools.map((t) => `<span class="tag">${Hufi.esc(t)}</span>`).join('') : '<span class="faint">Keine</span>'}
          </div>
        </details>

        <div class="agent-detail-footer">
          <button type="button" class="btn btn--ghost btn--sm" id="openSystemView">Details / System</button>
        </div>
      </div>
    `));

    container.querySelector('#openSystemView').addEventListener('click', () => openSystemView());

    loadAgentActivity(container, agent.id);
    loadRoutines(container, agent.id);
  }

  async function loadRoutines(container, agentId) {
    const target = container.querySelector('#agentRoutines');
    try {
      const routines = await Hufi.api(`/routines?owner_agent_id=${encodeURIComponent(agentId)}`);
      target.innerHTML = routines.map((r) => `<div class="row"><span>${Hufi.esc(r.schedule)}</span><span class="pill ${r.enabled ? 'tone-ok' : 'tone-idle'}">${r.enabled ? 'Aktiv' : 'Pausiert'}</span><button class="btn btn--ghost btn--sm" data-routine="${Hufi.esc(r.id)}">${r.enabled ? 'Pausieren' : 'Fortsetzen'}</button></div><p class="faint">Nächster Lauf: ${Hufi.esc(r.next_run || 'wird geplant')}</p>`).join('') || '<p class="faint">Keine Routinen.</p>';
      const add = Hufi.el('<button type="button" class="btn btn--ghost btn--sm">Routine anlegen</button>');
      add.addEventListener('click', async () => {
        const schedule = window.prompt('Wann? Zum Beispiel: every monday at 08:00');
        if (!schedule) return;
        try {
          await Hufi.api('/routines', {method: 'POST', body: JSON.stringify({owner_agent_id: agentId, mission_template: {outcome: 'Erstelle einen sicheren Statusbericht.', risk_ceiling: 'R0'}, schedule, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Berlin'})});
          loadRoutines(container, agentId);
        } catch (e) { window.alert(`Routine konnte nicht angelegt werden: ${e.message}`); }
      });
      target.appendChild(add);
      target.querySelectorAll('[data-routine]').forEach((button) => button.addEventListener('click', async () => {
        const action = button.textContent === 'Pausieren' ? 'pause' : 'resume';
        await Hufi.api(`/routines/${encodeURIComponent(button.dataset.routine)}/${action}`, {method: 'POST'});
        loadRoutines(container, agentId);
      }));
    } catch (e) { target.innerHTML = `<p class="empty-hint">Routinen konnten nicht geladen werden: ${Hufi.esc(e.message)}</p>`; }
  }

  async function loadAgentActivity(container, agentId) {
    const target = container.querySelector('#agentActivity');
    if (!target) return;
    try {
      const events = await fetchAggregatedAudit();
      const mine = events.filter((e) => e.actor === agentId).slice(0, 25);
      target.innerHTML = '';
      if (!mine.length) {
        target.appendChild(Hufi.el('<p class="empty-hint">Noch keine Aktivität.</p>'));
        return;
      }
      const list = Hufi.el('<div class="activity-list"></div>');
      for (const e of mine) {
        list.appendChild(Hufi.el(`
          <div class="activity-item" data-fade-in>
            <span class="activity-dot ${eventTone(e.event_type)}"></span>
            <div class="activity-body">
              <div class="activity-label">${Hufi.esc(eventLabel(e.event_type))}</div>
              <div class="activity-time faint">${Hufi.esc(Hufi.fmtTime(e.ts))}</div>
            </div>
          </div>`));
      }
      target.appendChild(list);
    } catch (e) {
      target.innerHTML = '';
      target.appendChild(Hufi.el(`<p class="empty-hint">Aktivität konnte nicht geladen werden.</p>`));
    }
  }

  // ---------- "+ Neuer Hufi" flow ----------

  const SWATCHES = [0, 30, 200, 260, 140, 340].map((h) => `hsl(${h}, 58%, 42%)`);

  function openNewHufiModal() {
    const overlay = Hufi.el(`<div class="modal-overlay" data-fade-in></div>`);
    let selectedColor = SWATCHES[0];

    const card = Hufi.el(`
      <div class="modal-card card" role="dialog" aria-modal="true" aria-label="Neuer Hufi">
        <div class="row">
          <h3 class="spacer">Neuer Hufi</h3>
          <button type="button" class="icon-btn" id="newHufiClose" aria-label="Schließen">✕</button>
        </div>
        <form id="newHufiForm" class="stack">
          <label class="field-label" for="newHufiName">Name</label>
          <input id="newHufiName" type="text" placeholder="z. B. Marketing-Hufi" required />

          <label class="field-label">Avatar-Farbe</label>
          <div class="swatch-row" id="swatchRow"></div>

          <label class="field-label" for="newHufiPurpose">Wofür soll dieser Hufi verantwortlich sein?</label>
          <textarea id="newHufiPurpose" placeholder="Beschreibe kurz den Verantwortungsbereich …" required></textarea>

          <div class="row">
            <span class="spacer"></span>
            <button type="submit" class="btn btn--primary">Hufi anlegen</button>
          </div>
        </form>
        <div id="newHufiMsg" class="new-hufi-msg" hidden></div>
      </div>
    `);
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    // QA fix: nothing here used to move focus into the dialog, and the
    // overlay is appended as the last body child, so a keyboard user tabbed
    // straight through the rest of the page behind it instead of entering
    // the modal at all (verified via automated Tab-simulation). Move focus
    // in on open, trap it while open, and restore it to the trigger on close.
    const previouslyFocused = document.activeElement;
    const swatchRow = card.querySelector('#swatchRow');
    SWATCHES.forEach((color, idx) => {
      const btn = Hufi.el(`<button type="button" class="color-swatch${idx === 0 ? ' is-selected' : ''}" style="background:${color}" aria-label="Farbe wählen"></button>`);
      btn.addEventListener('click', () => {
        selectedColor = color;
        swatchRow.querySelectorAll('.color-swatch').forEach((s) => s.classList.remove('is-selected'));
        btn.classList.add('is-selected');
      });
      swatchRow.appendChild(btn);
    });

    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') previouslyFocused.focus();
    }
    function focusableElements() {
      return Array.from(card.querySelectorAll('button, input, textarea, [href]'))
        .filter((el) => !el.disabled && el.tabIndex !== -1);
    }
    function onKeydown(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      const focusable = focusableElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKeydown);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });
    card.querySelector('#newHufiClose').addEventListener('click', close);
    card.querySelector('#newHufiName').focus();

    card.querySelector('#newHufiForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = card.querySelector('#newHufiForm');
      const msg = card.querySelector('#newHufiMsg');
      const name = card.querySelector('#newHufiName').value.trim();
      const description = card.querySelector('#newHufiPurpose').value.trim();
      const id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      try {
        const created = await Hufi.api('/agents', {method: 'POST', body: JSON.stringify({id, name, role: name, description, capabilities: {tools: [], providers: []}, risk_ceiling: 'R0'})});
        await loadSidebar();
        selectAgent(created);
        close();
      } catch (err) {
        msg.hidden = false;
        msg.textContent = `Hufi konnte nicht angelegt werden: ${err.message}`;
      }
    });
  }

  function wireNewHufiButton() {
    const btn = document.getElementById('newHufiBtn');
    if (btn) btn.addEventListener('click', () => openNewHufiModal());
  }

  // ---------- Details / System (expert view) ----------

  function jsonDump(value) {
    return `<pre class="json-dump">${Hufi.esc(JSON.stringify(value, null, 2))}</pre>`;
  }

  async function renderSystemView(container) {
    container.appendChild(Hufi.el(`
      <div class="system-view" data-fade-in>
        <p class="faint system-view-note">
          Technische Rohdaten (Provider, Risikoklassen, Missions-/Task-IDs, Audit-Events).
          Für den normalen Hufi-Alltag nicht nötig.
        </p>
        <p class="faint">
          <a href="/legacy" target="_blank" rel="noopener">Vollständiges technisches Dashboard öffnen ↗</a>
        </p>
        <section class="agent-section">
          <h3>Agenten (Rohdaten)</h3>
          <div id="sysAgents"><p class="empty-hint">Lädt …</p></div>
        </section>
        <section class="agent-section">
          <h3>Modelle &amp; Provider</h3>
          <div id="sysModels"><p class="empty-hint">Lädt …</p></div>
        </section>
        <section class="agent-section">
          <h3>Projekte</h3>
          <div id="sysProjects"><p class="empty-hint">Lädt …</p></div>
        </section>
        <section class="agent-section">
          <h3>Audit (aktuell)</h3>
          <p class="faint system-view-note">
            Hinweis: <code>/audit</code> verlangt serverseitig eine <code>mission_id</code> –
            diese Ansicht sammelt die letzten Missionen und mischt deren Audit-Trails zusammen.
          </p>
          <div id="sysAudit"><p class="empty-hint">Lädt …</p></div>
        </section>
      </div>
    `));

    const setBox = (id, html) => {
      const el = container.querySelector(id);
      if (el) el.innerHTML = html;
    };

    Hufi.api('/agents').then((data) => setBox('#sysAgents', jsonDump(data)))
      .catch((e) => setBox('#sysAgents', `<p class="empty-hint">Fehler: ${Hufi.esc(e.message)}</p>`));

    Hufi.api('/models').then((data) => setBox('#sysModels', jsonDump(data)))
      .catch((e) => setBox('#sysModels', `<p class="empty-hint">Fehler: ${Hufi.esc(e.message)}</p>`));

    Hufi.api('/projects').then((data) => setBox('#sysProjects', jsonDump(data)))
      .catch((e) => setBox('#sysProjects', `<p class="empty-hint">Fehler: ${Hufi.esc(e.message)}</p>`));

    fetchAggregatedAudit({ missionsLimit: 20, perMissionLimit: 20 })
      .then((data) => setBox('#sysAudit', jsonDump(data.slice(0, 100))))
      .catch((e) => setBox('#sysAudit', `<p class="empty-hint">Fehler: ${Hufi.esc(e.message)}</p>`));
  }

  function openSystemView() {
    Hufi.rightPane.show('System / Details', renderSystemView);
  }

  // ---------- Public contract ----------
  Hufi.agents = {
    getAll: () => agentsCache.slice(),
    getById: (id) => agentsCache.find((a) => a.id === id),
    humanizeId,
    openSystemView,
  };

  // ---------- Init ----------
  Hufi.onReady(() => {
    wireSearch();
    wireNewHufiButton();
    loadSidebar();
  });
})();
