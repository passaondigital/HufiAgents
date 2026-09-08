/* ==========================================================================
   Hufi — credential UX module.

   The fix for "paste your secret into a chat message": a reusable, generic
   connect-a-credential modal, plus a pure detector + warning-banner
   component that other code (chat.js's send flow, once wired in during
   integration — see interceptChatInput below) can use to catch a secret
   before it is ever sent as a chat message.

   SECURITY NOTE: no secret value is ever read/logged/persisted beyond what
   is strictly needed for the one submit request. Nothing here writes a
   secret to localStorage, console, or any Hufi.* state object — only
   non-secret connection METADATA (connector id, label, connectedAt, mock
   flag) is kept in memory so the modal can show a "connected" state.

   BACKEND STATUS: POST /credentials (and DELETE /credentials/{connector})
   exist as real code on Codex's unmerged codex/v1-2-core-capabilities
   branch, not yet on main. Every request is wrapped in try/catch; on any
   failure (404 today, or a real error later) this falls back to the same
   isolated, clearly-labelled mock pattern org-data.js uses elsewhere —
   the modal still completes, but says so honestly ("Nur lokale Vorschau").

   Nothing here touches app.js/app.css/index.html/agents.js/agents.css/chat.js.

   Public contract:
     - Hufi.credentials.openConnectModal({connector, label})
     - Hufi.credentials.interceptChatInput(text) -> {looksLikeSecret, reason}
         Pure function — no DOM, no state. Safe to call from anywhere.
     - Hufi.credentials.renderSecretWarning(onSecure, onDiscard) -> HTMLElement
   ========================================================================== */
(function () {
  const Hufi = (window.Hufi = window.Hufi || {});
  const esc = Hufi.esc;

  // Known connectors get a friendlier secret-field label; anything else
  // falls back to a generic one rather than guessing a wrong term.
  const SECRET_FIELD_LABEL = {
    github: 'Personal Access Token',
    openai: 'API-Schlüssel',
    anthropic: 'API-Schlüssel',
    slack: 'Bot-Token',
  };
  function secretLabelFor(connector) {
    return SECRET_FIELD_LABEL[connector] || 'Zugangsschlüssel';
  }

  // In-memory ONLY, per page load. Holds connection METADATA, never the
  // secret itself. connector -> { label, connectedAt, mock, maskedHint }
  const connectionState = new Map();

  let activeOverlay = null;
  let activeTrigger = null;

  // ---------- Overlay: open/close + focus trap (same pattern as agents.js modals) ----------
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

    const overlay = Hufi.el(`<div class="cred-overlay" data-fade-in></div>`);
    const card = Hufi.el(`<div class="cred-card card" role="dialog" aria-modal="true"></div>`);
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

    const closeBtn = card.querySelector('[data-cred-close]');
    if (closeBtn) closeBtn.addEventListener('click', closeOverlay);

    const focusable = focusableElements(card);
    if (focusable.length) focusable[0].focus();
    return card;
  }

  // ---------- Client-side "Prüfen": a loose plausibility check ONLY.
  // This never calls out to GitHub/OpenAI/etc — there is no real
  // credential-check endpoint to call. It just catches empty/obviously
  // malformed input before submit. ----------
  function loosePlausibilityCheck(rawValue) {
    const value = rawValue.trim();
    if (!value) return { ok: false, message: 'Bitte einen Zugangsschlüssel eingeben.' };
    if (/\s/.test(value)) return { ok: false, message: 'Das enthält Leerzeichen — ein Zugangsschlüssel ist meist eine einzelne, zusammenhängende Zeichenfolge.' };
    if (value.length < 8) return { ok: false, message: 'Das wirkt zu kurz für einen Zugangsschlüssel.' };
    return { ok: true, message: 'Sieht plausibel aus. Das ist keine echte Prüfung beim Anbieter.' };
  }

  // ---------- Views ----------
  function renderConnectForm(card, connector, label, onConnected) {
    const title = `${label || connector} verbinden`;
    const secretLabel = secretLabelFor(connector);

    card.innerHTML = '';
    card.appendChild(Hufi.el(`
      <div class="row">
        <h3 class="spacer">${esc(title)}</h3>
        <button type="button" class="icon-btn" data-cred-close aria-label="Schließen">✕</button>
      </div>
    `));

    const form = Hufi.el(`
      <form class="stack cred-form" novalidate>
        <label class="field-label" for="credSecretInput">${esc(secretLabel)}</label>
        <div class="cred-input-row">
          <input id="credSecretInput" type="password" autocomplete="off" spellcheck="false" required />
          <button type="button" class="icon-btn cred-eye" aria-label="Zugangsschlüssel anzeigen" aria-pressed="false">👁</button>
        </div>
        <p class="cred-check-msg faint" id="credCheckMsg" aria-live="polite" hidden></p>
        <div class="row cred-form__actions">
          <span class="spacer"></span>
          <button type="button" class="btn btn--ghost" id="credCheckBtn">Prüfen</button>
          <button type="submit" class="btn btn--primary">Verbinden</button>
        </div>
        <p class="cred-error" id="credError" aria-live="polite" hidden></p>
      </form>
    `);
    card.appendChild(form);

    const input = form.querySelector('#credSecretInput');
    const eyeBtn = form.querySelector('.cred-eye');
    const checkMsg = form.querySelector('#credCheckMsg');
    const errorEl = form.querySelector('#credError');

    eyeBtn.addEventListener('click', () => {
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      eyeBtn.setAttribute('aria-pressed', String(!showing));
      eyeBtn.setAttribute('aria-label', showing ? 'Zugangsschlüssel anzeigen' : 'Zugangsschlüssel verbergen');
      eyeBtn.textContent = showing ? '👁' : '🙈';
    });

    form.querySelector('#credCheckBtn').addEventListener('click', () => {
      const result = loosePlausibilityCheck(input.value);
      checkMsg.hidden = false;
      checkMsg.textContent = result.message;
      checkMsg.classList.toggle('cred-check-msg--ok', result.ok);
      checkMsg.classList.toggle('cred-check-msg--bad', !result.ok);
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const value = input.value; // read once; scoped to this handler only
      if (!value.trim()) {
        errorEl.hidden = false;
        errorEl.textContent = 'Bitte einen Zugangsschlüssel eingeben.';
        return;
      }
      const submitBtn = form.querySelector('button[type="submit"]');
      const checkBtn = form.querySelector('#credCheckBtn');
      submitBtn.disabled = true;
      checkBtn.disabled = true;
      errorEl.hidden = true;

      let maskedHint = null;
      try {
        const response = await Hufi.api('/credentials', {
          method: 'POST',
          body: JSON.stringify({ connector, label: label || connector, secret: value }),
        });
        if (response && typeof response.masked_hint === 'string') maskedHint = response.masked_hint;
      } catch (err) {
        // The backend currently exposes metadata-only credential handles and
        // intentionally rejects plaintext registration. Never show a fake
        // connected state when durable secure storage is unavailable.
        errorEl.hidden = false;
        errorEl.textContent = 'Diese Verbindung kann in dieser Version noch nicht dauerhaft sicher gespeichert werden.';
        submitBtn.disabled = false;
        checkBtn.disabled = false;
        return;
      }
      // `value` goes out of scope here — never stored anywhere beyond this line.
      onConnected({ mock: false, maskedHint });
    });
  }

  function renderConnectedState(card, connector, label, info, onReplace, onDisconnect) {
    card.innerHTML = '';
    card.appendChild(Hufi.el(`
      <div class="row">
        <h3 class="spacer">${esc(label || connector)}</h3>
        <button type="button" class="icon-btn" data-cred-close aria-label="Schließen">✕</button>
      </div>
    `));

    const body = Hufi.el(`<div class="stack cred-connected"></div>`);
    // TRUTHFULNESS (v1.2 product acceptance review, section 9): even on the
    // real, non-mock success path, POST /credentials only ever creates a
    // metadata handle (CredentialRef has no secret field at all -- see
    // hufiagents/contracts.py) -- the actual secret is never stored, so
    // Hufi cannot yet use this connection for anything. "✓ verbunden"
    // (unconditionally, real or mock) claimed a working, usable connection
    // that doesn't exist yet. Never say "sicher gespeichert" here.
    if (info.mock) {
      body.appendChild(Hufi.el(`<p class="cred-connected__status">${esc(label || connector)}: Verbindung vorbereitet</p>`));
      body.appendChild(Hufi.el(`<p class="cred-mocknote">Nur lokale Vorschau — Backend noch nicht verbunden.</p>`));
    } else {
      body.appendChild(Hufi.el(`<p class="cred-connected__status">${esc(label || connector)}: Verbindung vorbereitet</p>`));
      body.appendChild(Hufi.el(`<p class="faint">Zugang wird in dieser Version noch nicht dauerhaft gespeichert. Hufi kann diese Verbindung noch nicht für Aufgaben nutzen.</p>`));
    }
    if (info.maskedHint) {
      body.appendChild(Hufi.el(`<p class="faint">${esc(info.maskedHint)}</p>`));
    }
    const actions = Hufi.el(`
      <div class="row cred-connected__actions">
        <span class="spacer"></span>
        <button type="button" class="btn btn--ghost" id="credReplace">Token ersetzen</button>
        <button type="button" class="btn btn--danger" id="credDisconnect">Verbindung trennen</button>
      </div>
    `);
    body.appendChild(actions);
    card.appendChild(body);

    actions.querySelector('#credReplace').addEventListener('click', onReplace);
    actions.querySelector('#credDisconnect').addEventListener('click', onDisconnect);
  }

  // ---------- Public: openConnectModal ----------
  function openConnectModal({ connector, label } = {}) {
    if (!connector) {
      console.error('Hufi.credentials.openConnectModal: connector is required');
      return;
    }

    function handleConnected(card, { mock, maskedHint }) {
      const info = { label: label || connector, connectedAt: new Date().toISOString(), mock, maskedHint };
      connectionState.set(connector, info);
      showConnected(card, info);
    }

    function showConnected(card, info) {
      renderConnectedState(card, connector, label, info,
        () => renderConnectForm(card, connector, label, (result) => handleConnected(card, result)),
        async () => {
          try {
            await Hufi.api(`/credentials/${encodeURIComponent(connector)}`, { method: 'DELETE' });
          } catch (e) {
            // No real endpoint yet (or it failed) — still an honest local
            // disconnect, nothing was really persisted server-side to begin with.
          }
          connectionState.delete(connector);
          renderConnectForm(card, connector, label, (result) => handleConnected(card, result));
        }
      );
    }

    openOverlay((card) => {
      const existing = connectionState.get(connector);
      if (existing) {
        showConnected(card, existing);
      } else {
        renderConnectForm(card, connector, label, (result) => handleConnected(card, result));
      }
    }, `${label || connector} verbinden`);
  }

  // ---------- Public: interceptChatInput (pure — no DOM, no state) ----------
  // Conservative heuristic: common secret-token prefixes, or a long
  // high-entropy alphanumeric run with no spaces. Errs toward flagging —
  // a false positive is a minor annoyance, a missed real secret is a leak.
  const SECRET_PATTERNS = [
    { re: /\bghp_[A-Za-z0-9]{20,}/, reason: 'Beginnt wie ein GitHub Personal Access Token (ghp_…).' },
    { re: /\bgithub_pat_[A-Za-z0-9_]{20,}/, reason: 'Beginnt wie ein GitHub Personal Access Token (github_pat_…).' },
    { re: /\bgho_[A-Za-z0-9]{20,}/, reason: 'Beginnt wie ein GitHub-OAuth-Token (gho_…).' },
    { re: /\bsk-[A-Za-z0-9]{20,}/, reason: 'Beginnt wie ein API-Schlüssel (sk-…).' },
    { re: /\bxox[bpoa]-[A-Za-z0-9-]{10,}/, reason: 'Beginnt wie ein Slack-Token (xox…-).' },
    { re: /\bAKIA[0-9A-Z]{16}\b/, reason: 'Sieht wie eine AWS Access Key ID aus (AKIA…).' },
  ];

  function interceptChatInput(text) {
    const value = String(text || '');
    for (const { re, reason } of SECRET_PATTERNS) {
      if (re.test(value)) return { looksLikeSecret: true, reason };
    }
    // Long, no-space, high-entropy-looking run: mixed letters+digits (or
    // mixed case) at length >= 30 — the shape of a raw token/secret, not
    // of a normal German sentence.
    const runs = value.match(/[A-Za-z0-9_-]{30,}/g) || [];
    for (const run of runs) {
      const hasDigit = /\d/.test(run);
      const hasLetter = /[A-Za-z]/.test(run);
      const hasMixedCase = /[a-z]/.test(run) && /[A-Z]/.test(run);
      if ((hasDigit && hasLetter) || hasMixedCase) {
        return { looksLikeSecret: true, reason: 'Enthält eine lange, zufällig wirkende Zeichenfolge ohne Leerzeichen.' };
      }
    }
    return { looksLikeSecret: false, reason: null };
  }

  // ---------- Public: renderSecretWarning ----------
  function renderSecretWarning(onSecure, onDiscard, onSend) {
    const el = Hufi.el(`
      <div class="cred-warning" role="alert">
        <span class="cred-warning__icon" aria-hidden="true">⚠</span>
        <span class="cred-warning__text">Das sieht nach einem Zugangsschlüssel aus.</span>
        <span class="spacer"></span>
        <button type="button" class="btn btn--sm btn--primary" data-action="secure">Sicher hinterlegen</button>
        <button type="button" class="btn btn--sm btn--ghost" data-action="discard">Verwerfen</button>
        <button type="button" class="btn btn--sm btn--ghost" data-action="send">Trotzdem senden</button>
      </div>
    `);
    el.querySelector('[data-action="secure"]').addEventListener('click', () => {
      if (typeof onSecure === 'function') onSecure();
    });
    el.querySelector('[data-action="discard"]').addEventListener('click', () => {
      if (typeof onDiscard === 'function') onDiscard();
    });
    el.querySelector('[data-action="send"]').addEventListener('click', () => {
      if (typeof onSend === 'function') onSend();
    });
    return el;
  }

  Hufi.credentials = {
    openConnectModal,
    interceptChatInput,
    renderSecretWarning,
  };
})();
