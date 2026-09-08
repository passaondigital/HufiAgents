# Hufi UX-Sprachregeln

**Zweck:** Jeder Text, der ein normaler Nutzer sieht (nicht im "Details"/"System"-Modus), folgt diesen Regeln. Ziel: Hufi klingt wie ein kompetenter Kollege, nicht wie ein Log-File. Diese Liste ist die Referenz für jeden neuen Screen/Text — bei Zweifel: NICHT-Spalte vermeiden, SONDERN-Spalte nachbauen.

## Grundregeln

1. Kein Backend-Vokabular im Haupt-Flow: kein `mission`, `task`, `provider`, `risk_ceiling`, `event_type`, `tool_call`, `idempotency_key`.
2. Kein Enum-Wert roh anzeigen (`queued`, `R3`, `waiting_approval`, `policy_blocked`) — immer übersetzen.
3. Keine UUIDs, keine internen IDs, keine Zeitstempel im ISO-Format im Haupt-Flow.
4. Erste Person für Hufi ("Ich prüfe …"), zweite Person für den Nutzer ("Du kannst …") — nie unpersönliches Passiv ("Es wurde geprüft").
5. Sätze kurz, ein Gedanke pro Satz. Keine Schachtelsätze.
6. Ehrlichkeit vor Beschönigung: wenn etwas nicht geht (z. B. Hufi-Erstellung), das klar sagen statt es zu verstecken oder falsch positiv zu tun.

## Missions- / Status-Sprache

| # | NICHT | SONDERN |
|---|---|---|
| 1 | "Mission 42b3e6ac running" | "Ich prüfe HufManager." |
| 2 | "Status: queued" | "Wird eingeplant …" |
| 3 | "Status: planning" | "Hufi plant die nächsten Schritte …" |
| 4 | "Status: running, 2 tasks" | "2 Agenten arbeiten daran …" |
| 5 | "Status: review" | "Hufi prüft das Ergebnis …" |
| 6 | "Status: blocked" | "Kommt gerade nicht weiter — Hufi sucht einen anderen Weg …" |
| 7 | "Status: retrying (attempt 2/3)" | "Ein Schritt wird noch einmal versucht …" |
| 8 | "Status: completed" | "Fertig." |
| 9 | "Status: failed" | "Nicht geschafft." (+ verständlicher Grund, wenn bekannt) |
| 10 | "Status: cancelled" | "Abgebrochen." |
| 11 | "Task 3f655f80 assigned to agent builder" | (keine eigene Meldung nötig — fließt in die Team-Aussage: "Ich hole mir das passende Team.") |
| 12 | Fortschrittsbalken mit Prozentzahl ohne Bedeutung | Kurze, konkrete Statuszeile ("Repository geprüft", "Review läuft") — lieber eine ehrliche Zeile als eine erfundene Prozentzahl |

## Risiko- / Freigabe-Sprache

| # | NICHT | SONDERN |
|---|---|---|
| 13 | "Risk R3 approval required" | "Ich brauche kurz deine Freigabe." |
| 14 | "risk_class: R3" | (nur unter "Details": "Risikostufe: mittel-hoch") |
| 15 | "ApprovalRequest pending" | "Hufi wartet auf deine Entscheidung." |
| 16 | "approve / deny" (Button-Label) | "Zulassen" / "Ablehnen" |
| 17 | "Policy blocked: git.push denied by policy" | "Das darf Hufi ohne deine Zustimmung nicht tun." |
| 18 | "task.risk_ceiling exceeded agent.default_risk_ceiling" | "Das geht über das hinaus, was dieser Hufi allein entscheiden darf." |
| 19 | "R0 / R1 / R2 / R3 / R4" als Label | Klartext: "nur lesend", "lokal, rückgängig machbar", "kleine externe Wirkung", "braucht deine Freigabe", "kritisch, braucht deine Freigabe" — nur im Details-Modus überhaupt als Code sichtbar |
| 20 | "execution_started: false, result_status: blocked" | "Hufi hat noch nichts verändert." |
| 21 | Freigabe-Karte ohne Kontext | Immer: was, warum, welche Auswirkung, ob rückgängig machbar — siehe Approval-Card-Struktur im Design System |

## Modell- / Provider-Sprache

| # | NICHT | SONDERN |
|---|---|---|
| 22 | "Provider failover: primary → secondary" | "Das erste Modell war nicht verfügbar. Ich habe automatisch gewechselt." |
| 23 | "hufi-local-router unhealthy" | "Ein Teil meiner Werkzeuge ist gerade nicht erreichbar. Ich melde mich, sobald es weitergeht." |
| 24 | "model: hufi-qwen9-fast, tokens: 512" | (nichts — reine Interna, gehören unter Details) |
| 25 | "routing_reason: local, privacy-preferring" | (nur unter Details, in Klartext: "Lokal verarbeitet, aus Datenschutzgründen") |
| 26 | "Model call timeout after 180s" | "Das dauert gerade länger als sonst. Ich bleibe dran." |

## Fehler- / Wiederherstellungs-Sprache

| # | NICHT | SONDERN |
|---|---|---|
| 27 | "executor_error: Connection refused" | "Da ist etwas schiefgelaufen. Ich versuche es noch einmal." |
| 28 | "Retry 2/3, reason: tool_error" | "Ich probiere einen anderen Weg." |
| 29 | "recovery: stale heartbeat, task requeued" | "Ich musste kurz neu starten — die Arbeit geht normal weiter." |
| 30 | "ReviewResult verdict: reject" | "Das Ergebnis hat meine eigene Prüfung nicht bestanden. Ich arbeite es noch einmal." |
| 31 | "ReviewResult verdict: revise" | "Ein Kollege von mir hatte noch Anmerkungen — ich bessere nach." |
| 32 | Leere Fehlermeldung / stiller Abbruch | Immer einen Satz, was passiert ist und was als Nächstes kommt |
| 33 | "Fatal error, mission failed permanently" | "Das hat leider nicht geklappt: [Grund in einem Satz]." + klare nächste Aktion (z. B. "Noch einmal versuchen") |

## Agenten-Sprache

| # | NICHT | SONDERN |
|---|---|---|
| 34 | "agent_id: builder, status: active" | Name + eine Zeile Rolle + Status-Pille ("Aktiv") |
| 35 | "default_risk_ceiling: R2" | (nur unter "Weitere Informationen": "Risikodecke: R2") |
| 36 | "capabilities.tools: [files, shell, git]" | (nur unter Details, als Tags: "Dateien", "Terminal", "Git" — deutsche Werkzeugnamen, nicht die internen IDs) |
| 37 | "Bounded workspace builder" (Rohtext aus der Registry) | "Arbeitet eigenständig in einer abgesicherten Umgebung." |
| 38 | "agent_registered" (Audit-Event-Label) | "Wurde registriert" |
| 39 | "agent_assigned" (Audit-Event-Label) | "Wurde zugewiesen" |
| 40 | Kein Feedback bei Hufi-Erstellung | Klar und freundlich: "Danke! Eigene Hufis können in dieser Version noch nicht dauerhaft angelegt werden – das kommt mit den dynamischen Agenten." (nie stiller Fehlschlag, nie vorgetäuschter Erfolg) |

## Audit- / Technik-Sprache (nur unter "Details" sichtbar, aber auch dort möglichst klar)

| # | NICHT | SONDERN |
|---|---|---|
| 41 | "tool_call: git.push auf hufmanager · reviewer_gate" | "Werkzeug angefordert: git.push auf hufmanager" |
| 42 | "state_transition: queued → planning" | "Statuswechsel: Wird eingeplant → Wird geplant" |
| 43 | "task_created, dependencies: []" | "Aufgabe erstellt" |
| 44 | Rohes JSON als einzige Darstellung | Übersetzte Zeile zuerst, Rohdaten als aufklappbares "Rohdaten"-Detail darunter |
| 45 | ISO-Zeitstempel ("2026-09-08T05:17:30.949697Z") | Lokalisiertes Datum/Zeit ("8.9.2026, 07:17") |

## Struktur / Ton

| # | NICHT | SONDERN |
|---|---|---|
| 46 | "Es wurde ein Fehler erkannt." (Passiv, unpersönlich) | "Das hat nicht geklappt." (Aktiv, direkt) |
| 47 | Übertrieben enthusiastischer Ton ("Super! Alles perfekt erledigt! 🎉") | Sachlich-freundlich, ohne Ausrufezeichen-Inflation: "Fertig. [Ergebnis in einem Satz]." |
| 48 | Warnungen ohne Handlungsoption | Immer mit klarer nächster Aktion (Button oder ein Satz, was der Nutzer tun kann) |
| 49 | Technischer Jargon in Tooltips/Platzhaltern ("z. B. task objective") | Alltagssprache ("Beschreibe kurz den Verantwortungsbereich …") |
| 50 | Mehrdeutige Statuswörter ohne Kontext ("Aktiv") allein für Freigaben/Approvals | Immer mit Objekt: "Aktiv" nur für Agentenstatus; Freigaben nutzen eigene Wörter ("Wartet auf dich", "Freigegeben", "Abgelehnt") |
| 51 | Platzhaltertext, der wie ein Fehler aussieht ("undefined", "null", "—" ohne Erklärung) | Bewusster Leerzustand mit Satz ("Noch keine Aktivität.", "Noch nicht verbunden.") |
| 52 | Konfirmations-Dialoge mit Ja/Nein ohne Konsequenz-Text | Immer: was passiert, wenn ich zustimme; ist es rückgängig machbar |

## Anwendung

- Neue Texte immer gegen diese Tabelle prüfen, bevor sie in `chat.js`/`agents.js` landen.
- Wenn ein neuer Backend-Enum-Wert dazukommt (neuer `event_type`, neuer Status), zuerst hier eine Zeile ergänzen, dann implementieren — nie umgekehrt.
- Der komplette Wortschatz für Statuszeilen lebt aktuell in `chat.js` (`EVENT_LABELS`, `statusLine()`) und `agents.js` (`EVENT_LABELS`, `friendlyRole()`) — beide Listen sollten mit dieser Datei synchron bleiben.
