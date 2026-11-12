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
    'Engagement und Entwicklung': ['Leistungsbereitschaft','Weiterempfehlung','Zugehörigkeit',
        'Entwicklungsmöglichkeiten','Detail Entwicklungsmöglichkeiten'],
    'Führung und Feedback': ['Befähigung Führungsrolle','Detail Führungsrolle','Führungskultur im AFA',
        'Detail Führungskultur','Führungsstil Vorgesetzte/r','Detail Fürhungsstil','Zielvorgaben Vorgesetzte/r',
        'Feedbackkultur','Fehlerkultur','Detail Feedback-/Fehlerkultur','Feedback an GL'],
    'Information und Orientierung': ['ZHub','Detail ZHub','Informationsfluss','Detail Informationsfluss',
        'Geschäftsabläufe','Detail Geschäftsabläufe','Klarheit Strategie','Detail Strategie',
        'Info AFA 2030','Information AFA Flex','Information Detail AFA Flex','Anmerkungen AFA Werte'],
    'Zusammenarbeit und Austausch': ['Austausch AFA','Detail Austausch/Vernetzung',
        'Zusammenarbeit Team','Detail Zusammenarbeit Team'],
    'Arbeitsbedingungen und Gesundheit': ['Anstellungsbedingungen','Anstellungsbedingungen Gründe',
        'Detail Anstellungsbedingungen','Arbeitsbelastung','Über-/Unterbelastung','BGM','BGM2','Detail BGM'],
}
