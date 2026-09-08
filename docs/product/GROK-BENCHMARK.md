# HufiAgents vs. Grok Bot — Produkt-Benchmark

**Datum:** 2026-09-08
**Quelle Grok Bot:** eigene frühere Produktrecherche (Verhaltens-/Musterreferenz, keine Implementierungsdetails übernommen).
**Quelle HufiAgents:** live getestete App (siehe `PRODUCT-FLOW-FINDINGS.md` für Methodik), Port 8102, gleicher Prüflauf.

Für jede Dimension: was Grok Bot tut, was HufiAgents heute tut (live verifiziert, mit Markierung wo aus Code abgeleitet), was wir übernehmen sollten (Produktprinzip, nicht Implementierung), und wo unsere eigene Vision (das "digital company"-Modell, Audit-Trail, Risiko/Freigabe-Modell) über Grok Bot hinausgehen sollte statt es nur zu kopieren.

---

## 1. Einstieg (Onboarding / erster Screen)

**Grok Bot:** Direkter Einstieg in eine Chat-Oberfläche mit sichtbarer Bot-Liste; kein mehrstufiger Onboarding-Flow, der Nutzer landet sofort im Arbeitsmodus.

**HufiAgents:** Live gesehen — nach Login direkt der Chat-Screen mit Avatar "H", Frage "Was soll ich für dich erledigen?", erklärendem Satz ("Ich bin Hufi. Sag mir dein Ziel — ich hole mir das passende Team und melde mich mit dem Ergebnis.") und 5 anklickbaren Starter-Chips. Kein Tutorial, kein Setup-Wizard — funktional bereits sehr nah am Grok-Muster.

**Was übernehmen:** Nichts Neues nötig — der direkte Einstieg ohne Onboarding-Reibung ist bereits vorhanden und sollte so bleiben.

**Was besser machen:** Die Starter-Chips sind aktuell statisch/global (dieselben 5 für jeden Nutzer, jederzeit). Grok Bot zeigt kontextuelle Vorschläge pro Bot. HufiAgents könnte hier weitergehen als reines Kopieren: Starter-Vorschläge, die aus dem Audit-Trail echter vorheriger Missionen generiert werden ("Wiederhole: Tagesbericht wie letzten Montag") — das nutzt unseren bereits vorhandenen Audit-Vorteil, den Grok Bot in dieser Form nicht hat.

---

## 2. Sidebar

**Grok Bot:** Schmale linke Bot-/Chat-Sidebar als primäres Navigationselement, ein Bot pro Zeile.

**HufiAgents:** Live gesehen — Sidebar mit "+ Neuer Hufi"-Button, Suchfeld, Liste von 6 Agenten (`builder`, `hufi_chief`, `integrator`, `project_lead`, `reviewer`, `security`), jede Zeile mit Avatar (Farbe aus Hash der ID), Name, freundlicher Rollenbeschreibung (aus `ROLE_TRANSLATIONS`, mit Fallback auf bereinigten Rohtext) und Status-Pille ("Aktiv"). Auf Mobile per ☰-Button einklappbar (Overlay von links).

**Was übernehmen:** Struktur ist schon nah dran und funktioniert gut — nichts Grundsätzliches fehlt.

**Was besser machen:** Aktuell zeigt die Sidebar ausschließlich statische, vordefinierte Registry-Agenten. Sobald PR #12 dynamische Agenten liefert, sollte die Sidebar (anders als Grok Bot, das primär "Bots als Werkzeuge" listet) den "digitale Firma"-Charakter stärker zeigen — z. B. Gruppierung nach aktueller Zuständigkeit/Projekt statt nur einer flachen Liste, weil unser Modell explizit Hierarchie (Hufi Chief → Project Lead → Spezialisten) kennt, die Grok Bot als reine Bot-Sammlung nicht abbildet.

---

## 3. Agent-Erstellung

**Grok Bot:** Ein bestehender Bot kann im beobachteten Testlauf einen neuen Bot ("HufiLabTest") erzeugen, ohne dass ein Mensch manuell durch einen Erstellungs-Dialog klickt — der neue Bot erscheint direkt mit eigenem Chat, Persona und Desktop-Slot.

**HufiAgents:** Live gesehen — "+ Neuer Hufi" öffnet ein Modal (Name, Avatar-Farbe, Verantwortungsbereich-Text), aber jeder Submit endet in der ehrlichen Nachricht: "Danke! Eigene Hufis können in dieser Version noch nicht dauerhaft angelegt werden – das kommt mit den dynamischen Agenten." Kein `POST /agents` im Backend vorhanden (bestätigt im Code-Kommentar von `agents.js`).

**Was übernehmen:** Das Zielbild "Agent erstellt Agent" ohne manuellen Dialog-Umweg ist genau der High-Value-Pattern, den wir mit PR #12 (`POST /agents`) anstreben sollten — aktuell ist der manuelle Modal-Weg nur ein Platzhalter dafür.

**Was besser machen:** Grok Bots neuer Bot entsteht "unsichtbar" im Hintergrund einer Bot-Aktion. Für HufiAgents mit seinem Risiko-/Freigabe-Modell wäre der bessere Ansatz **nicht** blindes Kopieren dieser Unsichtbarkeit: Eine von einem Agenten selbst initiierte Agent-Erstellung sollte, abhängig von Risikoklasse, im Audit-Trail sichtbar und ggf. freigabepflichtig sein ("Hufi Chief möchte einen neuen Spezialisten anlegen: Marketing-Hufi — Zulassen/Ablehnen"). Das verbindet das Grok-Muster mit unserem eigenen Freigabe-Modell, statt es 1:1 zu übernehmen.

---

## 4. Chat

**Grok Bot:** Chat ist die zentrale Arbeitsfläche pro Bot, mit persönlicher Persona.

**HufiAgents:** Live gesehen — Chat ist tatsächlich die Hauptfläche (mittlere Spalte), Nachrichten als Bubbles, klare Statuszeilen während der Bearbeitung, Ergebnis-Karten mit Kurz-/Volltext-Umschaltung, ausklappbare "Details anzeigen"-Timeline pro Turn. Beim Anklicken eines Agenten in der Sidebar wechselt der Chat-Kontext ("Chat mit builder" als System-Notiz — hier leckt die rohe Agenten-ID statt des Anzeigenamens, siehe Findings-Dokument).

**Was übernehmen:** Grundstruktur ist bereits richtig. Ein Punkt, den Grok Bot klarer löst: eindeutige Persona pro Bot-Chat (eigene "Stimme"/Ton je nach Rolle). Bei HufiAgents antwortet aktuell in jedem Chat dieselbe generische Hufi-Bubble ("Alles klar. Ich prüfe das mit meinem Team.") unabhängig davon, welcher Agent gerade im Kontext ausgewählt ist.

**Was besser machen:** Unser Vorteil gegenüber Grok Bot ist der pro Turn verfügbare, vollständige Audit-Trail (übersetzt in Klartext, mit Rohdaten-Fallback) — das ist mehr Nachvollziehbarkeit, als ein reiner Chat-Verlauf normalerweise bietet. Dieses Feature ist bereits gebaut und sollte prominenter (nicht nur als kleiner "Details anzeigen"-Link) beworben werden, weil es unser Vertrauens-Differenzierungsmerkmal ist.

---

## 5. Computer

**Grok Bot:** Sichtbarer "Computer"-/Desktop-Slot pro Bot als persistentes Konzept, inklusive Update/Reset und Snapshot/Recovery.

**HufiAgents:** Live gesehen — jede Agenten-Detailansicht zeigt eine Karte "🖥️ Computer / Noch nicht verbunden". Das Konzept ist visuell vorbereitet, aber funktionslos (reiner Platzhalter, kein Backend dahinter).

**Was übernehmen:** Das Grundprinzip — ein sichtbarer, greifbarer "Arbeitsplatz" pro Agent statt einer abstrakten Blackbox — ist ein starkes Vertrauenselement und sollte übernommen werden, sobald es technisch belegbar ist (Workspace/Sandbox pro Agent existiert im Backend bereits als `Workspace`-Konzept laut `engine.py`, ist aber nicht mit diesem UI-Slot verbunden).

**Was besser machen:** Da HufiAgents bereits ein Audit-/Recovery-Modell hat (Wiederherstellung nach Neustart, siehe `EVENT_LABELS.recovery`), könnte der "Computer"-Slot mehr als Grok Bots Reset/Snapshot bieten: eine direkte Verbindung zum Audit-Trail dieses Workspace (welche Dateien wurden wann durch welchen Task verändert) — Nachvollziehbarkeit statt nur Reset-Knopf.

---

## 6. Routine

**Grok Bot:** Routinen pro Bot als eingebautes Konzept (wiederkehrende, terminierte Aufgaben).

**HufiAgents:** Live gesehen — Agenten-Detailansicht hat eine "Routinen"-Sektion mit Pille "Bald verfügbar", Beispieltext, und dem Hinweis, dass Routinen in dieser Version fehlen. Wichtiger Befund: Wird eine Routine stattdessen im Chat formuliert ("Mach das jeden Montag um 8 Uhr."), erkennt die App das **nicht** und führt es fälschlich als Einmal-Auftrag aus (siehe Findings-Dokument, Flow D) — kein Verweis auf die eigentlich vorhandene "Bald verfügbar"-Botschaft.

**Was übernehmen:** Das Grundkonzept "Routine pro Agent" ist bereits im UI vorgesehen; sobald PR #12s Routinen-Modul landet, sollte diese Sektion damit verbunden werden.

**Was besser machen:** Bis dahin — kurzfristig ohne Backend-Änderung umsetzbar — sollte der Chat selbst Routine-artige Formulierungen erkennen und auf die bereits existierende ehrliche Botschaft verweisen, statt eine Fake-Einmal-Mission auszuführen (siehe MUSS-Punkt 1 im Findings-Dokument). Das wäre bereits besser als Grok Bots reine Feature-Verfügbarkeit, weil es dem Nutzer aktiv sagt, was er stattdessen tun kann, statt ihn nur ins Leere laufen zu lassen.

---

## 7. Freigaben (Approvals)

**Grok Bot:** Kein prominentes, granulares Freigabe-Konzept bekannt; eher pro-Aktion lokale Ausführungsberechtigung (per-action local execution permission) auf Werkzeugebene.

**HufiAgents:** Nicht live beobachtet (aus Code abgeleitet, `chat.js` `renderApprovalCard()`), da eine normale Chat-Mission strukturell nie über `R1` hinauskommt (siehe Findings, Flow E). Der Code zeigt: eine Karte "Hufi möchte etwas tun" mit Klartext-Zusammenfassung, ausklappbaren Details (Risiko-Pille R0–R4, farbcodiert), zwei klaren Buttons ("Zulassen"/"Ablehnen") und Klartext-Rückmeldung nach der Entscheidung. Kein technischer Jargon in der Grundansicht.

**Was übernehmen:** Grok Bots Prinzip "pro Aktion lokal freigeben" ist im Kern das, was unsere Risikostufen R2–R4 bereits strukturell abbilden — das ist konzeptionell richtig angelegt, nur aktuell im Chat unerreichbar (feste R1-Ceiling).

**Was besser machen:** Hier übertrifft unser Vision-Anspruch Grok Bot bereits im Design (nicht in der Erreichbarkeit): Eine einzelne, konsistente Freigabekarte mit Risikoklasse statt vieler kleiner Pro-Tool-Permission-Prompts ist für den Nutzer kognitiv leichter als Grok Bots granulares Pro-Aktion-Modell. Sobald die R1-Ceiling-Blockade behoben ist (MUSS Punkt 3), ist das Freigabe-Erlebnis bereits potenziell besser als das Referenzmuster — es muss nur noch erreichbar gemacht werden.

---

## 8. Agentenstatus

**Grok Bot:** Kein spezifisches Detail aus der Referenz bekannt jenseits allgemeiner Bot-Übersicht.

**HufiAgents:** Live gesehen — jeder Agent zeigt eine Status-Pille ("Aktiv"/"Deaktiviert"), und im Detail-Panel eine "Live-Aktivität"-Sektion, die aggregierte Audit-Events dieses Agenten aus den letzten ~25 Missionen zeigt (Klartext-Label + Zeitstempel, z. B. "Denkt nach …", "Antwort erhalten", "Aktion abgeschlossen"). Das ist bereits ein granulares, laufendes Aktivitätsprotokoll pro Agent.

**Was übernehmen:** Nichts Zusätzliches aus der Grok-Referenz nötig — dieser Bereich ist bereits ein Stärkefeld von HufiAgents.

**Was besser machen:** Aktuell ist "Live-Aktivität" ein Pull-Snapshot beim Öffnen des Panels (kein Live-Update/Polling während das Panel offen bleibt) — ein Live-Ticker (analog zur Chat-Progress-Line) würde das Konzept "digitale Firma, die gerade arbeitet" glaubwürdiger machen, statt eines statischen Abrufs.

---

## 9. Marketplace

**Grok Bot:** Plugin-Marktplatz und Bot-/Template-Marktplatz als eigene Konzepte.

**HufiAgents:** Live geprüft — es existiert **keinerlei** Marketplace-Oberfläche, kein Menüpunkt, kein Hinweis darauf in Sidebar, Chat oder Agentenansicht. Vollständig abwesend, auch nicht als Platzhalter.

**Was übernehmen:** Das Grundprinzip — vorgefertigte Agenten-/Werkzeug-Vorlagen statt jeden Agenten von Null zu bauen — ist sinnvoll, sobald dynamische Agentenerstellung (PR #12) existiert; aktuell gibt es nichts zu vermarkten.

**Was besser machen:** Kein aktueller Bewertungspunkt, da nicht gebaut — als SPÄTER einzuordnen, klar nachgelagert zu MUSS/SOLL-Punkten dieses Audits.

---

## 10. Nutzung (Usage/Billing)

**Grok Bot:** Nutzung/Abrechnung bewusst außerhalb der Hauptarbeitsfläche gehalten.

**HufiAgents:** Live geprüft — es gibt in der neuen Chat-first-UI **keine sichtbare Nutzungs-/Kosten-Anzeige** irgendwo (weder Sidebar noch Topbar noch Agentenpanel). Das entspricht dem Grok-Prinzip "raushalten aus der Arbeitsfläche" — allerdings eher dadurch, dass es schlicht noch nicht gebaut ist, nicht durch bewusste Verlagerung an einen anderen Ort (es gibt aktuell auch keinen anderen sichtbaren Ort dafür — kein Settings-Menü mit Nutzung/Abrechnung im getesteten UI).

**Was übernehmen:** Prinzip bestätigen und beibehalten, sobald Nutzung/Kosten überhaupt eingeführt werden — sie gehören nicht in Chat oder Agentenprofil.

**Was besser machen:** Da HufiAgents bereits Provider-Routing und Modell-Kosten im Audit-Trail mitloggt (`model_call`/`model_result`-Events mit Provider/Modell), könnte eine spätere Nutzungsansicht direkt auf diesen bereits vorhandenen Audit-Daten aufbauen, statt eine komplett neue Kosten-Tracking-Schicht zu bauen — ein Vorteil gegenüber einer Grok-artigen separaten Billing-Komponente.

---

## 11. Settings

**Grok Bot:** Keine spezifischen Details aus der Referenz zu Settings bekannt.

**HufiAgents:** Live geprüft — es gibt **kein Settings-Menü** in der neuen Chat-first-UI. Einzige globale Aktion ist "Abmelden" im Sidebar-Footer, daneben ein "verbunden"-Verbindungsstatus-Text. Der einzige Weg zu "mehr" ist der Link "Vollständiges technisches Dashboard öffnen ↗" im System-View (führt zu `/legacy`, dem alten Admin-Dashboard).

**Was übernehmen:** Kein direktes Grok-Bot-Vorbild zu übernehmen — hier gibt es aus der Referenz keine konkrete Vorgabe.

**Was besser machen:** Aktuell landet jede "erweiterte" Konfigurationsabsicht zwangsläufig im alten technischen `/legacy`-Dashboard — ein harter Bruch der sonst konsequent vereinfachten Sprache. Ein minimales, eigenes Settings-Panel (z. B. Standard-Risikoceiling, Benachrichtigungen) innerhalb der neuen UI, statt eines Sprungs ins alte Dashboard, würde die "ein Produkt, eine Sprache"-Konsistenz besser wahren als jedes Grok-Bot-Muster vorgibt.

---

## Gesamtfazit Benchmark

HufiAgents hat die **Chat-, Sidebar- und Detailansicht-Grundstruktur** bereits sehr nah an das Grok-Bot-Muster herangeführt und übertrifft es konzeptionell in zwei Bereichen, die im Code bereits sichtbar sind: dem **übersetzten Audit-Trail** (Klartext-Timeline statt roher Logs) und dem **einheitlichen, klar gestalteten Freigabe-Karten-Design** (aktuell nur nicht erreichbar). Die größten Lücken sind nicht gestalterisch, sondern strukturell: dynamische Agentenerstellung, Routinen und ein funktionierender "Computer"-Slot fehlen komplett im Backend (bekannt, auf PR #12 verwiesen), während zwei Dinge — die Chat-Ceiling-Blockade der Freigaben und die fehlende Routine-Erkennung im Chat — mit vergleichsweise kleinem Aufwand behoben werden könnten, ohne auf PR #12 zu warten.
