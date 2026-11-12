# Berichte insgesamt oder zu einer Bezugswelle

Unter «Ergebnisse und Berichte» lässt sich der Berichtsumfang auswählen:

- **Gesamtauswertung:** alle eingeschalteten Fragen der ausgewählten Vergleichswellen.
- **Bezugswelle:** nur eingeschaltete Fragen, die in dieser Welle erhoben wurden. Für diese Fragen werden alle vorhandenen Vergleichswerte aus dieser und früheren Wellen einbezogen. Spätere Wellen werden nicht angezeigt. Fragen werden anhand der konfigurierten Verknüpfungen über unterschiedliche Quell-IDs hinweg erkannt.

Eine Bezugswelle ist kein reiner Datumsfilter: Sie bestimmt den Fragenumfang, während der Zeitverlauf erhalten bleibt. Beispiel: Eine Frage wurde in Welle 1 und 2 gestellt, eine andere nur in Welle 1. Der Bericht zu Welle 2 enthält die erste Frage mit beiden Messzeitpunkten. Die zweite Frage erscheint nur in der Gesamtauswertung oder im Bericht zu Welle 1.

Die Reihenfolge ergibt sich aus den Antwortdaten der Wellen. Die Häkchen unter «Vergleichswellen für die Gesamtauswertung» gelten nur ohne Bezugswelle. Globale Frageausschlüsse und Ausschlüsse einzelner Quellfragen je Welle werden berücksichtigt. Eine Frage, die in der Bezugswelle vollständig ausgeschlossen ist, erscheint auch nicht mit historischen Ergebnissen im Bericht zu dieser Welle.

Segmentfilter und Mindestfallzahl gelten weiterhin für jeden dargestellten Messzeitpunkt. Liegt eine Frage in der Bezugswelle unter der Mindestfallzahl, können ausreichend grosse historische Stichproben weiterhin gezeigt werden; die geschützten Ergebnisse bleiben ausgeblendet. Vollständige Freitexte sind standardmässig nicht Teil der Weitergabeberichte; die explizite Freigabe ist unten beschrieben.

Die Auswahl gilt für die Ergebnisansicht, Berichtsvorschau, heruntergeladene HTML-Berichte und PNG-/ZIP-Exporte. Der Berichtskopf nennt die Bezugswelle; Charts zeigen die tatsächlich dargestellten Zeitpunkte. Der Rücklauf wird für die einbezogenen Vergleichswellen dargestellt.

## OE-Berichte und thematische Besprechungsgrundlage

Unter «Ergebnisse & Berichte» ersetzt eine Auswahl nach Organisationspfad die bisherigen Freitextfelder Merkmal/Einheit. Die Vorschau öffnet in einem neuen Tab und bietet einen Link zurück zur App. HTML-Downloads bleiben eigenständig nutzbar.

Das gemeinsame OE-Verzeichnis unter «Organisation» unterstützt vollständige CSV-/XLSX-Importe und das Anlegen/Bearbeiten einzelner Einträge. Die ausgefüllten Ebenen bilden den Pfad Amt → Bereich → RAV-Gruppe → Abteilung → RAV → Team; leere Zwischenebenen werden übersprungen. Ein Import ersetzt den vollständigen Verzeichnisstand ab dem angegebenen Datum. Änderungen am selben Gültigkeitsdatum ersetzen diesen Stand; spätere Stände gelten bis zur nächsten Änderung. Die vorhandene Liste wird bei der ersten Änderung als Ausgangsstand erhalten. Das Verzeichnis ändert weder Antwortzuordnungen noch gespeicherte Grundmengen. Beim Import gilt weiterhin die erste Tabelle.

Die Auswahl berücksichtigt den vollständigen Pfad, damit gleich benannte Untereinheiten verschiedener Bereiche getrennt bleiben. Historische, tatsächlich in Antworten vorkommende Pfade bleiben auswählbar. Die Untereinheiten für den aktuellen Vergleich stammen aus dem Verzeichnisstand zum Beginn der Bezugswelle; fehlt ein Verzeichnis, werden die beobachteten Antwortpfade verwendet. Eine neue Verzeichnisversion erzeugt keine rückwirkende Umorganisation historischer Antworten. Umbenennungen bilden zunächst unterschiedliche Pfade; fachlich gewollte historische Zusammenführungen benötigen weiterhin geprüfte wellenbezogene Segmentregeln. Stabile, von der Bezeichnung unabhängige OE-Identitäten und Profilgenerierung sind eine spätere Ausbaustufe.

Berichte gliedern die freigegebenen Fragen nach dem Feld «Thema» aus der Fragenverwaltung. Für Puls AFA kann ein Themenvorschlag übernommen werden; er ergänzt nur leere Themenfelder:

- Engagement und Entwicklung
- Führung und Feedback
- Information und Orientierung
- Zusammenarbeit und Austausch
- Arbeitsbedingungen und Gesundheit

Unter «Weitere Fragen» stehen nicht zugeordnete Fragen. Die Zuordnung ist anschliessend unter «Fragen» editierbar. Aus Themen werden keine neuen Summenscores gebildet.

Jedes Thema zeigt zunächst gemeinsame Punktdiagramme mit bis zu fünf Fragen gleicher Skala: Zeitvergleich der ausgewählten OE und aktueller Vergleich der direktunterstellten Einheiten inklusive des ausgewählten Gesamtergebnisses. Die AFA-Themen folgen der obigen Reihenfolge. Unterschiedliche Skalen erscheinen getrennt; Fragen mit im Zeitverlauf veränderter Skala bleiben in den Details. Farben und Symbole kennzeichnen Wellen bzw. Einheiten; die Legende erlaubt deren Auswahl. Fehlende oder geschützte aktuelle Werte bleiben leer und werden nicht mit historischen Werten aufgefüllt. Es werden keine Themenmittelwerte berechnet. Mittelwert/Zustimmung gilt auch für die Übersichten.

Die Einzelfragen stehen unter «Einzelfragen und Details» aufklappbar bereit; Themen ohne Skalenübersicht zeigen die Details zunächst offen. Dort bleiben die bisherigen Diagrammkarten verfügbar: Zeitverlauf der ausgewählten OE und aktueller Vergleich der direktunterstellten Einheiten. Der vollständige Fragewortlaut stammt aus der Exportspalte `Question`, ersatzweise aus dem konfigurierten Fragetitel. Mittelwert/Zustimmung werden für den Bericht gemeinsam umgeschaltet. Skalenachsen beschriften ganze Werte; halbe Werte erhalten dezente Hilfslinien. Tabellen unter einzelnen Charts entfallen; gültige n bleiben sichtbar.

Vergleichslinien zeigen die direkt übergeordnete OE und das Projektgesamtresultat. Sie lassen sich gemeinsam per Checkbox und einzeln per Legende schalten. Der PNG-Export übernimmt den sichtbaren Linienzustand. Beide Vergleichsgrössen enthalten die ausgewählte OE. Alle Ergebnisse werden aus Antworten berechnet, nicht als ungewichteter Durchschnitt der Untereinheiten. Die Mindestfallzahl gilt auch für Untereinheiten und Vergleichslinien.

Teilnahme/Grundmengen/Rücklauf stehen am Anfang, zusätzlich für die direktunterstellten Einheiten in der Bezugswelle (bei Gesamtauswertung: letzte ausgewählte Welle). Grundmengen werden nicht addiert. Bei mehrfach vergebenem Dimensionswert mit verschiedenen Eltern bleibt eine nur nach Dimension/Wert hinterlegte Grundmenge offen: Sie lässt sich dem konkreten Teilpfad nicht eindeutig zuordnen. Fehlende historische Grundmengen werden nicht ersetzt. Personen ohne Untereinheitszuordnung können im übergeordneten Ergebnis enthalten sein; die Untereinheiten müssen sich deshalb nicht zum Gesamtergebnis summieren.

## Berichtstexte und Freitexte

In der App können pro OE-Pfad und Bezugswelle «Erkenntnisse auf einen Blick» sowie redaktionelle Texte pro Thema gespeichert werden. Freigegebene Textantworten der aktuellen Welle stehen dort zum Sichten bereit; die Mindestfallzahl gilt je Frage. Die Texte werden nicht automatisch zusammengefasst, codiert oder quantitativ interpretiert. Eigene Zusammenfassungen werden im HTML-Bericht dargestellt und HTML-sicher ausgegeben.

Vollständige Textantworten bleiben standardmässig aus dem Weitergabebericht ausgeschlossen. Die ausdrücklich aktivierte Option nimmt die Texte der aktuellen Welle aufklappbar unter dem jeweiligen Thema auf. Nicht angezeigte Textantworten sind auch nicht im Chart-JSON enthalten. Zusätzlich können pro Themenzusammenfassung Textbelege über Checkboxen ausgewählt und gemeinsam mit dem Text gespeichert werden. Der Fragewortlaut bleibt bei der Auswahl und als Quellenangabe im Bericht sichtbar. Die Auswahl gilt ausschliesslich für die konkrete OE und Welle. Gleiche Texte derselben Frage werden einmal angeboten; dies ist keine Codierung oder Häufigkeitsauswertung.

Die separate Berichtsoption «Ausgewählte Textbelege im Bericht anzeigen» nimmt nur diese ausgewählten Aussagen auf. Ohne diese Option enthält der Bericht keine ausgewählten Zitate; die bestehende Freigabe vollständiger Texte ist davon unabhängig. Es werden nur Referenzen zu den aktuellen Aussagen gespeichert, keine zusätzlichen Textkopien. Ändert sich eine Antwort oder wird sie wegen Mindestfallzahl, Frageausschluss oder Themenwechsel nicht mehr verfügbar, verschwindet der Beleg aus dem Bericht. Die Redaktion zeigt nicht mehr verfügbare Referenzen zur Prüfung an. Eine nicht mehr gültige Auswahl wird beim Speichern vollständig abgewiesen, ohne den bisherigen Berichtstext zu überschreiben. Ein erneutes Speichern der geprüften Auswahl entfernt alte Referenzen.

Ein allgemeines Codierungssystem und qualitative Zeitvergleiche stehen noch aus.

PNG-/ZIP-Exporte enthalten weiterhin drei Grössen, zusätzlich die OE-Vergleichsgrafiken. Die Grafiken nennen Befragung, OE, Fragewortlaut, Zeitpunkte und gültige n; die wiederholten Befragungsmetadaten entfallen in der HTML-Chartdarstellung. Zusätzlich lassen sich Themenverlauf und Themenvergleich als eigene 1920 × 1080-PNGs exportieren; sie werden auch in das vollständige ZIP aufgenommen. Diese Folien enthalten vollständige Fragewortlaute und n je Frage in der Reihenfolge der Legende. Pro Folie stehen höchstens fünf Fragen. Redaktionelle Zusammenfassungen und Freitexte bleiben im HTML-Bericht und werden nicht in diese Grafikexporte übernommen. Der Export eines gesamten Kapitels inklusive redaktioneller Texte bleibt offen.

Validierung: `python -m unittest discover -s tests -q`; 45 Tests. Ergänzt um ausgewählte Textbelege (OE-/Wellenbindung, Opt-in, Mindestfallzahl, Änderungen, atomare Validierung, Dubletten und HTML-Escaping) sowie skalenreine Themenübersichten, Folienaufteilung, fehlende aktuelle Werte sowie Metrik und Legendenauswahl beim Themen-PNG-Export, ausserdem Pfadtrennung, gewichtete Elternwerte, Untereinheiten, Fallzahlschutz, Freitextfreigabe, redaktionelle Texte und Verzeichnisstände. Zusätzlich Berichtserzeugung mit lokalen Puls-AFA-Exporten und tatsächliches PNG-Rendering. Ein vollständiger Browser-Layouttest war in der Ausführungsumgebung nicht möglich (Chromium-Start durch Socket-Beschränkung verhindert).
