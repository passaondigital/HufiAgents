# Hufi Design System

**Status:** living reference for the V1.1 chat-first frontend (`hufiagents/api/static/`)
**Scope:** documents the design system as implemented in PR #13, plus the principles it should keep obeying as it grows. Not abstract design theory — every section maps to real tokens/classes in `app.css`, `chat.css`, `agents.css`.

## 1. Design principles

1. **Messenger first, dashboard never.** If a screen looks like it belongs in an admin panel, it's wrong. Chat is the main surface; everything else is a supporting pane.
2. **One idea per screen.** The empty chat state has exactly one primary action (type or tap a chip). The result card has exactly two actions. Resist adding a third button "while we're at it."
3. **Plain language first, technical truth available.** Every raw identifier, risk code, provider name, or JSON blob lives behind an explicit "Details" affordance — never in the primary flow. See `HUFI-UX-LANGUAGE.md`.
4. **Calm motion, not decoration.** Animation exists to explain a state change (a message arriving, a pane opening), never to entertain. 150–250ms, no bounce.
5. **Same shell, three widths.** Desktop, tablet and mobile are the same information architecture (sidebar → chat → context), not three different apps. What changes is *how much is visible at once*, never *what exists*.
6. **Reuse the primitive before inventing a new one.** `.btn`, `.pill`, `.card`, `.avatar` cover the vast majority of new UI. A new component class is justified only when none of these fit.

## 2. Layout

Three-pane shell, defined once in `app.css`, never redefined by feature modules:

| Breakpoint | Sidebar | Chat | Right pane |
|---|---|---|---|
| < 700px | full-screen overlay (slide-in from left, scrim) | full width, primary surface | full-screen overlay (slide-in from right, scrim) |
| 700–1099px | static column, 240px | fills remaining width | overlay (slide-in from right, scrim) |
| ≥ 1100px | static column, 280px | fills remaining width, capped ~720px content column, centered | static column, 340px |

Implementation notes (for anyone extending the shell):
- The grid lives on `#shell` (`display:grid` from 700px up). It **must** keep an explicit `grid-template-rows: minmax(0, 1fr)` — an implicit `auto` row will size to the tallest item's *content* height and stretch every column to match (this broke the chat column once already when the System/Details JSON dump was open; see `docs/workstreams/CLAUDE-UX-STATE.md`).
- Every grid item that owns internal scrolling (`.sidebar`, `.chat`, `.rightpane`) needs `min-height: 0` — without it, `overflow-y: auto` on a descendant silently does nothing.
- Below 1100px, `#topbar` becomes the only chrome: hamburger (`#sidebarToggle`) — title — info icon (`#rightpaneToggle`). It does not exist above 1100px; both panes are just always visible there.
- Visibility toggled via `.sidebar--open` / `.rightpane--open` classes, never inline `style.display`. If you toggle the `hidden` attribute on an element that also carries a class declaring `display` (e.g. `.row`, `.stack`, `.chat-empty`, `.chat-msglist`), you must add a matching `[hidden]` override — plain `[hidden]{display:none}` loses to any class selector on specificity.

## 3. Color tokens (`app.css :root`)

Dark-only today (see §12 for light-mode readiness).

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0b0e14` | page background |
| `--surface` | `#12161f` | sidebar, rightpane, topbar, modal card |
| `--surface-2` | `#171c27` | cards, chips, inputs, hufi bubble |
| `--surface-raised` | `#1c2230` | hover state on surface-2 elements |
| `--border` / `--border-soft` | `#232a38` / `#1a202c` | dividers, card borders |
| `--text` / `--text-muted` / `--text-faint` | `#eef1f6` / `#8b93a3` / `#5b6578` | primary / secondary / tertiary text |
| `--accent` / `--accent-soft` / `--accent-bg` | `#4f7dfb` / `#8fb0ff` / rgba(79,125,251,.14) | primary action, links, user bubble |
| `--ok` / `--warn` / `--bad` / `--idle` (+ `-bg` pairs) | green / amber / red / gray | status pills, dots, tone system |

**Tone system:** every status surface (pill, dot) picks one of `ok / warn / bad / idle / accent` and uses the token pair consistently — never a one-off color. Current mapping: agent `active` → ok, `disabled` → idle; audit events with `error`/`policy_blocked` → bad, `approval_requested`/`recovery` → warn, `tool_result`/`review`/`state_transition` → ok, everything else → idle. Keep new status types inside this five-tone vocabulary rather than adding a sixth color.

## 4. Spacing & radius

Two linear scales, both in `app.css :root`, used everywhere — no ad-hoc `padding: 13px`:

- Spacing: `--space-1` 4px … `--space-6` 32px (4/8/12/16/24/32).
- Radius: `--radius-sm` 8px (chips-inside-cards, inputs), `--radius` 12px (cards, panels), `--radius-lg` 18px (message bubbles, modal-adjacent), `--radius-full` (pills, avatars, chips, buttons).
- Shadow: `--shadow-card` (default card elevation), `--shadow-pop` (modal/overlay elevation — not yet used everywhere it should be, see audit).

## 5. Typography

System font stack (`-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Inter, system-ui, sans-serif`), no webfont download — keeps first paint instant and matches the OS look Grok Bot also leans on.

| Role | Size | Weight | Example |
|---|---|---|---|
| Empty-state title | 1.5rem (1.25rem <480px) | 700 | "Was soll ich für dich erledigen?" |
| Section label (uppercase, tracked) | .78–.82rem | 600 | "Live-Aktivität", card `.l` labels |
| Body / bubble text | .9–.93rem | 400 | chat bubbles, result text |
| Secondary / meta | .78–.86rem | 400 | timestamps, role lines, faint hints |
| Pill / badge | .74–.76rem | 600 | status pills, tags |

Line-height 1.4–1.5 throughout. No more than 3 weights in use (400/500/600/700) — resist adding a 300 or 800 for emphasis; use color/size instead.

## 6. Core components

**Buttons (`.btn`)** — pill-shaped, `--radius-full`. Variants: `.btn--primary` (accent fill, one per screen max), `.btn--ghost` (default, most actions), `.btn--danger` (destructive/deny), `.btn--sm` (compact, cards/toolbars). Minimum tap height 40px on any control that appears below 1100px (chat send/mic, chips already comply; audit whether all `.btn--sm` instances do — see `UX-AUDIT-REPORT.md`).

**Pills (`.pill.tone-*`)** — status-only, never interactive. Five tones per §3.

**Cards (`.card`)** — the one elevated-surface primitive: result cards, approval cards, the "Computer" placeholder, the modal body. `surface-2` background, `--radius`, `--shadow-card`, `--space-4` padding. Don't nest a `.card` inside a `.card`.

**Avatars (`.avatar` / `--sm` / `--lg`)** — circular, initials or a single letter, background color deterministically hashed from an id (`hashHue()` in `agents.js`) so the same agent always gets the same color across sessions without a color field in the backend.

**Chat bubbles** — user: accent fill, right-aligned, `border-bottom-right-radius` clipped for a "tail" cue. Hufi: `surface-2`, left-aligned, same clipped-corner cue mirrored. Both `white-space:pre-wrap; word-break:break-word` (never let a long word force horizontal scroll).

**Approval card** — plain-language framing ("Hufi möchte etwas tun") + `summary` field as body copy; `risk_class` only inside a `<details>` toggle. Two actions: Zulassen (`.btn--primary`) / Ablehnen (`.btn--ghost`). This is the one card type that should feel the most deliberate/weighty — it's a real decision, not a status update.

**Result card** — status pill (`tone-ok`/`tone-bad`/`tone-idle` matching Fertig/Nicht geschafft/Abgebrochen) + free-text result, truncated at 320 chars with a "Bericht öffnen" expand. Collapses to a small dashed pill ("Ergebnis anzeigen") on dismiss rather than disappearing — the result is never fully lost from view.

**Modal (`.modal-overlay` / `.modal-card`)** — centered, `role="dialog" aria-modal="true"`, Escape-to-close, scrim-click-to-close, max-width 420px, internal scroll if content exceeds `90vh`. Currently the only modal in the product ("+ Neuer Hufi") — keep future modals to this same pattern rather than inventing a second one.

**Inputs** — `surface`/`surface-2` background, 1px `--border`, `--radius-sm` (form fields) or `--radius-lg` (chat composer, deliberately friendlier/rounder since it's the primary action surface). Focus state: `border-color: var(--accent)`, no default browser outline removed without a replacement.

**Toasts** — **not yet implemented anywhere in the product.** Errors currently render inline (e.g. the Hufi bubble replaced with an error message, `alert()`-free). Before introducing a toast system, check whether inline/contextual feedback (the existing pattern) can just be extended — a toast is justified only for global, non-blocking notices that don't belong to one specific card/thread (e.g. "Verbindung wiederhergestellt"). If added: `surface-raised` background, `--shadow-pop`, bottom-center on mobile / bottom-right on desktop, auto-dismiss 4–6s, one visible at a time.

## 7. Motion

`--fast` 150ms / `--normal` 250ms, both `cubic-bezier(.2,.7,.2,1)` (`--ease`) — a slight overshoot-free ease-out, used for every hover/toggle/slide-in. `[data-fade-in]` is the one content-entrance animation (opacity+translateY, 250ms) — apply it to new chat turns, cards, and right-pane content as they mount, never to persistent chrome (sidebar, topbar).

## 8. Hover / focus / touch

- Hover: background shifts one step up the surface scale (`surface` → `surface-2` → `surface-raised`); never a color-only change on dark backgrounds (too subtle to notice reliably).
- Focus: rely on the browser's native `:focus-visible` ring wherever possible; only `.agent-row` currently defines an explicit focus style (background match with `:hover`). Audit whether every other interactive element (chips, pills-that-should-not-be-interactive, modal buttons) has a visible focus state — see `UX-AUDIT-REPORT.md`.
- Touch targets: 40px minimum height on anything tappable below 1100px. Verified for chat input bar controls and chips; needs verification for `.btn--sm` instances inside cards (approval/result actions) and the `.color-swatch` picker (currently 28px — likely too small, flagged for audit).

## 9. Agent avatars

No avatar image upload in V1.1 — identity is: hashed hue → `hsl(hue, 58%, 42%)` background + initials (first two letters of a one-word name, first letters of two words otherwise). This is deterministic and free (no backend field needed) but means all avatars share the same saturation/lightness — visually consistent, but two agents can land on visually similar hues by chance. If a real avatar/color field ever ships in the backend (PR #12 doesn't add one yet), prefer it over the hash but keep the hash as the fallback for agents that don't set one.

## 10. Responsive summary

See §2 for the shell. Component-level rules: message bubbles cap at 82% width (90% below 480px); the chat content column caps at 720px and centers on wide screens so lines don't run edge-to-edge on a 1920px monitor; the right pane caps at 380px/90vw so it never eats the whole screen on a small tablet.

## 11. Dark/light readiness

**Dark-only today** (`color-scheme: dark` hardcoded, no light palette defined). All colors are CSS custom properties on `:root`, which is the correct starting shape for a future light mode — the work would be adding a `prefers-color-scheme: light` (or explicit toggle) block that redefines the same token names, not a rewrite of any component CSS. Not scheduled for V1.1; noting the readiness for whoever picks it up next.

## 12. What this system deliberately does NOT do (yet)

- No design tokens file separate from `app.css` (no build step in this repo — see `docs/ARCHITECTURE.md`, V1 is intentionally framework/bundler-free). If a build step is ever introduced, extracting tokens to JSON/TS would be the natural next step, not before.
- No component library/Storybook — five feature files (`app.*`, `chat.*`, `agents.*`) are still small enough to hold the whole system in your head. Revisit if a fourth feature module (e.g. Routinen, Computer) grows large.
