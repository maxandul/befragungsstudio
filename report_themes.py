"""Themenvorschlag und kompakte, skalenreine Berichtsübersichten."""


def topic_overviews(cards, reference_wave, limit=5):
    """Gruppe nur vergleichbare Skalen; historische Werte ersetzen keine aktuellen."""
    groups = {}
    for index, card in enumerate(cards):
        if card['rows'][0]['type'] != 'scale':
            continue
        scales = {(r['minimum'], r['maximum']) for r in card['rows']}
        if len(scales) != 1:
            continue
        minimum, maximum = next(iter(scales))
        groups.setdefault((card['theme'], minimum, maximum), []).append(index)
    overviews = []
    for (theme, minimum, maximum), indices in groups.items():
        for start in range(0, len(indices), limit):
            overviews.append(dict(theme=theme, indices=indices[start:start+limit],
                                  minimum=minimum, maximum=maximum,
                                  reference_wave=reference_wave,
                                  part=start//limit+1, parts=(len(indices)+limit-1)//limit))
    return overviews


AFA_THEMES = {
    'Engagement und Entwicklung': ['Leistungsbereitschaft','Weiterempfehlung','Zugehörigkeit'],
    'Führung und Feedback': ['Befähigung Führungsrolle','Detail Führungsrolle','Führungskultur im AFA',
        'Detail Führungskultur','Führungsstil Vorgesetzte/r','Detail Fürhungsstil','Zielvorgaben Vorgesetzte/r',
        'Feedbackkultur','Fehlerkultur','Detail Feedback-/Fehlerkultur','Feedback an GL'],
    'Information und Orientierung': ['ZHub','Detail ZHub','Informationsfluss','Detail Informationsfluss',
        'Geschäftsabläufe','Detail Geschäftsabläufe','Klarheit Strategie','Detail Strategie',
        'Info AFA 2030','Information AFA Flex','Information Detail AFA Flex','Anmerkungen AFA Werte'],
    'Zusammenarbeit und Austausch': ['Austausch AFA','Detail Austausch/Vernetzung',
        'Zusammenarbeit Team','Detail Zusammenarbeit Team'],
    'Arbeitsbedingungen und Gesundheit': ['Anstellungsbedingungen','Anstellungsbedingungen Gründe',
        'Detail Anstellungsbedingungen','Entwicklungsmöglichkeiten','Detail Entwicklungsmöglichkeiten',
        'Arbeitsbelastung','Über-/Unterbelastung','BGM2','Detail BGM','BGM'],
}

# Geprüfte Zuordnung der AFA-Quellfragen; IDs anderer Befragungen werden nicht verwendet.
AFA_TEXT_PARENTS = {'144795':'121873','144791':'121884','144789':'121883',
    '144787':'121882','171494':'121886','144798':'121877','144802':'121869',
    '144800':'143715','144804':'121868','171495':'121876','144793':'121874',
    '144797':'121880','144807':'144875','145766':'121872','121972':'121872'}
AFA_PARENT_ALIASES = {'121873':'145779','121884':'145786','121883':'145794',
    '121882':'145789','121886':'145795','121877':'145773','121869':'145760',
    '121868':'145757','121876':'145783','121874':'145782','121880':'145776',
    '144875':'145767','121872':'145770'}

# Exakte, in den gelieferten BGM2-Exporten vorhandene Optionen beider Wortlautversionen.
# Kommas innerhalb der vollständigen Option bleiben erhalten. Keine Freitextzerlegung.
AFA_BGM_OPTIONS = ['Hohe Arbeitsmenge oder Zeitdruck','Personelle Unterbesetzung',
    'Unklare Prozesse oder ineffiziente Abläufe','Technische Probleme oder unzuverlässige IT-Systeme',
    'Physische Arbeitsbedingungen (z. B. Raumklima, Luft, Lärm, Licht, Möbel)',
    'Emotionale Belastung','Emotionale Belastung durch anspruchsvolle Kund:innen oder Fälle',
    'Fehlende Wertschätzung oder Unterstützung','Fehlende Wertschätzung oder Unterstützung durch Vorgesetzte',
    'Mangelnde Kommunikation oder Informationsfluss','Schwieriges Arbeitsklima oder Konflikte',
    'Schwieriges Arbeitsklima oder Konflikte im Team',
    'Unsicherheit durch Veränderungen oder fehlende Klarheit zur Zukunft',
    'Ungleich verteilte Aufgaben oder fehlende Fairness','Fehlende Entwicklungsmöglichkeiten / Perspektiven',
    'Erschwerte Vereinbarkeit von Beruf und Privatleben',
    'Nein, aktuell wirkt sich kein Aspekt negativ auf meine Gesundheit aus','Kommentar hinzufügen']


def apply_afa_report_defaults(c):
    """Einmalige Ergänzung bestehender AFA-Einrichtungen, auch nach einem Seed-Import."""
    pids=[r[0] for r in c.execute('''SELECT DISTINCT project FROM answers
        WHERE source IN ('121873','145779','144875','145767')
        AND json_extract(raw,'$."Survey ID"')='2330' ''')]
    for pid in pids:
        if c.execute("SELECT 1 FROM report_migrations WHERE project=? AND version='report-details-1'",(pid,)).fetchone():
            continue
        rows=list(c.execute('SELECT source,canonical,label,theme FROM questions WHERE project=?',(pid,)))
        canonical={r[0]:r[1] for r in rows}
        for source,key,label,theme in rows:
            for topic,labels in AFA_THEMES.items():
                if label in labels:
                    if not theme or (label in ['Entwicklungsmöglichkeiten','Detail Entwicklungsmöglichkeiten'] and theme=='Engagement und Entwicklung'):
                        c.execute('UPDATE questions SET theme=? WHERE project=? AND canonical=?',(topic,pid,key))
                    c.execute('UPDATE questions SET sort_order=? WHERE project=? AND canonical=? AND sort_order=0',((labels.index(label)+1)*10,pid,key))
                    break
            parent_source=AFA_TEXT_PARENTS.get(source)
            parent_key=canonical.get(parent_source) or canonical.get(AFA_PARENT_ALIASES.get(parent_source))
            if parent_key:
                c.execute("UPDATE questions SET text_parent=? WHERE project=? AND canonical=? AND text_parent=''",
                          (parent_key,pid,key))
            if source in ['144875','145767']:
                c.execute("UPDATE questions SET options=? WHERE project=? AND canonical=? AND type='choice_multiple' AND options=''",
                          ('\n'.join(AFA_BGM_OPTIONS),pid,key))
        c.execute("INSERT INTO report_migrations VALUES(?,'report-details-1')",(pid,))
