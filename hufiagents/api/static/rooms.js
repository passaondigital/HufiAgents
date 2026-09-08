/* ==========================================================================
   Hufi — chat rooms (Teamchat / Projektchat / Firmenchat).

   Renders a keyboard-accessible overlay panel for team/project/company
   group conversations. Visually matches chat.js's bubble style (reuses
   .bubble / .bubble--user from chat.css) but is a SEPARATE rendering path,
   because chat.js's data model is strictly 1:1 agent messaging.

   HONESTY NOTE (read before touching this file): there is no backend
   message-storage endpoint for rooms anywhere (not even on the unmerged
   Codex branch that adds /rooms metadata). So messages sent here are
   optimistic, in-memory only, and reset on page reload. No fake agent
   reply is ever generated — that would fabricate working AI behaviour.
   Room *metadata* (id/name/type/host) does go through the real/mock
   Hufi.orgData.createRoom(), same real/mock split as everything else in
   org-data.js.

   Nothing here touches app.js/app.css/index.html/nav.js/agents.js/chat.js.

   Public contract:
     - Hufi.rooms.open({room_type, host_type, host_id, name})
         Opens (creating the room via Hufi.orgData.createRoom(...) first if
         it doesn't already exist for that host_id+room_type) a room panel.
         Stable signature — team/project cards call this directly.
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});
  const esc = Hufi.esc;

  const TYPE_LABEL = { team: 'Teamchat', project: 'Projektchat', company: 'Firmenchat', agent: 'Chat' };

  // Local-only message store: roomId -> [{text, ts}]. Never persisted
  // (no localStorage, no backend call) — intentionally lost on reload.
  const messagesByRoom = new Map();

  let activeOverlay = null;
  let activeTrigger = null;

  // ---------- Org-graph state ----------
  async function ensureOrgState() {
    let state = Hufi.orgData && Hufi.orgData.getState();
    if (state) return state;
    if (Hufi.orgData && typeof Hufi.orgData.load === 'function') {
      try { return await Hufi.orgData.load(); } catch (e) { /* fall through */ }
    }
    return Hufi.orgData ? Hufi.orgData.getState() : null;
  }

  function findExistingRoom(state, roomType, hostId) {
    if (!state || !Array.isArray(state.rooms)) return null;
    return state.rooms.find((r) => r.room_type === roomType && r.host_id === hostId) || null;
  }

  function resolveParticipants(state, room) {
    if (!state) return [];
    if (room.room_type === 'company') return (state.agents || []).slice();
    if (room.room_type === 'team') {
      return Hufi.orgData.relationshipsFor('team', room.host_id)
        .filter((r) => r.relationship_type === 'member_of_team' && r.target_type === 'team' && r.target_id === room.host_id)
        .map((r) => Hufi.orgData.getAgentById(r.source_id))
        .filter(Boolean);
    }
    if (room.room_type === 'project') {
      return Hufi.orgData.relationshipsFor('project', room.host_id)
        .filter((r) => r.relationship_type === 'works_on_project' && r.target_type === 'project' && r.target_id === room.host_id)
        .map((r) => Hufi.orgData.getAgentById(r.source_id))
        .filter(Boolean);
    }
    if (room.room_type === 'agent') {
      const agent = Hufi.orgData.getAgentById(room.host_id);
      return agent ? [agent] : [];
    }
    return [];
  }

  function agentDisplayName(agent) {
    return (Hufi.agents && typeof Hufi.agents.humanizeId === 'function')
      ? Hufi.agents.humanizeId(agent.id)
      : String(agent.id);
  }

  function hostDisplayName(room) {
    if (room.room_type === 'company') return 'Hufi';
    if (room.room_type === 'team') return (Hufi.orgData.getTeamById(room.host_id) || {}).name || room.name;
    if (room.room_type === 'project') return (Hufi.orgData.getProjectById(room.host_id) || {}).name || room.name;
    if (room.room_type === 'agent') {
      const agent = Hufi.orgData.getAgentById(room.host_id);
      return agent ? agentDisplayName(agent) : room.name;
    }
    return room.name;
  }

  function buildHeaderLine(room, participants) {
    const typeLabel = TYPE_LABEL[room.room_type] || 'Chat';
    const count = participants.length;
    const peopleLabel = count === 1 ? '1 digitaler Mitarbeiter' : `${count} digitale Mitarbeiter`;
    if (room.room_type === 'company') return `${typeLabel} · ${peopleLabel}`;
    return `${hostDisplayName(room)} · ${typeLabel} · ${peopleLabel}`;
  }

  // ---------- Overlay: open/close + focus trap (pattern matches agents.js modals) ----------
  function focusableElements(container) {
    return Array.from(container.querySelectorAll('button, input, textarea, select, [href], [tabindex]:not([tabindex="-1"])'))
      .filter((el) => !el.disabled && el.tabIndex !== -1 && el.offsetParent !== null);
  }

  function closeOverlay() {
    if (!activeOverlay) return;
    const overlay = activeOverlay;
    activeOverlay = null;
    document.removeEventListener('keydown', overlay.__onKeydown);
    overlay.remove();
    if (activeTrigger && typeof activeTrigger.focus === 'function') activeTrigger.focus();
    activeTrigger = null;
  }

  function openOverlay(buildFn, ariaLabel) {
    if (activeOverlay) closeOverlay();
    activeTrigger = document.activeElement;

    const overlay = Hufi.el(`<div class="room-overlay" data-fade-in></div>`);
    const card = Hufi.el(`<div class="room-panel card" role="dialog" aria-modal="true"></div>`);
    if (ariaLabel) card.setAttribute('aria-label', ariaLabel);
    overlay.appendChild(card);

    buildFn(card);

    document.body.appendChild(overlay);
    activeOverlay = overlay;

    function onKeydown(e) {
      if (e.key === 'Escape') { closeOverlay(); return; }
      if (e.key !== 'Tab') return;
      const focusable = focusableElements(card);
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
    overlay.__onKeydown = onKeydown;
    document.addEventListener('keydown', onKeydown);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeOverlay(); });

    const closeBtn = card.querySelector('[data-room-close]');
    if (closeBtn) closeBtn.addEventListener('click', closeOverlay);

    const focusable = focusableElements(card);
    if (focusable.length) focusable[0].focus();
    return card;
  }

  // ---------- Render ----------
  function renderBubble(message) {
    const wrap = Hufi.el(`<div class="turn room-turn" data-fade-in></div>`);
    const bubble = Hufi.el(`<div class="bubble bubble--user"></div>`);
    bubble.textContent = message.text;
    wrap.appendChild(bubble);
    wrap.appendChild(Hufi.el(`<span class="room-turn__time faint">${esc(Hufi.fmtTime(message.ts))}</span>`));
    return wrap;
  }

  function renderRoom(card, room) {
    const state = Hufi.orgData.getState();
    const participants = resolveParticipants(state, room);
    const headerLine = buildHeaderLine(room, participants);
    const isMock = Hufi.orgData.isMock();

    card.setAttribute('aria-label', `${room.name} — Chat`);
    card.innerHTML = '';

    card.appendChild(Hufi.el(`
      <div class="room-panel__head">
        <div class="room-panel__heading">
          <h2 class="room-panel__title">${esc(room.name)}</h2>
          <p class="room-panel__meta muted">${esc(headerLine)}</p>
        </div>
        <button type="button" class="icon-btn" data-room-close aria-label="Schließen">✕</button>
      </div>
    `));

    if (isMock) {
      card.appendChild(Hufi.el(`<div class="room-panel__mockbanner">Entwicklungsmodus — Beispieldaten</div>`));
    }

    const participantsWrap = Hufi.el(`<div class="room-participants"></div>`);
    if (participants.length) {
      participants.forEach((agent) => {
        participantsWrap.appendChild(Hufi.el(`<span class="room-participant-chip">${esc(agentDisplayName(agent))}</span>`));
      });
    } else {
      participantsWrap.appendChild(Hufi.el(`<span class="faint">Noch keine Mitglieder zugeordnet.</span>`));
    }
    card.appendChild(participantsWrap);

    const threadEl = Hufi.el(`<div class="room-thread"></div>`);
    card.appendChild(threadEl);

    const messages = messagesByRoom.get(room.id) || [];
    if (!messages.length) {
      threadEl.appendChild(Hufi.el(
        `<p class="empty-hint room-thread-empty">Noch keine Nachrichten in diesem Chat. Schreib die erste Nachricht — sie ist nur für dich in diesem Browser-Tab sichtbar.</p>`
      ));
    } else {
      messages.forEach((m) => threadEl.appendChild(renderBubble(m)));
    }

    const composerWrap = Hufi.el(`
      <div class="room-composer">
        <div class="room-composer__bar">
          <textarea class="room-composer__input" rows="1" placeholder="Nachricht schreiben …" aria-label="Nachricht"></textarea>
          <button type="button" class="room-composer__send" aria-label="Senden">➤</button>
        </div>
        <p class="room-composer__note">Nachrichten in Team-, Projekt- und Firmenchats werden aktuell nur lokal angezeigt und nicht gespeichert.</p>
      </div>
    `);
    card.appendChild(composerWrap);

    const input = composerWrap.querySelector('.room-composer__input');
    const sendBtn = composerWrap.querySelector('.room-composer__send');

    function send() {
      const text = input.value.trim();
      if (!text) return;
      const message = { text, ts: new Date().toISOString() };
      const list = messagesByRoom.get(room.id) || [];
      list.push(message);
      messagesByRoom.set(room.id, list);

      const emptyHint = threadEl.querySelector('.room-thread-empty');
      if (emptyHint) emptyHint.remove();
      threadEl.appendChild(renderBubble(message));
      threadEl.scrollTop = threadEl.scrollHeight;

      input.value = '';
      input.style.height = 'auto';
    }

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 140) + 'px';
    });

    requestAnimationFrame(() => {
      threadEl.scrollTop = threadEl.scrollHeight;
      input.focus();
    });
  }

  // ---------- Public API ----------
  Hufi.rooms = {
    async open({ room_type, host_type, host_id, name } = {}) {
      if (!room_type || !host_id) {
        console.error('Hufi.rooms.open: room_type and host_id are required');
        return;
      }
      const state = await ensureOrgState();
      if (!state) {
        console.error('Hufi.rooms.open: org data unavailable');
        return;
      }
      let room = findExistingRoom(state, room_type, host_id);
      if (!room) {
        try {
          room = await Hufi.orgData.createRoom({
            room_type, host_type, host_id, name: name || TYPE_LABEL[room_type] || 'Chat',
          });
        } catch (e) {
          console.error('Hufi.rooms.open: room could not be created', e);
          return;
        }
      }
      openOverlay((card) => renderRoom(card, room), `${room.name} — Chat`);
    },
  };

  // ---------- Optional entry point: Firmenchat ----------
  // rooms.js owns no nav view of its own, so there is no natural slot for a
  // company-chat entry point yet. A small floating button keeps
  // Hufi.rooms.open({room_type:'company', ...}) reachable without touching
  // nav.js/index.html — the integrating engineer can relocate or remove
  // this once firma/routinen views land their own entry point.
  function mountCompanyEntryPoint() {
    if (document.getElementById('hufiCompanyChatFab')) return;
    const btn = Hufi.el(
      `<button type="button" class="room-fab" id="hufiCompanyChatFab" title="Firmenchat öffnen" aria-label="Firmenchat öffnen">💬<span class="room-fab__label">Firmenchat</span></button>`
    );
    btn.addEventListener('click', () => {
      Hufi.rooms.open({ room_type: 'company', host_type: 'company', host_id: 'hufi', name: 'Firmenchat' });
    });
    document.body.appendChild(btn);
  }

  Hufi.onReady(() => {
    mountCompanyEntryPoint();
  });
})();
