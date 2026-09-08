/* ==========================================================================
   Hufi — app shell integration layer.
   Provides the shared `Hufi` namespace that chat.js and agents.js build on.
   Owned by the integration layer — feature modules must not redefine these.

   Contract for feature modules:
     - Hufi.api(path, opts)         fetch() wrapper: JSON, 401 -> /login redirect
     - Hufi.esc(value)              HTML-escape a string
     - Hufi.fmtTime(value)          locale timestamp formatting
     - Hufi.mount.{sidebarList,chat,rightpaneTitle,rightpaneContent,topbarTitle}
                                     raw DOM nodes to render into
     - Hufi.rightPane.show(title, renderFn)   renderFn(container) fills it
     - Hufi.rightPane.hide()
     - Hufi.onReady(fn)             fn() runs once, after DOM is ready
     - Hufi.chat.openAgent(agentId) IMPLEMENTED BY chat.js — sidebar clicks call this
     - Hufi.agents.*                IMPLEMENTED BY agents.js
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});

  Hufi.mount = {
    sidebarList: document.getElementById('sidebarList'),
    chat: document.getElementById('chat'),
    rightpaneTitle: document.getElementById('rightpaneTitle'),
    rightpaneContent: document.getElementById('rightpaneContent'),
    topbarTitle: document.getElementById('topbarTitle'),
  };

  Hufi.esc = function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  };

  Hufi.fmtTime = function fmtTime(value) {
    if (!value) return '—';
    return new Date(value).toLocaleString('de-DE');
  };

  Hufi.el = function el(html) {
    const div = document.createElement('div');
    div.innerHTML = html.trim();
    return div.firstElementChild;
  };

  const connStatus = document.getElementById('connStatus');

  Hufi.api = async function api(path, opts) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (response.status === 401) {
      window.location.href = '/login';
      throw new Error('unauthenticated');
    }
    if (connStatus) connStatus.textContent = 'verbunden';
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch (e) { /* not JSON */ }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
  };

  const rightpane = document.getElementById('rightpane');
  const rightpaneScrim = document.getElementById('rightpaneScrim');
  const shell = document.getElementById('shell');

  // v1.1.2: the right pane is no longer a permanent desktop column (see
  // app.css) -- it only occupies grid width once it actually has context
  // to show. #shell carries .rightpane-open so the CSS grid can react;
  // below 1100px that class is a no-op and the existing slide-in overlay
  // (.rightpane--open + scrim) still does the work.
  Hufi.rightPane = {
    show(title, renderFn) {
      Hufi.mount.rightpaneTitle.textContent = title;
      Hufi.mount.rightpaneContent.innerHTML = '';
      renderFn(Hufi.mount.rightpaneContent);
      rightpane.classList.add('rightpane--open');
      rightpaneScrim.classList.add('scrim--visible');
      shell.classList.add('rightpane-open');
    },
    hide() {
      rightpane.classList.remove('rightpane--open');
      rightpaneScrim.classList.remove('scrim--visible');
      shell.classList.remove('rightpane-open');
    },
  };

  const readyFns = [];
  let domReady = false;
  Hufi.onReady = function onReady(fn) {
    if (domReady) fn();
    else readyFns.push(fn);
  };

  // ---------- Chrome wiring (sidebar/rightpane toggles, logout) ----------
  const sidebar = document.getElementById('sidebar');
  const sidebarScrim = document.getElementById('sidebarScrim');
  function openSidebar() { sidebar.classList.add('sidebar--open'); sidebarScrim.classList.add('scrim--visible'); }
  function closeSidebar() { sidebar.classList.remove('sidebar--open'); sidebarScrim.classList.remove('scrim--visible'); }
  document.getElementById('sidebarToggle').onclick = () => {
    sidebar.classList.contains('sidebar--open') ? closeSidebar() : openSidebar();
  };
  sidebarScrim.onclick = closeSidebar;
  Hufi.closeSidebar = closeSidebar;

  document.getElementById('rightpaneToggle').onclick = () => {
    if (rightpane.classList.contains('rightpane--open')) {
      Hufi.rightPane.hide();
    } else {
      rightpane.classList.add('rightpane--open');
      rightpaneScrim.classList.add('scrim--visible');
      shell.classList.add('rightpane-open');
    }
  };
  document.getElementById('rightpaneClose').onclick = () => Hufi.rightPane.hide();
  rightpaneScrim.onclick = () => Hufi.rightPane.hide();

  document.getElementById('logoutBtn').onclick = async () => {
    await fetch('/logout', { method: 'POST' }).catch(() => {});
    window.location.href = '/login';
  };

  window.addEventListener('DOMContentLoaded', () => {
    domReady = true;
    readyFns.forEach((fn) => {
      try { fn(); } catch (e) { console.error(e); }
    });
  });
})();
