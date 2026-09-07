# HufiAgents V1 — User Guide

## Öffnen

https://agents.heyhufi.com — Login mit dem Benutzernamen und Passwort, die
Pascal separat erhalten hat (nicht im Repository, nicht in diesem Dokument).
Die Sitzung bleibt danach 7 Tage im Browser gültig (`Abmelden`-Button oben
rechts loggt sofort aus).

## Dashboard

Erste Seite nach dem Login. Zeigt auf einen Blick:

- **Systemstatus** — läuft HufiAgents.
- **Aktive Missionen** — was gerade arbeitet.
- **Offene Approvals** — was auf eine Entscheidung wartet.
- **Agenten aktiv / Modelle gesund** — Kurzstatus.
- **Letzte Ergebnisse** — zuletzt abgeschlossene Missionen mit Ergebnis.
- **Letzte Fehler** — zuletzt fehlgeschlagene Missionen.

Jede Zeile in einer Missionstabelle ist klickbar → Mission Detail.

## Eine Mission erstellen

„Mission erstellen" in der Navigation.

1. **„Was soll HufiAgents erledigen?"** — freier Text, z. B. „Analysiere den
   aktuellen HufManager technisch und erstelle einen priorisierten
   Statusbericht."
2. **Projekt** — optional. Ohne Projekt bearbeitet HufiAgents die Aufgabe
   frei (nur Text/Dateien im eigenen Arbeitsbereich, kein Repo-Zugriff).
   Mit Projekt (`hufiagents` oder `hufmanager`) klont der Agent zuerst das
   jeweilige Repository.
3. **Risikostufe** — R0 (nur lesend) bis R4 (kritisch). Für reine Analysen
   reicht R1. Höhere Stufen sind nur relevant, wenn eine Mission tatsächlich
   schreibende/externe Schritte enthalten soll.
4. **Dry Run** — angehakt lassen, solange kein echter Push/keine echte
   Änderung am Zielrepository gewollt ist. Dry Run meldet, was passieren
   würde, ohne es zu tun.
5. „Mission starten" → man landet direkt auf der Mission-Detail-Seite.

## Mission Detail

Ziel, Status, Risikostufe, Zeitpunkte, das **Ergebnis** (sobald vorhanden)
und pro Task: zugewiesener Agent, verwendetes Modell und Auswahlgrund,
Anzahl Wiederholungen, Reviewer-Verdikt, sowie die einzelnen Tool-Aufrufe
hinter „Details". Darunter der vollständige **Audit-Verlauf** dieser Mission
als lesbare Zeitleiste — jedes Ereignis mit rohem JSON hinter „Details" für
den technischen Blick.

## Agents

Zeigt jeden registrierten Agenten mit Rolle, Status, Risikodecke und
erlaubten Tools. `builder`, `integrator` und `reviewer` führen tatsächlich
Arbeit aus; `Hufi Chief`, `Project Lead` und `Security` sind zur
Transparenz gelistet (sie tragen aktuell keine ausführenden Fähigkeiten —
sie werden nicht fälschlich als „arbeitend" dargestellt).

## Projects

Die beiden konfigurierten Projekte (`hufiagents`, `hufmanager`) mit
Repository, Branch und ob Test/Build/Lint-Befehle hinterlegt sind. Nur hier
gelistete, erlaubte Projekte sind für Missionen wählbar — eine Mission kann
kein beliebiges anderes Repository ansprechen.

## Models

Zeigt jeden konfigurierten Provider (aktuell: `hufi-local-router` als
Standard, dazu `fake`/`ollama` als nicht genutzte Alternativen), dessen
Health und Auswahlgrund. Darunter der **Failover-Status** des lokalen HUFI
AI Routers: erreichbare Modelle, Requests gesamt, Primary/Secondary
up/down, Anzahl Failovers.

## Approvals

Alle Freigabeanfragen (R3/R4-Aktionen), offen und bereits entschieden.
Bei offenen Anfragen: **Approve** oder **Deny**, jeweils mit optionaler
Begründung. Ohne Entscheidung führt HufiAgents die Aktion nicht aus — das
gilt technisch, nicht nur visuell (der zugrundeliegende Tool-Aufruf startet
erst nach Freigabe).

## Audit

Missionsauswahl oben, darunter die komplette Ereignis-Zeitleiste dieser
Mission in Klartext (z. B. „Modell hat geantwortet", „Reviewer-Prüfung",
„Statuswechsel") statt rohem JSON. Jedes Ereignis kann über „Details"
aufgeklappt werden.

## System

Kurzüberblick: HufiAgents-Status, Standardmodell, maximale parallele Tasks,
ob Login aktiv ist, ob der AI Router erreichbar ist. Technische API-Referenz
unter „/docs" verlinkt.

## Was HufiAgents in V1 (noch) nicht tut

- Kein automatischer Push/PR ohne konfigurierten, separat verwalteten
  GitHub-Token (in dieser Instanz standardmäßig nicht gesetzt).
- Das lokale Modell hält sich nicht immer an Längenvorgaben — ein sehr
  knappes Ergebnis ist ein Modell-Verhalten, kein Systemfehler; ein
  erneuter Versuch (ggf. mit präziserem Auftrag) hilft meist.
- Analysen basieren auf dem, was HufiAgents dem Modell explizit als
  Kontext mitgibt (Auftragstext, Constraints, Ergebnisse vorheriger Tasks
  in derselben Mission) — nicht automatisch auf jeder Datei im geklonten
  Repository.
