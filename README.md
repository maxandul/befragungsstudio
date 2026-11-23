# Befragungsstudio 0.1.26

Erste lokale Umsetzung für Befragungsdaten. Charts mit lokal mitgeliefertem Chart.js 4.4.8; Matplotlib wird nicht benötigt. Python 3.11 oder neuer mit Python
Launcher unter Windows. Alle Oberflächendateien werden mitgeliefert.

## Start

1. ZIP vollständig entpacken.
2. Einmalig `INSTALL.bat` ausführen. Die Installation benötigt Paketdownloadzugriff.
3. `START.bat` öffnen. Die App startet unter http://127.0.0.1:5051.
4. Das Konsolenfenster geöffnet lassen. Strg+C beendet die App.

Alternativ: `python -m pip install -r requirements.txt`, danach
`python app.py --open-browser`. Ein anderer Port ist mit `--port 5061` möglich.
Der Server bindet ausschliesslich an 127.0.0.1. Node.js ist nicht erforderlich.

## Erster Durchlauf

1. Bereich Echonovum oder Andere Daten/Tools öffnen, Befragung anlegen.
2. CSV/XLSX laden. Bei Excel kann ein Blattname ausgewählt werden.
3. Spaltenzuordnung prüfen. Echonovum erhält Vorschläge für Long-Format.
4. Fehlende Wellen über Zeiträume ergänzen. Beispiel für AWI:
   `Puls AWI 2024 | 01.01.2024 | 31.12.2024`.
   Befüllte Wellenfelder haben Vorrang vor Zeiträumen; ein fester Name überschreibt beides.
5. Vorschau prüfen und Daten übernehmen.
6. Unter Fragen Berichtsbezeichnungen, gemeinsame Fragenkennungen, Skalen,
   Zustimmungsgrenzen und fehlende Werte prüfen. Bei Skala 1–10 ist die
   Standardgrenze 4 zu ändern. Mehrfachauswahl benötigt vollständige Optionen.
7. Unter Segmentierung je Welle Quellspalten den frei benennbaren Merkmalen zuordnen.
   Wertzuordnungen vereinheitlichen abweichende Namen.
8. Unter Grundmengen Gesamtzahlen sowie bei Bedarf die Zahlen einzelner Einheiten
   hinterlegen. Es sind vollständige Zahlen inklusive Untereinheiten; keine Summierung.
9. Ergebnisse prüfen. Merkmal und Einheit filtern, Wellen und Mindestfallzahl wählen.
   HTML-Bericht oder PNG-ZIP herunterladen.

## Daten und Sicherung

Daten und gespeicherte Regeln liegen im Ordner `instance`. Zur Sicherung die App
beenden und diesen Ordner vollständig kopieren. Beim Update bleibt er erhalten.
Die SQLite-Datei enthält Originalantworten und Rohwerte einschliesslich Freitexten.
Das Auslieferungspaket enthält keine Befragungs- oder Personaldaten.
Die App führt keine Netzwerkaufrufe aus. Berichte enthalten Chart.js, die berechneten Ergebnisdaten und den Exportcode vollständig eingebettet;
Empfänger benötigen keine laufende App und keinen Internetzugang.

Antworten werden über Befragung + Welle + Fragebogenkennung + Quellfrage
wiedererkannt. Erneutes Importieren aktualisiert vorhandene Antworten und ergänzt
neue. Aus dem Export entfernte Antworten werden nicht automatisch gelöscht.
Ohne ID im breiten Format ist nur dieselbe unveränderte Datei wiedererkennbar.
Für aktualisierte Exporte ist eine stabile ID erforderlich.

## Umfang und nächste Etappen

Dies ist ein erster funktionsfähiger Durchlauf, noch keine vollständige Umsetzung
aller besprochenen Funktionen. Implementiert sind zwei Importwege, gespeicherte
Konfiguration, Fragen- und Wertzuordnung, manuelle Grundmengen, Mittelwerte,
Zustimmungsanteile, Auswahlhäufigkeiten und HTML/PNG-Exporte. Im Bericht kann bei Skalen zwischen Mittelwert und Zustimmungsanteil gewechselt werden.

Noch offen: stabile OE-Identitäten und historische Zuordnungsbereinigung,
Grundmengen-Tabellenimport, Berichtspakete für ganze Hierarchiezweige,
gestapelte Antwortverteilungen und Top-2-Zeitdiagramme, Engagement-Index,
Freitextprüfung und -freigabe, Optionsspalten als gemeinsame Multiple-Choice-Frage,
Vorlagenverwaltung, Profilgenerierung und Echonovum-Upload.

Das OE-Verzeichnis kann bereits importiert werden. Es ändert keine historischen
Antwortzuordnungen. Diese werden vorerst über die Segmentregeln gepflegt.
Die Berichtsauswahl erfolgt über den vollständigen Organisationspfad inklusive unterstellter Einheiten. Unter «Organisation» lassen sich Einträge und datierte Verzeichnisstände pflegen.
Skalencharts zeigen Mittelwerte oder Zustimmungsanteile über die Wellen. Auswahlcharts zeigen die letzte
Welle nach dem frühesten Antwortdatum. Rücklaufquoten werden als Tabelle gezeigt.
Fragen werden zunächst anhand ihrer Quell-ID angelegt. Änderungen des Wortlauts
bei gleicher ID werden noch nicht automatisch als neue Version angezeigt.

Pulsimporte enthalten gemäss vereinbartem Exportverfahren nur abgeschlossene
Feedbacks. Andere Tabellen sind vor dem Import auf die gewünschte Teilnahmebasis
zu beschränken. Mindestfallzahlen gelten je Frage; Teilnahmezahlen sind sichtbar.
Mehrfachauswahl mit unklaren Resten wird als ungeklärt ausgewiesen und nicht
teilweise gezählt. Wellen werden nach ihrem frühesten Antwortdatum sortiert; ohne Datumsangaben
werden sie ans Ende gestellt und nach Namen sortiert.

## Tests

`python -m unittest discover -s tests -v`
Die Tests arbeiten ausschliesslich mit synthetischen Daten und temporären Datenbanken.

## Update von 0.1

Matplotlib ist vollständig entfernt. Chart.js ist als lokale JavaScript-Datei
mitgeliefert (MIT-Lizenz unter static/vendor). Kein npm, kein CDN-Aufruf beim
Betrieb und kein zusätzliches Python-Chartpaket sind nötig. Bereits vorhandene
Python-Abhängigkeiten wie Flask, Waitress, pandas und openpyxl bleiben erforderlich.
Wenn diese fehlen, kann die App ohne deren Installation weiterhin nicht starten.

Die App beenden und die Programmdateien aus dem ZIP ersetzen; den bestehenden
Ordner instance mit Daten und Konfiguration beibehalten. Neue Datenbankfelder werden beim Start automatisch ergänzt. Nach dem Update START.bat ausführen. Eine erneute Installation nur
wegen des Chartwechsels ist nicht nötig.

PNGs werden im Browser erstellt, mit weissem Hintergrund, Berichtskontext und
aktueller Metrik. Grössen: 1920 × 1080, 960 × 1080 und 1200 × 900 Pixel. Der
ZIP-Export bündelt alle drei Formate je sichtbarem Chart. Ein vorhandener Einstieg
«Alle PNGs als ZIP» öffnet dafür den Bericht und startet die Erstellung.
Downloads setzen einen Browser mit aktiviertem JavaScript und erlaubten Downloads
voraus. Die Tabellen bleiben auch ohne JavaScript lesbar.

Die automatisierten Tests prüfen Berechnung, Import, eingebettete Berichte,
Exportkonfiguration und ZIP-Struktur. Der optionale Node-Test verwendet ein
Canvas-Testdouble und ist kein Nachweis für die tatsächliche Browserdarstellung.

## Startdiagnose ab 0.1.2

START.bat zeigt sofort den Programmordner und den Aufruf von Python. run_web.py
zeigt anschliessend das Laden jedes Pakets, die Datenbankinitialisierung und das
Belegen des lokalen Ports. Die Browserseite öffnet erst nach erfolgreichem
Serverstart. Ohne automatische Browseröffnung die angezeigte Adresse manuell
öffnen. Das Fenster bleibt auch nach einem Fehler offen.

Diagnoseprotokoll: instance/start.log. Bei Startproblemen die letzte sichtbare
Meldung und gegebenenfalls das Protokoll weitergeben. Wenn die Ausgabe nach
«Starte Python» stehenbleibt, wurde der Python-Code noch nicht erreicht; eine
Ursache kann dann ausserhalb der App liegen. Bei einem Lade-Schritt ist das
betroffene Paket sichtbar. Bei Portkonflikten wird der Fehler angezeigt.
Der Fix benötigt keine zusätzlichen Pakete. Die Batchdatei selbst wurde hier
nicht unter Windows ausgeführt; die Python-Startlogik ist automatisiert geprüft.

## Portkorrektur

Standardport ist 5051. Port 5060 wird von Chromium-basierten Browsern als unsicherer Port blockiert (ERR_UNSAFE_PORT). Keine Browser-Sicherheitsausnahme erforderlich.

## Verständlichere Importzuordnung ab 0.1.3

Teilnahme-ID ersetzt die missverständliche Fragebogenkennung. Bei Echonovum ist
Feedback ID die Kennung einer Teilnahme, Survey ID dagegen die Befragung.
Long bedeutet eine Zeile je Frage und Teilnahme; Breit eine Zeile je Teilnahme.

Die Quelle der Erhebungszuordnung wird ausdrücklich gewählt:
- Jahr und Monat des Antwortdatums (neuer Echonovum-Standard, z. B. 2026-06).
- Eigene Erhebungszeiträume, als Tabelle mit Name, Von und Bis.
- Eine Spalte, z. B. Befragung (object).
- Ein fester Name für die ganze Datei.

Datumsmethoden ignorieren das Befragungsattribut. Monat bedeutet Gruppierung aller
Zeilen nach Jahr und Monat, keinen Ausschluss anderer Monate. Für übergreifende
Durchläufe (etwa Juni/Juli) einen gemeinsamen Zeitraum verwenden. Nicht zugeordnete
Antworten verhindern die Übernahme und werden nicht still ausgeschlossen.
Gespeicherte alte Einrichtungen verwenden zunächst die bisherige Regel, bis die
Methode ausdrücklich geändert wird. Bereits importierte Wellen werden nicht
rückwirkend umbenannt oder zusammengeführt. Bei bereits importierten Daten die
Wellendefinition vor einem weiteren Import beibehalten; eine Umgruppierung alter
Importe ist in dieser Etappe noch nicht implementiert.

## Fragen gemeinsam bearbeiten ab 0.1.4

Die Fragenverwaltung zeigt eine Karte pro gemeinsamer Berichtsfrage. Alle Änderungen
lassen sich mit «Alle Änderungen speichern» gesammelt speichern. Mit aktiviertem
JavaScript geschieht das ohne Seitenwechsel. Bei einer Verknüpfung wird die Liste
aktualisiert und die Scrollposition wiederhergestellt. Suche reduziert die sichtbaren
Karten, ohne Änderungen an ausgeblendeten Fragen zu verwerfen.

Fragen markieren, Zielfrage auswählen, «Markierte Fragen verknüpfen» ausführen.
Die Zielfrage bestimmt Berichtsbezeichnung und Einstellungen der gemeinsamen Frage.
Gleicher Fragetyp und gleiche Skala/Zustimmungsgrenze sind Voraussetzung. Die fachliche
Gleichwertigkeit ist anhand der angezeigten Originaltexte zu prüfen. Gleiche Bedeutung
wird nicht automatisch aus ähnlichen Texten abgeleitet. Enthält eine Teilnahme mehrere
der Quellfragen, wird die Verknüpfung vor dem Speichern verhindert. Quell-IDs, Wellen
und Rohantworten bleiben erhalten. Einzelne Quellfragen können wieder getrennt werden.

«Thema» heisst jetzt «Berichtsabschnitt (optional)» und dient der thematischen
Anordnung, beispielsweise Führung oder Zusammenarbeit. Es berechnet keinen Index.

Fehlende Antwortwerte werden zentral pro Befragung gepflegt und von allen Fragen
ohne Ausnahme geerbt, auch bei zukünftigen Importen. Eigene Listen sind nur bei
aktivierter Ausnahme nötig. Beim Update bleiben abweichende alte Fragenlisten als
Ausnahme erhalten; unveränderte Standardlisten verwenden die gemeinsame Einstellung.
Das Update ergänzt die Datenbank automatisch, ohne Neuimport oder Paketinstallation.
Vor dem Update die App beenden und den Ordner instance sichern.

## Speichern und Sitzungen ab 0.1.5

Der AJAX-Speicheraufruf liest die Zieladresse nun ausdrücklich über getAttribute.
Buttons mit dem Namen action können dadurch nicht mehr die Formularadresse
überdecken und einen Aufruf an eine falsche URL verursachen.

Die App verwendet einen eigenen Session-Cookie-Namen, damit andere localhost-Apps
mit dem Standardnamen session sie nicht überschreiben. Bei abgelaufenem CSRF-Token
wird die Sitzung einmal ohne Seitenwechsel erneuert und nur der zuvor abgewiesene
Aufruf erneut gesendet. Andere Fehler werden nicht automatisch wiederholt.
Validierungsfehler, HTTP-Fehler und interne Serverfehler liefern bei AJAX-Anfragen
lesbare JSON-Meldungen. Interne Fehler erhalten eine Kennung und ein Protokoll in
instance/app.log. Formularwerte werden dabei nicht gezielt protokolliert.

Update: App beenden, Programmdateien ersetzen, .venv und instance beibehalten,
START.bat ausführen und die Browserseite neu laden. Keine neuen Pakete nötig.
Noch nicht gespeicherte Änderungen vor dem Neuladen separat sichern.

## Datenvorschau für Segmentierungen ab 0.1.6

Unter Segmentierung zuerst eine Erhebung auswählen. Typische Organisations- und
Segmentspalten werden mit Anzahl befüllter Teilnahmen, verschiedenen Werten und
Beispielen angezeigt. Mit «Auch andere Datenfelder anzeigen» werden weitere
befüllte Spalten sichtbar. Eine Suche kann Spaltennamen und Beispielwerte filtern.
Nach Auswahl einer Spalte zeigt die Vorschau alle Werte samt Teilnahmezahlen,
fehlende Angaben und widersprüchliche Werte innerhalb einer Teilnahme.

Nach Speichern der Spaltenzuordnung können vorhandene Werte für eine Namensregel
ausgewählt werden. Die Vorschau zeigt Originalwert, aktuellen Berichtsnamen und
Berichtsnamen nach der vorgeschlagenen Änderung, zusätzlich die resultierende
Verteilung. Die Vorschau verwendet dieselben Prioritäten wie die Auswertung und
speichert selbst keine Regeln. Die gewählte Erhebung gilt für beide Formulare.
Alle Erhebungen gemeinsam zählen Teilnahmen über ihre Kombination aus Welle und
Feedback-ID. Antwortzeilen werden nicht mehrfach als Teilnahmen gezählt.
Bei widersprüchlichen Werten kann die Summe über die Werte grösser als die Zahl
der Teilnahmen sein; die Vorschau weist solche Konflikte ausdrücklich aus.

Namensregeln vergleichen jeweils den ursprünglichen Merkmalswert. Eine speziellere
Regel überschreibt eine allgemeine Regel; Umbenennungen werden nicht als Kette
aufeinander angewendet.

## Merkmalauswahl ab 0.1.7

Merkmale werden über ein vollständiges Dropdown ausgewählt. Amt, Bereich,
Abteilung, RAV Gruppe, RAV und Team sind immer sichtbar. Gespeicherte eigene
Merkmale ergänzen die Liste; gleiche Namen erscheinen nur einmal, auch wenn sie
für mehrere Erhebungen zugeordnet sind. Über «Eigenes Merkmal …» wird ein eigener
Name erfasst, der nach dem Speichern ebenfalls in der Liste erscheint.
Beim Wechsel von Merkmal oder Erhebung wird die bereits gespeicherte Quellspalte
für diese Kombination angezeigt. Fehlt eine Regel, bleibt die Quellspalte leer,
damit nicht versehentlich die zuvor ausgewählte Spalte zugeordnet wird.

## Pulsreihen automatisch vorbereiten (Version 0.1.8)

1. App beenden und die aktualisierten Programmdateien übernehmen. `instance` und `.venv` behalten; keine Neuinstallation erforderlich.
2. Die drei ursprünglichen Puls-CSV-Exporte in einen lokalen Ordner legen. Optional `OE_Liste.xlsx` dazulegen. Es dürfen auch nur einzelne Pulsreihen im Ordner liegen.
3. `SEED_PULS.bat` ausführen und diesen Ordner angeben. Das Skript erkennt AWI, AFA und GS anhand der Survey ID. Alternativ zunächst `SEED_PULS.bat --dry-run` für eine Vorschau ohne Datenbankänderung.
4. `instance/seed_puls_report.txt` lesen, dann `START.bat` ausführen.

Vor Änderungen wird eine SQLite-Sicherung unter `instance/backups` angelegt. Die Einrichtung ergänzt vorhandene Projekte und Daten, übernimmt eindeutige bestehende Wellenbezeichnungen und lässt bereits gespeicherte Antworten sowie eigene Berichtstitel erhalten. Bei widersprüchlicher Wellenzuordnung bricht sie ab. Ein erneuter Lauf erzeugt keine doppelten Antworten. Die drei gelieferten Exporte enthalten gemäss Vorgabe ausschliesslich abgeschlossene Feedbacks; ein Statusfilter wird mangels Statusfeld nicht erfunden.

Vorbereitet werden:

- AWI: Juli 2024, Januar 2025, Juni/Juli 2025, Januar 2026 und Juni/Juli 2026. AFA: Oktober/November 2024, 2025 und 2026. GS: September 2024 und August 2026. Diese Zeitfenster sind Vorlagen für die vorliegenden Exporte; spätere Wellen müssen zusätzlich erfasst werden. Ein bestehendes Importprofil wird erhalten.
- Berichtstitel ohne `(PAFA)`, `(PAWI)`, `(PGS)` oder `(PAFM)`, ohne unsichtbare Leerzeichen. GS: «Initiative» wird zu «Leistungsbereitschaft», der falsche Titel «Führungskultur im AWI» zu «Führungskultur im GS».
- 15 geprüfte AFA-Fragenpaare und ein GS-Fragenpaar mit unterschiedlichen IDs. Das Skript kontrolliert zusätzlich Wortlaut, gleiche Einstellungen und doppelte Teilnahmen. Manuell konfigurierte Gruppen werden erhalten. Ähnliche Fragen mit unterschiedlicher Bedeutung bleiben getrennt, insbesondere Feedback durch Vorgesetzte und Feedbackkultur im Team. «Detail BGM» mit den IDs 144807/145766 bleibt wegen unterschiedlichem Inhalt getrennt.
- AWI Januar 2025: sechs Zusatzfragen werden nur für diese Welle ausgeschlossen, wenn alle sechs tatsächlich nur derselben einzelnen Teilnahme zugeordnet sind. Alle Rohantworten, die übrigen Antworten und der Rücklauf bleiben erhalten. Keine pauschale Unterdrückung aller kleinen Fallzahlen.
- Eindeutig benannte Segmentspalten werden als Ausgangsbasis ergänzt. Eine mitgelieferte OE-Liste wird als Referenz ergänzt. AI/AZ werden wegen der Reorganisation getrennt erhalten.

**Noch zu prüfen:** Historische HS-/Hierarchiespalten sind nicht durchgehend identische Ebenen. Deshalb wird HS3 nicht pauschal als Abteilung oder RAV Gruppe gesetzt. Widersprüchliche historische OE-Zuordnungen bleiben offen; die Einrichtung liefert noch keine bereinigte Zuordnung pro Feedback ID für den Anbieter. Auch die vollständigen Optionskataloge für Mehrfachauswahlfragen fehlen im Antwortexport und müssen aus dem Fragebogen ergänzt werden. Vorher erscheinen diese Antworten als nicht auswertbar. Grundmengen für Rücklaufquoten werden nicht aus der Zahl der Antworten geschätzt.

Ausschlüsse lassen sich unter **Fragen → Quellfragen und Erhebungen vergleichen** pro Quell-ID und Welle setzen oder wieder aufheben. «Alle Änderungen speichern» übernimmt sie gemeinsam mit den übrigen Einstellungen. Beim erneuten Seed-Lauf werden einmal bewusst aufgehobene Januar-Ausschlüsse nicht wieder gesetzt.

CLI: `python seed_puls.py --input-dir "C:\Pfad\Exporte" --dry-run`; ohne `--dry-run` werden die Änderungen gespeichert. Für einen abweichenden Datenordner gibt es `--instance`. Keine neuen Python-Pakete erforderlich.


## Puls-Neustart statt vorhandene Einrichtung ergänzen (Version 0.1.9)

Die separat bereitgestellte vollständige Fragenliste enthält 159 Berichtsfragen mit stabilen Kennungen, Quell-IDs, Typen, Wellen und sämtlichen Wortlautvarianten aus den vorliegenden Exporten. Die bestätigten Berichtsausschlüsse sind im Seed hinterlegt: 29 AWI- und 8 AFA-Berichtsfragen werden für alle Wellen ausgeschaltet. Zusätzlich bleiben die sechs AWI-Zusatzfragen im Januar 2025 wellenspezifisch ausgeschlossen. Die Rohantworten und die Teilnahmezählung bleiben erhalten.

Für einen vollständigen Neustart die App beenden und **`SEED_PULS_NEUSTART.bat`** starten. Den Ordner mit den ursprünglichen Puls-CSV-Dateien angeben. Das Skript sichert die Datenbank, entfernt die bisherigen Projekte samt Antworten, Importprofilen, Grundmengen und Frage-/Segmentierungseinstellungen für die mitgelieferten Pulsreihen und richtet sie anschliessend frisch ein. Es ersetzt keine anderen Projekte und löscht nicht das gemeinsame OE-Verzeichnis. Alte Daten und Einstellungen bleiben in der Sicherung erhalten. Es findet keine Löschung auf deinem Rechner statt, bevor du das Skript dort ausführst.

Die Projektzuordnung erfolgt über die Survey ID in den Daten, auch bei abweichenden Projektnamen. Leere Echonovum-Projekte mit dem Namen «Puls AWI», «Puls AFA», «Puls AWA» oder «Puls GS» werden nur entfernt, wenn der passende Export mitgeliefert wird. Enthält ein Projekt zusätzlich andere Befragungen, bricht der Neustart ab. Zurücksetzen und Neuimport laufen in einer gemeinsamen Transaktion: Schlägt die Neueinrichtung fehl, werden auch die Löschungen zurückgerollt.

Vorschau ohne Änderung: `SEED_PULS_NEUSTART.bat --dry-run`. CLI: `python seed_puls.py --reset-puls --input-dir "C:\Pfad\Exporte"`. `SEED_PULS.bat` bleibt für das bisherige Ergänzen erhalten.

Frisch angelegte Wellen heissen nun **AWI: 2024-07, 2025-01, 2025-07, 2026-01, 2026-07** und **AFA: 2024-10, 2025-10, 2026-10**. Die Sommerwellen umfassen weiterhin Juni/Juli und die AFA-Wellen Oktober/November. GS: 2024-09 und 2026-08. Beim blossen Ergänzen werden vorhandene eindeutige Wellenbezeichnungen weiterhin übernommen. Neue zukünftige Wellen müssen im Import einmal mit Namen und Zeitraum ergänzt werden.


## AFA-Grundmengen Oktober 2026 (Version 0.1.10)

`EXPORT_Sendout.XLSX` und `OE_Liste.xlsx` zu den Puls-CSV-Exporten in denselben lokalen Ordner legen. Nach dem App-Update `SEED_PULS.bat` ausführen, um die Grundmengen zu einer bereits eingerichteten AFA-Befragung zu ergänzen. Ein Neustart der Einrichtung ist dafür nicht erforderlich. Bei einer vollständigen Neueinrichtung übernimmt auch `SEED_PULS_NEUSTART.bat` diese Grundmengen. Beide Skripte unterstützen weiterhin `--dry-run` und legen vor dem Speichern eine Datenbanksicherung an.

Die Mitarbeitendenliste enthält eine Spalte mit einem OE-Kürzel pro Person. Jede Zeile zählt eine Person; gleiche Kürzel werden nicht dedupliziert. Die Zuordnung zum Amt erfolgt über das Blatt «OE Liste» des OE-Verzeichnisses, unabhängig vom Spaltentitel der Mitarbeitendenliste. Es werden ausschliesslich Grundmengen für das AFA und die Erhebung Oktober/November 2026 gespeichert. Bestehende eindeutige Wellenbezeichnungen werden übernommen. Andere Ämter und frühere AFA-Wellen erhalten keine Grundmengen aus diesem Export.

Gespeichert werden die Gesamtgrundmenge, Amt, Bereiche, Abteilungen, RAV-Gruppen, RAVs und Teams gemäss den Zuordnungsspalten der OE-Liste. Jede Person zählt auf jeder zugeordneten Ebene genau einmal. Übergeordnete Werte enthalten die über ihre Pfadmerkmale zugehörigen Untereinheiten. Personen mit leerem Bereich bleiben in der Gesamtgrundmenge enthalten, ohne einem Bereich zugeschlagen zu werden. Referenzeinheiten ohne zugeordnete Mitarbeitende werden mit null gespeichert. Direkte OE-Besetzungen werden separat für alle AFA-Kürzel des Verzeichnisses gespeichert, damit direkte Besetzung und Grundmengen inklusive Untereinheiten unterscheidbar bleiben.

Unter «Grundmengen» ist die gespeicherte Mitarbeitendenbasis mit den direkten Besetzungen je OE-Kürzel einsehbar. Ein Quellen- und OE-Verzeichnis-Fingerabdruck dokumentiert die Basis. Die Originaldateien und die berechneten Ist-Zahlen werden nicht ins öffentliche Repository übernommen.

Unbekannte oder mehrdeutige OE-Kürzel, fehlende Pflichtspalten und eine auf mehrere Wellen verteilte AFA-Erhebung führen zum Abbruch statt zu einer unvollständigen Grundmenge. Abweichende bereits manuell hinterlegte Grundmengen werden beim Ergänzen beibehalten und im Seed-Protokoll zur Prüfung ausgewiesen. Bei bewusstem vollständigem Neustart werden sie aus den Dateien neu aufgebaut. Die Stammdateien müssen nach wie vor die tatsächlich eingeladenen Personen abbilden; das Skript erfindet keine weiteren Teilnahmefilter. Historische Segmentkonflikte in den Befragungsdaten werden durch den Grundmengenimport nicht umgedeutet.

Für die zukünftige Profilerstellung steht die wiederverwendbare Berechnung in `population.py` bereit. Die Erstellung der Profile samt automatischer Grundmengensicherung im UI ist noch nicht umgesetzt. Keine zusätzlichen Python-Pakete erforderlich.

## Thematische Berichte für Besprechungen

Die Berichte zeigen pro Thema gemeinsame Punktdiagramme für Zeitverlauf und aktuelle Untereinheiten. Einzelfragen stehen darunter aufklappbar zur Verfügung. Bis zu fünf Fragen gleicher Skala werden auf einer Übersicht zusammengefasst; eine Übersicht berechnet keinen Summenscore. Mittelwert und Zustimmung lassen sich gemeinsam umschalten. Fehlende aktuelle Werte bleiben leer.

Themenverlauf und Themenvergleich können als PNG für eine ganze PPT-Folie heruntergeladen werden. Die Themen-PNGs stehen zusätzlich im vollständigen PNG-ZIP und enthalten Fragewortlaut, OE, Wellen und gültige n. Redaktionelle Texte und gegebenenfalls freigegebene vollständige Textantworten ergänzen die Themen im HTML-Bericht. Einzelheiten und Grenzen: `BERICHTE.md`.

Pro Themenzusammenfassung können passende Textbelege ausgewählt werden. «Berichtstext und Belege speichern» speichert beides je OE und Welle. Die separate Option «Ausgewählte Textbelege im Bericht anzeigen» nimmt nur die gewählten Aussagen auf. Geänderte, ausgeschlossene oder unter der Mindestfallzahl liegende Belege werden nicht ausgegeben und in der Redaktion zur Prüfung angezeigt. Das Update ergänzt die Referenztabelle automatisch; kein Neuimport und keine neuen Pakete erforderlich.

Aktuelle Themenübersichten zeigen zusätzlich die direkt übergeordnete OE und das klar benannte Gesamtergebnis als getrennt schaltbare Referenzen. Das funktioniert auch ohne Untereinheiten. Ausgeblendete Legendenreihen bleiben beim Wechsel von Mittelwert/Zustimmung und im PNG-/ZIP-Export ausgeblendet.

## Fragenreihenfolge und Berichtsdetails (Version 0.1.11)

Unter «Fragen» legt «Reihenfolge im Berichtsabschnitt» die Reihenfolge fest: kleinere ganze Zahlen zuerst, etwa 10, 20, 30. Gleiche Zahlen werden nach Fragetitel sortiert. «Alle Änderungen speichern» übernimmt die Reihenfolge für den HTML-Bericht, die Themenübersichten und die PNGs.

Textfragen können einer zugehörigen quantitativen Frage zugeordnet werden. Sie folgen dann deren Berichtsabschnitt und erscheinen bei aktivierten vollständigen Textantworten unter der Frage innerhalb von «Einzelfragen und Details». Ohne Zuordnung verwenden sie ihren eigenen Abschnitt und stehen dort in den Details. Die bekannten AFA-Zuordnungen werden beim Update ergänzt. Entwicklungsmöglichkeiten und die zugehörige Textfrage wechseln aus dem bisherigen Standardabschnitt zu «Arbeitsbedingungen und Gesundheit».

BGM2 erhält für Puls AFA den geprüften Optionskatalog mit beiden vorliegenden Wortlautversionen. Die vollständige Option «Nein, aktuell wirkt sich kein Aspekt negativ auf meine Gesundheit aus» und Kommas innerhalb von Optionen bleiben zusammen. Vorhandene eigene Optionskataloge bleiben erhalten. Neue, nicht im Katalog enthaltene Inhalte bleiben ungeklärt; andere Multiple-Choice-Fragen erhalten keinen geratenen Optionskatalog.

Die bisherigen doppelten n-Angaben unter den Einzelcharts entfallen. Stattdessen steht dort die Anzahl ohne auswertbare Antwort, zusätzlich zu gegebenenfalls ungeklärten Antworten. «Ohne auswertbare Antwort» schliesst leere/als fehlend definierte Werte und Teilnahmen ohne Eintrag zur Frage ein. Nicht beantwortet und nicht angezeigt lassen sich aus dem Export nicht zuverlässig unterscheiden. Die Antwortbasis von Auswahlcharts wird separat ausgewiesen.

Heruntergeladene HTML-Berichte enthalten keinen Link zur App; in der Vorschau bleibt er verfügbar. Die zusätzliche Produktzeile entfällt. Zustimmungsanteile werden als Antworten 4 und 5 der gültigen Antworten erklärt; abweichende Grenzen werden weiterhin beachtet.

Update: App beenden, `instance` sichern, Programmdateien aktualisieren und `START.bat` starten. Kein Neuimport und kein erneuter Seed-Lauf erforderlich. Die einmaligen AFA-Anpassungen respektieren eigene Abschnittszuordnungen und bereits gespeicherte Reihenfolgen; spätere Änderungen werden nicht bei jedem Start zurückgesetzt. 51 automatisierte Tests bestanden; BGM2-PNGs mit AFA-Daten in Ganz- und Halbfoliengrösse visuell geprüft.

## Lesbarkeit und Grundmengen korrigieren (Version 0.1.12)

Berichte trennen Kopf, Teilnahme, Navigation und Themen durch eigene Flächen und grössere Abstände. Diagramme erhalten dezente Rahmen und Schatten. Textantworten stehen in deutlich erkennbaren blauen Aufklappfeldern mit Beitragszahl; geöffnet sind die einzelnen Aussagen nummeriert und voneinander abgegrenzt. Das gilt auch für die eigenständigen HTML-Downloads. Im Druck entfallen die Schatten.

Unter «Grundmengen» steht bei jedem gespeicherten Eintrag «Bearbeiten». Anzahl, Welle, Merkmal und Einheit können korrigiert werden. Existiert für ein neues Ziel bereits eine Grundmenge, wird die Änderung abgewiesen und keiner der beiden Einträge überschrieben. «Grundmenge löschen» entfernt ausschliesslich den betreffenden Wert. Antwortdaten, andere Einheiten und die ursprüngliche Mitarbeitendenbasis bleiben erhalten; ohne Grundmenge bleibt die Rücklaufquote offen. Zwischenzeitlich geänderte Einträge können aus einem alten Browser-Tab nicht überschrieben oder gelöscht werden.

Ein erneuter Seed-Lauf kann fehlende Grundmengen wieder aus der Mitarbeitendenbasis ergänzen. Manuelle Änderungen betreffen die im Bericht verwendeten Werte, nicht die gespeicherte Herkunft der ursprünglichen Berechnung.

Die Zuordnung der Grundmengen im Bericht wird für jede Befragungswelle anhand des damals gültigen OE-Verzeichnisses und der Antwortpfade dieser Welle geprüft. Historische Pfade aus anderen Wellen bleiben auswählbar, blockieren aber keine eindeutige Grundmenge der aktuellen Welle. Bei mehreren gleichnamigen Einheiten innerhalb derselben Welle oder einem abweichenden ausgewählten Pfad erscheint «Zuordnung nicht eindeutig»; fehlende Grundmengen werden weiterhin mit «Nicht hinterlegt» bezeichnet.

Für einzelne historische Rücklaufquoten können getrennte Darstellungsregeln in `participation_policies` hinterlegt werden. `published` zeigt einen bestätigten veröffentlichten Prozentwert mit seiner damaligen Definition. Zähler und Nenner bleiben in dieser Zeile leer, damit die historische Quote nicht neben heute anders berechneten Fallzahlen steht. `omit` lässt eine nicht vergleichbare Quote samt Einladungszahl weg und zeigt die Begründung. Die Regeln gelten je Projekt, Welle, Merkmal und Einheit in Vorschau, Bericht und HTML-Download; Mindestfallzahlen für unterstellte Einheiten gelten weiter. Mehrdeutige Teilpfade erhalten keine veröffentlichte Gesamtquote. Antworten, Ergebnisberechnung, Leitungs­ausschluss und gespeicherte Grundmengen werden nicht geändert; Werte werden nicht auf 100 % begrenzt. Die Regeln sind nicht im öffentlichen Quellcode vorbelegt und werden bei einem vollständigen Puls-Neustart des betreffenden Projekts entfernt.

54 Tests bestanden, darunter Korrektur, Löschung, Kollisionen, Validierung, veraltete Browser-Tabs und Abgrenzung nach Projekt. Keine neuen Pakete, keine Datenbankänderung und kein Neuimport nötig. Der vollständige Browser-Layouttest bleibt in der Ausführungsumgebung eingeschränkt.

## Leitung der eigenen OE ausschliessen (Version 0.1.13)

In OE-Auswertungen werden ausschliesslich Teilnahmen mit Kadertyp `100` ausgeschlossen, deren vollständiger Organisationspfad genau der ausgewerteten OE entspricht. Leitungspersonen unterstellter Einheiten bleiben im übergeordneten Ergebnis enthalten. Andere Kadertypen, beispielsweise `110`, bleiben erhalten. Mehrere direkte Leitungspersonen mit `100` werden vollständig ausgeschlossen. Für die Gesamtauswertung betrifft dies die Leitung der obersten Organisationsebene. Die Zuordnung verwendet die gepflegten wellenbezogenen Segmentregeln und vollständigen Pfade, keine Personennamen oder pauschalen Kaderstufen.

Der Ausschluss erfolgt vor Berechnung und Mindestfallzahlprüfung. Er gilt für Mittelwert, Zustimmung, Auswahlhäufigkeiten, Teilnahme, fehlende Antworten, Freitexte und ausgewählte Textbelege. Jede Vergleichs-OE wird nach derselben Regel für ihre eigene Leitung berechnet. Rohantworten und redaktionelle Zusammenfassungen bleiben unverändert; vorhandene Zusammenfassungen sind fachlich zu prüfen.

Für Rücklaufquoten ist bei «Grundmengen» zusätzlich «Davon Leitungspersonen dieser OE (Kadertyp 100)» zu hinterlegen. Gezählt werden die eingeladenen eigenen Leitungspersonen, nicht die tatsächlich eingegangenen Leitungsantworten und nicht unterstellte Leitungen. Der Bericht zieht den bestätigten Anteil von der gespeicherten Grundmenge ab. `0` bedeutet, dass in der erfassten Grundmenge keine eigene Leitung enthalten ist; leer bedeutet unbekannt. Bei Exporten mit Kadertyp-Feld bleibt die Quote ohne bestätigten Leitungsanteil offen. Die bisherige Mitarbeitendenliste mit ausschliesslich OE-Kürzeln erlaubt keine automatische Bestimmung dieses Anteils. Bei einem Puls-Neustart werden diese Angaben nur für die zurückgesetzten Projekte entfernt.

57 Tests bestanden. Neu geprüft sind eigene/unterstellte Leitungen, mehrere direkte Leitungen, Kadertyp 110, Freitext- und Fallzahlschutz, Vergleichswerte sowie ausdrücklich bestätigte Einladungszahlen unabhängig vom Rücklauf der Leitungspersonen. Das Update ergänzt eine Tabelle für Leitungsanteile automatisch; kein Neuimport nötig.

## Optionale 95%-Konfidenzintervalle (Version 0.1.14)

Im Bericht unter den Darstellungseinstellungen «95%-Konfidenzintervalle in den Einzelfragen anzeigen» einschalten. Der Schalter ist zunächst aus und betrifft ausschliesslich «Einzelfragen und Details», nicht die kompakten Themenübersichten. Im Zeitverlauf erhält die ausgewählte OE vertikale Fehlerbalken; die Vergleichslinien bleiben ohne Intervalle. Im aktuellen Einheitenvergleich erhält jede dargestellte Untereinheit horizontale Fehlerbalken. Tooltip und PNG-/ZIP-Export berücksichtigen Kennzahl, Intervallschalter und die sichtbaren Reihen. PNG-Dateien mit Intervallen tragen `_ci95` im Namen und nennen Methode und Modellhinweis.

Mittelwerte: zweiseitiges punktweises 95%-t-Intervall mit n−1 Freiheitsgraden und Stichprobenstandardabweichung. Mindestens zwei gültige Antworten sind nötig. Zustimmungsanteile: zweiseitiges 95%-Wilson-Intervall für die konfigurierte Zustimmungsgrenze. Fehlende oder ungeklärte Antworten bleiben ausgeschlossen. Die bestehenden Leitungsausschlüsse und Mindestfallzahlen gelten unverändert. Rechnerische t-Grenzen ausserhalb der Skala werden nur im Diagramm abgeschnitten; im Tooltip bleiben sie vollständig. Bei identischen Antworten kann das t-Intervall rechnerisch die Breite null haben.

Die Intervalle beruhen auf einem Modell unabhängiger Beobachtungen, nicht auf einer abgesicherten Zufallsauswahl aus der Belegschaft. Sie erfassen keine Verzerrung durch Nichtteilnahme. Bei einer angestrebten Vollerhebung dienen sie als optionale Analysehilfe; die Ergebnisse der Teilnehmenden sind deskriptiv bekannt. Es gibt keine Korrektur für endliche Grundmengen oder Mehrfachvergleiche. Überlappungen sind kein Signifikanztest. Für Zeit- und überlappende OE-Vergleiche wird keine Unabhängigkeit der verglichenen Gruppen behauptet.

Vollständig erfasste Skalenfragen erhalten pro Frage, Welle und OE ein Sternchen am Wert und kein Konfidenzintervall. Voraussetzung sind eine eindeutig zugeordnete, bekannte Grundmenge, bestätigte eigene Leitungsanteile bei vorhandenen Kaderangaben und genau so viele Teilnehmende und gültige Antworten wie die bereinigte Grundmenge. Historische Prozentangaben ersetzen diese Prüfung nicht. Die Erklärung steht einmal unter «So liest du die Ergebnisse»; Charts, Tooltips und PNGs übernehmen nur die Markierung. Bei unvollständigen Antworten bleiben die bisherigen Intervalle unverändert.

**Update:** App beenden, `instance` sichern, Programmdateien aktualisieren und einmal `INSTALL.bat` ausführen. Für die t-Verteilung wird neu SciPy installiert. Danach `START.bat` starten. Kein Neuimport und keine Datenbankänderung nötig.

Validierung: 62 Tests bestanden, darunter numerische Referenzen, Grenzfälle, Ausschlüsse/Mindestfallzahlen, Schalter, Tooltips, Fehlerbalkenrichtung und PNG-Übernahme. Tatsächliche PNGs mit lokalen AFA-Daten gerendert und visuell geprüft; der vollständige Browser-Layouttest bleibt offen.

## Frühere OE-Textauswertung ohne API (Version 0.1.15, bestehende Aufträge)

Unter **Textauswertung** eine Welle und OE auswählen, Mindestfallzahl prüfen und
Textfragen markieren. Die Auswahl verwendet die Berichtsregeln einschliesslich
Fragenausschlüssen, Fehlwerten, vollständigem OE-Pfad und Leitungsausschluss.

1. **Exportprüfung:** Frage- und Antworttexte auf Personenbezüge prüfen und bearbeiten.
   E-Mail-Adressen und Schweizer Telefonnummern werden als einfache Vorschläge ersetzt.
   Namen, Funktionen, Gesundheitsangaben, Orte und identifizierende Vorfälle erfordern
   eine manuelle Prüfung. Die Ersetzung ist keine Garantie vollständiger Anonymität.
2. **Exportfassung festhalten**, dann das ZIP herunterladen. Es enthält `daten.json`,
   `standardprompt.txt` und `rueckgabe_vorlage.json`. Nur bereinigte Texte und zufällige
   Auftrags-/Frage-/Antwortkennungen verlassen die App; keine Rohmetadaten oder
   Zuordnungstabellen. ZIP entpacken, die JSON-Dateien in die selbst gewählte KI laden
   und den Standardprompt verwenden. Die App führt keine Netzwerkaufrufe aus.
3. **Ergebnis importieren:** Die KI soll eine UTF-8-Datei `ergebnis.json` liefern.
   Die App prüft Formatversion, Auftrag, Quellen pro Frage und vollständige Abdeckung.
   Jede Antwort muss mindestens einem Thema oder mit Begründung «nicht auswertbar»
   zugeordnet sein. Ungültige oder unvollständige Importe ändern den Auftrag nicht.
4. **Inhaltlich prüfen:** Themen und Aussagen neben den Originalen sichten und redigieren.
   Auch nicht ausgewertete Antworten prüfen. Titel und Aussagen lassen sich bearbeiten.
   Quellenkorrekturen benötigen in dieser ersten Version einen neuen Auftrag.
5. **Freigeben:** Unter Ergebnisse & Berichte «Geprüfte Textzusammenfassungen im Bericht
   anzeigen» aktivieren. Zusammenfassungen erscheinen bei der jeweiligen Textfrage,
   unabhängig davon, ob vollständige Originaltexte ebenfalls ausgewählt sind.
   Für einen erneuten HTML-Export ist keine neue KI-Auswertung erforderlich.

Die erste Ausbaustufe speichert **fragebezogene Themenzusammenfassungen für genau
eine OE und Welle je Auftrag**. Mehrere Fragen sind pro Auftrag möglich. GL und
Abteilungen benötigen jeweils eigene Aufträge. Eine automatische Wiederverwendung
codierter Einzelaussagen über verschiedene OEs, ein zweiter GL-Syntheseexport und
ein wellenübergreifendes Codebuch sind spätere Ausbaustufen.

Geprüfte Fassungen werden nur für den passenden Berichtsumfang ausgegeben und
unterliegen dessen aktueller Mindestfallzahl. Bei mehreren freigegebenen Aufträgen
zur gleichen Frage gilt der zuletzt erstellte aktuelle Auftrag. Eine Freigabe kann
zurückgenommen werden; bis zur erneuten Freigabe wird diese Fassung nicht ausgegeben.
Änderungen der ausgewählten Antworten, des Fragewortlauts/-labels, der Zuordnung
oder Ausschlüsse können einen Auftrag veralten lassen. Veraltete Aufträge bleiben
lesbar, werden aber weder weiterverarbeitet noch im Bericht ausgegeben. Neue Aufträge
überschreiben keine alten Fassungen; parallele Bearbeitungen sind versionsgeschützt.
Alle Aufträge, Originale und Rückgaben liegen in der lokalen SQLite-Datenbank und
werden mit dem Ordner `instance` gesichert. Das ZIP enthält keine lokale Zuordnung.
Die Format-/Auftragsversion ist derzeit 1; fehlende oder fremde IDs werden abgewiesen.

Validierung: automatisierter vollständiger Export-/Import-/Freigabe-/Berichtsdurchlauf
mit synthetischen Daten sowie Negativfälle für Quellen, Vollständigkeit, Datenänderungen,
OE-Abgrenzung, Mindestfallzahl, HTML-Escaping, CSRF und parallele Bearbeitung.
Ein realer Auswertungsversuch mit AFA-Daten in der vom Anwender gewählten KI steht aus.


## Einmalige Textaufbereitung pro Welle (Version 0.1.16)

Neue Aufträge unter **Textauswertung** gelten für eine ganze Welle. Die OE-Auswahl
im Bericht begrenzt den Wellenauftrag nicht. Alle gewünschten Textfragen markieren
(standardmässig sind alle ausgewählt) und «Wellenauftrag vorbereiten» wählen.
Die erste Export-/Importversion bleibt für bereits erstellte OE-Aufträge erhalten.

**Gemeinsame Grundlage:** Formatversion 2 liefert kurze sinngemässe Einzelaussagen
pro Antwort mit Themenbezeichnung, statt eine fertige OE-Zusammenfassung zu erzeugen.
Eine Aussage darf nur den Inhalt ihrer eigenen Quellantwort enthalten. Ihre lokale
Zuordnung zu Teilnahme, Frage und Welle bleibt erhalten. Alle Leitungspersonen bleiben
in der gemeinsamen Aufbereitung enthalten, weil sie je nach ausgewerteter OE ein-
oder ausgeschlossen werden müssen. Fragen- und Fehlwertausschlüsse gelten bereits
für die Vorbereitung. Im späteren Bericht werden zuerst die Quellen nach dem exakten
OE-Pfad und Leitungsausschluss gefiltert und erst dann die Aussagen gruppiert.
Dadurch ist keine erneute KI-Auswertung pro Abteilung erforderlich.

**Grosse Datenmengen:** Der Auftrag wird je Frage nach höchstens 50 Antworten und
normalerweise 24'000 Zeichen Antwortdaten in stabile Teilpakete zerlegt. Die gesamte
JSON-Eingabe ist auf 28'000 Zeichen pro Paket begrenzt, einschliesslich Metadaten und
Fragetext. Einzelne aussergewöhnlich lange Antworten werden nicht abgeschnitten;
wenn sie die Paketgrenze überschreiten, muss ihr Exporttext manuell gekürzt/bereinigt
werden. Die Originalantwort bleibt lokal erhalten. Jedes Teilpaket hat eigene zufällige
Kennungen. Die Prüfseiten laden nur ein Teilpaket, niemals sämtliche Textantworten als
ein einziges grosses Formular. Die Wellenübersicht berechnet keine Diagramme/OE-Vergleiche.

1. Teilpaket öffnen, Frage- und Antworttexte prüfen/bereinigen. Zwischenstände lassen
   sich speichern und später fortsetzen. Erst nach ausdrücklicher Prüfung auf direkte
   und indirekte Personenbezüge die Exportfassung festhalten.
2. Teilpaket einzeln oder alle bereinigten Teile zusammen als ZIP herunterladen.
   Ungeprüfte Exportteile sind im Sammel-ZIP nicht enthalten. Originalkennungen und
   Merkmale wie OE, Rolle und Datum verlassen die App nicht. Zufällige Antwort-IDs
   unterscheiden sich auch zwischen Fragen derselben Teilnahme.
3. In der gewählten KI mit dem mitgelieferten Standardprompt auswerten. Das Sammel-ZIP
   enthält je Teil Daten und Rückgabevorlage. Jede Rückgabe bleibt eine eigenständige
   JSON-Datei. Modellgrenzen können mehrere Arbeitsschritte erforderlich machen;
   die App garantiert keine Verarbeitung einer ganzen grossen Welle in einem KI-Aufruf.
4. Eine oder mehrere JSON-Rückgaben gemeinsam importieren (höchstens 100 Dateien pro
   Upload, zusammen innerhalb der bestehenden 60-MB-Anfragegrenze). Formatversion,
   Auftrag, Teil, Frage und sämtliche Antwortkennungen werden geprüft. Jede Antwort
   benötigt Aussagen oder einen begründeten Nichtauswertungsvermerk. Ein fehlerhafter
   gemeinsamer Upload verändert keine seiner Teilpakete. Bereits identische Rückgaben
   dürfen gefahrlos erneut hochgeladen werden; Bearbeitungen/Freigaben bleiben erhalten.
5. Pro Teil die Aussagen neben ihren Originalen inhaltlich prüfen, redigieren und
   freigeben. Abweichende KI-Rückgaben dürfen vorhandene Prüfungen nicht still ersetzen.
   Vor der Freigabe ist ein ausdrücklich bestätigtes Ersetzen im Teilpaket möglich.
6. Erst wenn **alle Teilpakete des Auftrags** freigegeben sind, ist die Auswertung für
   alle OE-Berichte verfügbar. Der Berichtsschalter für geprüfte Textzusammenfassungen
   bleibt erforderlich. Mindestfallzahlen und Fragenumfang gelten wie bisher.

**Darstellung:** Themen werden aus den zur ausgewählten OE gehörenden Einzelaussagen
zusammengesetzt. Nur bis auf Gross-/Kleinschreibung und Leerzeichen identische Aussagen
werden automatisch gebündelt, keine semantisch ähnlichen Aussagen zusammengezogen.
Pro Thema stehen zunächst drei Aussagen sichtbar, weitere sind aufklappbar vollständig
enthalten. Einzelhinweise und Gegensätze bleiben so verfügbar. Es handelt sich um eine
quellenbasierte Themenübersicht, keine neu generierte erzählerische GL-Gesamtsynthese.
Eine solche zusätzliche Gesamtsynthese ist weiterhin eine spätere Ausbaustufe.

Unterschiedliche Themenbezeichnungen aus mehreren KI-Teilen lassen sich in der
Wellenübersicht auf denselben Zielnamen zuordnen. Das verändert nur die Gruppierung,
nicht die Aussagen oder deren Quellen. Änderungen der Themenliste zwischen Anzeige
und Speichern werden erkannt. Änderungen an OE-Zuordnungen oder Leitungsrollen
benötigen keine neue KI-Aufbereitung; sie wirken beim nächsten Bericht über die
aktuellen Quellenfilter. Änderungen an ausgewählten Originalantworten, Fragen,
Fragenverknüpfungen, Fehlwerten oder Ausschlüssen können den Wellenauftrag veralten
lassen. Ein veralteter Auftrag bleibt lesbar, wird aber nicht weiterbearbeitet oder
in Berichten verwendet. Bei Rücknahme einer Teilfreigabe ist der Wellenauftrag wieder
unvollständig. Andere bereits geprüfte Teile bleiben gespeichert.

Prüfung: 10'000 synthetische Textantworten ohne Verlust über begrenzte Teilpakete
verteilt, validiert und für einen ausgewählten Quellumfang gruppiert; zusätzlich
Auftragsvorbereitung mit über 4'000 Datenbankantworten und begrenzten Prüfseiten.
Weitere Tests prüfen Wiederverwendung zwischen OEs, eigenen Leitungsausschluss,
Teilimporte, atomare Sammelimporte, sichere Wiederholung, Quellenverwechslung,
Themenvereinheitlichung, Zwischenstände und veraltete Daten. Ein realer AFA-Versuch in
der selbst gewählten KI steht weiterhin aus. Keine neuen Python-Pakete erforderlich.

Bei verknüpften Freitextnachfragen enthält der bearbeitbare Exportfragetext zusätzlich
den Wortlaut der zugehörigen Skalenfrage aus derselben Welle (ohne individuelle
Skalenwerte). Fehlt deren Originalwortlaut, wird die Berichtsbezeichnung verwendet.
Änderungen dieses Kontextes lassen den Wellenauftrag ebenfalls veralten.


## Berichtsvorlagen und gemeinsame Anliegen (Version 0.1.17)

Unter **Textauswertung → Wellenauftrag → Anliegen bündeln und Kernaussagen auswählen**
lassen sich geprüfte Einzelaussagen frageweise zu gemeinsamen Anliegen zusammenführen.
Voraussetzung ist ein aktueller, vollständig freigegebener Wellenauftrag. Pro Seite
werden höchstens 50 Einzelaussagen sowie 50 gespeicherte Anliegen bearbeitet. Suche
und Frageauswahl helfen bei grossen Wellen. Eine gespeicherte Bündelung kann auf weiteren
Seiten um Quellen ergänzt werden (mit aktiviertem JavaScript); vorhandene Anliegen
lassen sich auch ohne JavaScript bearbeiten oder auflösen.

Jedes Anliegen erhält Thema, kurze neutrale Formulierung, Reihenfolge und Darstellung:
Kernaussage, abweichende Sichtweise, besonderer Hinweis oder weiteres Anliegen.
Die Redaktion bestätigt ausdrücklich, dass **jede einzelne verknüpfte Quelle die gesamte
Formulierung stützt**. Die App prüft die Zuordnung und unveränderte Quellen technisch,
kann diese inhaltliche Voraussetzung aber nicht automatisch beurteilen. Verschiedene
Anliegen oder Gegensätze dürfen nicht in eine allgemeine Formulierung eingeebnet werden.
Alle ursprünglichen Einzelaussagen bleiben als Nuancen erhalten. Die gemeinsame Redaktion
gilt für die Welle; es ist kein erneuter KI-Lauf pro OE nötig und es gibt keine API-Aufrufe.

Eine Einzelaussage kann höchstens einem aktuellen Anliegen derselben Textfrage zugeordnet
sein. Änderungen an zugehörigen Einzelaussagen lassen die betroffene Bündelung ungültig
werden. Dann werden stattdessen die aktuellen Einzelaussagen ausgegeben. Die Redaktion
zeigt «Quellen verändert» und erlaubt Auflösen/Neuprüfen. Das Auflösen einer Bündelung
löscht keine Quell- oder Einzelaussagen. Gleichlautende Aussagen werden weiterhin nur
nach Gross-/Kleinschreibung und Leerzeichen automatisch gebündelt, semantische Bündelungen
benötigen die beschriebene Prüfung. Quellen und Nuancen werden vor der Berichtsausgabe
nach dem exakten OE-Pfad und Leitungsausschluss gefiltert. Unpassende Quellen gelangen
auch nicht in die aufklappbaren Vertiefungen oder Drucktexte.

Unter **Ergebnisse & Berichte** stehen zwei Vorlagen bereit:

- **GL kompakt:** Nach den Übersichts-Charts erscheinen pro Textfrage höchstens drei
  wiederkehrende Anliegen mit jeweils mindestens zwei Textantwortenden. Massgebend ist
  die tatsächlich passende Zahl verschiedener Personen nach OE- und Leitungsfilter;
  KI-Etiketten allein befördern keine Einzelhinweise in die Übersicht. Die Häufigkeit
  ist keine Bewertung der Wichtigkeit. Alle Anliegen, abweichenden Sichtweisen und
  Einzelhinweise bleiben gemeinsam aufklappbar. Kompakter Druck nutzt dieselbe Auswahl;
  der vollständige Druck enthält weiterhin alle Anliegen.
- **OE ausführlich:** Alle passenden Anliegen erscheinen bei der jeweiligen Frage.
  Bei mehr als acht Anliegen innerhalb eines Themas wird dessen vollständige Liste
  aufklappbar dargestellt. Es gibt keine pauschale Auswahl der ersten drei Aussagen.
  Nuancen der Quellen bleiben ebenfalls aufklappbar. Die Detailfragen öffnen initial.

Berichtsvorlage und Datenfilter sind voneinander unabhängig. Die Kennzahlen und deren
Grundlagen ändern sich durch die Vorlage nicht. Die Auswahl «Geprüfte Textzusammenfassungen»
steuert die Ausgabe; bei einem direkten Aufruf mit einer Vorlage ist sie voreingestellt,
über das Berichtsformular kann sie ausdrücklich ausgeschaltet werden. Originaltexte
bleiben ein separater Opt-in. Alte Berichtlinks ohne Vorlagenauswahl bleiben kompatibel.

Die **GL-Gesamtsynthese** wird redaktionell im bestehenden Feld «Erkenntnisse auf einen Blick»
verfasst, beispielsweise fünf bis sieben Erkenntnisse aus Skalen und Freitexten. Es gibt
keine automatisch erzeugte Gesamterzählung. Der Text bleibt an die ausgewählte OE und
Welle gebunden und wird nicht in unterstellte OE-Berichte kopiert. Die Formulierung
muss am jeweiligen Datenstand geprüft werden; bestehende freie Berichtstexte werden
bei Datenänderungen nicht automatisch umgeschrieben.

**Druck/PDF:** «Kompakt ohne Textvertiefungen» enthält die Hauptaussagen der gewählten
Vorlage; «Mit vollständigem Textanhang» enthält zusätzlich weitere Anliegen und sämtliche
passenden Nuancen. Originalantworten kommen nur bei ausdrücklicher Auswahl und in der
vollständigen Druckansicht dazu. Der Browserdruck (bei Bedarf «Als PDF speichern») nutzt
separate fest gerenderte Textblöcke ausserhalb der interaktiven Aufklappfelder. Die
Textausgabe hängt deshalb nicht von deren Öffnungszustand ab. Das ist kein zusätzlicher
serverseitiger PDF-Export. Diagramm-/PNG-Exporte enthalten weiterhin keine Berichtstexte.

**Berichtspakete:** Im Berichtsformular «Berichtspaket für mehrere OEs erstellen» öffnen,
eine bis höchstens 50 OEs des aktuellen Organisationszweigs markieren und das ZIP laden.
Es enthält eigenständige Offline-HTML-Berichte mit der aktuellen Wellen-, Vorlagen-,
Text- und Druckauswahl. Jede OE wird einzeln gefiltert. Die Dateinamen haben eindeutige
Nummern, sodass gleich benannte OEs keine Dateien überschreiben. Originaltexte und
Quellenkennungen werden ohne ausdrücklichen Rohtext-Opt-in nicht eingebettet.

Validierung mit synthetischen Daten: vollständige Redaktion, Bündeln/Ergänzen/Auflösen,
Quellenänderungen, verbotene Doppel-/Fremdzuordnungen, unveränderte quantitative Ergebnisse,
OE-gebundene Gesamtsynthese, Vorlagen, getrennte Drucktexte und OE-Berichtspakete. Zusätzlich
Projektion von 10'000 Einzelaussagen auf einen begrenzten Quellumfang ohne fremde Nuancen.
Die bestehenden Wellen-/Teilpaket-Lasttests bleiben erhalten. Kein neuer Paketbedarf.
Eine visuelle Prüfung des Browserdrucks und ein realer AFA-Durchlauf stehen noch aus.


## Wählbare Paketgrössen (Version 0.1.18)

Beim Erstellen eines neuen Wellenauftrags kann die Paketgrösse gewählt werden:

| Auswahl | Höchstens Antworten | Richtgrenze Antwortdaten (Zeichen) |
| --- | ---: | ---: |
| Klein | 50 | 24'000 |
| **Standard (Voreinstellung)** | **150** | **60'000** |
| Gross | 250 | 100'000 |

Die zuerst erreichte Grenze bestimmt die Aufteilung; Fragen werden weiterhin getrennt
gehalten. Die Zeichenzählung berücksichtigt die JSON-Antworteinträge einschliesslich
Kennungen. Fragetext und Auftragsmetadaten haben zusätzlich bis zu 4'000 Zeichen Platz
in der kompakten JSON-Darstellung. Die eingerückten Download-Dateien sind durch die
Formatierung grösser. Kein Inhalt wird still abgeschnitten. Eine aussergewöhnlich lange
Einzelantwort muss bei Bedarf vor der Freigabe manuell bereinigt/gekürzt werden.

Die gewählte Grösse wird mit dem Auftrag gespeichert und beim Festhalten der Exporttexte
auch auf Antwortzahl und Textumfang geprüft. Änderungen bei der Bereinigung können daher
nicht unbemerkt über die gewählte Exportgrenze hinauswachsen. Die KI-Rückgabe wird wie
bisher auf vollständige Quellenabdeckung geprüft; grössere Pakete garantieren nicht,
dass die gewählte KI sämtliche Ausgaben in einem Schritt liefert. Zunächst ein grösseres
Paket auf vollständige Rückgabe prüfen und bei Bedarf «Klein» verwenden.

**Bestehende Aufträge behalten ihre Teilpakete, Kennungen und Fortschritte unverändert.**
Sie werden beim Update als «Klein» eingestuft. Für weniger Pakete einen neuen Auftrag
mit «Standard» oder «Gross» erstellen; es erfolgt keine automatische Neupartitionierung
oder Übertragung bereits zurückgegebener Ergebnisse auf neue Kennungen. JSON-Formatversion 2
bleibt unverändert. Neue Aufträge ohne explizite Grössenauswahl verwenden «Standard».
Keine neuen Python-Pakete erforderlich; die Datenbankergänzung erfolgt beim App-Start.

Tests prüfen alle Antwortgrenzen, Vorrang der Zeichengrenze, vollständige Abdeckung,
Fragentrennung, Export- und Importdurchlauf mit 150 Antworten sowie Migration und
unveränderte Paketkennungen bestehender Aufträge. Die vorangegangenen Last- und
Berichtstests bleiben erhalten.


## Konkrete Themen und verständliche Aussagen (Version 0.1.19)

Der Standardprompt für die Wellenaufbereitung verlangt jetzt inhaltliche Überschriften:
Gegenstand plus konkrete Erfahrung, Anliegen oder offene Frage. Ein Etikett wie
«Strategiekommunikation» reicht nicht; bei entsprechendem Quellinhalt wäre beispielsweise
«Bezug der Strategie zur eigenen Arbeit unklar» geeignet. Eigenständig verständliche
Einzelaussagen konkretisieren diese Überschrift. Unterschiedliche Anliegen zur selben
Sache und positive/abweichende Erfahrungen bleiben getrennt erhalten.

Die Anleitung unterscheidet ausdrücklich zwischen Beobachtung, Frage und Wunsch:
Verständnisprobleme dürfen nicht als Ablehnung, offene Fragen nicht als Forderung und
positive Erfahrungen nicht als Verbesserungsbedarf umgedeutet werden. Bezüge kurzer
Antworten dürfen nur bei eindeutigem Fragekontext aufgelöst werden. Allgemeine Quellen
bleiben allgemein, statt mit erfundenen Details präziser zu erscheinen. Stilbeispiele
sind ausdrücklich keine zusätzlichen Auswertungsdaten. Die zulässigen JSON-Felder,
Quellenkennungen, Formatversion 2 und Grössenbegrenzungen bleiben unverändert.

Der neue Prompt wird bei erneutem Download von Einzel- oder Sammelpaketen mitgeliefert,
auch bei bereits festgehaltenen Exporten. Dazu ist kein neuer Wellenauftrag nötig:
Daten, Kennungen und bestehende Ergebnisse werden nicht automatisch verändert. Für
bereits importierte Ergebnisse gelten weiterhin die ausdrücklichen Prüf-/Ersetzungsregeln.
Bereits heruntergeladene lokale ZIP-Dateien aktualisieren sich nicht selbst.

Automatisierte Integrationstests prüfen den aktualisierten Prompt in beiden Downloadwegen,
unveränderte Exportdaten und Kennungen sowie die Importierbarkeit des unveränderten
Rückgabeformats. Die tatsächliche inhaltliche Qualität muss mit der KI der Wahl anhand
echter Antworten geprüft werden; ein Modellaufruf ist nicht Bestandteil dieser Änderung.


## Gesamtauftrag: Kürzen, Verdichten und Kernaussagen vorschlagen (Version 0.1.20)

Der folgende Ablauf beschreibt die frühere Prüfung mit separater Freigabe. Seit 0.1.22 gilt der Schnellablauf am Ende dieses Dokuments. Dieser arbeitet mit einem Gesamtauftrag pro Welle. Im Wellenauftrag
**«Gesamtauftrag exportieren und verdichtetes Ergebnis importieren»** öffnen.

1. Die Frage- und Antworttexte aller Teilpakete wie bisher auf Personenbezüge prüfen,
   bereinigen und ihre Exportfassungen festhalten. Ohne vollständige Exportprüfung wird
   kein angeblich vollständiges Gesamtpaket erzeugt. Der alte Teilpaketweg bleibt erhalten.
2. Den **Gesamtauftrag** als ZIP herunterladen. Er enthält alle ausgewählten Texte mit
   Fragekontext in technischen Teilpaketen, ein vollständiges `manifest.json`, den
   Gesamt-`standardprompt.txt`, den bisherigen `teilprompt.txt` und eine
   `gesamt_ergebnis_vorlage.json`. Bereits vorhandene Teilergebnisse können als separate
   Zwischenstände mitgeliefert werden. Es werden keine lokalen OE-/Personenzuordnungen
   oder unbereinigten Originaltexte beigefügt.
3. Das ZIP in der KI der Wahl verarbeiten. Der Gesamtprompt fordert zunächst die
   vollständige paketweise Kürzung und anschliessend eine fragebezogene Verdichtung
   über **alle** Teile. Gleichbedeutende Aussagen werden Anliegen zugeordnet, Gegensätze
   und Einzelhinweise erhalten. Kernaussagen werden mit Begründung vorgeschlagen.
   Bei begrenztem Modellkontext Zwischenergebnisse speichern und die Verarbeitung
   fortsetzen. Eine unvollständige Welle darf nicht als vollständig ausgegeben werden.
4. Eine `gesamt_ergebnis.json` importieren. Das äussere Format ist Version 3 mit genau
   `version`, `auftrag`, `teile`, `anliegen`. `teile` enthält alle inneren Version-2-
   Rückgaben. Jedes Anliegen enthält `id`, `frage`, `thema`, `aussage`, `art`,
   `prioritaet`, `begruendung`, `quellen`. Eine Quelle bezeichnet `teil`, `antwort`
   und `aussage` (Position der Einzelaussage in der Antwortliste, beginnend bei 1).
   Die Formate und Regeln sind im Gesamtprompt konkret beschrieben.
5. Die App prüft vor jeder Änderung alle Teile, alle Antwortkennungen und jede
   Anliegenquelle. Jede auswertbare Einzelaussage muss genau einem Anliegen derselben
   Frage zugeordnet sein. Nicht auswertbare Antworten benötigen weiterhin einen Grund.
   Fehlende Teile/Antworten/Zuordnungen, doppelte Quellen und fremde Fragen werden
   abgewiesen. Es wird nichts teilweise überschrieben. Die Gesamtdatei darf höchstens
   50 MB gross sein; die bestehende HTTP-Grenze von 60 MB gilt weiterhin.
6. Die verdichteten Vorschläge in der Gesamtauswertung prüfen. Pro Anliegen werden
   Begründung, automatisch berechnete Nennungen und bis zu fünf Quellen zum Vergleich
   gezeigt; weitere Quellen und Bearbeitung stehen unter «Anliegen bearbeiten» bereit.
   Begründet nicht ausgewertete Antworten sind mit Original und Begründung separat
   seitenweise prüfbar, damit inhaltliche Auslassungen erkannt werden können.
   Die Übersicht ist mit 50 Anliegen je Seite begrenzt. Bezeichnungen, Aussagen,
   Vorschlagsart, Reihenfolge und Begründung können vor der Gesamtfreigabe redigiert
   werden. Die technische Quellenprüfung ersetzt keine inhaltliche Prüfung.
7. **«Gesamte Welle für Berichte freigeben»** bestätigt nach inhaltlicher Prüfung die
   komplette Auswertung gemeinsam. Es ist keine separate Freigabe jedes Teilpakets
   erforderlich. Die Bestätigung umfasst alle Seiten, nicht nur die angezeigten Anliegen.
   Bis dahin werden auch einzeln freigegebene Teile einer importierten Gesamtauswertung
   nicht als vollständig geprüfte Welle ausgegeben. Rücknahme oder spätere Bearbeitung
   eines Teilpakets setzt die Gesamtfreigabe wieder auf «Prüfung».

**Quantifizierung:** Die KI liefert Quellen, keine geschätzten Zahlen. Die App zählt
unterschiedliche Textantwortende je Anliegen und Frage höchstens einmal. In der
Gesamtprüfung ist der Nenner die komplette exportierte Wellenbasis dieser Frage,
einschliesslich begründet nicht ausgewerteter Textantworten und vor OE-/Leitungsfilterung.
Im Bericht werden zuerst Quellen und Nuancen nach dem gewählten OE-Pfad sowie eigenem
Leitungsausschluss gefiltert; Zähler und Nenner beziehen sich dann auf diese Textantwortenden.
Die Anzeige lautet z.B. «8 von 23 Textantwortenden dieser Frage». Mehrere Anliegen pro
Person sind möglich. Das sind keine Anteile aller Mitarbeitenden und kein repräsentatives
Meinungsbild. Ein CSV-Download der Prüftabelle ergänzt JSON um Nennungszahlen und Anteile
auf der globalen Wellenbasis; UTF-8 mit BOM und Semikolon für Excel. CSV ist eine Prüfansicht,
kein zweites Importformat. Quellen-/Originalkennungen werden in der CSV nicht ausgegeben.

**Ersetzen und Wiederholen:** Eine identische Gesamtrückgabe kann ohne Überschreiben
redaktioneller Änderungen erneut hochgeladen werden. Eine abweichende Rückgabe ersetzt
vorhandene Ergebnisse, Anliegen und Freigaben nur nach ausdrücklicher Bestätigung. Auch
parallele Änderungen zwischen Anzeige und Speichern werden erkannt. Originalantworten,
Exportbereinigung und Paketkennungen bleiben erhalten. Veraltete Datenstände blockieren
Export, Gesamtimport und Freigabe. Bestehende Version-2-Einzelimporte bleiben kompatibel.

Der Gesamtprompt ersetzt die manuelle Erstbündelung durch KI-Vorschläge; die endgültige
Prüfung bleibt beim Anwender. Die redaktionelle narrative GL-Gesamtsynthese unter
«Erkenntnisse auf einen Blick» wird weiterhin nicht automatisch erstellt. Es gibt keine
Modell-API-Aufrufe. Automatisierte Tests prüfen Gesamtexport, Manifest, atomaren Import,
Vollständigkeit, Quellenabgrenzung, gemeinsame Freigabe, sichere Wiederholung, redaktionelles
Ersetzen, lokale Häufigkeiten und 10'000 synthetische Antworten. Ein echter KI-Durchlauf
mit dem neuen Gesamtprompt und die visuelle Browserprüfung stehen noch aus.


## Überschaubare GL-Berichte und Quellenprüfung (Version 0.1.21)

Die GL-Übersicht zeigt pro Frage maximal drei Anliegen nach Häufigkeit, auch über
verschiedene Themen hinweg. Identische Formulierungen werden dort einmal angezeigt,
ohne möglicherweise überlappende Personenzahlen zu addieren. Lange Aussagen werden
nur in der Übersicht auf maximal 300 Zeichen gekürzt; der vollständige Text bleibt
in der Vertiefung. Wiederholte Überschriften entfallen. OE-Berichte behalten alle
passenden Anliegen.

Unter «Berichtsinhalte prüfen» stehen die gespeicherten Anliegen zuerst, sortiert
nach Zahl verschiedener Textantwortender. Einzelaussagen und neue Bündelungen sind
eine optionale, zunächst geschlossene Quellenprüfung. Ausgegraute Quellen sind bereits
einem Anliegen zugeordnet; ein Link führt zur zugehörigen Bündelung. Die redaktionelle
Reihenfolge (z. B. 10) ist eine Sortierzahl, kein Gewicht oder Prozentwert.

Bestehende Gesamtimporte, Freigaben und gespeicherte Anliegen bleiben verwendbar.
Kein neuer KI-Auftrag oder Neuimport erforderlich. Die narrative Gesamtsynthese unter
«Erkenntnisse auf einen Blick» bleibt redaktionell.

Validierung: 106 Tests, darunter 100 Einzelhinweise, Häufigkeit über Themen hinweg,
Deduplizierung ohne Addition, OE-Ausgabe, Diagrammreihenfolge, geschlossene Vertiefung
und dieselbe Auswahl im kompakten Druck.


## Schnellablauf für neue Wellen (Version 0.1.22)

1. Unter Textauswertung die Welle auswählen und «Gesamtauftrag vorbereiten». Alle
   Textfragen sind vorausgewählt; Fragen und Paketgrösse lassen sich optional ändern.
2. «Gesamtpaket mit Prompt herunterladen». Die App bereitet alle übrigen Teilpakete
   gemeinsam vor. Einzeln gespeicherte Bereinigungen bleiben erhalten. Das ZIP mit
   Standardprompt wird manuell der gewählten KI übergeben. Die technische Aufteilung
   dient der Verarbeitung grosser Wellen, verlangt aber keine Einzelbestätigungen.
3. Die vollständige gesamt_ergebnis.json mit «Importieren und für alle Berichte
   verwenden» laden. Erst nach vollständiger technischer Validierung wird die gesamte
   Welle atomar für Berichte aktiviert. Keine weitere Gesamt- oder Teilfreigabe nötig.
4. «Berichte erstellen» öffnen. Die gleiche Grundlage wird für GL- und OE-Berichte
   lokal gefiltert und gezählt. Eine narrative Gesamtsynthese bleibt optional.

Exportprüfung (Personenbezüge) und Importredaktion (Bündelung, Wortlaut, Quellen und
verworfene Antworten) sind bei Bedarf erreichbar. «Nur importieren» erlaubt weiterhin
eine Prüfung vor der Aktivierung. Aktivierung bezeichnet die Verwendung in Berichten,
keine behauptete manuelle Inhaltsprüfung. Ein identischer erneuter Import erhält
Redaktion und bestehende Freigaben; er kann eine zunächst nur importierte Fassung
aktivieren. Abweichende Ersatzimporte benötigen weiterhin ausdrückliche Bestätigung.
Veraltete Daten und unvollständige Rückgaben werden weiterhin abgewiesen.

Datenschutz: Exportiert werden Zufallskennungen, Fragetext und Exportantworten. OE- und
Personenmetadaten bleiben lokal. Automatisch entfernt werden E-Mail-Adressen und
erkennbare Telefonnummern. Das ist keine vollständige Freitextanonymisierung: Namen,
Ereignisse und indirekte Personenbezüge können verbleiben und lassen sich optional
vor dem Download bereinigen. Keine automatische Übertragung an eine KI.

Validierung: 110 Tests erfolgreich. Der Schnellablauf wird ohne Einzelbestätigungen
vom Gesamt-Download bis zur Berichtsausgabe geprüft, einschliesslich fehlerhafter
Gesamtrückgaben, atomarem Export, beibehaltener Bereinigung und Aktivierung identischer
Rückgaben bei erhaltener Redaktion.


## Nächste Schritte im Bericht (Version 0.1.23)

Unter «Ergebnisse & Berichte» → «Berichtstexte und Gesamtsynthese» steht das freie
Textfeld «Nächste Schritte» für Massnahmen, Zuständigkeiten und Termine bereit.
Der gespeicherte Inhalt gilt für die ausgewählte OE und Welle. Er erscheint am
Berichtsende vor den Berechnungshinweisen, mit einem Link im Inhaltsverzeichnis.
Vorschau, eigenständiger HTML-Export, Berichtspakete und Druck/PDF verwenden
denselben Abschnitt. Ohne Text wird er ausgeblendet. Keine Datenmigration nötig.


## Verständliche Methodik, Enthaltungen und PDF (Version 0.1.24)

Im Abschnitt Teilnahme und Rücklauf wird der Ausschluss der jeweils vorstehenden
Führungskräfte sichtbar erklärt, einschliesslich der Regel für unterstellte Einheiten.
«So lesen Sie die Ergebnisse» erklärt Mittelwerte, Zustimmung, Rücklauf, Vergleiche
und Unsicherheitsbereiche mit Alltagsbeispielen. Technische Formeln bleiben vertiefbar.

Enthaltungen sind ausschliesslich tatsächlich gespeicherte, nicht leere Antwortcodes
aus der Fragenverwaltung (z. B. «Keine Antwort»). Nicht vorhandene Fragezeilen und
leere Felder zählen nicht als Enthaltungen. Dadurch werden Personen ohne die nur an
Führungskräfte gestellte Frage nicht aus der Gesamtteilnahme heraus als Enthaltungen
ermittelt. Die bestehende Diagnosezahl `unanswered` bleibt intern kompatibel, wird
im Bericht aber nicht mehr als Enthaltungszahl verwendet. Nicht zuordenbare Antworten
werden weiterhin separat ausgewiesen.

PDF über Browserdruck: A4 mit Druckrändern, kleinere Schrift, einspaltige Details und
Seitenumbrüche zwischen Themen/Detailfragen. Vor dem Druck werden die für die Druckvorlage passenden Details
und die verständliche Methodik geöffnet; die kompakte GL-Fassung lässt wiederholte
Skalen-Detailcharts weg und behält Auswahlfragen bei; Diagramme werden in fester Druckgrösse als
Bilder ausgegeben. Nach dem Druck werden Aufklappzustände und Chartgrössen wiederhergestellt.
Die festgelegte kompakte/vollständige Textauswahl bleibt unabhängig vom Bildschirmzustand.
Der Druckknopf ist erst nach der Chartinitialisierung aktiv.


## Schlankere Berichte und Vergleiche (Version 0.1.25)

Die Standardvorlage heisst «Kompakt» und eignet sich auch für Bereiche und andere OEs.
Lesehinweise stehen gemeinsam am Anfang; technische Statuszeilen und wiederholte
Hinweise zwischen Diagrammen und Textantworten entfallen. Die ausgeschlossenen
vorstehenden Führungskräfte werden kurz erklärt.

Bei einer einzigen obersten OE entfällt die zusätzliche Auswahl «Gesamtbefragung»;
alte Links bleiben nutzbar und zeigen den Namen dieser OE. Bestehende Berichtstexte
der früheren Gesamtansicht bleiben auch bei Auswahl der obersten OE erhalten. Die
oberste OE vergleicht sich nicht mit sich selbst; identische übergeordnete und
Gesamt-Vergleichspfade werden nur einmal angeboten. Bei mehreren obersten OEs bleibt
«Alle Organisationseinheiten» als gemeinsame Auswahl erforderlich.

Anliegen in der vollständigen Textvertiefung sind frageweise über alle Themen hinweg
nach Zahl Textantwortender absteigend geordnet. Auswahlcharts ordnen Optionen ebenfalls
nach Häufigkeit. Die Vergleichsschalter haben mehr Abstand. Detaillegenden zeigen
Linien; auch bei direktunterstellten Einheiten werden eingeschaltete Vergleichsgruppen
als Referenzlinien angezeigt. Jeder OE-Wert wird weiterhin mit dem Ausschluss seiner
eigenen Leitung berechnet; übergeordnete Werte enthalten unterstellte Leitungen.


## Geschlossene Lesehinweise und Textblöcke (Version 0.1.26)

«So liest du die Ergebnisse» und die Zusammenfassungen der Textantworten sind
standardmässig geschlossen. Die Lesehinweise nennen die tatsächlich gewählte
Mindestanzahl (standardmässig n = 5). Der doppelte Leitungshinweis bei Teilnahme
und Rücklauf sowie die Einheit-/Mindestfallzahlbox entfallen. Nach dem Laden
der Diagramme wird keine Bereitschaftsmeldung mehr angezeigt; Exportfortschritt
und Fehlermeldungen bleiben sichtbar. Die Druckauswahl bleibt unabhängig von den
geöffneten Aufklappfeldern.


## Textantworten: Themen, Kernaussagen und Nuancen

Der Gesamtprompt strukturiert die Auswertung pro Freitextfrage nach gemeinsamen
Gegenständen (Themen), wiederkehrenden Erfahrungen, Einschätzungen oder Anliegen
(Kernaussagen) und ergänzenden Unterschieden (Nuancen). Themenüberschriften benennen
den Gegenstand, die Aussagen beschreiben den Inhalt. Auch der Teilprompt verwendet
diese Trennung, damit gleiche Gegenstände über Teilpakete hinweg zusammenfinden.

Gebündelt wird nach Bedeutung. Jede Quelle muss die gesamte gemeinsame Formulierung
stützen. Besonderheiten bleiben in den Einzelaussagen erhalten und können im Bericht
als Nuancen erscheinen; eigenständige wiederkehrende Gegensätze bilden getrennte
Kernaussagen unter demselben Thema. Einzelstimmen bleiben in den Teilpaketen erhalten.
Die KI soll keine Ursachen oder Empfehlungen ergänzen und Erfahrungen nicht pauschal
in Verbesserungswünsche umformulieren. Die Zahl der Themen ergibt sich aus dem Material.

Das technische JSON-Feld `anliegen` umfasst weiterhin alle gebündelten Kernaussagen,
auch Erfahrungen und Einschätzungen. Es gibt keine neuen JSON-Felder oder Formatversionen.
Die App berechnet Anzahl und Herkunft weiterhin lokal und wendet die bestehenden
Anonymitätsregeln an. Die Prompts enthalten keine eigenen OE-Zuordnungen oder Zahlen.

Für die neue Anleitung das Gesamtpaket erneut herunterladen. Bestehende Aufträge,
Kennungen, Exporttexte und Ergebnisse werden dadurch nicht verändert. Bereits geladene
ZIP-Dateien bleiben unverändert; vorhandene Ergebnisse werden nicht automatisch neu
ausgewertet. Die bestehenden Regeln zum Ersetzen importierter Ergebnisse gelten weiter.
Export-/Importtests prüfen die Auslieferung beider Prompts sowie unveränderte Nutzdaten
bei wiederholtem Download. Die tatsächliche Qualität der KI-Verdichtung muss anhand
echter Antworten geprüft werden; diese Änderung führt keinen Modellaufruf aus.
