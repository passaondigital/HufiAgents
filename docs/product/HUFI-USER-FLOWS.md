# Hufi User Flows

**Status:** Ziel-Flows für die 8 Pflicht-Journeys aus dem V1.1-Produkt-QA-Auftrag. Jeder Flow ist bewusst auf das Minimum reduziert. Wo der aktuelle Stand (PR #13, live geprüft — siehe `PRODUCT-FLOW-FINDINGS.md`) vom Ziel abweicht, steht das explizit unter "Heute" — das ist keine Spekulation, sondern beobachtetes Verhalten.

---

## A) Login → Auftrag → Ergebnis

**Ziel:** In unter 30 Sekunden von "ich will etwas" zu einem lesbaren Ergebnis, ohne ein einziges technisches Wort zu sehen.

```
Login (Benutzername, Passwort)
  → Chat-Startbildschirm ("Was soll ich für dich erledigen?" + 5 Vorschlags-Chips)
  → Text eingeben oder Chip antippen
  → Senden
  → Hufi-Bubble: "Alles klar. Ich prüfe das mit meinem Team."
  → eine kurze Statuszeile, live aktualisiert
  → Ergebnis-Karte: Status-Pille + Text + "Bericht öffnen" / "Später"
```

**Heute:** Funktioniert exakt so. Stärkster Flow im ganzen Produkt (4 Interaktionen bis zum Auftrag, danach reines Warten, kein Jargon). Einziger Mangel: Ergebnistext enthält oft rohes Markdown vom Modell (`**fett**`), das nicht gerendert wird.

---

## B) Auftrag → zwei Agenten arbeiten → Review → Ergebnis

**Ziel:** Bei einem größeren Auftrag sieht der Nutzer, dass mehrere Hufis parallel arbeiten, bevor Hufi das Ergebnis zusammenfasst.

```
Auftrag senden
  → "2 Agenten arbeiten daran …"
  → "Hufi prüft das Ergebnis …" (Review)
  → Ergebnis-Karte
```

**Heute:** Nicht erreichbar. Eine normale Chat-Nachricht erzeugt serverseitig immer genau eine Aufgabe (kein `steps`-Array im Request), also erscheint nie "N Agenten arbeiten", nur "Ein Agent arbeitet daran …". Der Review-Schritt läuft synchron und ist für das 2,5-Sekunden-Polling praktisch unsichtbar. **Das ist eine Lücke zwischen Versprechen ("ich hole mir das passende Team") und Verhalten (immer 1 Agent) — siehe MUSS/SOLL-Liste in `PRODUCT-FLOW-FINDINGS.md`.**

---

## C) Neuer Hufi → Rolle → Agent verfügbar

**Ziel:** In unter 30 Sekunden einen neuen digitalen Mitarbeiter mit Name, Farbe und Zuständigkeit anlegen.

```
"+ Neuer Hufi"
  → Name, Avatar-Farbe, "Wofür soll dieser Hufi verantwortlich sein?"
  → "Hufi anlegen"
  → neuer Hufi erscheint in der Sidebar, sofort ansprechbar
```

**Heute:** Die ersten drei Schritte funktionieren und fühlen sich richtig an. Der letzte Schritt fehlt: das Backend kann noch keine Agenten dauerhaft anlegen (`POST /agents` kommt erst mit PR #12). Statt eines falschen Erfolgs zeigt das Modal ehrlich: *"Danke! Eigene Hufis können in dieser Version noch nicht dauerhaft angelegt werden – das kommt mit den dynamischen Agenten."* Das ist der richtige Umgang mit einer echten Backend-Lücke — kein Fake, keine stille Fehlermeldung. Verbesserungspotenzial: ein früher Hinweis im Modal selbst, bevor der Nutzer alle drei Felder ausgefüllt hat.

---

## D) Routine: "Mach das jeden Montag um 8 Uhr."

**Ziel:** Der Nutzer beschreibt einen wiederkehrenden Auftrag in einem Satz; Hufi bestätigt die Routine in Klartext oder sagt ehrlich, dass das noch nicht geht.

```
"Mach das jeden Montag um 8 Uhr."
  → Hufi: "Routine erstellt: [Kurzbeschreibung] — jeden Montag, 08:00 Uhr."
     ODER (solange Routinen fehlen):
  → Hufi: "Wiederkehrende Aufträge kann ich in dieser Version noch nicht — ich lege das als einmaligen Auftrag an. Möchtest du das?"
```

**Heute:** Weder noch. Der Text wird stillschweigend als normaler Einmal-Auftrag ausgeführt — keine Erkennung, keine Rückfrage, keine Klarstellung. Die ehrliche "Bald verfügbar"-Botschaft existiert bereits (im Agenten-Detailpanel, Abschnitt "Routinen"), ist aber vom Chat aus nicht erreichbar. **Das ist der größte MUSS-Fund des gesamten Audits** — die App täuscht Verständnis vor, das nicht existiert. Siehe `PRODUCT-FLOW-FINDINGS.md`, MUSS Punkt 1, für einen konkreten, backend-freien Fix-Vorschlag (Schlüsselwort-Heuristik im Chat).

---

## E) Approval: Hufi möchte einen PR erstellen

**Ziel:** Hufi stoppt sichtbar, erklärt in einem Satz was/warum/Auswirkung/rückgängig-machbar, und wartet auf eine bewusste Entscheidung.

```
Auftrag mit riskanter Aktion (z. B. "Veröffentliche die Korrektur auf GitHub")
  → Karte: "Hufi möchte eine Änderung veröffentlichen."
     Projekt: HufManager
     Warum: "Die getestete Korrektur soll auf GitHub bereitgestellt werden."
     Auswirkung: "Ein neuer Branch und Pull Request werden erstellt."
     Rückgängig: "Ja."
     [ Zulassen ]  [ Ablehnen ]
  → nach Entscheidung: "Freigegeben. Hufi macht weiter." / "Abgelehnt. Hufi sucht einen anderen Weg."
```

**Heute:** Die Karte selbst ist bereits fertig und gut gebaut (`chat.js` `renderApprovalCard()`) — Klartext-Rahmung, Risikocode nur hinter "Details", zwei klare Buttons, Klartext-Rückmeldung. Sie ist nur **strukturell unerreichbar**: der Chat sendet jede Mission fest mit `risk_ceiling: "R1"`, das ist zu niedrig, um je eine Freigabe auszulösen. Ein absichtlich riskant formulierter Testauftrag lief einfach durch und wurde von der App als grün-"Fertig" markiert — obwohl das Modell den Auftrag intern verweigert hatte. Zwei Dinge müssen sich ändern, bevor dieser Flow erlebbar wird: (1) die Chat-Ceiling darf nicht dauerhaft bei R1 hart verdrahtet bleiben, (2) eine interne Modell-Verweigerung muss als eigener Status erkennbar sein, nicht als Erfolg. Siehe MUSS Punkte 2 und 3 in `PRODUCT-FLOW-FINDINGS.md`.

---

## F) Fehler → Retry → Recovery

**Ziel:** Ein Fehlschlag ist klar erkennbar UND bietet sofort einen Weg zurück ("Nochmal versuchen"), ohne dass der Nutzer den Text neu tippen muss.

```
Auftrag scheitert
  → Ergebnis-Karte: rote Pille "Nicht geschafft" + kurzer, verständlicher Grund
  → [ Nochmal versuchen ]  [ Bericht öffnen ]  [ Später ]
```

**Heute:** Die "Nicht geschafft"-Karte selbst existiert und sieht klar aus (rote Pille, Fallback-Text). Es fehlt der "Nochmal versuchen"-Button — der Nutzer kann nur den Audit-Trail lesen oder wegklicken; um es erneut zu probieren, muss der komplette Text neu eingetippt werden. Zusätzlich ist `failed` über den normalen Chat praktisch nicht erreichbar (das lokale Modell antwortet fast immer irgendetwas, selbst auf Unsinnseingaben) — das ist eher ein Backend-/Review-Strenge-Thema als ein reines UI-Thema. SOLL-Punkt 4 in `PRODUCT-FLOW-FINDINGS.md`.

---

## G) Mobile Bedienung

**Ziel:** Flow A fühlt sich auf 390px genauso schnell und klar an wie auf dem Desktop.

```
(identisch zu Flow A, plus:)
  ☰ öffnet die Sidebar als Overlay von links
  ⓘ öffnet den Kontext als Overlay von rechts
  Eingabeleiste unten bleibt immer erreichbar, 40px-Touch-Ziele
```

**Heute:** Funktioniert bereits sehr gut — kein mobilspezifischer Reibungspunkt im Kern-Flow, alle Touch-Ziele ausreichend groß, keine Layoutprobleme. Ein kleiner, aber echter Sprachbruch: nach Agentenauswahl zeigen Topbar-Titel und die "Chat mit …"-Systemnotiz die rohe Backend-ID ("builder") statt des sauber formatierten Namens ("Builder"), der in der Sidebar direkt daneben bereits korrekt angezeigt wird. SOLL-Punkt 6 in `PRODUCT-FLOW-FINDINGS.md` — ein Ein-Zeilen-Fix (bestehende `humanizeId()`-Funktion wiederverwenden statt der rohen ID).

---

## H) Details / Expertenmodus

**Ziel:** Technische Wahrheit ist für alle da, die sie wollen — aber nie im Weg, und immer leicht wieder verlassbar.

```
Agent in Sidebar wählen
  → rechtes Panel: Agentenansicht
  → Button "Details / System"
  → Rohdaten (Provider, Risikoklassen, IDs, Audit-JSON) + Link zum vollständigen technischen Dashboard
  → zurück zur normalen Ansicht
```

**Heute:** Der Weg hinein ist klar, der Hinweistext oben im System-View ("Für den normalen Hufi-Alltag nicht nötig") ist genau richtig, kein Jargon leckt in den Normalmodus. Auf Tablet/Mobile ist der Rückweg eindeutig (✕-Button schließt das Panel). Auf Desktop (≥1100px) ist das Panel eine dauerhafte dritte Spalte ohne ✕-Button und ohne einen "Zurück zur Agentenansicht"-Button innerhalb des System-Views selbst — der einzige Rückweg ist, erneut einen Agenten in der Sidebar anzuklicken. Kleiner, aber real: SOLL-Punkt 8 in `PRODUCT-FLOW-FINDINGS.md`.

---

## Übergreifend

Der vollständige Befund pro Flow (Klick-Zahlen, Jargon-Lecks, stille Fehlzustände, echte Dead-Ends) steht in `docs/product/PRODUCT-FLOW-FINDINGS.md` — dieses Dokument zeigt bewusst nur das *Ziel* pro Flow plus die *wichtigste* Abweichung, nicht jedes Detail doppelt.
