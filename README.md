# Befragungsstudio 0.1.7

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

Noch offen: bearbeitbarer Organisationsbaum und historische OE-Versionen,
Grundmengen-Tabellenimport, Berichtspakete für ganze Hierarchiezweige,
gestapelte Antwortverteilungen und Top-2-Zeitdiagramme, Engagement-Index,
Freitextprüfung und -freigabe, Optionsspalten als gemeinsame Multiple-Choice-Frage,
Vorlagenverwaltung, Profilgenerierung und Echonovum-Upload.

Das OE-Verzeichnis kann bereits importiert werden. Es ändert keine historischen
Antwortzuordnungen. Diese werden vorerst über die Segmentregeln gepflegt.
Die Auswahl einer Einheit erfolgt über Merkmal und exakten Wert.
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
Ordner instance mit Daten und Konfiguration beibehalten. Das Datenbankschema bleibt
unverändert. Nach dem Update START.bat ausführen. Eine erneute Installation nur
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
