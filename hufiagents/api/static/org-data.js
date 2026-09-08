/* ==========================================================================
   Hufi — shared org-graph data adapter (v1.2 "digital company").

   Single source of truth for teams / projects / resources / relationships /
   chat rooms, consumed by nav.js's views (firma/projekte/routinen/arbeit),
   org-canvas.js, cards.js, work.js and rooms.js. Building this once here
   (instead of once per feature module) keeps every view showing the exact
   same graph and the exact same mock/real state.

   BACKEND STATUS (verified 2026-09-08): the real endpoints this module
   wants -- GET/POST /org, /teams, /graph-projects, /resources,
   /relationships, /rooms, /credentials, /work-evidence -- exist as real,
   working code (hufiagents/api/org.py + org_graph.py) but on Codex's
   unmerged codex/v1-2-core-capabilities branch, not yet on main. /agents
   IS real on main today and is never mocked.

   So: agents always come from the real API. Everything else tries the
   real API first and falls back to a CLEARLY LABELED, isolated mock
   dataset (see MOCK_* below and `_mock: true` on every mock object) built
   using the real fetched agents so the graph stays internally consistent.
   Every UI that reads isMock()===true MUST show a visible "Beispieldaten"
   notice -- never render mock content as if it were real company data.
   Swap-over plan once the backend branch merges: nothing in the UI layer
   needs to change, only the fallback path stops triggering (delete
   buildMockSnapshot + the try/catch fallback once /org is reachable from
   main in every environment this runs in).

   Contract:
     - Hufi.orgData.load()                 async, populates state, notifies
     - Hufi.orgData.getState()             sync snapshot (null before load)
     - Hufi.orgData.isMock()               true if org-graph is mock-backed
     - Hufi.orgData.subscribe(fn)          fn(state) on every change
     - Hufi.orgData.getAgentById(id)
     - Hufi.orgData.relationshipsFor(type, id)   edges touching a node
     - Hufi.orgData.createTeam({name, description})
     - Hufi.orgData.createGraphProject({name, description, repository_ref})
     - Hufi.orgData.createResource({name, resource_type, description, metadata})
     - Hufi.orgData.createRoom({room_type, host_type, host_id, name})
     - Hufi.orgData.addRelationship({relationship_type, source_type, source_id,
                                      target_type, target_id, primary})
         -> resolves the created relationship, or throws an Error with
            `.needsApproval = true` and `.message` in plain German when the
            backend returns 409 (cycle / archived membership / policy).
     - Hufi.orgData.removeRelationship(id)
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});

  let state = null; // { agents, teams, graphProjects, resources, relationships, rooms, mock }
  const listeners = [];

  function notify() {
    listeners.forEach((fn) => {
      try { fn(state); } catch (e) { console.error(e); }
    });
  }

  function nowIso() { return new Date().toISOString(); }
  function mockId(prefix) { return `${prefix}-${Math.random().toString(36).slice(2, 10)}`; }

  // ---------- Error translation ----------
  // The real backend (hufiagents/org_graph.py and friends) raises plain
  // English/technical `ValueError`s that FastAPI surfaces as the JSON
  // `detail` string on 4xx responses -- Hufi.api() turns that into
  // `err.message`. This product is German-only and plain-language by rule
  // (docs/product/HUFI-UX-LANGUAGE.md); every caller that shows a rejection
  // to the user MUST route it through this translator first rather than
  // rendering `err.message` directly. Known strings come from reading
  // org_graph.py's `raise ValueError(...)` call sites; unknown ones fall
  // back to a generic German sentence rather than leaking raw English.
  const KNOWN_ERRORS = [
    [/reporting cycle/i, 'Diese Zuordnung würde einen Kreis in deiner Teamstruktur erzeugen.'],
    [/archived nodes cannot gain memberships/i, 'Das geht nicht: Ein Team oder Mitarbeiter davon ist bereits archiviert.'],
    [/self relationships are not allowed/i, 'Das geht nicht auf sich selbst.'],
    [/reports_to requires agent nodes/i, 'Eine Berichtsbeziehung ist nur zwischen zwei Mitarbeitern möglich.'],
    [/unsupported relationship type/i, 'Diese Art von Verbindung wird nicht unterstützt.'],
    [/task does not belong to mission/i, 'Das passt nicht zusammen.'],
    [/cannot rotate revoked credential/i, 'Eine aufgehobene Verbindung kann nicht erneuert werden.'],
    [/resource not found/i, 'Das wurde nicht gefunden.'],
    [/external cost budget exceeded/i, 'Diese Aufgabe darf aktuell keine kostenpflichtige KI verwenden.'],
    [/approval resolution disabled/i, 'Freigaben sind in dieser Umgebung noch nicht eingerichtet.'],
    [/owner approval token required/i, 'Dafür fehlt die Berechtigung.'],
    [/authentication required/i, 'Bitte melde dich erneut an.'],
  ];
  Hufi.errors = {
    translate(rawMessage) {
      const raw = String(rawMessage || '');
      const hit = KNOWN_ERRORS.find(([pattern]) => pattern.test(raw));
      return hit ? hit[1] : 'Das hat leider nicht geklappt.';
    },
  };

  // Every mutation below goes through this instead of calling Hufi.api()
  // directly, so a rejection's `.message` is already German/plain-language
  // by the time it reaches a UI catch block -- callers never need their own
  // translation step.
  async function postJson(path, body) {
    try {
      return await Hufi.api(path, { method: 'POST', body: JSON.stringify(body) });
    } catch (e) {
      throw new Error(Hufi.errors.translate(e.message));
    }
  }

  // ---------- Mock dataset (dev-only, see banner requirement above) ----------
  function buildMockSnapshot(agents) {
    const teams = [
      { id: 'mock-team-mkt', name: 'Marketing', description: 'Kampagnen, Inhalte, Auftritt.', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-team-dev', name: 'Entwicklung', description: 'Produkt- und Plattformentwicklung.', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-team-infra', name: 'Infrastruktur', description: 'Server, Deployments, Betrieb.', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-team-qa', name: 'Qualitätsprüfung', description: 'Prüfungen und Freigaben.', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
    ];
    const graphProjects = [
      { id: 'mock-proj-hufmanager', name: 'HufManager', description: 'Interne Steuerungsoberfläche.', repository_ref: 'passaondigital/HufManager', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-proj-hufiapp', name: 'HufiApp', description: 'Mobile/Web-App für Kunden.', repository_ref: 'passaondigital/HufiApp', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-proj-hufiagents', name: 'HufiAgents', description: 'Diese Plattform.', repository_ref: 'passaondigital/HufiAgents', status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
    ];
    const resources = [
      { id: 'mock-res-repo-hufiagents', name: 'HufiAgents', resource_type: 'github_repo', description: 'Haupt-Repository.', metadata: { visibility: 'private', language: 'Python' }, status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
      { id: 'mock-res-xxl', name: 'XXL Server', resource_type: 'server', description: 'Produktionsserver.', metadata: {}, status: 'active', created_at: nowIso(), archived_at: null, _mock: true },
    ];
    const rooms = [
      { id: 'mock-room-company', room_type: 'company', host_type: 'company', host_id: 'hufi', name: 'Firmenchat', created_at: nowIso(), archived_at: null, _mock: true },
      ...teams.map((t) => ({ id: `mock-room-team-${t.id}`, room_type: 'team', host_type: 'team', host_id: t.id, name: `${t.name} Teamchat`, created_at: nowIso(), archived_at: null, _mock: true })),
      ...graphProjects.map((p) => ({ id: `mock-room-proj-${p.id}`, room_type: 'project', host_type: 'project', host_id: p.id, name: `${p.name} Projektchat`, created_at: nowIso(), archived_at: null, _mock: true })),
    ];

    const relationships = [];
    let i = 0;
    agents.forEach((agent) => {
      const team = teams[i % teams.length];
      const project = graphProjects[i % graphProjects.length];
      relationships.push({
        id: mockId('mock-rel'), relationship_type: 'member_of_team',
        source_type: 'agent', source_id: agent.id, target_type: 'team', target_id: team.id,
        primary: true, created_at: nowIso(), removed_at: null, _mock: true,
      });
      relationships.push({
        id: mockId('mock-rel'), relationship_type: 'works_on_project',
        source_type: 'agent', source_id: agent.id, target_type: 'project', target_id: project.id,
        primary: true, created_at: nowIso(), removed_at: null, _mock: true,
      });
      i += 1;
    });

    return { teams, graphProjects, resources, relationships, rooms };
  }

  // ---------- Load ----------
  Hufi.orgData = {
    async load() {
      const agents = await Hufi.api('/agents').catch(() => []);
      let graph;
      let unavailable = false;
      let mock = false;
      try {
        graph = await Hufi.api('/org');
        graph = {
          teams: graph.teams || [],
          graphProjects: graph.graph_projects || [],
          resources: graph.resources || [],
          relationships: graph.relationships || [],
          rooms: graph.chat_rooms || [],
        };
      } catch (e) {
        // Release-candidate default: never present fabricated company data.
        // Development fixtures remain in this file for explicit test harnesses,
        // but an unavailable backend is represented as an empty state.
        unavailable = true;
        graph = { teams: [], graphProjects: [], resources: [], relationships: [], rooms: [] };
      }
      state = { agents, ...graph, mock, unavailable };
      notify();
      return state;
    },

    getState() { return state; },
    isMock() { return !!(state && state.mock); },
    subscribe(fn) { listeners.push(fn); return () => { const i = listeners.indexOf(fn); if (i >= 0) listeners.splice(i, 1); }; },

    getAgentById(id) { return state?.agents.find((a) => a.id === id) || null; },
    getTeamById(id) { return state?.teams.find((t) => t.id === id) || null; },
    getProjectById(id) { return state?.graphProjects.find((p) => p.id === id) || null; },
    getResourceById(id) { return state?.resources.find((r) => r.id === id) || null; },

    relationshipsFor(nodeType, nodeId) {
      if (!state) return [];
      return state.relationships.filter(
        (r) => !r.removed_at && ((r.source_type === nodeType && r.source_id === nodeId) || (r.target_type === nodeType && r.target_id === nodeId))
      );
    },

    async createTeam({ name, description }) {
      if (state.mock) {
        const team = { id: mockId('mock-team'), name, description: description || '', status: 'active', created_at: nowIso(), archived_at: null, _mock: true };
        state.teams.push(team);
        notify();
        return team;
      }
      const team = await postJson('/teams', { name, description });
      state.teams.push(team);
      notify();
      return team;
    },

    async createGraphProject({ name, description, repository_ref }) {
      if (state.mock) {
        const project = { id: mockId('mock-proj'), name, description: description || '', repository_ref: repository_ref || null, status: 'active', created_at: nowIso(), archived_at: null, _mock: true };
        state.graphProjects.push(project);
        notify();
        return project;
      }
      const project = await postJson('/graph-projects', { name, description, repository_ref });
      state.graphProjects.push(project);
      notify();
      return project;
    },

    async createResource({ name, resource_type, description, metadata }) {
      if (state.mock) {
        const resource = { id: mockId('mock-res'), name, resource_type, description: description || '', metadata: metadata || {}, status: 'active', created_at: nowIso(), archived_at: null, _mock: true };
        state.resources.push(resource);
        notify();
        return resource;
      }
      const resource = await postJson('/resources', { name, resource_type, description, metadata });
      state.resources.push(resource);
      notify();
      return resource;
    },

    async createRoom({ room_type, host_type, host_id, name }) {
      if (state.mock) {
        const room = { id: mockId('mock-room'), room_type, host_type, host_id, name, created_at: nowIso(), archived_at: null, _mock: true };
        state.rooms.push(room);
        notify();
        return room;
      }
      const room = await postJson('/rooms', { room_type, host_type, host_id, name });
      state.rooms.push(room);
      notify();
      return room;
    },

    async addRelationship({ relationship_type, source_type, source_id, target_type, target_id, primary }) {
      if (state.mock) {
        const rel = { id: mockId('mock-rel'), relationship_type, source_type, source_id, target_type, target_id, primary: !!primary, created_at: nowIso(), removed_at: null, _mock: true };
        state.relationships.push(rel);
        notify();
        return rel;
      }
      try {
        const rel = await Hufi.api('/relationships', { method: 'POST', body: JSON.stringify({ relationship_type, source_type, source_id, target_type, target_id, primary }) });
        state.relationships.push(rel);
        notify();
        return rel;
      } catch (e) {
        // Hufi.api() surfaces the FastAPI `detail` string as e.message for
        // any non-2xx status, including 409 (cycle / archived / policy).
        // We can't see the raw status code here, so treat every rejection
        // from this endpoint as approval-needed language rather than a
        // generic failure -- matches the product rule that relationship
        // changes never fail silently or with technical text. The raw
        // `detail` from org_graph.py is English/technical ("reporting
        // cycle", "archived nodes cannot gain memberships", ...) -- run it
        // through Hufi.errors.translate() so the user only ever sees the
        // German plain-language version (found during v1.2 product
        // acceptance review: this previously rendered the raw string).
        const err = new Error(Hufi.errors.translate(e.message));
        err.needsApproval = true;
        throw err;
      }
    },

    async removeRelationship(id) {
      if (state.mock) {
        const rel = state.relationships.find((r) => r.id === id);
        if (rel) rel.removed_at = nowIso();
        notify();
        return;
      }
      try {
        await Hufi.api(`/relationships/${id}`, { method: 'DELETE' });
      } catch (e) {
        throw new Error(Hufi.errors.translate(e.message));
      }
      const rel = state.relationships.find((r) => r.id === id);
      if (rel) rel.removed_at = nowIso();
      notify();
    },

    // ---------- Work evidence (visible work / transparency) ----------
    // Same real/mock split as everything else here: /work-evidence exists
    // as real code on Codex's unmerged branch, not yet on main. Used by
    // both cards.js ("Arbeit ansehen" on an agent card) and work.js (the
    // Arbeit/Verlauf view + work summary), so it lives here once rather
    // than being reimplemented twice with potentially different mock data.
    // `query` may include mission_id / task_id (real API filters); agent_id
    // is a client-side filter applied after fetch/mock-generation since the
    // real endpoint has no agent_id filter documented in the contract.
    async loadWorkEvidence(query = {}) {
      const params = new URLSearchParams();
      if (query.mission_id) params.set('mission_id', query.mission_id);
      if (query.task_id) params.set('task_id', query.task_id);
      let items;
      let mock = false;
      try {
        items = await Hufi.api(`/work-evidence${params.toString() ? `?${params}` : ''}`);
      } catch (e) {
        // Do not fabricate evidence in normal RC operation.
        items = [];
      }
      if (query.agent_id) {
        items = items.filter((ev) => ev.metadata && ev.metadata.agent_id === query.agent_id);
      }
      return { items, mock };
    },
  };

  const EVIDENCE_TYPES = [
    { type: 'diff', summary: 'Änderung an der Codebasis vorbereitet.' },
    { type: 'test', summary: 'Tests ausgeführt und geprüft.' },
    { type: 'file', summary: 'Datei erstellt und abgelegt.' },
    { type: 'report', summary: 'Bericht zusammengestellt.' },
    { type: 'routine_result', summary: 'Routine ausgeführt.' },
  ];

  function buildMockWorkEvidence(agents) {
    if (!agents.length) return [];
    const items = [];
    agents.forEach((agent, idx) => {
      const pick = EVIDENCE_TYPES[idx % EVIDENCE_TYPES.length];
      items.push({
        id: mockId('mock-evidence'),
        mission_id: mockId('mock-mission'),
        task_id: mockId('mock-task'),
        source_type: 'agent',
        evidence_type: pick.type,
        summary: pick.summary,
        content: null,
        artifact_ref: null,
        metadata: { agent_id: agent.id },
        created_at: nowIso(),
        redacted_at: null,
        _mock: true,
      });
    });
    return items;
  }
})();
