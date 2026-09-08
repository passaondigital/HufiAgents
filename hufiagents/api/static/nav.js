/* ==========================================================================
   Hufi — primary navigation (v1.2 "digital company" shell).
   Owned by the integration layer, same tier as app.js.

   Contract for feature modules:
     - Hufi.views.register(name, { onShow(container), onHide() })
         Called once at load. `container` is the view's <section data-view>
         element (already in the DOM, empty). onShow runs every time the
         view becomes active (including the first time) -- mount your UI
         into `container` there, lazily. onHide is optional (pause polling,
         stop a chat-room subscription, etc.) and runs when the user
         navigates away.
     - Hufi.views.show(name)     switch views programmatically (e.g. a
                                  "Projekt öffnen" button inside another view)
     - Hufi.views.current()      the active view name

   Five views ship in index.html: hufi, firma, projekte, routinen, arbeit.
   "hufi" is the existing v1.1.2 chat surface (chat.js) and needs no
   registration -- it is simply what's visible before any other view has
   ever been opened.
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});

  const root = document.getElementById('root');
  const navButtons = Array.from(document.querySelectorAll('.primary-nav__item'));
  const sections = {};
  document.querySelectorAll('.view').forEach((el) => {
    sections[el.dataset.view] = el;
  });

  const registry = {}; // name -> { onShow, onHide, mounted }
  let current = 'hufi';

  function setActiveNavButton(name) {
    navButtons.forEach((btn) => {
      if (btn.dataset.view === name) btn.setAttribute('aria-current', 'page');
      else btn.removeAttribute('aria-current');
    });
  }

  Hufi.views = {
    register(name, handlers) {
      registry[name] = { onShow: handlers.onShow, onHide: handlers.onHide, mounted: false };
    },
    current() {
      return current;
    },
    show(name) {
      if (!sections[name]) return;
      if (name === current) return;

      const prevEntry = registry[current];
      if (prevEntry && typeof prevEntry.onHide === 'function') {
        try { prevEntry.onHide(); } catch (e) { console.error(e); }
      }

      sections[current].hidden = true;
      sections[name].hidden = false;
      root.dataset.activeView = name;
      setActiveNavButton(name);
      Hufi.mount.topbarTitle.textContent = navButtons.find((b) => b.dataset.view === name)?.textContent.trim() || 'Hufi';
      current = name;

      const entry = registry[name];
      if (entry && typeof entry.onShow === 'function') {
        try {
          entry.onShow(sections[name]);
          entry.mounted = true;
        } catch (e) {
          console.error(e);
          sections[name].innerHTML = '<p class="empty-hint">Das hat leider nicht geklappt.</p>';
        }
      }

      // Non-Hufi views don't use the agent contact sidebar -- if it was
      // open as a mobile overlay, close it so it doesn't linger.
      if (name !== 'hufi' && typeof Hufi.closeSidebar === 'function') Hufi.closeSidebar();
    },
  };

  navButtons.forEach((btn) => {
    btn.addEventListener('click', () => Hufi.views.show(btn.dataset.view));
  });

  // Org-graph data (agents/teams/projects/resources/relationships/rooms) is
  // shared by every non-Hufi view, so load it once at boot rather than
  // once per view-open. See org-data.js for the real/mock fallback.
  Hufi.onReady(() => {
    Hufi.orgData.load().catch((e) => console.error('orgData.load failed', e));
  });
})();
