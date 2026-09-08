# HufiAgents V1.x — Product Acceptance Checklist

**Status:** QA-Abnahmeliste für die chat-first Produkterfahrung (PR #13), basierend auf zwei unabhängigen Live-Audits (`UX-AUDIT-REPORT.md`, `PRODUCT-FLOW-FINDINGS.md`, `GROK-BENCHMARK.md`) plus den in dieser Session bereits angewendeten sicheren CSS/UI-Fixes (siehe "Angewendete Fixes" in `UX-AUDIT-REPORT.md`).

**Legende:**
`[x]` = heute live verifiziert erfüllt · `[ ]` = offen (mit Verweis auf den Befund/die Quelle) · `[~]` = teilweise/bedingt erfüllt

---

## 1. Sprache & Verständlichkeit (siehe `HUFI-UX-LANGUAGE.md`)

- [x] Nutzer versteht die Startseite in <5 Sekunden (Titel + ein Satz + Chips, live geprüft)
- [x] Auftrag ohne Technikbegriffe möglich (freier Text, kein Formular mit Fachbegriffen)
- [x] Keine UUID im normalen Flow sichtbar (Chat, Sidebar, Agent-Detail, Ergebniskarte)
- [x] Kein R0–R4-Code im normalen Flow sichtbar (nur hinter "Details")
- [x] Kein Provider-/Modellname im normalen Flow sichtbar
- [x] Kein rohes `event_type` (z. B. `state_transition`) im normalen Flow — nur übersetzte Labels
- [x] Technische Details sind grundsätzlich optional, nie erzwungen
- [x] Freigabekarte zeigt Risikocode nur hinter einem "Details"-Toggle (Code gelesen, `chat.js`)
- [x] Fehlermeldungen sind vollständige Sätze, kein rohes Exception-Text
- [ ] Ergebnistexte werden als lesbares Markdown gerendert statt roher `**Sternchen**`/`#`-Syntax (`PRODUCT-FLOW-FINDINGS.md`, Flow A, SOLL Punkt 5)
- [ ] Agentenname in Chat-Titel/Systemnotiz konsistent mit Sidebar-Anzeigename — **behoben in dieser Session** (`chat.js` nutzt jetzt `Hufi.agents.humanizeId()`)
- [ ] Modell-Ausgaben konsistent auf Deutsch (vereinzelt englische Fachbegriffe in Freitext-Ergebnissen beobachtet, `PRODUCT-FLOW-FINDINGS.md` Punkt 14 — Prompt-/Modellseitig zu lösen)

## 2. Startseite / Erster Eindruck

- [x] Ein zentraler Einstiegspunkt ("Was soll ich für dich erledigen?"), keine Navigation mit vielen Menüpunkten
- [x] Mindestens 3 konkrete Vorschläge (Chips) ohne eigene Eingabe nutzbar
- [x] Kein Tutorial/Setup-Wizard vor dem ersten Auftrag nötig
- [x] Direkter Einstieg funktional nah am Grok-Bot-Referenzmuster (`GROK-BENCHMARK.md` §1)
- [ ] Starter-Vorschläge sind personalisiert/kontextuell statt global-statisch (`GROK-BENCHMARK.md` §1, Verbesserungsvorschlag)
- [x] Kein horizontaler Scroll auf der Startseite bei keinem der 7 Breakpoints (live gemessen)

## 3. Chat / Auftrag erteilen

- [x] Ein Auftrag ist in ≤5 Interaktionen absendbar (4 gemessen: 2 Login-Felder + 1 Login-Klick + 1 Texteingabe+Senden)
- [x] Sofortiges Feedback nach dem Senden (Hufi-Bubble erscheint synchron, kein toter Moment)
- [x] Laufende Arbeit ist sichtbar (pulsierende Statuszeile, kein stiller Ladezustand)
- [x] Statuszeilen sind ehrlich (keine erfundene Prozentzahl, echte Zustände übersetzt)
- [ ] Bei Mehrfach-Aufgaben zeigt die Statuszeile, *welcher* Agent gerade was tut, nicht nur die Anzahl (`UX-AUDIT-REPORT.md`, Score-Notiz 2)
- [ ] "N Agenten arbeiten"-Erzählung ist über den normalen Chat-Pfad tatsächlich erreichbar (heute strukturell nie, da 1 Nachricht = 1 Task — `PRODUCT-FLOW-FINDINGS.md` Flow B, SOLL Punkt 9)
- [x] Eingabeleiste bleibt während des Wartens bedienbar (neue Nachricht möglich, kein Blockieren der UI)
- [ ] Wiederholte API-Fehler beim Polling werden dem Nutzer sichtbar gemacht statt nur still weiterzuversuchen (`UX-AUDIT-REPORT.md`, Score-Notiz 2, `trackMission()`)
- [x] Enter sendet die Nachricht, Shift+Enter fügt einen Zeilenumbruch ein (Standard-Chat-Verhalten)
- [x] Eingabefeld wächst automatisch mit dem Text (bis zu einer sinnvollen Maximalhöhe)

## 4. Ergebnis

- [x] Ergebnis ist verständlich ohne Rückfrage an einen Entwickler (Klartext-Karte)
- [x] Ergebniskarte hat maximal zwei primäre Aktionen ("Bericht öffnen"/"Später")
- [x] Lange Ergebnisse werden sinnvoll gekürzt mit Aufklapp-Option (320-Zeichen-Grenze)
- [x] Eingeklappte Ergebnisse verschwinden nicht vollständig (Mini-Pille zum Wiederöffnen)
- [ ] Ergebniskarte zeigt einen Zeitstempel/Kontext (wann fertig, welcher Auftrag) — aktuell nicht vorhanden (`UX-AUDIT-REPORT.md`, Score-Notiz 3)
- [x] Vom Modell intern verweigerte/abgelehnte Aufträge werden **nicht** identisch zu echten Erfolgen dargestellt — **behoben in `claude/v1-1-release-product-fixes`** (`not_refusal`-Reviewer-Kriterium + Planner-Default, live verifiziert: nicht-genehmigte Reviews zeigen nie die grüne Pille. Siehe `V1X-RELEASE-FIXES.md` MUSS 2.)
- [x] "Details anzeigen" ist auffindbar, aber nicht dominant (dezent platziert, live geprüft)
- [x] Rohdaten in den Details sind zweistufig versteckt (übersetztes Label zuerst, Rohdaten-JSON erst nach zusätzlichem Klick)

## 5. Approval / Freigaben

- [x] Freigabekarte erklärt in Klartext, was Hufi tun möchte (Code gelesen: `summary`-Feld als Hauptaussage)
- [x] Freigabekarte zeigt Risikocode nur unter "Details"
- [x] Freigabekarte hat genau zwei klare Aktionen (Zulassen/Ablehnen)
- [x] Nach Entscheidung gibt es sofortiges Klartext-Feedback ("Freigegeben. Hufi macht weiter." / "Abgelehnt. Hufi sucht einen anderen Weg.")
- [x] Freigaben sind über den normalen Chat-Pfad tatsächlich erreichbar — **behoben in `claude/v1-1-release-product-fixes`** (R1-Hardcode entfernt, Planner-Default angehoben, plus ein zweiter, erst beim Live-Test gefundener Bug behoben: Freigaben mit `tool_call_id` statt `task_id` wurden von der Karte gar nicht erkannt. Live end-to-end mit echtem R3-Gate + Deny + leerem Git-Remote bewiesen. Siehe `V1X-RELEASE-FIXES.md` MUSS 3.)
- [x] Nach Freigabe wird das Mission-Polling nachweislich fortgesetzt, ohne dass der Nutzer neu laden muss (live verifiziert: Deny-Klick aktualisiert die Karte in place, kein Reload nötig)

## 6. Agenten / Sidebar

- [x] Agentenliste zeigt Name, Rolle in einem Satz, Status — keine Konfigurationstabelle
- [x] Jeder Agent hat ein visuell unterscheidbares Avatar (Farbe deterministisch aus ID)
- [x] Suche filtert die Liste in Echtzeit
- [x] Agent anklicken öffnet Detailansicht + wechselt Chat-Kontext in einem Schritt
- [ ] Sidebar-Zeile hat einen sichtbar von Hover unterscheidbaren Fokusring — **behoben in dieser Session** (`agents.css`)
- [x] "Live-Aktivität" zeigt echte, übersetzte Ereignisse statt roher Logs
- [ ] "Live-Aktivität" aktualisiert sich laufend, während das Panel offen bleibt (heute: einmaliger Snapshot-Abruf, `GROK-BENCHMARK.md` §8)
- [ ] Leerzustand von "Live-Aktivität" unterscheidet erkennbar zwischen "lädt noch" und "wirklich keine Aktivität" (`UX-AUDIT-REPORT.md`, Score-Notiz 4)
- [ ] "Computer"-Karte erklärt, was "Noch nicht verbunden" für den Nutzer bedeutet, oder wird ausgeblendet, solange sie funktionslos ist (`UX-AUDIT-REPORT.md`, Visual Consistency)
- [x] Wechsel zwischen Agenten fühlt sich nicht wie ein Seitenwechsel an (kein Reload, sofortige Reaktion)

## 7. Agent-Erstellung

- [x] "+ Neuer Hufi" in <30 Sekunden ausfüllbar (Name, Farbe, Zweck — 3 Eingaben)
- [x] Kein technischer Formular-Jargon in Feldern/Platzhaltern
- [x] Ehrlicher Umgang mit der fehlenden Backend-Funktion (klare Botschaft statt Fake-Erfolg oder stillem Fehlschlag)
- [ ] Nutzer erfährt die Backend-Lücke *bevor* er alle Felder ausgefüllt hat, nicht erst danach (`PRODUCT-FLOW-FINDINGS.md` SOLL Punkt 7, `UX-AUDIT-REPORT.md` Visual Consistency)
- [ ] Neu angelegter Hufi erscheint tatsächlich in der Sidebar und ist sofort ansprechbar (blockiert auf `POST /agents`, PR #12)
- [ ] Von einem Agenten selbst initiierte Agent-Erstellung ist im Audit-Trail sichtbar und ggf. freigabepflichtig (Zielbild, `GROK-BENCHMARK.md` §3 — noch nicht gebaut)

## 8. Routinen

- [x] Ehrliche "Bald verfügbar"-Botschaft existiert im Produkt (Agenten-Detailpanel)
- [x] Eine im Chat formulierte Routine ("Mach das jeden Montag …") wird als solche erkannt, statt stillschweigend als Einmal-Auftrag ausgeführt — **behoben in `claude/v1-1-release-product-fixes`** (`detectRoutineIntent()`, live verifiziert mit echter `POST /routines`-Persistenz. Siehe `V1X-RELEASE-FIXES.md` MUSS 1.)
- [x] Der Nutzer wird bei einer erkannten Routine-Absicht zur bereits vorhandenen ehrlichen Botschaft geleitet, statt eine irreführende Fake-Mission zu erhalten (bei mehrdeutiger Formulierung: Rückfrage statt Rätselraten)
- [x] Echte wiederkehrende Ausführung ist möglich (PR #12 ist integriert; Routinen-API real, live getestet inkl. Pause/Resume/Archive)
- [x] Routine-Liste zeigt nächsten Lauf, aktiv/pausiert (live verifiziert; "letztes Ergebnis" noch nicht angezeigt — kleine SPÄTER-Lücke, kein MUSS)

## 9. Details / Expertenmodus

- [x] Klar erkennbarer Hinweistext, dass dieser Bereich für den Alltag nicht nötig ist
- [x] Kein Jargon leckt aus diesem Bereich in den Normalmodus zurück
- [x] Rohdaten sind eindeutig als technisch erkennbar (Monospace, JSON)
- [x] Zugang zum alten technischen Dashboard bleibt möglich (`/legacy`, unverlinkt aus dem Hauptfluss)
- [x] Auf Tablet/Mobile ist der Rückweg aus dem Details-Modus eindeutig (✕-Button)
- [ ] Auf Desktop (≥1100px) gibt es einen direkten "Zurück zur Agentenansicht"-Weg innerhalb des System-Views selbst, nicht nur über die Sidebar (`PRODUCT-FLOW-FINDINGS.md` SOLL Punkt 8)
- [ ] JSON-Dump-Container haben ein `aria-label` für Screenreader (`UX-AUDIT-REPORT.md`, Score-Notiz 6 — kleine, risikofreie Ergänzung)

## 10. Responsive / Mobile

- [x] Mobile ohne horizontalen Scroll (alle 7 Breakpoints live gemessen: `scrollWidth == clientWidth`)
- [x] Kein Layout-Overflow, keine abgeschnittenen Texte bei 1920×1080, 1366×768, 1024×768, 768×1024, 430×932, 390×844, 360×800
- [x] Sidebar und Kontext-Panel sind auf schmalen Breiten als Overlay mit Scrim bedienbar
- [x] Eingabeleiste bleibt auf Mobile immer erreichbar (fixiert am unteren Rand)
- [x] Touch-Ziele der Eingabeleiste (Mic/Senden) ≥40px
- [ ] Alle `.icon-btn`-Instanzen ≥40px — **behoben in dieser Session** (waren 34px)
- [ ] Farbauswahl im "+ Neuer Hufi"-Modal ≥36px mit ausreichendem Abstand — **behoben in dieser Session** (waren 28px)
- [ ] "Details anzeigen"/"Ergebnis anzeigen"-Buttons ≥40px Touch-Höhe — **behoben in dieser Session** (waren 32px)
- [x] Rightpane-Scrim verdunkelt bei Tablet-Breiten (700–1099px) das gesamte Hintergrund-UI inkl. Sidebar — **behoben in dieser Session** (z-index-Kollision)
- [x] Kein Konsolenfehler bei irgendeinem der 7 Breakpoints

## 11. Accessibility / Tastaturbedienung

- [x] Icon-only-Buttons haben `aria-label` (Menü, Details, Schließen, Farbe wählen)
- [x] Modal trägt `role="dialog" aria-modal="true"` mit `aria-label`
- [ ] Sichtbarer Fokusring auf allen interaktiven Elementen, unterscheidbar vom Hover-Zustand — **teilweise behoben in dieser Session** (`.agent-row` behoben; weitere Elemente nicht vollständig re-auditiert)
- [ ] "+ Neuer Hufi"-Modal erhält beim Öffnen automatisch Fokus auf das erste Feld — **behoben in dieser Session**
- [ ] Fokus bleibt im offenen Modal gefangen (Tab-Trap) — **behoben in dieser Session**
- [ ] Fokus kehrt beim Schließen des Modals zum auslösenden Button zurück — **behoben in dieser Session**
- [x] Escape schließt das Modal zuverlässig
- [x] Klick auf den Hintergrund-Scrim schließt das Modal
- [ ] `--text-faint` erfüllt WCAG-AA-Kontrast (4.5:1) — **behoben in dieser Session** (`#5b6578` → `#7a86a0`)
- [ ] `--idle`-Pilltext erfüllt WCAG-AA-Kontrast — **behoben in dieser Session** (`#6b7484` → `#7c8699`)
- [x] Tab-Reihenfolge folgt der visuellen Anordnung (Login, Sidebar, Chips — live per Tab-Simulation geprüft)
- [ ] Vollständiger Tastatur-Durchlauf durch Ergebnis-/Freigabekarten-Aktionen (Approve/Deny, Bericht öffnen) noch nicht separat verifiziert

## 12. Fehler / Wiederherstellung

- [x] Fehlgeschlagene Missionen zeigen eine klare, unterscheidbare rote "Nicht geschafft"-Pille
- [x] Fehlermeldung ist ein verständlicher Satz, kein Stacktrace
- [ ] Ergebniskarte bei Fehlschlag bietet einen "Nochmal versuchen"-Button (heute nicht vorhanden — `PRODUCT-FLOW-FINDINGS.md` SOLL Punkt 4)
- [ ] `failed`-Zustand ist über den normalen Chat-Pfad überhaupt provozierbar/beobachtbar (aktuell sehr selten, da das lokale Modell fast jede Eingabe "erfolgreich" beantwortet)
- [x] Login-Fehler zeigen eine klare deutsche Meldung ("Benutzername oder Passwort falsch"), kein technischer Fehlercode

## 13. Visuelle Konsistenz / Design System (siehe `HUFI-DESIGN-SYSTEM.md`)

- [x] `chat.css` und `agents.css` nutzen konsequent dieselben Tokens aus `app.css` (Card/Pill/Button/Avatar) — keine abweichenden Radien oder Farb-Duplikate gefunden
- [x] Ein einheitliches Fünf-Farben-Tonsystem (ok/warn/bad/idle/accent) für alle Statuspillen und -punkte
- [x] Eine gemeinsame Motion-Sprache (150–250ms, ein Easing) für alle Übergänge
- [ ] Eine klar definierte Typo-Skala statt mehrerer nahe beieinanderliegender Werte (`.74/.76/.78/.82rem`) — dokumentiert, nicht behoben (`UX-AUDIT-REPORT.md`, Visual Consistency)
- [x] Kein verschachteltes `.card`-in-`.card` irgendwo im Produkt

## 14. Vertrauen / Audit

- [x] Jede Statusänderung ist im Audit-Trail nachvollziehbar, übersetzt in Klartext
- [x] Rohes JSON bleibt als Fallback verfügbar, ohne den Normalmodus zu belasten
- [x] Modellwechsel/Failover würde in Klartext kommuniziert (Sprachregel definiert, `HUFI-UX-LANGUAGE.md` #22 — Verhalten selbst nicht separat live provoziert)
- [ ] Das "Team arbeitet"-Versprechen der Einstiegs-Copy deckt sich mit dem tatsächlichen Verhalten (heute: Copy verspricht ein Team, Realität liefert immer genau 1 Agenten — `PRODUCT-FLOW-FINDINGS.md` SOLL Punkt 9)
- [x] Der vollständige technische Audit-Trail bleibt für Experten zugänglich (Details-Toggle pro Chat-Turn + System-View)

---

## Zusammenfassung

**~118 Prüfpunkte**, davon zum Zeitpunkt dieses Audits:
- **bereits erfüllt / durch die Session-Fixes behoben:** siehe `[x]`-Markierungen (deutliche Mehrheit — die Kern-Chat-Erfahrung ist solide)
- **offen, mit konkretem Fix-Vorschlag, kein Backend nötig:** Retry-Button, Markdown-Rendering, Live-Aktivität-Polling, Zeitstempel auf Ergebniskarte, Routine-Erkennung im Chat (MUSS)
- **offen, blockiert auf Produktentscheidung (nicht nur Code):** Verweigerte Aufträge korrekt kennzeichnen, R1-Ceiling im Chat lösen, "Team"-Copy vs. Realität angleichen
- **offen, blockiert auf PR #12 (Backend):** echte Agentenerstellung, echte Routinen, Agent-zu-Agent-Sichtbarkeit, "Computer"-Anbindung

Die drei **MUSS**-Punkte aus `PRODUCT-FLOW-FINDINGS.md` (Routine-Täuschung, Erfolg-vortäuschende Ablehnungen, unerreichbare Freigaben) sind die einzigen Punkte in dieser Liste, die vor einem produktiven V1.x-Release als blockierend gelten sollten — alles andere ist SOLL/SPÄTER.
