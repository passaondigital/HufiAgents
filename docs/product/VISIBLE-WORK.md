# Hufi Visible Work / Arbeitsnachweis

Stand: 2026-09-08

## Verbindliches Produktprinzip

Hufi soll nicht nur behaupten, dass er arbeitet. Hufi soll für normale Menschen verständlich zeigen können, was tatsächlich passiert, was real erledigt wurde und welches Ergebnis entstanden ist.

Das ist besonders wichtig für Pferdeprofis, Handwerker, Solo-Selbstständige und andere Nutzer, für die KI neu oder ungewohnt ist.

> Ich sehe, dass mein digitales Team arbeitet. Ich sehe, was es gemacht hat. Und ich sehe, was es mir gebracht hat.

Visible Work / Work Evidence ist eine wiederverwendbare HUFI-Capability und kein dekorativer UI-Effekt.

## Audit ist nicht Work Evidence

- **Audit** ist die technische Wahrheit für Security, Review, Recovery und Diagnose.
- **Work Evidence / Arbeitsnachweis** ist eine bereinigte, nutzerverständliche Projektion realer Arbeit.

Der normale Nutzer soll bei Bedarf sehen können:

- was Hufi gerade macht,
- welcher Agent oder welches Team arbeitet,
- welche wichtigen Schritte abgeschlossen sind,
- welches echte Artefakt oder Ergebnis entstanden ist,
- ob etwas blockiert ist,
- was als Nächstes passiert,
- ob eine Freigabe erforderlich ist.

Technische IDs, Risk-Codes, Provider, rohe Tool-Calls und interne Statuswerte bleiben unter `Details / System`.

## Keine Fake-Aktivität

Fortschritt, Screenshots, Snapshots, Animationen und erledigte Schritte dürfen niemals erfunden werden.

Jeder sichtbare Arbeitsnachweis muss aus einem realen Event, Tool-Ergebnis oder Artefakt ableitbar sein. Beispiele:

- sicherer Screenshot oder Snapshot,
- erzeugte oder geänderte Datei,
- Vorher-/Nachher-Ansicht,
- Git-Diff oder Commit-Zusammenfassung,
- Branch-/Pull-Request-Vorschau,
- Test-/Build-Ergebnis,
- Browser-/App-Zustand,
- Server-/Service-Zustand,
- erzeugter Bericht, Entwurf, Bild oder anderes Artefakt.

Wenn kein echter Beleg vorhanden ist, zeigt Hufi das ehrlich an statt einen Beleg zu simulieren.

## Sichtbarkeitsmodi

### Einfach

Nur wichtige Meilensteine, Freigaben und das Ergebnis.

### Transparent

Meilensteine plus sichere Snapshots, Dateien, Tests, Diffs oder andere Evidence-Artefakte. Dieser Modus eignet sich besonders für neue oder skeptische Nutzer.

### Live

Optionales Beobachten einer echten Browser-, Computer- oder Terminal-Session, sobald die entsprechende Capability verfügbar ist. Live ist niemals Voraussetzung für die normale Nutzung.

## Org-Canvas / digitale Firma

Agenten- und Teamkarten sollen reale Arbeit anzeigen können:

- Status `arbeitet / wartet / fertig`,
- aktuelle Aufgabe,
- Projekt,
- Laufzeit,
- letzte echte Aktion,
- letzter Arbeitsnachweis,
- nächster Schritt,
- Aktion `Arbeit ansehen`.

Delegations- und Arbeitsflussanimationen dürfen nur reale Zustände visualisieren und keine Aktivität vortäuschen.

## Tages- und Wertbericht

Hufi soll später natürlich beantworten können:

> Was hat mein digitales Team heute für mich erledigt?

Die Antwort darf reale erledigte Aufgaben, Ergebnisse, Artefakte, Blocker, Routinen und betroffene Projekte zusammenfassen.

Zeitersparnis, ROI oder wirtschaftlicher Nutzen dürfen nur als gemessene Werte oder ausdrücklich als Schätzung gekennzeichnet dargestellt werden.

## Security / Privacy / Redaction

Work Evidence wird vor Anzeige und Speicherung bereinigt.

Nie unmaskiert in Chat, Snapshot, Artefakt oder nutzerseitigem Evidence-Eintrag anzeigen:

- Passwörter,
- API-Keys,
- Personal Access Tokens,
- private Schlüssel,
- `.env`-Inhalte,
- Session-Secrets,
- andere Credentials.

Personen-, Kunden- und Geschäftsdaten bleiben an Scope, Berechtigungen und Produktkontext gebunden. Wo ein kleinerer Beleg genügt, wird kein unnötig großer Screenshot gespeichert.

## Capability-first

Zielmodell:

```text
reales Event / Tool-Ergebnis / Artefakt
        ↓
Evidence Collector
        ↓
Redaction / Safety Filter
        ↓
Work-Evidence-Eintrag
        ↓
nutzerverständliche UI / Chat / Org-Canvas
        ↓
optional: technischer Audit-Drilldown
```

Die Capability soll von HufiBoss/HufiOS, HufiAgents, Hufi Manager, HufiApp, AgentHufi, HufiCloud und HUFI Factory wiederverwendet werden.

## Roadmap

- **Heute / vorhandene Basis:** Evidence aus Audit-, Tool-, Datei-, Test-, Review- und Git-Ereignissen ableiten.
- **V1.2:** Skills, Memory, Routinen und Learning mit Work Evidence verknüpfen.
- **V1.3:** echte Browser-/Computer-Snapshots, Live Preview und Handoff ergänzen.
- **Org-Canvas:** Evidence als sichtbaren Arbeitsstatus von Agenten, Teams und Projekten verwenden.
- **Produktintegration:** dieselbe Capability in Hufi Manager und HufiApp wiederverwenden.

## Definition of Done

Visible Work ist gut umgesetzt, wenn ein nicht-technischer Nutzer ohne Git-, Server-, Modell- oder Agentenwissen beantworten kann:

1. Was passiert gerade?
2. Wer arbeitet daran?
3. Was wurde wirklich erledigt?
4. Woran kann ich das sehen?
5. Was kam dabei heraus?
6. Was bringt es mir?
7. Muss ich etwas entscheiden?

**Hufi ist keine Blackbox. Hufi arbeitet autonom, aber nachvollziehbar.**
