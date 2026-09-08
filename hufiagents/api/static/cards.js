/* ==========================================================================
   Hufi — reusable card components (v1.2 "digital company" shell) + the
   "Projekte" and "Routinen" nav views.
   Owned by this feature module. Builds on Hufi.* (app.js), Hufi.orgData
   (org-data.js) and Hufi.agents (agents.js); never touches those files.

   Public contract (other feature modules depend on these):
     - Hufi.cards.renderAgentCard(agent, opts)      -> HTMLElement
     - Hufi.cards.renderTeamCard(team, opts)        -> HTMLElement
     - Hufi.cards.renderProjectCard(project, opts)  -> HTMLElement
     - Hufi.cards.renderResourceTile(resource, opts)-> HTMLElement
   `opts.expanded` (agent card only) renders the detail content open instead
   of behind a click. Every renderer is defensive: missing/partial data never
   throws, it renders a truthful fallback sentence instead.
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});
  const esc = Hufi.esc;
  const el = Hufi.el;

  // ---------- Avatar helpers (same convention as agents.js -- there is no
  // real photo field on Agent yet, initials+hashed-color is correct here,
  // not a gap to fix) ----------
  function hashHue(str) {
    let h = 0;
    const s = String(str || '');
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % 360;
  }
  const AVATAR_PALETTE = ['#f47f1f', '#c14f15', '#f59f0a', '#c96a48', '#d65d42', '#8f3e2b', '#5d514b'];
  function avatarColor(id) {
    return AVATAR_PALETTE[hashHue(id) % AVATAR_PALETTE.length];
  }
  function initials(name) {
    const words = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  function avatarHtml(idForColor, label, sizeClass) {
    const color = avatarColor(idForColor);
    return `<span class="avatar ${sizeClass}" style="background:${color};color:#fff;">${esc(initials(label))}</span>`;
  }

  function humanizeId(id) {
    if (Hufi.agents && typeof Hufi.agents.humanizeId === 'function') return Hufi.agents.humanizeId(id);
    return String(id || '')
      .replace(/[_-]+/g, ' ')
      .trim()
      .split(' ')
      .filter(Boolean)
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ') || String(id || '');
  }

  // Light version of agents.js's friendlyRole -- strips implementation-
  // detail asides ("(routines.py, ...)") but doesn't need the full
  // translation table here, cards show role as secondary text only.
  function friendlyRoleShort(role) {
    const stripped = String(role || '').replace(/\s*\([^)]*\.py[^)]*\)\s*$/, '').trim();
    return stripped || 'Noch keine Rollenbeschreibung.';
  }

  const AGENT_STATUS_LABEL = { active: 'Aktiv', disabled: 'Deaktiviert', archived: 'Archiviert' };
  function agentStatusTone(status) {
    return status === 'active' ? 'tone-ok' : 'tone-idle';
  }

  // ---------- Cross-module lookups (agents.js cache first, org-data.js as
  // the self-contained fallback so cards keep working even if agents.js
  // hasn't finished loading its own sidebar cache yet) ----------
  function resolveAgent(id) {
    if (!id) return null;
    if (Hufi.agents && typeof Hufi.agents.getById === 'function') {
      const a = Hufi.agents.getById(id);
      if (a) return a;
    }
    if (Hufi.orgData && typeof Hufi.orgData.getAgentById === 'function') return Hufi.orgData.getAgentById(id);
    return null;
  }
  function resolveTeam(id) {
    return (Hufi.orgData && Hufi.orgData.getTeamById && Hufi.orgData.getTeamById(id)) || null;
  }
  function resolveProject(id) {
    return (Hufi.orgData && Hufi.orgData.getProjectById && Hufi.orgData.getProjectById(id)) || null;
  }
  function resolveResource(id) {
    return (Hufi.orgData && Hufi.orgData.getResourceById && Hufi.orgData.getResourceById(id)) || null;
  }

  function mockNoticeHtml(extra) {
    if (!(Hufi.orgData && Hufi.orgData.isMock && Hufi.orgData.isMock())) return '';
    return `<p class="mock-notice">Entwicklungsmodus — Beispieldaten${extra ? ` (${esc(extra)})` : ''}.</p>`;
  }

  // ==========================================================================
  // Hufi.cards.renderAgentCard
  // ==========================================================================
  function renderAgentCard(agent, opts) {
    opts = opts || {};
    agent = agent || {};
    const id = agent.id || '';
    const name = id ? humanizeId(id) : 'Unbekannter Hufi';
    const role = friendlyRoleShort(agent.role);
    const status = agent.status || 'active';

    const card = el(`
      <article class="card hufi-card hufi-card--agent" data-fade-in>
        <button type="button" class="hufi-card__row hufi-card__row--clickable">
          ${avatarHtml(id, name, 'avatar--md')}
          <span class="hufi-card__main">
            <span class="hufi-card__title">${esc(name)}</span>
            <span class="hufi-card__subtitle muted">${esc(role)}</span>
          </span>
          <span class="status-dot ${agentStatusTone(status)}" title="${esc(AGENT_STATUS_LABEL[status] || status)}"></span>
        </button>
        <div class="hufi-card__detail" ${opts.expanded ? '' : 'hidden'}></div>
      </article>
    `);

    const toggleBtn = card.querySelector('.hufi-card__row--clickable');
    const detail = card.querySelector('.hufi-card__detail');
    let detailLoaded = false;

    function fillDetail() {
      if (detailLoaded) return;
      detailLoaded = true;
      const tools = (agent.capabilities && agent.capabilities.tools) || [];
      const rels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('agent', id) : [];
      const teamRel = rels.find((r) => r.relationship_type === 'member_of_team' && r.source_type === 'agent' && r.source_id === id);
      const team = teamRel ? resolveTeam(teamRel.target_id) : null;
      const projectRels = rels.filter((r) => r.relationship_type === 'works_on_project' && r.source_type === 'agent' && r.source_id === id);
      const projects = projectRels.map((r) => resolveProject(r.target_id)).filter(Boolean);

      detail.appendChild(el(`
        <div class="hufi-card__facts">
          <div class="hufi-card__fact"><span class="muted">Team</span><span>${team ? esc(team.name) : 'Noch keinem Team zugeordnet.'}</span></div>
          <div class="hufi-card__fact"><span class="muted">Projekt${projects.length === 1 ? '' : 'e'}</span><span>${projects.length ? esc(projects.map((p) => p.name).join(', ')) : 'Aktuell an keinem Projekt beteiligt.'}</span></div>
          <div class="hufi-card__fact"><span class="muted">Aktuelle Aufgabe</span><span>Aktuell ist keine laufende Aufgabe hinterlegt.</span></div>
        </div>
      `));

      const activityBox = el('<div class="hufi-card__activity"><p class="empty-hint">Lädt letzte Aktivität …</p></div>');
      detail.appendChild(activityBox);

      const workBtnRow = el('<div class="row hufi-card__actions"></div>');
      const workBtn = el('<button type="button" class="btn btn--ghost btn--sm">Arbeit ansehen</button>');
      const workList = el('<div class="hufi-card__work" hidden></div>');
      workBtnRow.appendChild(workBtn);
      detail.appendChild(workBtnRow);
      detail.appendChild(workList);

      let workPromise = null;
      function loadWork() {
        if (!workPromise) {
          workPromise = (Hufi.orgData && Hufi.orgData.loadWorkEvidence
            ? Hufi.orgData.loadWorkEvidence({ agent_id: id })
            : Promise.resolve({ items: [], mock: false }));
        }
        return workPromise;
      }

      loadWork().then(({ items, mock }) => {
        if (!items.length) {
          activityBox.innerHTML = '<p class="empty-hint">Noch keine Aktivität bekannt.</p>';
          return;
        }
        const latest = items[0];
        activityBox.innerHTML = `<p class="faint">Letzte Aktivität: ${esc(Hufi.fmtTime(latest.created_at))} — ${esc(latest.summary || 'Aktivität ohne Zusammenfassung.')}</p>`;
      }).catch(() => {
        activityBox.innerHTML = '<p class="empty-hint">Aktivität konnte nicht geladen werden.</p>';
      });

      workBtn.addEventListener('click', async () => {
        workBtn.disabled = true;
        workBtn.textContent = 'Lädt …';
        try {
          const { items, mock } = await loadWork();
          workList.innerHTML = '';
          workList.hidden = false;
          if (!items.length) {
            workList.appendChild(el('<p class="empty-hint">Für diesen Hufi liegt noch keine sichtbare Arbeit vor.</p>'));
          } else {
            if (mock) workList.appendChild(el(mockNoticeHtml('Beispiel-Arbeitsnachweise')));
            const list = el('<ul class="hufi-card__work-list"></ul>');
            items.slice(0, 20).forEach((ev) => {
              list.appendChild(el(`<li><span class="faint">${esc(Hufi.fmtTime(ev.created_at))}</span> — ${esc(ev.summary || 'Ohne Zusammenfassung.')}</li>`));
            });
            workList.appendChild(list);
          }
        } catch (e) {
          workList.hidden = false;
          workList.innerHTML = `<p class="empty-hint">Arbeit konnte nicht geladen werden: ${esc(e.message)}</p>`;
        } finally {
          workBtn.disabled = false;
          workBtn.textContent = 'Arbeit ansehen';
        }
      });

      detail.appendChild(el(`
        <details class="hufi-card__raw">
          <summary>Details</summary>
          <dl class="kv-list">
            <dt>ID</dt><dd>${esc(id || '—')}</dd>
            <dt>Rollenbeschreibung</dt><dd>${esc(agent.role || 'Keine Beschreibung.')}</dd>
            <dt>Risikodecke</dt><dd>${esc(agent.default_risk_ceiling || agent.risk_ceiling || 'Nicht gesetzt.')}</dd>
            <dt>Angelegt am</dt><dd>${esc(Hufi.fmtTime(agent.created_at))}</dd>
          </dl>
          <div class="tag-list-label muted">Werkzeuge</div>
          <div class="tag-list">
            ${tools.length ? tools.map((t) => `<span class="tag">${esc(t)}</span>`).join('') : '<span class="faint">Keine.</span>'}
          </div>
        </details>
      `));
    }

    if (opts.expanded) {
      fillDetail();
    } else {
      toggleBtn.addEventListener('click', () => {
        const nowHidden = detail.hidden;
        detail.hidden = !nowHidden;
        if (!detail.hidden) fillDetail();
      });
    }

    return card;
  }

  // ==========================================================================
  // Hufi.cards.renderTeamCard
  // ==========================================================================
  function renderTeamCard(team, opts) {
    opts = opts || {};
    team = team || {};
    const name = team.name || 'Unbenanntes Team';
    const description = team.description || 'Keine Beschreibung.';

    const rels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('team', team.id) : [];
    const memberIds = rels
      .filter((r) => r.relationship_type === 'member_of_team' && r.target_type === 'team' && r.target_id === team.id)
      .map((r) => r.source_id);
    const members = memberIds.map(resolveAgent).filter(Boolean);

    const projectIds = new Set();
    members.forEach((agent) => {
      const agentRels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('agent', agent.id) : [];
      agentRels
        .filter((r) => r.relationship_type === 'works_on_project' && r.source_id === agent.id)
        .forEach((r) => projectIds.add(r.target_id));
    });
    const projects = Array.from(projectIds).map(resolveProject).filter(Boolean);

    const card = el(`
      <article class="card hufi-card hufi-card--team" data-fade-in>
        <div class="hufi-card__title">${esc(name)}</div>
        <p class="hufi-card__desc muted">${esc(description)}</p>
        <div class="hufi-card__fact"><span class="muted">Mitglieder</span></div>
        <div class="hufi-card__avatars"></div>
        <div class="hufi-card__fact"><span class="muted">Projekte</span><span>${projects.length ? esc(projects.map((p) => p.name).join(', ')) : 'Noch kein Projekt verknüpft.'}</span></div>
        <div class="row hufi-card__actions"></div>
      </article>
    `);

    const avatarsRow = card.querySelector('.hufi-card__avatars');
    if (!members.length) {
      avatarsRow.appendChild(el('<p class="empty-hint">Noch keine Mitglieder.</p>'));
    } else {
      members.forEach((agent) => {
        const n = humanizeId(agent.id);
        const span = el(avatarHtml(agent.id, n, 'avatar--sm'));
        span.title = n;
        avatarsRow.appendChild(span);
      });
    }

    const actionsRow = card.querySelector('.hufi-card__actions');
    const chatBtn = el('<button type="button" class="btn btn--ghost btn--sm">Teamchat</button>');
    if (typeof Hufi.rooms !== 'undefined' && Hufi.rooms && typeof Hufi.rooms.open === 'function') {
      chatBtn.addEventListener('click', () => {
        Hufi.rooms.open({ room_type: 'team', host_type: 'team', host_id: team.id, name: `${name} Teamchat` });
      });
    } else {
      chatBtn.disabled = true;
      chatBtn.title = 'Teamchat ist noch nicht verfügbar.';
    }
    actionsRow.appendChild(chatBtn);

    return card;
  }

  // ==========================================================================
  // Hufi.cards.renderProjectCard
  // ==========================================================================
  function renderProjectCard(project, opts) {
    opts = opts || {};
    project = project || {};
    const name = project.name || 'Unbenanntes Projekt';
    const description = project.description || 'Keine Beschreibung.';

    const rels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('project', project.id) : [];
    const workRels = rels.filter((r) => r.relationship_type === 'works_on_project' && r.target_type === 'project' && r.target_id === project.id);
    const primaryRels = workRels.filter((r) => r.primary);
    const leadAgents = (primaryRels.length ? primaryRels : workRels).map((r) => resolveAgent(r.source_id)).filter(Boolean);
    const leadsAreExplicit = primaryRels.length > 0;

    // Team: no direct project<->team relationship exists in the graph, so
    // derive it from the teams of the agents working on this project.
    const teamIds = new Set();
    workRels.forEach((r) => {
      const agent = resolveAgent(r.source_id);
      if (!agent) return;
      const agentRels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('agent', agent.id) : [];
      agentRels
        .filter((ar) => ar.relationship_type === 'member_of_team' && ar.source_id === agent.id)
        .forEach((ar) => teamIds.add(ar.target_id));
    });
    const teams = Array.from(teamIds).map(resolveTeam).filter(Boolean);
    let teamLabel = 'Noch keinem Team zugeordnet.';
    if (teams.length === 1) teamLabel = teams[0].name;
    else if (teams.length > 1) teamLabel = 'Mehrere Teams beteiligt.';

    // Related resources: resources touched (responsible_for/may_use) by
    // agents who work on this project. Simple one-hop traversal, no deeper.
    const resourceIds = new Set();
    workRels.forEach((r) => {
      const agent = resolveAgent(r.source_id);
      if (!agent) return;
      const agentRels = (Hufi.orgData && Hufi.orgData.relationshipsFor) ? Hufi.orgData.relationshipsFor('agent', agent.id) : [];
      agentRels
        .filter((ar) => (ar.relationship_type === 'responsible_for_resource' || ar.relationship_type === 'may_use_resource') && ar.source_id === agent.id)
        .forEach((ar) => resourceIds.add(ar.target_id));
    });
    const resources = Array.from(resourceIds).map(resolveResource).filter(Boolean);

    const card = el(`
      <article class="card hufi-card hufi-card--project" data-fade-in>
        <div class="hufi-card__title">${esc(name)}</div>
        <p class="hufi-card__desc muted">${esc(description)}</p>
        <div class="hufi-card__fact"><span class="muted">Team</span><span>${esc(teamLabel)}</span></div>
        <div class="hufi-card__fact"><span class="muted">${leadsAreExplicit ? 'Verantwortlich' : 'Beteiligte Hufis'}</span><span>${leadAgents.length ? esc(leadAgents.map((a) => humanizeId(a.id)).join(', ')) : 'Noch niemand zugewiesen.'}</span></div>
        <div class="hufi-card__fact"><span class="muted">Ressourcen</span><span>${resources.length ? esc(resources.map((r) => r.name).join(', ')) : 'Keine verknüpften Ressourcen.'}</span></div>
        <div class="row hufi-card__actions"></div>
      </article>
    `);

    const actionsRow = card.querySelector('.hufi-card__actions');
    const chatBtn = el('<button type="button" class="btn btn--ghost btn--sm">Projektchat</button>');
    if (typeof Hufi.rooms !== 'undefined' && Hufi.rooms && typeof Hufi.rooms.open === 'function') {
      chatBtn.addEventListener('click', () => {
        Hufi.rooms.open({ room_type: 'project', host_type: 'project', host_id: project.id, name: `${name} Projektchat` });
      });
    } else {
      chatBtn.disabled = true;
      chatBtn.title = 'Projektchat ist noch nicht verfügbar.';
    }
    actionsRow.appendChild(chatBtn);

    return card;
  }

  // ==========================================================================
  // Hufi.cards.renderResourceTile
  // ==========================================================================
  function toHttpsGithubUrl(repoUrl, githubRepo) {
    if (githubRepo && /^[\w.-]+\/[\w.-]+$/.test(githubRepo)) return `https://github.com/${githubRepo}`;
    if (!repoUrl) return null;
    const sshMatch = String(repoUrl).match(/^git@github\.com:(.+?)(\.git)?$/);
    if (sshMatch) return `https://github.com/${sshMatch[1]}`;
    if (/^https?:\/\//.test(repoUrl)) return repoUrl.replace(/\.git$/, '');
    return null;
  }

  function renderResourceTile(resource, opts) {
    opts = opts || {};
    resource = resource || {};
    const name = resource.name || 'Unbenannte Ressource';
    const description = resource.description || 'Keine Beschreibung.';
    const meta = resource.metadata || {};
    const isRepo = resource.resource_type === 'github_repo';
    const notConnected = !!resource._notConnected;

    const badges = [];
    if (notConnected) {
      badges.push(`<span class="pill tone-idle">Noch nicht verbunden</span>`);
    } else if (isRepo) {
      if (meta.visibility === 'public') badges.push('<span class="pill tone-ok">Öffentlich</span>');
      else if (meta.visibility === 'private') badges.push('<span class="pill tone-idle">Privat</span>');
      badges.push(`<span class="pill tone-accent">${esc(meta.language || 'Sprache unbekannt')}</span>`);
      if (meta.has_test) badges.push('<span class="tag">Tests</span>');
      if (meta.has_build) badges.push('<span class="tag">Build</span>');
      if (meta.has_lint) badges.push('<span class="tag">Lint</span>');
    } else if (resource.resource_type) {
      badges.push(`<span class="pill tone-idle">${esc(humanizeId(resource.resource_type))}</span>`);
    }

    const tile = el(`
      <article class="card resource-tile" data-fade-in>
        <div class="resource-tile__header">
          <span class="resource-tile__name">${esc(name)}</span>
        </div>
        <p class="hufi-card__desc muted">${esc(description)}</p>
        <div class="resource-tile__badges">${badges.join('')}</div>
        <div class="row hufi-card__actions resource-tile__actions"></div>
      </article>
    `);

    const actionsRow = tile.querySelector('.resource-tile__actions');

    if (isRepo) {
      const info = { ghRepo: meta.github_repo || null, url: meta.url || toHttpsGithubUrl(meta.repo_url, meta.github_repo) };
      const openBtn = el('<button type="button" class="btn btn--ghost btn--sm">Öffnen</button>');
      if (info.url) {
        openBtn.addEventListener('click', () => window.open(info.url, '_blank', 'noopener'));
      } else {
        openBtn.disabled = true;
        openBtn.title = 'Kein Link hinterlegt.';
      }
      const analyzeBtn = el('<button type="button" class="btn btn--ghost btn--sm">Analysieren</button>');
      analyzeBtn.disabled = true;
      analyzeBtn.title = 'Noch nicht verfügbar.';
      const prsBtn = el('<button type="button" class="btn btn--ghost btn--sm">PRs</button>');
      const issuesBtn = el('<button type="button" class="btn btn--ghost btn--sm">Issues</button>');
      if (info.url) {
        prsBtn.addEventListener('click', () => window.open(`${info.url}/pulls`, '_blank', 'noopener'));
        issuesBtn.addEventListener('click', () => window.open(`${info.url}/issues`, '_blank', 'noopener'));
      } else {
        prsBtn.disabled = true;
        issuesBtn.disabled = true;
        prsBtn.title = issuesBtn.title = 'Kein Link hinterlegt.';
      }
      actionsRow.append(openBtn, analyzeBtn, prsBtn, issuesBtn);
    } else {
      const detailsBtn = el('<button type="button" class="btn btn--ghost btn--sm">Details</button>');
      if (notConnected) {
        detailsBtn.disabled = true;
        detailsBtn.title = 'Diese Ressource ist noch nicht verbunden.';
      } else {
        detailsBtn.addEventListener('click', () => {
          Hufi.rightPane.show(name, (container) => {
            const metaEntries = Object.entries(meta);
            container.appendChild(el(`
              <div class="stack">
                <p class="muted">${esc(description)}</p>
                <dl class="kv-list">
                  <dt>Typ</dt><dd>${esc(humanizeId(resource.resource_type || 'unbekannt'))}</dd>
                  ${metaEntries.map(([k, v]) => `<dt>${esc(humanizeId(k))}</dt><dd>${esc(v === null || v === undefined || v === '' ? 'Nicht angegeben.' : String(v))}</dd>`).join('')}
                </dl>
              </div>
            `));
          });
        });
      }
      actionsRow.appendChild(detailsBtn);
    }

    return tile;
  }

  Hufi.cards = { renderAgentCard, renderTeamCard, renderProjectCard, renderResourceTile };

  // ==========================================================================
  // "Projekte" view
  // ==========================================================================
  function placeholderServerResources() {
    return [
      { id: 'placeholder-xxl-server', name: 'XXL Server', resource_type: 'server', description: 'Für die zukünftige Anbindung vorgesehen.', metadata: {}, status: 'planned', _notConnected: true },
      { id: 'placeholder-ovh-server', name: 'OVH Server', resource_type: 'server', description: 'Für die zukünftige Anbindung vorgesehen.', metadata: {}, status: 'planned', _notConnected: true },
      { id: 'placeholder-opencloud-server', name: 'OpenCloud Server', resource_type: 'server', description: 'Für die zukünftige Anbindung vorgesehen.', metadata: {}, status: 'planned', _notConnected: true },
    ];
  }

  async function loadRegistryProjects() {
    try {
      const rows = await Hufi.api('/projects');
      return rows.map((p) => ({
        id: `registry:${p.id}`,
        name: p.github_repo || p.repo_url || 'Repository',
        resource_type: 'github_repo',
        description: 'Verbundenes Git-Repository.',
        metadata: {
          github_repo: p.github_repo || null,
          url: toHttpsGithubUrl(p.repo_url, p.github_repo),
          visibility: null,
          language: null,
          has_test: p.has_test,
          has_build: p.has_build,
          has_lint: p.has_lint,
        },
        status: p.allowed ? 'active' : 'disabled',
        created_at: null,
        archived_at: null,
        _registry: true,
      }));
    } catch (e) {
      console.error('GET /projects failed', e);
      return null; // signals a real load error, distinct from "no projects"
    }
  }

  function openNewProjectModal(onCreated) {
    const overlay = el(`<div class="modal-overlay" data-fade-in></div>`);
    const card = el(`
      <div class="modal-card card" role="dialog" aria-modal="true" aria-label="Neues Projekt">
        <div class="row">
          <h3 class="spacer">Neues Projekt</h3>
          <button type="button" class="icon-btn" id="newProjectClose" aria-label="Schließen">✕</button>
        </div>
        <form id="newProjectForm" class="stack">
          <label class="field-label" for="newProjectName">Name</label>
          <input id="newProjectName" type="text" placeholder="z. B. HufiApp" required />
          <label class="field-label" for="newProjectDesc">Worum geht es kurz?</label>
          <textarea id="newProjectDesc" placeholder="Ein Satz reicht."></textarea>
          <div class="row">
            <span class="spacer"></span>
            <button type="submit" class="btn btn--primary">Projekt anlegen</button>
          </div>
        </form>
        <div id="newProjectMsg" class="new-hufi-msg" hidden></div>
      </div>
    `);
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    const previouslyFocused = document.activeElement;
    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') previouslyFocused.focus();
    }
    function focusableElements() {
      return Array.from(card.querySelectorAll('button, input, textarea, [href]')).filter((e) => !e.disabled && e.tabIndex !== -1);
    }
    function onKeydown(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      const focusable = focusableElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', onKeydown);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    card.querySelector('#newProjectClose').addEventListener('click', close);
    card.querySelector('#newProjectName').focus();

    card.querySelector('#newProjectForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = card.querySelector('#newProjectMsg');
      const name = card.querySelector('#newProjectName').value.trim();
      const description = card.querySelector('#newProjectDesc').value.trim();
      if (!name) return;
      try {
        await Hufi.orgData.createGraphProject({ name, description });
        close();
        onCreated();
      } catch (err) {
        msg.hidden = false;
        msg.textContent = `Projekt konnte nicht angelegt werden: ${err.message}`;
      }
    });
  }

  function registerProjekteView() {
    Hufi.views.register('projekte', {
      onShow(container) {
        container.innerHTML = '';
        const root = el(`
          <div class="cards-view stack">
            <section class="cards-view__section">
              <div class="cards-view__header row">
                <h2 class="spacer">Projekte</h2>
                <button type="button" class="btn btn--primary btn--sm" id="newProjectBtn">+ Projekt</button>
              </div>
              <div id="mockNoticeSlot"></div>
              <div id="projectGrid" class="cards-grid"><p class="empty-hint">Lädt …</p></div>
            </section>
            <section class="cards-view__section">
              <div class="cards-view__header row">
                <h2 class="spacer">Ressourcen</h2>
              </div>
              <div class="resource-controls row">
                <input type="search" id="resourceSearch" placeholder="Ressourcen durchsuchen …" autocomplete="off" />
                <select id="resourceTypeFilter">
                  <option value="">Alle Typen</option>
                  <option value="github_repo">GitHub-Repositories</option>
                  <option value="server">Server</option>
                </select>
                <select id="resourceSort">
                  <option value="name">Name (A–Z)</option>
                  <option value="recent">Zuletzt angelegt</option>
                </select>
              </div>
              <div id="resourceGrid" class="cards-grid cards-grid--resources"><p class="empty-hint">Lädt …</p></div>
            </section>
          </div>
        `);
        container.appendChild(root);

        const projectGrid = root.querySelector('#projectGrid');
        const resourceGrid = root.querySelector('#resourceGrid');
        const mockSlot = root.querySelector('#mockNoticeSlot');
        const searchInput = root.querySelector('#resourceSearch');
        const typeFilter = root.querySelector('#resourceTypeFilter');
        const sortSelect = root.querySelector('#resourceSort');

        let registryResources = [];
        let registryError = false;

        function renderProjects() {
          const state = Hufi.orgData.getState();
          mockSlot.innerHTML = mockNoticeHtml();
          projectGrid.innerHTML = '';
          if (!state) { projectGrid.innerHTML = '<p class="empty-hint">Lädt …</p>'; return; }
          if (!state.graphProjects.length) {
            projectGrid.appendChild(el('<p class="empty-hint">Noch kein Projekt angelegt. Lege dein erstes Projekt an.</p>'));
            return;
          }
          state.graphProjects
            .filter((p) => !p.archived_at)
            .forEach((p) => projectGrid.appendChild(Hufi.cards.renderProjectCard(p)));
        }

        function renderResources() {
          const state = Hufi.orgData.getState();
          resourceGrid.innerHTML = '';
          if (!state) { resourceGrid.innerHTML = '<p class="empty-hint">Lädt …</p>'; return; }

          let combined = state.resources.filter((r) => !r.archived_at).slice();
          if (registryResources) combined = combined.concat(registryResources);
          if (!combined.some((r) => r.resource_type === 'server')) {
            combined = combined.concat(placeholderServerResources());
          }

          const q = searchInput.value.trim().toLowerCase();
          const typeQ = typeFilter.value;
          let filtered = combined.filter((r) => {
            if (typeQ && r.resource_type !== typeQ) return false;
            if (!q) return true;
            return (r.name || '').toLowerCase().includes(q) || (r.description || '').toLowerCase().includes(q);
          });
          if (sortSelect.value === 'recent') {
            filtered.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
          } else {
            filtered.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'de'));
          }

          if (registryError) resourceGrid.appendChild(el('<p class="empty-hint">Verbundene Repositories konnten nicht geladen werden.</p>'));
          if (!filtered.length) {
            resourceGrid.appendChild(el('<p class="empty-hint">Keine Ressourcen gefunden.</p>'));
            return;
          }
          filtered.forEach((r) => resourceGrid.appendChild(Hufi.cards.renderResourceTile(r)));
        }

        function renderAll() { renderProjects(); renderResources(); }

        const unsubscribe = Hufi.orgData.subscribe(renderAll);
        renderAll();

        loadRegistryProjects().then((rows) => {
          if (rows === null) { registryError = true; registryResources = []; } else { registryResources = rows; }
          renderResources();
        });

        searchInput.addEventListener('input', renderResources);
        typeFilter.addEventListener('change', renderResources);
        sortSelect.addEventListener('change', renderResources);
        root.querySelector('#newProjectBtn').addEventListener('click', () => openNewProjectModal(renderProjects));

        this._unsubscribe = unsubscribe;
      },
      onHide() {
        if (this._unsubscribe) { this._unsubscribe(); this._unsubscribe = null; }
      },
    });
  }

  // ==========================================================================
  // "Routinen" view
  // ==========================================================================
  const ROUTINE_WEEKDAY_DE = {
    monday: 'Montag', tuesday: 'Dienstag', wednesday: 'Mittwoch',
    thursday: 'Donnerstag', friday: 'Freitag', saturday: 'Samstag', sunday: 'Sonntag',
  };
  function scheduleDe(schedule) {
    const m = String(schedule || '').match(/^every (day|monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (\d{2}):(\d{2})$/);
    if (!m) return schedule || 'Kein Zeitplan hinterlegt.';
    const [, kind, hh, mm] = m;
    const cadence = kind === 'day' ? 'Jeden Tag' : `Jeden ${ROUTINE_WEEKDAY_DE[kind]}`;
    return `${cadence} um ${hh}:${mm} Uhr`;
  }

  function routineStatusBadge(routine) {
    if (routine.status === 'archived') return '<span class="pill tone-idle">Archiviert</span>';
    if (!routine.enabled) return '<span class="pill tone-warn">Pausiert</span>';
    return '<span class="pill tone-ok">Aktiv</span>';
  }

  function openNewRoutineModal(agents, onCreated) {
    const overlay = el(`<div class="modal-overlay" data-fade-in></div>`);
    const options = agents.map((a) => `<option value="${esc(a.id)}">${esc(humanizeId(a.id))}</option>`).join('');
    const card = el(`
      <div class="modal-card card" role="dialog" aria-modal="true" aria-label="Routine erstellen">
        <div class="row">
          <h3 class="spacer">Routine erstellen</h3>
          <button type="button" class="icon-btn" id="newRoutineClose" aria-label="Schließen">✕</button>
        </div>
        <div class="stack">
          <label class="field-label" for="routineAgent">Welcher Hufi?</label>
          <select id="routineAgent">${options || '<option disabled selected>Keine Hufis verfügbar.</option>'}</select>
          <label class="field-label" for="routineTaskR">Was soll regelmäßig erledigt werden?</label>
          <textarea id="routineTaskR" required></textarea>
          <label class="field-label">Wann?</label>
          <div class="routine-choice"><button type="button" data-kind="day">Täglich</button><button type="button" data-kind="week" class="is-selected">Wöchentlich</button></div>
          <label class="field-label">Tag</label>
          <select id="routineDayR"><option value="monday">Montag</option><option value="tuesday">Dienstag</option><option value="wednesday">Mittwoch</option><option value="thursday">Donnerstag</option><option value="friday">Freitag</option><option value="saturday">Samstag</option><option value="sunday">Sonntag</option></select>
          <label class="field-label">Zeit</label>
          <input id="routineTimeR" type="time" value="08:00" required />
          <p id="routineErrorR" class="faint"></p>
          <div class="row">
            <span class="spacer"></span>
            <button type="button" id="routineCancelR" class="btn btn--ghost">Abbrechen</button>
            <button type="button" id="routineCreateR" class="btn btn--primary">Routine erstellen</button>
          </div>
        </div>
      </div>
    `);
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    const previouslyFocused = document.activeElement;
    let kind = 'week';
    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') previouslyFocused.focus();
    }
    function focusableElements() {
      return Array.from(card.querySelectorAll('button, input, textarea, select, [href]')).filter((e) => !e.disabled && e.tabIndex !== -1);
    }
    function onKeydown(e) {
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      const focusable = focusableElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', onKeydown);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    card.querySelector('#newRoutineClose').addEventListener('click', close);
    card.querySelector('#routineCancelR').addEventListener('click', close);
    card.querySelectorAll('[data-kind]').forEach((button) => button.addEventListener('click', () => {
      kind = button.dataset.kind;
      card.querySelectorAll('[data-kind]').forEach((b) => b.classList.toggle('is-selected', b === button));
      card.querySelector('#routineDayR').parentElement.style.display = kind === 'week' ? '' : 'none';
    }));
    card.querySelector('#routineCreateR').addEventListener('click', async () => {
      const agentId = card.querySelector('#routineAgent').value;
      const outcome = card.querySelector('#routineTaskR').value.trim();
      const time = card.querySelector('#routineTimeR').value;
      const errBox = card.querySelector('#routineErrorR');
      if (!agentId || !outcome || !time) { errBox.textContent = 'Bitte Hufi, Aufgabe und Zeit auswählen.'; return; }
      const schedule = kind === 'day' ? `every day at ${time}` : `every ${card.querySelector('#routineDayR').value} at ${time}`;
      try {
        await Hufi.api('/routines', {
          method: 'POST',
          body: JSON.stringify({
            owner_agent_id: agentId,
            mission_template: { outcome, risk_ceiling: 'R0' },
            schedule,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Berlin',
          }),
        });
        close();
        onCreated();
      } catch (err) {
        errBox.textContent = `Routine konnte nicht erstellt werden: ${err.message}`;
      }
    });
    if (agents.length) card.querySelector('#routineTaskR').focus();
  }

  function registerRoutinenView() {
    Hufi.views.register('routinen', {
      onShow(container) {
        container.innerHTML = '';
        const root = el(`
          <div class="cards-view stack">
            <div class="cards-view__header row">
              <h2 class="spacer">Routinen</h2>
              <label class="row routine-archived-toggle"><input type="checkbox" id="showArchivedRoutines" /> <span class="faint">Archivierte anzeigen</span></label>
              <button type="button" class="btn btn--primary btn--sm" id="newRoutineBtn">+ Routine</button>
            </div>
            <div id="routineList" class="stack"><p class="empty-hint">Lädt …</p></div>
          </div>
        `);
        container.appendChild(root);

        const listBox = root.querySelector('#routineList');
        const showArchived = root.querySelector('#showArchivedRoutines');

        async function load() {
          listBox.innerHTML = '<p class="empty-hint">Lädt …</p>';
          try {
            const routines = await Hufi.api('/routines');
            renderList(routines);
          } catch (e) {
            listBox.innerHTML = `<p class="empty-hint">Routinen konnten nicht geladen werden: ${esc(e.message)}</p>`;
          }
        }

        function renderList(routines) {
          const visible = routines.filter((r) => showArchived.checked || r.status !== 'archived');
          visible.sort((a, b) => new Date(a.next_run || 0) - new Date(b.next_run || 0));
          listBox.innerHTML = '';
          if (!visible.length) {
            listBox.appendChild(el('<p class="empty-hint">Noch keine Routinen angelegt.</p>'));
            return;
          }
          visible.forEach((r) => {
            const agent = resolveAgent(r.owner_agent_id);
            const ownerName = agent ? humanizeId(agent.id) : humanizeId(r.owner_agent_id);
            const outcome = (r.mission_template && r.mission_template.outcome) || 'Keine Aufgabenbeschreibung hinterlegt.';
            const row = el(`
              <article class="card routine-row" data-fade-in>
                <div class="routine-row__main">
                  <div class="routine-row__outcome">${esc(outcome)}</div>
                  <div class="routine-row__meta faint">${esc(scheduleDe(r.schedule))} — ${esc(ownerName)}</div>
                  ${r.status !== 'archived' ? `<div class="faint">Nächster Lauf: ${esc(r.next_run ? Hufi.fmtTime(r.next_run) : 'wird geplant')}</div>` : ''}
                </div>
                <div class="routine-row__status">${routineStatusBadge(r)}</div>
                <div class="row routine-row__actions"></div>
              </article>
            `);
            const actions = row.querySelector('.routine-row__actions');
            if (r.status !== 'archived') {
              const toggleBtn = el(`<button type="button" class="btn btn--ghost btn--sm">${r.enabled ? 'Pausieren' : 'Fortsetzen'}</button>`);
              toggleBtn.addEventListener('click', async () => {
                toggleBtn.disabled = true;
                try {
                  await Hufi.api(`/routines/${encodeURIComponent(r.id)}/${r.enabled ? 'pause' : 'resume'}`, { method: 'POST' });
                  load();
                } catch (e) {
                  toggleBtn.disabled = false;
                }
              });
              const archiveBtn = el('<button type="button" class="btn btn--ghost btn--sm">Archivieren</button>');
              archiveBtn.addEventListener('click', async () => {
                archiveBtn.disabled = true;
                try {
                  await Hufi.api(`/routines/${encodeURIComponent(r.id)}/archive`, { method: 'POST' });
                  load();
                } catch (e) {
                  archiveBtn.disabled = false;
                }
              });
              actions.append(toggleBtn, archiveBtn);
            }
            listBox.appendChild(row);
          });
        }

        showArchived.addEventListener('change', load);
        root.querySelector('#newRoutineBtn').addEventListener('click', () => {
          const agents = (Hufi.agents && Hufi.agents.getAll()) || (Hufi.orgData.getState() && Hufi.orgData.getState().agents) || [];
          openNewRoutineModal(agents, load);
        });

        load();
      },
      onHide() {},
    });
  }

  registerProjekteView();
  registerRoutinenView();
})();
