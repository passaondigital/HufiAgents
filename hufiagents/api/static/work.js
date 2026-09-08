/* ==========================================================================
   Hufi — Arbeit / Verlauf (visible-work / transparency view, v1.2).
   Owned by this feature module. Builds on the Hufi.* contract from app.js,
   nav.js and org-data.js; never touches those files or any sibling feature
   module's files.

   Product rule this view exists to enforce: Hufi is not a black box. Never
   fake a working/active state -- there is no real live-session/streaming
   signal wired in this pass, so Live mode always shows an honest "nicht
   verfügbar" text per item rather than a fake pulsing indicator or an empty
   box that looks like a stuck loader.

   Public contract:
     - Hufi.work.openForAgent(agentId)   switch to this view pre-filtered to
                                          one agent (cards.js may call this).

   Data: Hufi.orgData.loadWorkEvidence(query) — see org-data.js. Falls back
   to mock data internally when the real backend isn't reachable; `mock`
   tells us which, and every UI that reads it true must show a visible
   "Entwicklungsmodus — Beispieldaten" note (product rule, see org-data.js
   header comment). Team grouping additionally depends on the org graph
   (Hufi.orgData.isMock()), which can be mock independently of the evidence
   fetch, so both are checked and bannered separately.

   Redaction rule (hard security rule, not a nice-to-have): WorkEvidence.
   content can theoretically contain secret-bearing raw terminal text.
   redacted_at is the backend's signal that content has been cleared for
   display. If redacted_at is null/missing we treat content (and
   artifact_ref, which could just as easily point at something unredacted)
   as NOT YET SAFE TO SHOW and render only the summary sentence plus "Wird
   noch geprüft." -- never dump raw content on the strength of the summary
   alone. Mock evidence never sets redacted_at, so in practice the safe path
   is what you'll see in this dev pass -- that is correct, not a bug.
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});

  const STORAGE_KEY = 'hufi.transparencyMode';
  const MODES = ['einfach', 'transparent', 'live'];
  const MODE_LABELS = { einfach: 'Einfach', transparent: 'Transparent', live: 'Live' };
  const MODE_DESCRIPTIONS = {
    einfach: 'Nur Meilensteine und Ergebnis, ohne Nachweise.',
    transparent: 'Meilensteine und die tatsächlichen Nachweise: Dateien, Tests, Diffs, Berichte.',
    live: 'Laufende Sitzung in Echtzeit, sobald eine echte Verbindung dafür existiert.',
  };

  // ---------- Local state ----------
  let mountedContainer = null;
  let mode = loadMode();
  let agentFilter = null;
  let evidenceItems = [];
  let evidenceMock = false;
  let loading = false;
  let loadError = null;
  let orgUnsubscribe = null;
  let requestToken = 0;

  function loadMode() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (MODES.includes(v)) return v;
    } catch (e) { /* localStorage unavailable */ }
    return 'transparent';
  }
  function saveMode(m) {
    try { localStorage.setItem(STORAGE_KEY, m); } catch (e) { /* ignore */ }
  }

  // ---------- Plain-language copy for evidence_type ----------
  // Never print the raw enum in normal UI -- these are the only place the
  // string "diff"/"test"/"file"/"report"/"routine_result" may appear.
  const EVIDENCE_TYPE_INFO = {
    diff: { verb: 'Git-Änderung vorbereitet', singularNoun: 'Änderung', pluralNoun: 'Änderungen', pluralVerb: 'vorbereitet' },
    test: { verb: 'Test ausgeführt', singularNoun: 'Test', pluralNoun: 'Tests', pluralVerb: 'ausgeführt' },
    file: { verb: 'Datei erstellt', singularNoun: 'Datei', pluralNoun: 'Dateien', pluralVerb: 'erstellt' },
    report: { verb: 'Bericht erstellt', singularNoun: 'Bericht', pluralNoun: 'Berichte', pluralVerb: 'erstellt' },
    routine_result: { verb: 'Routine ausgeführt', singularNoun: 'Routine', pluralNoun: 'Routinen', pluralVerb: 'ausgeführt' },
  };
  const FALLBACK_TYPE_INFO = { verb: 'Aktivität durchgeführt', singularNoun: 'Aufgabe', pluralNoun: 'Aufgaben', pluralVerb: 'erledigt' };
  function typeInfo(type) {
    return EVIDENCE_TYPE_INFO[type] || FALLBACK_TYPE_INFO;
  }

  // ---------- Agent / team resolution ----------
  function agentName(agentId) {
    if (!agentId) return 'Unbekannter Agent';
    const agent = Hufi.agents && typeof Hufi.agents.getById === 'function' ? Hufi.agents.getById(agentId) : null;
    if (Hufi.agents && typeof Hufi.agents.humanizeId === 'function') {
      return Hufi.agents.humanizeId(agent ? agent.id : agentId);
    }
    return agent ? agent.id : agentId;
  }

  function agentTeam(agentId) {
    if (!agentId || !Hufi.orgData || typeof Hufi.orgData.relationshipsFor !== 'function') return null;
    const rels = Hufi.orgData.relationshipsFor('agent', agentId)
      .filter((r) => r.relationship_type === 'member_of_team');
    if (!rels.length) return null;
    const rel = rels.find((r) => r.primary) || rels[0];
    const teamId = rel.source_type === 'team' ? rel.source_id : rel.target_type === 'team' ? rel.target_id : null;
    if (!teamId || typeof Hufi.orgData.getTeamById !== 'function') return null;
    return Hufi.orgData.getTeamById(teamId);
  }

  function isToday(iso) {
    if (!iso) return false;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return false;
    const now = new Date();
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
  }

  // ---------- Data loading ----------
  async function fetchEvidence() {
    const token = ++requestToken;
    loading = true;
    loadError = null;
    renderAll();
    try {
      const query = {};
      if (agentFilter) query.agent_id = agentFilter;
      const res = await Hufi.orgData.loadWorkEvidence(query);
      if (token !== requestToken) return; // a newer request has superseded this one
      evidenceItems = (res.items || []).slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      evidenceMock = !!res.mock;
    } catch (e) {
      if (token !== requestToken) return;
      loadError = e && e.message ? e.message : 'Unbekannter Fehler.';
      evidenceItems = [];
      evidenceMock = false;
    } finally {
      if (token === requestToken) {
        loading = false;
        renderAll();
      }
    }
  }

  // ---------- Rendering ----------
  function mockBanner(text) {
    return Hufi.el(`
      <div class="work-mock-banner" data-fade-in>
        <span class="pill tone-warn">Entwicklungsmodus — Beispieldaten</span>
        <span class="faint">${Hufi.esc(text)}</span>
      </div>
    `);
  }

  function buildHeader() {
    const wrap = document.createElement('div');
    wrap.className = 'work-header';

    wrap.appendChild(Hufi.el(`
      <div class="work-heading">
        <h2 class="work-title">Arbeit &amp; Verlauf</h2>
        <p class="muted work-subtitle">Was Hufi und dein Team wirklich getan haben — nachvollziehbar, nicht nur behauptet.</p>
      </div>
    `));

    const controls = document.createElement('div');
    controls.className = 'work-controls';

    const modeSwitch = document.createElement('div');
    modeSwitch.className = 'work-mode-switch';
    modeSwitch.setAttribute('role', 'tablist');
    modeSwitch.setAttribute('aria-label', 'Transparenzmodus');
    MODES.forEach((m) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'work-mode-btn' + (m === mode ? ' is-active' : '');
      btn.textContent = MODE_LABELS[m];
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-selected', m === mode ? 'true' : 'false');
      btn.addEventListener('click', () => {
        if (mode === m) return;
        mode = m;
        saveMode(m);
        renderAll();
      });
      modeSwitch.appendChild(btn);
    });
    controls.appendChild(modeSwitch);

    const refreshBtn = Hufi.el('<button type="button" class="btn btn--ghost btn--sm work-refresh">Aktualisieren</button>');
    refreshBtn.disabled = loading;
    refreshBtn.addEventListener('click', () => fetchEvidence());
    controls.appendChild(refreshBtn);

    wrap.appendChild(controls);
    wrap.appendChild(Hufi.el(`<p class="faint work-mode-desc">${Hufi.esc(MODE_DESCRIPTIONS[mode])}</p>`));

    if (agentFilter) {
      const chip = Hufi.el(`
        <span class="pill tone-accent work-filter-chip">
          Gefiltert: ${Hufi.esc(agentName(agentFilter))}
          <button type="button" class="work-filter-clear" aria-label="Filter entfernen">✕</button>
        </span>
      `);
      chip.querySelector('.work-filter-clear').addEventListener('click', () => {
        agentFilter = null;
        fetchEvidence();
      });
      const filterRow = document.createElement('div');
      filterRow.className = 'work-filter-row';
      filterRow.appendChild(chip);
      wrap.appendChild(filterRow);
    }

    return wrap;
  }

  function buildSummary() {
    const wrap = document.createElement('div');
    wrap.className = 'work-summary stack';

    if (evidenceMock) {
      wrap.appendChild(mockBanner('Diese Nachweise sind Beispieldaten aus der Entwicklungsumgebung, keine echten Arbeitsergebnisse.'));
    }

    const todayItems = evidenceItems.filter((it) => isToday(it.created_at));
    const totalToday = todayItems.length;

    const summaryCard = document.createElement('div');
    summaryCard.className = 'card work-summary-card';
    summaryCard.appendChild(Hufi.el(`
      <div class="work-summary-heading">${totalToday
        ? Hufi.esc(`Heute erledigt — ${totalToday} ${totalToday === 1 ? 'Aufgabe' : 'Aufgaben'}`)
        : 'Heute noch keine abgeschlossene Aufgabe.'}</div>
    `));

    if (totalToday) {
      const byTeam = new Map(); // teamLabel -> Map(evidence_type -> count)
      todayItems.forEach((it) => {
        const agentId = it.metadata && it.metadata.agent_id;
        const team = agentTeam(agentId);
        const label = team ? team.name : 'Ohne Team-Zuordnung';
        if (!byTeam.has(label)) byTeam.set(label, new Map());
        const typeMap = byTeam.get(label);
        typeMap.set(it.evidence_type, (typeMap.get(it.evidence_type) || 0) + 1);
      });

      const teamList = document.createElement('div');
      teamList.className = 'work-team-list';
      Array.from(byTeam.entries())
        .sort((a, b) => a[0].localeCompare(b[0], 'de'))
        .forEach(([teamLabel, typeMap]) => {
          const parts = Array.from(typeMap.entries()).map(([type, count]) => {
            const info = typeInfo(type);
            const noun = count === 1 ? info.singularNoun : info.pluralNoun;
            return `${count} ${noun} ${info.pluralVerb}`;
          });
          teamList.appendChild(Hufi.el(`
            <div class="work-team-row">
              <span class="work-team-name">${Hufi.esc(teamLabel)}</span>
              <span class="muted work-team-detail">${Hufi.esc(parts.join(', '))}</span>
            </div>
          `));
        });
      summaryCard.appendChild(teamList);

      if (Hufi.orgData.isMock()) {
        summaryCard.appendChild(mockBanner('Die Team-Zuordnung basiert auf Beispieldaten aus der Entwicklungsumgebung (echtes /org existiert noch nicht).'));
      }
    }

    wrap.appendChild(summaryCard);
    return wrap;
  }

  function buildEvidenceCard(item) {
    const info = typeInfo(item.evidence_type);
    const agentId = item.metadata && item.metadata.agent_id;
    const card = Hufi.el(`
      <div class="card evidence-card" data-fade-in>
        <div class="evidence-card__head">
          <span class="evidence-card__title">${Hufi.esc(info.verb)}</span>
          <span class="faint evidence-card__time">${Hufi.esc(Hufi.fmtTime(item.created_at))}</span>
        </div>
        <div class="muted evidence-card__agent">${Hufi.esc(agentName(agentId))}</div>
        <p class="evidence-card__summary">${Hufi.esc(item.summary || 'Keine Beschreibung verfügbar.')}</p>
      </div>
    `);

    const details = document.createElement('details');
    details.className = 'evidence-card__snapshot';
    const summaryEl = document.createElement('summary');
    summaryEl.textContent = 'Snapshot ansehen';
    details.appendChild(summaryEl);

    const body = document.createElement('div');
    body.className = 'evidence-card__snapshot-body';
    const isRedacted = !!item.redacted_at;
    if (isRedacted) {
      let any = false;
      if (item.content) {
        any = true;
        const pre = document.createElement('pre');
        pre.className = 'json-dump';
        pre.textContent = item.content;
        body.appendChild(pre);
      }
      if (item.artifact_ref) {
        any = true;
        body.appendChild(Hufi.el(`<p class="faint">Referenz: <code>${Hufi.esc(item.artifact_ref)}</code></p>`));
      }
      if (!any) body.appendChild(Hufi.el('<p class="faint">Kein Inhalt hinterlegt.</p>'));
    } else {
      // Hard security rule: no redacted_at timestamp means the backend has
      // not confirmed this content is safe to show. Never render content or
      // artifact_ref here, even though they may be present on the object --
      // err toward showing less.
      body.appendChild(Hufi.el('<p class="faint">Wird noch geprüft.</p>'));
    }
    details.appendChild(body);
    card.appendChild(details);

    return card;
  }

  function buildSimpleRow(item) {
    const info = typeInfo(item.evidence_type);
    const agentId = item.metadata && item.metadata.agent_id;
    return Hufi.el(`
      <div class="work-simple-row" data-fade-in>
        <div class="work-simple-row__main">
          <strong>${Hufi.esc(agentName(agentId))}</strong>
          <span class="muted"> — ${Hufi.esc(info.verb)}.</span>
        </div>
        <div class="faint work-simple-row__time">${Hufi.esc(Hufi.fmtTime(item.created_at))}</div>
      </div>
    `);
  }

  function buildLiveCard(item) {
    const agentId = item.metadata && item.metadata.agent_id;
    return Hufi.el(`
      <div class="card evidence-card evidence-card--live" data-fade-in>
        <div class="evidence-card__head">
          <span class="evidence-card__title muted">${Hufi.esc(agentName(agentId))}</span>
          <span class="faint evidence-card__time">${Hufi.esc(Hufi.fmtTime(item.created_at))}</span>
        </div>
        <p class="faint work-live-empty">Live-Ansicht ist für diese Aufgabe nicht verfügbar.</p>
      </div>
    `);
  }

  function buildList() {
    const wrap = document.createElement('div');
    wrap.className = 'work-list-wrap';

    if (!evidenceItems.length) {
      if (!loading) wrap.appendChild(Hufi.el('<p class="empty-hint">Noch keine Aktivität.</p>'));
      return wrap;
    }

    const list = document.createElement('div');
    list.className = mode === 'einfach' ? 'work-simple-list' : 'evidence-list';
    evidenceItems.forEach((item) => {
      if (mode === 'einfach') list.appendChild(buildSimpleRow(item));
      else if (mode === 'live') list.appendChild(buildLiveCard(item));
      else list.appendChild(buildEvidenceCard(item));
    });
    wrap.appendChild(list);
    return wrap;
  }

  function renderAll() {
    if (!mountedContainer) return;
    const container = mountedContainer;
    container.innerHTML = '';
    container.className = 'work-view';
    container.appendChild(buildHeader());

    if (loadError) {
      container.appendChild(Hufi.el(`<p class="empty-hint">Arbeit konnte nicht geladen werden: ${Hufi.esc(loadError)}</p>`));
    }
    if (loading && !evidenceItems.length) {
      container.appendChild(Hufi.el('<p class="empty-hint">Lädt …</p>'));
      return;
    }

    container.appendChild(buildSummary());
    container.appendChild(buildList());
  }

  // ---------- View registration ----------
  Hufi.views.register('arbeit', {
    onShow(container) {
      mountedContainer = container;
      if (!orgUnsubscribe) {
        orgUnsubscribe = Hufi.orgData.subscribe(() => {
          if (Hufi.views.current() === 'arbeit') renderAll();
        });
      }
      renderAll();
      fetchEvidence();
    },
    onHide() {
      // No polling/live loop is started in this pass (there is no real
      // live-session signal yet), so there is nothing to stop here.
    },
  });

  // ---------- Public contract ----------
  Hufi.work = {
    openForAgent(agentId) {
      agentFilter = agentId || null;
      const wasMounted = !!mountedContainer;
      Hufi.views.show('arbeit');
      // If the view was already active, Hufi.views.show() is a no-op (see
      // nav.js), so onShow won't re-fire and re-fetch on its own -- do it
      // here. If the view was just mounted for the first time, onShow
      // already kicked off a fetch using the filter set above.
      if (wasMounted) fetchEvidence();
    },
  };
})();
