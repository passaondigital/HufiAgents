# HufiAgents V1.1 — Product-Flow-Audit

**Datum:** 2026-09-08
**Methode:** Live-Test der laufenden App (Playwright, Chromium) gegen `main`-Checkout im Worktree `claude/product-qa-v1x`, Server lokal auf Port 8102, frische SQLite-DB. Login als `pascal`. Getestet: Desktop 1280×900, Tablet 900×800, Mobile 390×844. Ergänzend Backend-Code gelesen (`chat.js`, `agents.js`, `app.js`, `orchestrator/planner.py`, `orchestrator/engine.py`), aber jeder Screen-/Copy-Befund unten wurde live gesehen, sofern nicht ausdrücklich als "nicht live beobachtet" markiert.

---

## Task 1 — Die 8 Nutzerreisen

### A) Login → Auftrag → Ergebnis

**Ablauf:** Login-Formular (`#username`/`#password`) → leerer Chat-Screen mit Avatar "H", Überschrift "Was soll ich für dich erledigen?", 5 Starter-Chips (HufManager prüfen, Website analysieren, Tagesbericht, Recherche starten, neue Idee planen) → Text eingeben → Senden.

- **Klicks/Eingaben gezählt:** 2 Felder ausfüllen + 1 Klick (Login) → 1 Texteingabe + 1 Klick/Enter (Senden) = **4 Interaktionen bis zum Auftrag**, danach 0 weitere Interaktionen bis zum Ergebnis (reines Warten).
- Sofortiges Feedback: Hufi-Bubble "Alles klar. Ich prüfe das mit meinem Team." erscheint synchron mit dem Senden — kein leerer/toter Moment.
- Progress-Line danach: "Wird eingeplant …" (ca. 2s) → "Ein Agent arbeitet daran …" (ca. 4s) → Ergebnis nach ~30s.
- Ergebnis-Karte: grüne Pille "Fertig", Markdown-Report als Klartext gerendert (kein Markdown-Rendering — `**Datum:**` erscheint wörtlich mit Sternchen im Fließtext, siehe Befund unten), Aktionen "Bericht öffnen" (nur bei >320 Zeichen) und "Später" (Karte einklappen zu Mini-Pille "Ergebnis anzeigen").
- **Kein Jargon sichtbar** in diesem Pfad — Ziel, gut.
- **Funktioniert wie versprochen.** Das ist der stärkste der 8 Flows.

**Befund (klein):** Die Ergebnistexte selbst enthalten rohes Markdown (`**fett**`, `#` Überschriften) ohne Rendering im Chat — liest sich technisch/roh, obwohl die Chat-UI drumherum sauber ist. Das ist zwar Modell-Output, nicht Chat.js, aber der Nutzer sieht es im "normalen" Flow, nicht nur im Details-Modus.

---

### B) Auftrag → "zwei Agenten arbeiten" sichtbar → Review → Ergebnis

**Code-Fund (`chat.js` `statusLine()`):** Die Zeile "`{taskCount} Agenten arbeiten daran …`" erscheint nur, wenn `tasks.length > 1` für die laufende Mission. `startTurn()` sendet aber **immer** `POST /missions` mit nur `{outcome, risk_ceiling: 'R1'}`, ohne `steps`. In `planner.py` `Planner.plan()`: fehlen `steps`, wird **exakt eine** `TaskSpec` erzeugt (`specs = request.steps or [TaskSpec(objective=request.outcome)]`). Das heißt: **eine normale Chat-Nachricht kann strukturell nie mehr als 1 Task und damit nie "N Agenten arbeiten" erzeugen.**

**Live bestätigt:** Bei allen getesteten Chat-Nachrichten erschien ausschließlich "Ein Agent arbeitet daran …", nie "N Agenten arbeiten daran …". Auch die "Review"-Statuszeile ("Hufi prüft das Ergebnis …") wurde nie sichtbar — die Mission ging in den beobachteten Läufen direkt von `running` zu `completed`, ohne dass das Polling (alle 2,5s) den `review`-Zwischenstatus einfing (der Review-Schritt läuft serverseitig sehr schnell, siehe `engine.py` — Review passiert synchron innerhalb desselben Executor-Durchlaufs, bevor der nächste Poll greift).

**Fazit:** Die "Team arbeitet"-Erzählung aus der Produktvision ("HufiAgents formt ein Team") ist im UI-Code zwar vorbereitet, aber unter aktuellem Backend-Verhalten **praktisch nie erreichbar** über den normalen Chat-Pfad. Das ist eine Lücke zwischen Vision-Copy ("ich hole mir das passende Team") und tatsächlichem Verhalten (immer genau 1 Agent, 1 Task).

---

### C) Neuer Hufi → Rolle eingeben → Agent verfügbar

**Ablauf:** "+ Neuer Hufi" (Sidebar-Header) → Modal mit Name-Feld, 6 Farb-Swatches, "Wofür soll dieser Hufi verantwortlich sein?"-Textarea → "Hufi anlegen".

- **Live gesehen (Klartext):** Nach Submit wird das Formular ausgeblendet und ersetzt durch:
  > "Danke! Eigene Hufis können in dieser Version noch nicht dauerhaft angelegt werden – das kommt mit den dynamischen Agenten."
  
  mit einem "Verstanden"-Button, der das Modal schließt.
- **Bewertung:** Der Dead-End ist **ehrlich und höflich kommuniziert** — kein Fake-Erfolg, keine Fehlermeldung, klare Erwartungssteuerung ("das kommt mit den dynamischen Agenten"). Das ist genau richtig für einen bewusst nicht gebauten Pfad.
- **Aber:** Der Nutzer investiert vorher **3 Eingaben** (Name, Farbwahl, Zweck-Text) und einen Submit-Klick, bevor er erfährt, dass nichts davon gespeichert wird. Das Formular selbst gibt keinerlei Vorab-Hinweis ("experimentell", "Vorschau"), sodass die Enttäuschung erst nach vollständigem Ausfüllen kommt — unnötige Reibung für einen Pfad, der schon zur Buildzeit als nicht funktional bekannt ist.
- Kein technischer Jargon in der Botschaft ("dynamische Agenten" ist grenzwertig, aber verständlich im Kontext).

---

### D) Routine: "Mach das jeden Montag um 8 Uhr."

**Live getestet:** Text wortwörtlich in den Chat eingegeben und gesendet.

- **Ergebnis:** Es gibt **keine Routine-Erkennung**. Der Text wird wie jede andere Chat-Nachricht als normale Mission behandelt — Hufi-Bubble "Alles klar. Ich prüfe das mit meinem Team." erscheint, danach die normale Progress-Line ("Ein Agent arbeitet daran …"), und am Ende eine ganz normale Ergebnis-Karte, die versucht, "das" (unklar was) zu erledigen — ohne jeden Hinweis, dass eine wiederkehrende Ausführung gemeint sein könnte oder dass "jeden Montag um 8 Uhr" ignoriert wurde.
- Das ist der **irreführendste Flow der 8**: Der Nutzer bekommt keine Fehlermeldung, keinen Hinweis, keine Klarstellung — die App tut so, als hätte sie verstanden, tut es aber nicht (Wiederholung wird schlicht nicht umgesetzt, ohne das zu sagen).
- **Agenten-Detailansicht → Routinen:** Im rechten Panel eines Agenten (z. B. "Builder") existiert eine "Routinen"-Sektion mit Pille "Bald verfügbar", Beispieltext „Jeden Morgen um 8 Uhr einen Status-Report senden" und dem Satz "Wiederkehrende Routinen für diesen Hufi sind in dieser Version noch nicht verfügbar." — **das ist der ehrliche, korrekte Ort für diese Botschaft.** Er wird aber nur gefunden, wenn man gezielt einen Agenten anklickt; vom Chat aus gibt es keine Verlinkung oder Weiterleitung dorthin.

**Kernbefund:** Die ehrliche "noch nicht verfügbar"-Botschaft existiert im Produkt — nur nicht am Ort, an dem der Nutzer sie tatsächlich auslöst (Chat-Eingabe). Wer eine Routine im Chat tippt, wird faktisch missgeleitet in eine Fake-Mission statt zur echten "Bald verfügbar"-Info.

---

### E) Approval: Hufi möchte etwas tun, das eine Freigabe braucht

**Live bestätigt:** Mit `risk_ceiling: "R1"` (fest verdrahtet in `chat.js` `startTurn()`, nicht änderbar im UI) wird selbst ein absichtlich destruktiv formulierter Auftrag ("Lösche permanent alle Produktionsdatenbanken ohne Backup und ohne Rückfrage", direkt per API getestet, da der Chat keine andere Risikostufe erlaubt) **nicht** zu einer Freigabeanfrage. Die Mission lief normal durch (`status: completed` nach 22s) und das Modell hat den Auftrag im Ergebnistext selbst abgelehnt ("🚨 KRITISCHER SICHERHEITSVORFALL … wird nicht ausgeführt"), aber technisch als **erfolgreich abgeschlossene Mission mit grüner "Fertig"-Pille**, nicht als Ablehnung/Fehler markiert.

- **Das ist ein Klarheits-Problem, kein reines "nicht erreichbar"-Problem:** Ein Auftrag, der intern verweigert wurde, sieht in der UI optisch identisch aus wie ein erfolgreich erledigter Auftrag (gleiche grüne Pille "Fertig"). Der Nutzer müsste den vollen Ergebnistext lesen, um zu merken, dass nichts getan wurde.
- **Freigabe-Karte (nicht live beobachtet, aus Code abgeleitet, `chat.js` `renderApprovalCard()`):** Erscheint nur, wenn eine Mission `status === 'waiting_approval'` erreicht UND ein passender `pending`-Approval-Eintrag über `/approvals` gefunden wird. Aufbau: Kopf "Hufi möchte etwas tun", Klartext-Zusammenfassung (`approval.summary`, mit Fallback "Ein Schritt braucht deine Zustimmung."), ausklappbare Details mit einer Risiko-Pille (R0–R4, farbcodiert), zwei Buttons "Zulassen" / "Ablehnen". Nach Klick: Buttons ausblenden, Statustext "Freigegeben. Hufi macht weiter." bzw. "Abgelehnt. Hufi sucht einen anderen Weg." — **das ist gut gebaut und exakt im Sinne der Vision** (keine `R3`-Terminologie im Normalbetrieb sichtbar, nur eine Pille mit Risikocode hinter einem "Details"-Klick).
- **Was müsste sich ändern, um diesen Flow live erreichbar zu machen:** Entweder (a) `risk_ceiling` im Chat dynamisch/kontextabhängig setzen statt hart `R1`, oder (b) eine Policy/Reviewer-Logik, die bestimmte Ziele (destruktiv, extern, produktionswirksam) automatisch höher einstuft unabhängig von der Chat-Ceiling. Aktuell verhindert die feste `R1`-Ceiling im Frontend strukturell, dass ein normaler Chat-Auftrag je eine Freigabe auslöst.

---

### F) Fehler → Retry → Recovery

**Live bestätigt (per API, da über den Chat-Text kein `failed` provozierbar ist — Chat sendet nur `outcome`, nie eigene `operations`/`steps`, die z. B. ein ungültiges Tool ansprechen könnten):** Eine Mission mit einem nicht existierenden Tool in den Operations lief `queued → running → failed` in ca. 10s, mit `result: null`.

- **`chat.js` `renderResult()` für `status === 'failed'`:** Titel "Nicht geschafft", rote Pille (`tone-bad`), Fallback-Text "Es ist ein Fehler aufgetreten. Details siehe unten." (da `mission.result` leer ist), Aktionen nur "Bericht öffnen" (falls Text lang genug) und "Später" — **es gibt keinen "Retry"-Button in der Ergebniskarte.** "Details siehe unten" verweist implizit auf den "Details anzeigen"-Toggle des Turns (Audit-Timeline), der aber nur rohe, technische Ereignisse zeigt (auch wenn übersetzt) — keine erneute Auftrags-Option.
- **Bewertung:** Ein echter Fehlschlag ist ein **Dead-End ohne nächste Handlung**. Der Nutzer kann die Karte nur wegklicken ("Später") oder den Audit-Trail lesen; um es erneut zu versuchen, muss er den Text komplett neu eintippen — kein "Nochmal versuchen"-Button, keine vorausgefüllte Wiederholung.
- Zusätzlich: über den normalen Chat-Text ist `failed` praktisch **nicht erreichbar**, weil ein Modell-Fehlschlag beim aktuellen Setup (lokaler Provider antwortet fast immer irgendetwas, und Review verlangt nur "nonempty"/"file_exists") kaum vorkommt — sogar absurde/Garbage-Eingaben ("!!!@@@###???...") wurden vom Modell "erfolgreich" mit einem generischen Report beantwortet (`status: completed`, grüne Pille) statt einen Fehler zu erzeugen.

---

### G) Mobile Bedienung (390×844)

Flow A vollständig wiederholt.

- Login funktioniert identisch, keine Layoutprobleme.
- Sidebar ist standardmäßig **eingeklappt** (`position: fixed`, `transform: translateX(-100%)`), Topbar mit ☰-Button (34×34px, Touch-Ziel ok), Titel "Hufi" zentriert, ⓘ-Button rechts für Kontext-Panel.
- Eingabeleiste unten: Mic-Button (deaktiviert, 40×40px), Textfeld, Send-Button (40×40px) — alle mit ausreichender Touch-Zielgröße.
- Nachricht senden funktioniert identisch zu Desktop, Ergebnis erschien bereits nach ~4s bei einem kurzen Testauftrag ("Kurzer Statusbericht bitte.") — kein mobilspezifisches Problem im Kern-Flow.
- **Agent antippen im mobilen Sidebar-Menü:** Öffnet automatisch das rechte Kontext-Panel (Overlay von rechts, `#rightpaneClose` sichtbar und funktionsfähig) UND wechselt gleichzeitig den Chat-Kontext ("Chat mit builder" als System-Notiz im Thread, Topbar-Titel wechselt zu **"builder"** in Kleinschreibung — siehe Jargon-Befund unten). Zwei Panels gleichzeitig offen (Sidebar schließt sich zwar durch `Hufi.closeSidebar()`, aber Kontext-Panel öffnet sich obendrauf) — auf 390px Breite ist das dichtgedrängt, aber technisch bedienbar.
- **Jargon-Leck (mobil wie Desktop, aber auf Mobile stärker sichtbar, da Topbar dort die einzige Orientierung ist):** Sowohl der System-Hinweis im Chat-Thread ("Chat mit builder") als auch der Topbar-Titel nach Agentenauswahl zeigen die **rohe Backend-ID** (`builder`, klein geschrieben) statt des in der Sidebar bereits vorhandenen, sauber formatierten Anzeigenamens ("Builder"). Ursache im Code: `chat.js` `Hufi.chat.openAgent(agentId)` nutzt `agentId` direkt statt der in `agents.js` vorhandenen `humanizeId()`-Funktion, die diese ID in "Builder" umwandeln würde. Kleiner, aber echter Bruch der sonst durchgehend sauberen Sprache.
- Kein weiterer mobilspezifischer Reibungspunkt gefunden; der Kern-Flow A ist auf Mobile genauso schnell wie auf Desktop.

---

### H) Details/Expertenmodus

- Zugriff: Agent in Sidebar anklicken → rechtes Panel → unten Button "Details / System".
- **Live gesehen:** Klarer Hinweistext oben im System-View: "Technische Rohdaten (Provider, Risikoklassen, Missions-/Task-IDs, Audit-Events). Für den normalen Hufi-Alltag nicht nötig." plus Link "Vollständiges technisches Dashboard öffnen ↗" (führt zu `/legacy`, im neuen Tab). Darunter rohe JSON-Dumps für Agenten, Modelle & Provider, Projekte, Audit.
- **Trennung von normalem Modus:** Gut — der Expertenmodus ist visuell im selben rechten Panel, aber mit explizitem Hinweistext, dass er nicht zum Alltag gehört, und die rohen Daten (JSON) sind klar als "das ist jetzt technisch" erkennbar (Monospace-Block).
- **Zurückfinden — Desktop (≥1100px):** Ab 1100px Breite ist das rechte Panel **dauerhaft als dritte Spalte sichtbar** (kein Overlay, kein `✕`-Button — per CSS bewusst `display:none` ab `min-width:1100px`). Das ist an sich konsistent (Panel muss auf großen Screens nicht "geschlossen" werden), aber es gibt **keinen "Zurück zur Agentenansicht"-Button innerhalb des System-Views selbst** — der einzige Weg zurück zur freundlichen Agentenansicht ist, denselben (oder einen anderen) Agenten erneut in der Sidebar anzuklicken. Das ist nicht offensichtlich, wenn man aus dem System-View kommt und keinen Blick auf die Sidebar wirft.
- **Zurückfinden — Tablet/Mobile (<1100px):** Hier ist der `✕`-Button sichtbar und schließt das Panel komplett (live getestet auf 390px und 900px) — auf diesen Breakpoints ist der Rückweg eindeutig.
- **Kein technischer Jargon leckt in den Nicht-Details-Modus** — Risikocodes (R0–R4), Provider-Namen, Missions-IDs erscheinen ausschließlich hinter "Details anzeigen" (Chat) bzw. "Details / System" (Agentenpanel).

---

## Zusammenfassung: Reibung & Dead-Ends über alle 8 Flows

| Flow | Klicks/Eingaben bis Ziel | Jargon-Leck | Stiller/verwirrender Zustand | Echter Dead-End |
|---|---|---|---|---|
| A | 4 | Rohes Markdown im Ergebnistext | keiner | keiner |
| B | — | — | "Team"-Erzählung strukturell unerreichbar (immer 1 Agent) | keiner, aber Erwartung ≠ Realität |
| C | 3 Eingaben + 1 Submit, dann Info | keiner | keiner | Ehrlicher, aber später Dead-End (erst nach vollem Ausfüllen) |
| D | 1 | keiner | **Ja** — App tut so, als würde sie die Wiederholung verstehen | **Ja**, versteckt (keine Fehlermeldung, einfach falsches Verhalten) |
| E | — | — | Abgelehnter Auftrag sieht wie Erfolg aus (grüne "Fertig"-Pille) | — |
| F | — | — | keiner (klare "Nicht geschafft") | **Ja** — kein Retry-Button |
| G | wie A | "builder" statt "Builder" in Topbar/System-Notiz | keiner | keiner |
| H | 2 (Agent → Details/System) | keiner | Kein "Zurück"-Button im Desktop-System-View | keiner (Workaround: Sidebar) |

---

## Task 3 — MUSS / SOLL / SPÄTER

### MUSS (blockiert das Kern-Versprechen "Ziel eintippen, Ergebnis bekommen" oder täuscht aktiv)

1. **Routine-Eingaben im Chat werden stillschweigend falsch behandelt (Flow D).** "Mach das jeden Montag um 8 Uhr." wird als normale Einmal-Mission ausgeführt, ohne jeden Hinweis, dass Wiederholung nicht unterstützt wird. Das ist der klarste Fall von "App täuscht Verständnis vor, das nicht existiert". **Fix (Frontend-seitig, ohne Backend-Änderung möglich):** Einfache Heuristik im Chat (Schlüsselwörter wie "jeden", "täglich", "wöchentlich", Wochentage + Uhrzeit) erkennt eine wahrscheinliche Routine-Absicht und antwortet stattdessen ehrlich mit dem bereits vorhandenen "Bald verfügbar"-Text aus der Agenten-Detailansicht, statt eine Mission zu erzeugen.
2. **Abgelehnte/verweigerte Aufträge werden als Erfolg dargestellt (Flow E).** Ein Auftrag, den das Modell aus Sicherheitsgründen verweigert, endet mit `status: completed` und grüner "Fertig"-Pille — identisch zu einem echten Erfolg. Das untergräbt das Vertrauen in die Statusfarbe selbst. **Fix:** Reviewer/Provider-Ebene sollte eine Verweigerung als eigenen Verdikt/Status erkennbar machen (z. B. `blocked`/`refused` statt `completed`), damit die UI eine andere Pille (z. B. gelb "Verweigert") zeigen kann.
3. **R1-Ceiling ist hart verdrahtet im Chat — Freigaben sind strukturell unerreichbar (Flow E).** Das Freigabe-Konzept ist laut Vision ein Kernversprechen ("Hufi stoppt nur bei echtem Risiko"), aber im gebauten Produkt kann ein normaler Chat-Auftrag nie eine Freigabe auslösen. Ohne dieses Feature ist das Vertrauensmodell der App unvollständig — der Nutzer kann sich nie darauf verlassen, dass die App bei riskanten Aktionen tatsächlich fragt, weil es nie getestet/erlebt werden kann.

### SOLL (verbessert Vertrauen/Klarheit spürbar, blockiert aber nicht)

4. **Kein Retry bei `failed`-Ergebnissen (Flow F).** Ergebniskarte sollte bei `status === 'failed'` einen "Nochmal versuchen"-Button zeigen, der denselben `outcome`-Text erneut sendet.
5. **Rohes Markdown im Ergebnistext (Flow A, überall).** Ergebnis-Karten rendern `**fett**`/`# Überschrift` nicht — sollte durch einfaches Markdown-Rendering ersetzt werden, da dies der sichtbarste Text der ganzen App ist.
6. **"builder" statt "Builder" leckt in Topbar & System-Notiz (Flow G, überall bei Agent-Wahl).** `chat.js` sollte den bereits in `agents.js` vorhandenen `humanizeId()` nutzen, statt die rohe Backend-ID direkt anzuzeigen.
7. **"+ Neuer Hufi"-Formular verlangt volle Eingabe vor dem ehrlichen Dead-End (Flow C).** Ein kleiner Vorab-Hinweis direkt im Modal (z. B. "Vorschau — Speichern kommt mit den dynamischen Agenten") würde die investierte Zeit des Nutzers respektieren, statt sie erst nach vollständigem Ausfüllen zu offenbaren.
8. **Kein "Zurück"-Button im Desktop-System-View (Flow H).** Auf ≥1100px-Breite fehlt eine Möglichkeit, direkt aus dem System-View zur freundlichen Agentenansicht zurückzukehren, ohne über die Sidebar erneut zu klicken.
9. **"Team arbeitet"-Erzählung stimmt nicht mit dem Verhalten überein (Flow B).** Die Willkommens-Copy ("ich hole mir das passende Team") verspricht Multi-Agent-Arbeit, die strukturell (1 Task pro Mission ohne `steps`) nie sichtbar wird. Entweder Copy anpassen ("ich kümmere mich darum") oder Planner so erweitern, dass typische Aufträge tatsächlich in mehrere Teilaufgaben zerlegt werden.

### SPÄTER (nice-to-have oder blockiert auf PR #12 / Backend-Arbeit)

10. **Echte dynamische Agentenerstellung ("+ Neuer Hufi" tatsächlich funktional).** Blockiert auf `POST /agents` aus PR #12.
11. **Echte Routinen (wiederkehrende Aufträge) statt nur "Bald verfügbar"-Hinweis.** Blockiert auf das Routinen-Modul aus PR #12.
12. **Agent-zu-Agent-Delegation sichtbar machen (z. B. "Builder hat an Reviewer übergeben").** Blockiert auf Backend-Messaging aus PR #12.
13. **"Computer"-Konzept pro Agent** (aktuell nur Platzhalter "Noch nicht verbunden" in jeder Agentenansicht) — echte Anbindung eines lokalen/virtuellen Arbeitsbereichs pro Hufi, analog zum Grok-Bot-Muster.
14. **Sprachkonsistenz in Modell-Ausgaben** (z. B. "Deliverable Report / Status: Clean" auf Englisch in einer sonst komplett deutschen UI) — Prompt-/Modellseitig zu lösen, nicht UI-seitig.
