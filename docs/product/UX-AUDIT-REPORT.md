# UX-Audit — HufiAgents V1.1 Chat-Shell (PR #13)

**Datum:** 2026-09-08
**Geprüfter Stand:** Branch `claude/product-qa-v1x`, `hufiagents/api/static/{index.html,app.css,app.js,chat.css,chat.js,agents.css,agents.js}`
**Methode:** Echte Browser-Sessions mit Playwright/Chromium gegen eine lokal laufende Instanz (Login als `pascal`, Agenten-Registry `builder/hufi_chief/integrator/project_lead/reviewer/security`). Es wurde tatsächlich geklickt, getippt, per Tab navigiert, die Fensterbreite verändert und eine echte Mission ("Sag in einem Satz Hallo.") bis zur fertigen Ergebniskarte durchlaufen. Screenshots liegen (nicht im Repo, nur lokal) unter `/tmp/hufi-qa1-shots/`.

**Abdeckung:** Alle 7 geforderten Breakpoints (1920×1080, 1366×768, 1024×768, 768×1024, 430×932, 390×844, 360×800) wurden für "leerer Chat" und "+ Neuer Hufi"-Modal erfasst. Agent-Detail-Pane und System/Details-Ansicht wurden vollständig für 1920×1080, 1366×768, 1024×768, 768×1024 und stellvertretend für die kleinste Handy-Breite (390×844) erfasst; bei 430×932 und 360×800 wurde dieselbe Interaktion aus Zeitgründen nicht zusätzlich wiederholt (identisches CSS/Verhalten wie 390×844 zu erwarten, da alle drei unterhalb des 700px-Breakpoints liegen und denselben Sidebar-Overlay-Pfad nutzen). Der vollständige Sende-Empfangs-Zyklus einer echten Mission wurde bei 1920×1080 und 390×844 durchgespielt. Keine Konsolenfehler und kein horizontales Scrollen des `<body>` wurden bei irgendeinem der geprüften Breakpoints beobachtet — das ist ein echtes Plus.

---

## Angewendete Fixes (nach diesem Audit, in derselben QA-Session)

Alle sechs als "SAFE FIX CANDIDATE" markierten Punkte wurden geprüft und angewendet, plus zwei kleine, in sich geschlossene JS-Fixes ohne API-/Backend-Berührung (Modal-Fokus-Trap, `humanizeId()`-Konsistenz). Jeder Fix wurde anschließend erneut live per Playwright verifiziert (echte Tab-Navigation, kein programmatisches `.focus()`).

- ✅ **Finding 1 (Rightpane-Scrim/Sidebar-z-index):** `z-index: auto` im 700px-Block ergänzt (`app.css`). Live bestätigt: Sidebar-z-index jetzt `auto` bei Tablet-Breite, Scrim korrekt sichtbar.
- ✅ **Finding 2 (Touch-Targets):** `.icon-btn` 34px→40px, `.color-swatch` 28px→36px (+ größerer Gap), `.details-toggle`/`.result-mini` `min-height` 32px→40px.
- ✅ **Finding 3 (kein Fokusring auf `.agent-row`):** Hover/Focus getrennt, `:focus-visible` bekommt `outline: 2px solid var(--accent)`. Live per echter Tab-Navigation bestätigt (`outlineStyle: solid`, `outlineColor: rgb(79,125,251)`).
- ✅ **Finding 4 (`--text-faint`/`--idle` Kontrast):** `#5b6578`→`#7a86a0`, `#6b7484`→`#7c8699`. Live bestätigt (`getComputedStyle` liefert `rgb(122,134,160)`).
- ✅ **Modal-Fokus-Trap (schwerwiegendster Einzelbefund):** `agents.js` `openNewHufiModal()` setzt jetzt initialen Fokus auf `#newHufiName`, hält den Fokus per Tab-Trap im Dialog und stellt ihn beim Schließen auf den auslösenden Button zurück. Live bestätigt: 10 aufeinanderfolgende Tabs blieben vollständig innerhalb `.modal-overlay`.
- ✅ **"builder" statt "Builder" in Topbar/Systemnotiz** (aus `PRODUCT-FLOW-FINDINGS.md`, SOLL Punkt 6): `agents.js` exportiert jetzt `Hufi.agents.humanizeId`, `chat.js` nutzt es in `openAgent()`. Live bestätigt: Topbar-Titel und Systemnotiz zeigen jetzt "Builder" statt "builder".

Nicht angewendet (bewusst nur dokumentiert, da kein reiner CSS/UI-Fix ohne Produktentscheidung möglich): Routine-Erkennung im Chat, Erfolg-vortäuschende Ablehnungen, R1-Ceiling-Blockade der Freigaben, fehlender Retry-Button, fehlendes Markdown-Rendering im Ergebnistext — alle in `PRODUCT-FLOW-FINDINGS.md` bzw. `V1X-PRODUCT-ACCEPTANCE.md` mit konkretem Vorschlag dokumentiert.

Vollständige Regressionsprüfung nach den Fixes: `uv run pytest` weiterhin 262/262 grün (reine Frontend-Änderung, kein Backend-Code berührt).

---

## Breakpoint Findings

### 1. Rightpane-Scrim deckt die Sidebar bei Tablet-Breiten (700–1099px) nicht ab
- **Breakpoints:** 768×1024, 1024×768 (jeder Breakpoint zwischen 700px und 1099px betroffen)
- **Schweregrad:** Mittel–Hoch (falsches Layering, wirkt wie ein Rendering-Bug)
- **Befund:** Öffnet man bei diesen Breiten die Agent-Detail- oder System/Details-Ansicht (Rightpane als Overlay, da `#rightpane` erst ab 1100px `position: static` wird), verdunkelt der `#rightpaneScrim` messbar den Chat-Bereich (Pixelwert vorher `rgb(11,14,20)` → nachher `rgb(6,9,14)`), aber **nicht** die Sidebar (Pixelwert bleibt exakt `rgb(18,22,31)` vor und nach dem Öffnen — per Screenshot-Diff verifiziert). Die Sidebar bleibt voll hell und interaktiv wirkend, während rechts ein Overlay mit Scrim liegt — inkonsistentes Stacking.
- **Ursache:** `#shell` ist ab 700px ein CSS-Grid; `#sidebar`, `#sidebarScrim`, `#rightpaneScrim` sind alle direkte Grid-Items. Bei Grid-/Flex-Items gilt `z-index` laut Spec **auch dann**, wenn `position: static` ist. `.sidebar` hat `z-index: 40` aus der mobilen Basisregel (nötig, damit die Sidebar dort über dem eigenen Scrim liegt), die 700px-Media-Query setzt zwar `position/transform/width` zurück, aber **nicht** `z-index`. Damit liegt die Sidebar (z-index 40) im Tablet-Bereich weiterhin über beiden Scrims (z-index 35), obwohl sie dort gar keinen eigenen Overlay-Zustand mehr hat.
- **SAFE FIX CANDIDATE:** In `hufiagents/api/static/app.css`, im Block `@media (min-width: 700px) { .sidebar { ... } }` (ca. Zeile 142-144) `z-index: auto;` ergänzen. Reines CSS, keine JS-/API-Logik betroffen, kein Risiko für den mobilen Overlay-Zustand (<700px), da diese Regel dort nicht greift.

### 2. Touch-Targets unter ~40px auf mobilen Breakpoints
- **Breakpoints:** alle ≤768px, am spürbarsten bei 430×932/390×844/360×800
- **Schweregrad:** Mittel
- **Befund:**
  - `.icon-btn` (app.css, Zeile 92-98) ist `34×34px` — verwendet für `#sidebarToggle`, `#rightpaneToggle`, `#rightpaneClose`, `#newHufiClose`. Alle vier sind die primären Navigations-Buttons auf dem Handy.
  - `.color-swatch` (agents.css, Zeile 190-198) ist `28×28px` mit nur `--space-2` (8px) Abstand — die Farbauswahl im "+ Neuer Hufi"-Modal (per Screenshot bei 390×844 verifiziert: sechs eng stehende Kreise).
  - `.details-toggle` und `.result-mini` (chat.css, Zeile 131-141 / 198-209) haben nur `min-height: 32px`.
  - Alle liegen unter der gängigen Mindestgröße von 40–44px für Touch-Ziele.
- **SAFE FIX CANDIDATE:** `.icon-btn` auf `width:40px;height:40px` anheben (app.css Z.96-97); `.color-swatch` auf `36px` Kantenlänge plus `--space-3` Gap anheben, oder Klick-/Tap-Fläche per `padding` bzw. einem transparenten Pseudo-Element ohne optische Vergrößerung erweitern (agents.css Z.190-196); `.details-toggle`/`.result-mini` `min-height: 32px` auf `40px` anheben (chat.css Z.139, 207). Rein CSS, keine Logik betroffen.

### 3. Kein sichtbarer Fokusring auf Sidebar-Zeilen
- **Breakpoints:** alle (Desktop-Tastaturnutzung getestet bei 1920×1080, betrifft aber jede Breite)
- **Schweregrad:** Hoch (Accessibility)
- **Befund:** `agents.css` Zeile 23-27:
  ```css
  .agent-row:hover,
  .agent-row:focus-visible {
    background: var(--surface-2);
    outline: none;
  }
  ```
  Per Tastatur gemessen (`getComputedStyle` nach `Tab`): `outline-style: none` auf jeder fokussierten `.agent-row`. Der einzige "Fokushinweis" ist ein Hintergrundwechsel von `#12161f` auf `#171c27` — ein Helligkeitsunterschied, der bei flüchtigem Hinsehen kaum wahrnehmbar ist, und identisch mit dem Hover-Zustand ist (man kann Fokus nicht von Hover unterscheiden).
- **SAFE FIX CANDIDATE:** In `agents.css` Zeile 23-27 Hover und Focus trennen: Hover behält `outline: none`, `:focus-visible` bekommt zusätzlich `outline: 2px solid var(--accent); outline-offset: -2px;`. Reines CSS.

### 4. `--text-faint` (#5b6578) erfüllt WCAG AA nicht
- **Breakpoints:** alle (Text-Token, kein Layout-Thema)
- **Schweregrad:** Mittel–Hoch (Lesbarkeit)
- **Befund:** Gemessener Kontrast von `--text-faint` gegen alle im UI tatsächlich genutzten Hintergründe liegt zwischen **2.90:1** (`--surface-2`) und **3.29:1** (`--bg`) — deutlich unter den geforderten 4.5:1 für normalen Text. Betroffene, häufig genutzte Klassen: `.empty-hint`, `.faint` (u. a. "Noch nicht verbunden" im Agent-Computer-Card, System-View-Hinweistexte, Zeitstempel in `.audit-timeline__meta`/`.activity-time`), `.details-toggle`, `.result-mini`. Das ist genau die Art "hellgrauer Text auf dunklem Grund", die laut Auftrag geprüft werden sollte — hier wirklich schwer lesbar, nicht nur "nicht AAA".
- **SAFE FIX CANDIDATE:** `--text-faint` in `app.css` Zeile 19 von `#5b6578` auf z. B. `#7a86a0` anheben (rechnerisch 4.66:1 gegen `--surface-2`, 5.28:1 gegen `--bg` — erfüllt AA überall). Reiner Token-Wert, kein Layout-Risiko. Zusatzhinweis: `--idle` (#6b7484, Pill-Text für "Deaktiviert"/"Bald verfügbar") liegt mit 3.84:1 ebenfalls unter AA für kleinen Text — selbe Behandlung empfohlen.

### 5. Grid-Fix (`grid-template-rows`) hält — bestätigt, keine Regression
- Der früher bekannte Bug (System/Details-Ansicht bläht `#chat` auf ~19000px auf) ist bei allen 7 Breakpoints weiterhin behoben. `document.body.scrollHeight` entspricht in jedem Fall exakt der Viewport-Höhe (z. B. 768×1024 → `scrollHeight=1024`, 1366×768 → `768`, 390×844 → `844`), obwohl die System-Ansicht mehrere lange JSON-Dumps rendert. Kein horizontales Scrollen (`document.documentElement.scrollWidth` == `clientWidth` überall).

---

## Real Mission Flow

Ablauf getestet mit "Sag in einem Satz Hallo." bei 1920×1080 und 390×844:

1. **Leerer Zustand:** Warmer Einstieg — großer Avatar "H", Titel "Was soll ich für dich erledigen?", Untertitel erklärt das Prinzip in einem Satz, fünf anklickbare Chips (HufManager prüfen / Website analysieren / Tagesbericht / Recherche starten / neue Idee planen). Wirkt einladend und undurchsichtige Fachbegriffe fehlen komplett — das Vision-Ziel ("wie ein Messenger") wird hier gut erreicht.
2. **Senden:** Nutzer-Bubble erscheint sofort rechtsbündig, direkt gefolgt von einer Hufi-Antwort "Alles klar. Ich prüfe das mit meinem Team." — guter, sofortiger Empfangs-Feedback, keine Wartezeit auf die erste Reaktion.
3. **Fortschritt:** Eine `.progress-line` mit pulsierendem Punkt (`hufiPulse`-Animation, 1.4s) zeigt Status wie "Ein Agent arbeitet daran …". Bei diesem einfachen Auftrag lief das nur ~2 Sekunden lang durch, wirkte aber grundsätzlich lebendig statt tot — die Pulsanimation ist ein gutes, ruhiges Signal.
4. **Ergebniskarte:** Grüne "Fertig"-Pille, klarer Ergebnistext ("Hallo."), unaufdringlicher "Später"-Button zum Einklappen. "Details anzeigen" liegt dezent (faint, klein) unterhalb der Hufi-Bubble — auffindbar, aber nicht dominant. Genau die geforderte Balance zwischen "sichtbar" und "nicht aufdringlich".
5. **Details-Panel:** Öffnet eine `.audit-timeline` mit übersetzten Event-Labels (z. B. "Mission erstellt" statt `mission_created`), pro Eintrag ein `<details>`-Element "Rohdaten" mit dem rohen JSON — sauber zweistufig versteckt, ein normaler Nutzer sieht auf den ersten Blick nur die freundlichen Labels.

**Ein echter Schwachpunkt im Flow:** Klickt man in der Sidebar auf einen Agenten (`selectAgent()` → `Hufi.chat.openAgent()`), wird der gesamte einladende Leerzustand (Avatar, Titel, Untertitel, fünf Chips) durch eine einzelne kleine graue Pille "Chat mit builder" ersetzt (`chat.js` Zeile 422-437) — der Rest des Chat-Bereichs ist danach einfach leerer, dunkler Raum ohne jede Handlungsaufforderung (per Screenshot bei 1920×1080 verifiziert). Das fühlt sich kälter an als der ursprüngliche Empfang und bricht den warmen Ersteindruck unnötig. **Verbesserung:** Auch im Agenten-Chat die Chips/Prompt-Einladung beibehalten (ggf. mit auf den Agenten zugeschnittenen Vorschlägen), statt nur eine Systemnotiz zu zeigen.

---

## Keyboard & Accessibility

Vollständiger Tab-Durchlauf ab Login (automatisiert protokolliert, `getComputedStyle`-Auswertung je Tab-Schritt):

- **Login-Formular:** `#username` → Tab → `#password` → Enter sendet das Formular korrekt.
- **Hauptinterface, Tab-Reihenfolge:** `#newHufiBtn` → `#sidebarSearch` → sechs `.agent-row` (in Registrierungsreihenfolge) → `#logoutBtn` → vier `.chip`-Elemente. Die Reihenfolge folgt sinnvoll der visuellen Anordnung von oben nach unten.
- **Kein sichtbarer Fokusring auf `.agent-row`** (siehe Breakpoint-Finding 3) — bei allen sechs Zeilen bestätigt.
- **"+ Neuer Hufi"-Modal — kritischer Fund:** Öffnet man das Modal per Tastatur (Fokus auf `#newHufiBtn`, dann Enter), bleibt der Fokus laut `document.activeElement` **auf dem Trigger-Button im Hintergrund** — es wird nicht automatisch in den Dialog verschoben. Drückt man danach Tab, springt der Fokus **nicht** in das Modal, sondern durch die dahinterliegende Sidebar (`#sidebarSearch` → alle `.agent-row` → `#logoutBtn` → Chips), obwohl das Modal sichtbar geöffnet ist und `aria-modal="true"` trägt. In zwölf aufeinanderfolgenden Tab-Schritten wurde **kein einziges Element innerhalb von `.modal-overlay`** fokussiert (`overlay.contains(activeElement)` war durchgehend `false`). Grund: `agents.js`, Funktion `openNewHufiModal()` (Zeile 317-386), ruft nirgends `.focus()` auf ein Element im Dialog auf, und es existiert keinerlei Tab-Handler, der den Fokus im Dialog hält. Da der Overlay-Knoten als letztes Kind von `document.body` angehängt wird (`overlay.appendChild(...); document.body.appendChild(overlay)`, Zeile 345-346), landet er im Tab-Index **hinter** der gesamten übrigen Seite — ein reiner Tastaturnutzer müsste durch das komplette restliche UI tabben, bevor er überhaupt das Namensfeld erreicht. Das Modal ist damit für Tastaturnutzer faktisch unbedienbar. **Das ist der schwerwiegendste Einzelbefund dieses Audits.**
  - Escape schließt das Modal zuverlässig (verifiziert: `document.addEventListener('keydown', onKeydown)` in Zeile 363-366 funktioniert).
  - Klick auf den Scrim schließt ebenfalls korrekt.
  - **Fix (nicht CSS-only, daher kein "Safe Fix Candidate"):** Beim Öffnen `card.querySelector('#newHufiName').focus()` aufrufen und einen einfachen Fokus-Trap-Handler auf `keydown`/`Tab` innerhalb des Dialogs ergänzen (erstes/letztes fokussierbares Element zyklisch verbinden), analog zum bestehenden APG-Dialog-Pattern.
- **Kontrast:** siehe Breakpoint-Finding 4 (`--text-faint`, `--idle`).
- **aria-label:** Icon-only-Buttons sind sauber beschriftet (`#sidebarToggle` "Menü öffnen", `#rightpaneToggle` "Details öffnen", `#rightpaneClose`/`#newHufiClose` "Schließen", Farbkreise "Farbe wählen") — das ist vorbildlich gemacht.
- **Modal-Ankündigung:** `role="dialog" aria-modal="true" aria-label="Neuer Hufi"` ist korrekt gesetzt (agents.js Zeile 322) — nur die tatsächliche Fokusführung/-falle fehlt (s. o.), wodurch die `aria-modal`-Semantik nicht der echten Tastatur-Erfahrung entspricht.

---

## Visual Consistency

- **Card/Pill/Button-Konsistenz:** `chat.css` und `agents.css` nutzen konsequent dieselben Tokens aus `app.css` (`.card`, `.pill`, `.btn`) — keine abweichenden Radien oder Farb-Duplikate gefunden. Das ist ein gutes Zeichen für die Integrationsschicht.
- **Kleinere Inkonsistenz bei "Meta"-Textgrößen:** `chat.css` verwendet für vergleichbare sekundäre Texte `.78rem` (`.details-toggle`, `.system-note`) und `.74rem`/`.76rem` uneinheitlich (`.audit-timeline__meta` `.74rem`, `.tag` `.76rem`, `.pill` `.74rem`) — keine harten Brüche, aber keine klare Skala (`.74/.76/.78/.82`). Nicht gravierend, aber bei einem "Apple-Level"-Anspruch würde man eine engere, definierte Type-Scale erwarten statt vieler Nahe-beieinander-Werte.
- **"Computer"-Karte im Agent-Detail (agents.js Zeile 235-243):** Zeigt "🖥️ Computer — Noch nicht verbunden" ohne jede Erklärung, was das für den Nutzer bedeutet oder wann/wie es sich ändert. Für den Ziel-Nutzer (nicht-technischer Pferdebetriebs-Inhaber) ist unklar, ob das ein Problem, ein Feature oder reine Zukunftsmusik ist. Sollte entweder ausgeblendet werden, solange es keine Funktion hat, oder einen erklärenden Satz bekommen.
- **"+ Neuer Hufi"-Formular:** Ehrliches Verhalten — nach Absenden erscheint klar "Eigene Hufis können in dieser Version noch nicht dauerhaft angelegt werden" statt einen Fake-Erfolg vorzutäuschen (agents.js Zeile 372-385). Gute Grundhaltung, aber der Nutzer merkt das erst, nachdem er Name, Farbe und Verantwortungsbereich ausgefüllt hat — der Button "Hufi anlegen" suggeriert bis dahin vollen Funktionsumfang. Kleiner Hinweis direkt im Modal (z. B. unter dem Titel) würde Frustration vermeiden.
- **System/Details-Ansicht ist visuell klar abgegrenzt:** Monospace-`<pre>`-JSON-Dumps, expliziter Warnhinweis oben ("Technische Rohdaten … Für den normalen Hufi-Alltag nicht nötig") und ein Link zum alten `/legacy`-Dashboard. Ein normaler Nutzer würde diese Ansicht kaum mit "der eigentlichen App" verwechseln — das Ziel aus der Produktvision wird hier gut erreicht.

---

## Apple-Level Scores

Bewertungsskala 1–10. Für alles unter 8 gibt es eine konkrete, umsetzbare Verbesserung.

| # | Ansicht | Klarheit | Einfachheit | Visuelle Ruhe | Verständlichkeit | Geschwindigkeit (gefühlt) | Vertrauen | Feedback | Mobile-Tauglichkeit | Accessibility | "Versteht das ein normaler Pferdemensch sofort?" |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Leerer Chat / Startbildschirm | 9 | 9 | 9 | 9 | – | 8 | – | 8 | 7 | **Ja** |
| 2 | Senden + Fortschritt | 8 | 8 | 8 | 7 | 8 | 7 | 8 | 8 | 7 | **Ja** |
| 3 | Ergebniskarte | 8 | 9 | 8 | 8 | – | 7 | 8 | 8 | 6 | **Ja** |
| 4 | Sidebar + Agent-Detail | 7 | 8 | 8 | 6 | – | 6 | 6 | 6 | 4 | Teilweise |
| 5 | "+ Neuer Hufi"-Modal | 8 | 8 | 8 | 7 | – | 6 | 6 | 6 | 3 | Teilweise |
| 6 | System/Details-Ansicht | 8 | 6 | 6 | 5 | – | 8 | 6 | 7 | 5 | Nein (bewusst, korrekt so) |

**Verbesserungsnotizen für alles < 8:**

- **1 / Vertrauen (8):** solide, keine Aktion nötig — höchstens als Ausblick: Chips könnten personalisiert werden (aus echten letzten Missionen), das ist aber kein Fix, sondern eine Erweiterung.
- **1 / Mobile-Tauglichkeit (8), Accessibility (7):** Fokusring auf `.chip`/`.agent-row` fehlt sichtbar (Finding 3); `.chat-empty__sub` nutzt `muted` (`--text-muted`, ok, 6.26:1) — kein Problem hier, der Abzug kommt vom fehlenden Fokusring, der auf jeder Seite auftritt.
- **2 / Verständlichkeit (7):** Statuszeilen wie "Ein Agent arbeitet daran …" sind gut, aber bei Missionen mit mehreren Tasks bleibt unklar, *welcher* Agent gerade was tut — konkret: in `statusLine()` (chat.js Zeile 85-99) den Agentennamen statt nur die Anzahl einblenden, sobald `tasks` mit `agent_id` vorliegen.
- **2 / Vertrauen (7):** Die pulsierende Progress-Line ist gut, aber es gibt keine sichtbare Fehlertoleranz-Anzeige, falls `Hufi.api()` wiederholt fehlschlägt (siehe `trackMission()` Zeile 274-276: Fehler werden komplett stillschweigend verschluckt — "keep polling silently"). Konkret: nach z. B. 3 aufeinanderfolgenden fehlgeschlagenen Polls eine dezente Zeile wie "Verbindung schwankt …" einblenden statt für den Nutzer unsichtbar weiterzupollen.
- **2 / Accessibility (7):** gleicher Fokusring-Punkt wie oben, betrifft `.chip` und ggf. `.chat-send`.
- **3 / Vertrauen (7):** "Bericht öffnen" bei langen Ergebnissen ist gut, aber es gibt keinerlei Timestamp/Kontext auf der Ergebniskarte selbst (wann war das fertig, welche Mission war das nochmal) — konkret: in `renderResult()` (chat.js Zeile 365-419) einen faint Zeitstempel unter der Pille ergänzen.
- **3 / Accessibility (6):** `--text-faint` auf `.result-mini`/`.details-toggle` (Finding 4) — direkter Text-Fix wie oben beschrieben.
- **4 / Verständlichkeit (6):** "Computer — Noch nicht verbunden" ohne Erklärung (siehe Visual Consistency) — Karte ausblenden oder erklärenden Satz ergänzen.
- **4 / Vertrauen (6), Feedback (6):** Live-Aktivität lädt per `fetchAggregatedAudit()` einen Umweg über alle letzten Missionen (agents.js Zeile 132-150) und liefert im Zweifel "Noch keine Aktivität." auch dann, wenn der Agent durchaus aktiv war, nur außerhalb des 15s-Caches/25-Missions-Fensters — für den Nutzer nicht erkennbar, ob das stimmt oder nur ein Lade-Artefakt ist. Konkret: bei leerem Ergebnis kurz differenzieren zwischen "lädt noch" und "wirklich keine Aktivität".
- **4 / Mobile-Tauglichkeit (6):** Touch-Targets (Finding 2) betreffen v. a. diese Ansicht (`#openSystemView`-Button ist ok mit `.btn--sm`, aber die umliegenden `.icon-btn` sind es nicht).
- **4 / Accessibility (4):** stärkster Abzug — fehlender Fokusring auf `.agent-row` (Finding 3) *und* das ist der primäre Navigationsweg der ganzen App.
- **5 / Vertrauen (6), Feedback (6):** Nutzer merkt erst nach vollständigem Ausfüllen, dass "Hufi anlegen" nicht wirklich etwas anlegt (siehe Visual Consistency) — Hinweistext direkt im Modal-Header ergänzen, bevor der Nutzer Zeit investiert.
- **5 / Accessibility (3):** stärkster Einzelabzug im gesamten Audit — der fehlende Fokus-Trap/keine Fokusverschiebung beim Öffnen (Finding "Modal — kritischer Fund" oben) macht das Modal für Tastaturnutzer praktisch unbedienbar. Fix: Fokus beim Öffnen auf `#newHufiName` setzen + Tab-Trap ergänzen (agents.js `openNewHufiModal()`).
- **5 / Mobile-Tauglichkeit (6):** `.color-swatch` 28×28px (Finding 2).
- **6 / Einfachheit (6), Visuelle Ruhe (6), Verständlichkeit (5):** hier bewusst niedriger, weil es die *Experten*-Ansicht ist — das ist by design so gewollt und richtig (siehe Visual Consistency: "wird nicht mit der eigentlichen App verwechselt"). Kein Fix nötig, nur zur Vollständigkeit der Skala mit aufgeführt.
- **6 / Feedback (6):** Alle vier Boxen (`#sysAgents`, `#sysModels`, `#sysProjects`, `#sysAudit`) laden unabhängig und zeigen bis dahin nur "Lädt …" ohne Skeleton/Fortschrittsindikator — bei langsamer Verbindung wirkt das etwas unfertig. Kleiner, optionaler Polish: ein `<pre>`-Platzhalter mit angedeuteter Struktur statt reinem Text.
- **6 / Accessibility (5):** JSON-Dumps in `<pre>` sind für Screenreader kaum sinnvoll konsumierbar — akzeptabel für eine bewusste Experten-Ansicht, aber ein `aria-label="Technische Rohdaten, JSON-Format"` auf den `<pre>`-Containern wäre eine kleine, risikofreie Verbesserung.

**Gesamteinschätzung Apple-Level:** Die drei Kern-Chat-Ansichten (leerer Zustand, Senden/Fortschritt, Ergebniskarte) liegen im Bereich **7–9** und fühlen sich tatsächlich nah an einem polierten Consumer-Produkt an — Ton, Tempo, Sprache stimmen. Sidebar/Agent-Detail und das "+ Neuer Hufi"-Modal liegen im Bereich **6–8** in den meisten Dimensionen, fallen aber durch die Accessibility-Befunde (fehlender Fokusring, fehlender Fokus-Trap) auf **3–4** ab — das sind die zwei Stellen, die vor einem echten "Apple-Level"-Anspruch zuerst behoben werden sollten. System/Details ist absichtlich technisch/nüchtern und dafür angemessen bewertet.

---

## Zusammenfassung der wichtigsten Befunde

1. **Kritisch — "+ Neuer Hufi"-Modal ist für Tastaturnutzer nicht erreichbar** (kein Fokus-Trap, kein initialer Fokus; verifiziert per automatisierter Tab-Simulation über 12 Schritte, `agents.js` Zeile 317-386).
2. **Hoch — Kein sichtbarer Fokusring auf `.agent-row`**, dem primären Navigationselement der App (`agents.css` Zeile 23-27; SAFE FIX CANDIDATE).
3. **Mittel–Hoch — `--text-faint` (#5b6578) unterschreitet WCAG AA** auf allen genutzten Hintergründen (2.90–3.29:1 statt 4.5:1), betrifft viele häufig sichtbare UI-Texte (`app.css` Zeile 19; SAFE FIX CANDIDATE, Vorschlag `#7a86a0`).
4. **Mittel — Rightpane-Scrim deckt die Sidebar bei 700–1099px nicht ab**, wirkt wie ein Rendering-Fehler (Grid-Item-`z-index`-Kollision, `app.css` Zeile 128-144; SAFE FIX CANDIDATE, `z-index: auto` im 700px-Block).
5. **Mittel — Touch-Targets unter 40px** bei `.icon-btn` (34px) und `.color-swatch` (28px) auf allen mobilen Breiten (SAFE FIX CANDIDATE).

Alle bereits als "known-fixed" markierten Bugs (Input-Bar-DOM-Bug, `[hidden]`-Spezifität, Grid-Row-Explosion) wurden gegengeprüft und sind bestätigt weiterhin behoben — keine Regression gefunden. Keine horizontalen Scrollbalken, keine Konsolenfehler bei irgendeinem der 7 Breakpoints.
