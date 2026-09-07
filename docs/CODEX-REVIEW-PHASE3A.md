# Codex Phase 3A — unabhängiger Security- und Reliability-Review

Datum: 2026-09-07. Prüfgegenstand: PR #3,
`claude/phase3a-hufmanager-write-e2e`, Commit
`f65bcbd2733bd2a17b01da3a6eb8eeccdf6ed344`.
Review/Fixes: `codex/review-phase3a-auth`, eigener Worktree.

**MERGE READY = NO.** Den unveränderten PR nicht mergen. Die Korrekturen dieses
Review-Branches schließen konkrete Credential-Angriffspfade, ersetzen aber keine
OS-Sandbox und keine zuverlässig überwachte Prozessgruppe bei Dienstabsturz.
Der vollständige HufManager-Test-/Build-Workflow ist deshalb weiterhin blockiert.

## Methode und Evidenz

`git fetch --all`; eigener Branch vom verlangten Remote-Branch; zusätzlich
`refs/pull/3/head` separat abgerufen. Code, ADR-009/010/011, SECURITY, Connector und
Handoffs eigenständig gelesen. Claudes frühere Testergebnisse wurden nicht als
Nachweis übernommen. Keine Produktionsänderung, kein HufManager-Push, keine PR dort,
keine Übernahme der persönlichen gh-Anmeldung und keine echten Tokens verwendet.
Alle Auth-Tests benutzen ausschließlich synthetische Werte und Loopback-Server.

Die ersten beiden neuen Regressionstests wurden **vor den Fixes** ausgeführt und
scheiterten am Originalstand:

- `test_pushurl_cannot_redirect_credentials`: statt der erwarteten Ablehnung wurde
  trotz erlaubter GitHub-Fetch-URL zum fremden lokalen Basic-Auth-Server gepusht.
- `test_credential_output_is_not_persistable_even_if_encoded_or_truncated`:
  credentialführende Ausgabe wurde als persistierbares ToolResult zurückgegeben.

## Findings und Fixes

| ID | Schwere | Befund | Maßnahme / Status |
| --- | --- | --- | --- |
| F1 | Kritisch | Registriertes `npm test`/build/lint führt Repository-Code unter der Dienst-UID aus. Auch ein neu angelegter Test kann beliebigen Code enthalten. Ein fixes argv isoliert weder Host-Dateien noch Prozesse, Credential-Speicher oder den installierten Helper. | Gefährliche Projektkommandos fail-closed deaktiviert. Nur inerte, geschlossene Kommandos bleiben verfügbar. Funktionale Wiederfreigabe benötigt eine echte OS-Sandbox. **Blocker.** |
| F2 | Hoch | `remote get-url origin` prüfte die Fetch-URL; `remote.origin.pushurl` konnte Credentials und Inhalt an ein anderes Ziel schicken. Weitere Git-Keys verändern Ref-Ziele, Helfer, Programme oder HTTP-Verhalten. | Konservative Konfigurations-Allowlist, Ablehnung unbekannter Sektionen/Keys, explizite Ziel-URL und vollständiger Quell-/Ziel-Refspec. Kein konfigurierbarer Push-Refspec, Mirror oder Receive-Pack. |
| F3 | Hoch | Musterredaktion kennt einen beliebigen opaken Token nicht. Serverausgabe kann ihn roh, kodiert oder an einer Trunkierungsgrenze zurückgeben; danach landet sie im ToolResult/DB. | Credentialführende Prozesse speichern überhaupt keine stdout/stderr-Inhalte. Nur statischer Erfolgs-/Fehlertext und Exitcode. Gilt auch für GH_TOKEN. Verlust detaillierter Push-/PR-Ausgabe ist bewusst. |
| F4 | Hoch | Kein eigener Transportfilter; Redirects und lokale HTTP-Konfiguration konnten die Ziel-/TLS-Grenze aufweichen. Lokale Pushes erhielten unnötig das Token, einschließlich lokalem Receive-Pack. | HTTPS für externe Ziele; HTTP nur auf numerischem Loopback für lokale Tests. Keine URL-Credentials, Query, Fragment, Escape-/Helper-/SSH-Syntax. Redirects aus, TLS-Prüfung an, erlaubtes Protokoll explizit. Lokale Dateirepos erhalten kein Token. |
| F5 | Mittel | Runtime-chmod am Helper statt Prüfung; Symlinks/unsichere Rechte konnten akzeptiert bzw. verändert werden. Git-Metadaten prüften keine Hardlinks. | Helper muss regulär, ausführbar, einfach verlinkt und ohne Gruppen-/Welt-Schreibrecht installiert sein; sonst Ablehnung, kein chmod. Metadaten-Links werden abgewiesen; lokale Clones nutzen `--no-hardlinks`. Askpass antwortet nur auf Username/Password und benutzt printf. |
| F6 | Hoch | `start_new_session=True` plus Python-Timeout schützt nicht vor hartem Tod des Elternprozesses. Ein Credential-Kind kann weiterlaufen; Recovery stoppt es nicht. | Eigenständig reproduziert, siehe Crash-Probe. Graceful cancellation/Timeout und keine Wiederholung unbekannter Push-Effekte sind getestet. **Harte Prozessbaum-Bereinigung bleibt Blocker.** |
| F7 | Mittel | add/commit schützten benannte Default-Branches, verlangten aber nicht tatsächlich immer `hufi/…`. Ein Projekt-Default namens `hufi/…` konnte Push-Prüfung passieren. | Branch-Prüfungen verschärft; keine Writes auf gewöhnlichen Feature-Branches oder Push auf Projekt-Default. |
| F8 | Mittel | `HOME=workspace` allein isoliert gh nicht von einer durch Tasks angelegten `.config/gh`-Konfiguration. | Privates temporäres GH_CONFIG_DIR, expliziter GH_HOST, validiertes owner/repo und Git-Metadatenprüfung. Config-Verzeichnis wird nach normalem Ende entfernt; es enthält keinen geschriebenen Token. |

F1/F6 hängen zusammen: Ohne Ausführung von Task-Code kann ein Task die
Git-Metadaten nicht über FilesTool verändern. Ein Prozess derselben UID außerhalb
des geschlossenen Toolmodells bleibt jedoch mächtiger als alle Python-Pfadprüfungen.
Die Review-Fixes behaupten keine Sicherheitsgrenze gegenüber einer kompromittierten
Dienst-UID, root, manipuliertem Python/Git oder einer beschreibbaren Installation.

## Credential-Pfad und geprüfte Grenzen

`HUFI_GITHUB_TOKEN` → `Settings.github_token` (SecretStr) →
`Orchestrator.tools()` → `GitTool.push_token` → fest aufgebautes Subprozess-Environment →
statischer `GIT_ASKPASS` → Git-HTTP-Transport.

| Anforderung / Angriff | Ergebnis |
| --- | --- |
| Token in argv, Remote-URL, Git-Konfiguration | Nicht injiziert; URL-/Config-Prüfung und echte Push-Tests. |
| Token in Audit, DB, Artifacts, Logs, Fehlerausgabe | 0 beobachtete Leaks nach Fix in lokalen Auth-Tests; credentialführende Ausgabe wird verworfen; SQLite zusätzlich binär geprüft. Keine universelle Aussage über bösartige Host-Prozesse. |
| Settings-Repr / Serialisierung | SecretStr maskiert; eigener Environment-Test. |
| Fehlender Token | Fail-closed vor dem eigentlichen Push. Lokale Branch-/Origin-Prüfprozesse können vorher laufen; die historische Aussage „vor jedem Subprozess“ war zu weitgehend. Dry-run braucht keinen Token. |
| Falscher / richtiger Token | Echter HTTP-Basic-Auth-Roundtrip: Fehler ohne Ausgabe-Leak / erfolgreicher Push mit nachgewiesenem Remote-Ref. Auch aus installiertem Wheel. |
| Task überschreibt Remote, env, GIT_ASKPASS | Task-Params ignoriert; überwachte Subprozess-Umgebung enthält nur beim echten HTTP-Push das Push-Credential. Eltern-Environment einschließlich Git-Konfigurationsvariablen wird nicht geerbt. |
| Fremder Remote / pushurl / URL-Rewrite | Abgewiesen; echte frühere Exfiltrationsroute reproduziert und Regression grün. |
| main/master, Projekt-Default, schädliche Branch-Namen | Geschützt; strikte bounded hufi-Regel und expliziter Ref-Zielname. |
| Builder / Integrator / erlaubte Projekte | Bestehende Gateway-/Policy-/Registry-Tests neu ausgeführt: Builder bleibt R1; Integrator braucht R2 und serverseitig erlaubte Ziele. |
| Shell-Injection / lokale Git-Ausführungshooks | Kein Shell-Interpreter für argv; Hooks aus; unbekannte Git-Konfiguration abgewiesen; Paketcode bis Sandbox gesperrt. |
| Symlinks / Hardlinks / Helper-Rechte | Neue Regressionen; keine automatische Reparatur unsicherer Helper. |
| Redirect zu anderem Server | Echter lokaler Redirect-Test scheitert geschlossen; kein Remote-Ref angelegt. |
| Paket/Wheel | Script im Wheel 0755; frische Installation geprüft; echter Auth-Erfolg und Auth-Fehler daraus. |
| Timeout / regulärer Abbruch | Testprozess beendet und gereapt; keine lesbare laufende Credential-Umgebung verbleibt. |
| Restart nach erfolgreichem Push vor Ergebnis-Commit | Echter lokaler Push plus simuliertes Abbruchfenster: nach Restart keine Wiederholung; Task scheitert zur manuellen Klärung. |
| Harter Elternprozess-Absturz | **Nicht sicher:** eigener Probeprozess zeigt weiterlebendes Credential-Kind. Nach Messung explizit beendet. |
| Race Conditions | Keine Task-Code-Ausführung mehr; dennoch keine atomare OS-Grenze gegen gleichzeitige Manipulation durch fremde Prozesse derselben UID. |

„Token nur im Push-Subprozess“ gilt nur als Weitergabegrenze: Der Dienst hält ihn
bereits in Settings/Arbeitsspeicher, und Git reicht das Environment an seine
HTTP-/Askpass-Kinder weiter. GH_TOKEN ist außerdem der ausdrücklich vorgesehene
PR-Pfad. Kein Python-String wird kryptografisch aus Speicher gelöscht; OS-Swap,
Core-Dumps und Same-UID-/root-Zugriff sind damit nicht ausgeschlossen.

## Reproduzierbare Prüfungen

```sh
uv sync --frozen
uv run ruff check
uv run ruff format --check
uv run pytest -q
uv build
uv run python scripts/review_phase3a_hufmanager.py
uv run python scripts/review_phase3a_crash.py
```

Die Tests benötigen lokale Loopback-Sockets; der HufManager-Probelauf benötigt
lesenden GitHub-Netzzugriff. Der Crash-Probelauf nutzt nur ein kurzlebiges `sleep`
über denselben `run_process`-Pfad, keinen Netzwerk-Push. Er meldet aktuell
`credential_child_survives_parent_sigkill: true` und räumt das Kind anschließend ab.
Das ist ein **negativer Sicherheitsnachweis**, kein bestandener Crash-Sicherheitstest.

Security-Regressionen: `tests/unit/test_phase3a_security_review.py`,
`tests/unit/test_git_push_credentials.py`,
`tests/integration/test_git_push_credentials_e2e.py`; dazu bestehende
Connector-, Gateway-, Registry-, Policy-, Restart- und Redaction-Tests.
Ergebnis: **242 Tests bestanden**, 45 mehr als am Ausgangsstand. Ruff-Check und
Format-Check bestanden, sdist und Wheel erfolgreich gebaut.
Zwei bestehende Dependency-Deprecation-Warnungen sind keine Testfehler.

Installation: Der Wheel-Eintrag hat 0755. Mit Host-umask 0002 erzeugte uv aus einem
alten Cache eine 0775-Datei; der neue Executor verweigert sie korrekt. Frische,
getestete Installation: umask 022, `uv --no-cache pip install --no-deps --link-mode copy`
in ein separates Ziel. Das Paket muss in einer vertrauenswürdig verwalteten,
nicht durch Task-Code beschreibbaren Installation liegen. Kein Runtime-chmod.

## Echter HufManager-Probelauf

Eigenständiger Live-Clone der registrierten URL, Source-Commit
`8c46bcdf07b326297b8a8d20f1b461cb61918137`; rein lokale Dokumentationsänderung und
Commit `70116efbd144ae535f3f0f11b0b51fed66421f7b` im entsorgten Test-Workspace.
Genau eine Datei im Commit, `docs/CODEX-AUTH-PROBE.md`; zwei Reviewer-Freigaben,
68 Audit-Events. Zweite abhängige Aufgabe: Push und Draft-PR ausschließlich Dry-run.
Zusätzlich echter Executor-Aufruf ohne Token: fail-closed, kein Git-Push-Prozess.

Der Provider war ausdrücklich **FakeProvider**, um Connector/Policy/Recovery
reproduzierbar zu prüfen; kein behaupteter Live-LLM-Nachweis. Der fachliche
Review ist weiterhin der vorhandene mechanische Reviewer. Clone macht den
Repository-Inhalt nach wie vor nicht automatisch zum Modellkontext.

Alle drei echten HufManager-Kommandos (`run_tests`, `run_build`, `run_lint`)
wurden an der neuen Sandbox-Grenze abgewiesen. **Keine Behauptung eines bestandenen
HufManager-Builds oder bestandener HufManager-Tests.** Keine Installation seiner
Dependencies, kein Deployment und kein Datenbank-/Supabase-Zugriff.
Der Git-/Dokumentationspfad bis zum Push ist belegt; der komplette Test-/Build-
Workflow vor Push ist nicht freigabefähig.

## Restrisiken, Bewertung und Merge-Empfehlung

1. Vor Wiederfreigabe von Projektcode: getrennte OS-Identität/Sandbox mit isoliertem
   Dateisystem, Prozesssicht und Credential-Installation; negative Ausbruchtests.
2. Harte Dienstabstürze müssen die gesamte Credential-Prozessgruppe zuverlässig
   beenden, z. B. über eine verifizierte Supervisor-/Cgroup-Grenze. Datenbank-
   Idempotenz allein reicht nicht. Ein solcher Deployment-Nachweis liegt nicht vor;
   der Review verändert bewusst keine laufenden Services.
3. Danach echte HufManager-Tests/Lint/Build in dieser Sandbox durchführen und die
   Merge-Entscheidung neu prüfen. Ein echter GitHub-Push ist für diesen Review
   nicht nötig und wurde nicht versucht; Token-/GitHub-Rechte bleiben ungeprüft.

Die Credential-Mechanik ist nach den Fixes deutlich enger und lokal nachgewiesen.
Die geforderte vollständige Security-/Reliability-Freigabe kann dennoch nicht
verantwortet werden. **MERGE READY = NO**, sowohl für den unveränderten PR als
auch für einen als vollständig freigegeben deklarierten Phase-3A-Workflow.

Offizielle Referenzen für die geprüften Git-Semantiken:
[Git-Konfiguration](https://git-scm.com/docs/git-config) (`remote.*.pushurl`,
HTTP-Redirects, Credential-Helper) und
[git push](https://git-scm.com/docs/git-push) (explizite Ref-Spezifikationen).

Rollback: Review-Commit nur zurücknehmen, wenn Push/PR und Projektcode-Ausführung
weiter deaktiviert bleiben. Ein Revert ist keine sichere operative Wiederfreigabe
des ursprünglichen Credential-Pfades.
