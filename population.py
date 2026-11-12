"""Grundgesamtheit aus einer lokalen OE-Liste; keine Mitarbeitendendaten im Programmcode."""
from collections import Counter

POPULATION_FIELDS = {
    'Amt': 'Amt', 'Bereich': 'Bereich', 'Abteilung': 'Abteilung',
    'RAV Gruppe': 'RAV_Gruppe', 'RAV': 'RAV', 'Team': 'Team',
}


def population_from_oe(employee_codes, organisation, amt):
    """Eine Quellzeile zählt eine Person. Gleiche OE-Kürzel werden nicht dedupliziert.

    Benannte Ebenen zählen alle Personen mit dem jeweiligen Pfadmerkmal.
    OE-Kürzel zählen separat die direkte Besetzung, ohne vermutete Elternpfade.
    """
    required={'OE_Kürzel', *POPULATION_FIELDS.values()}
    if not required.issubset(organisation.columns):
        raise ValueError('OE-Liste: Es fehlen Spalten: '+', '.join(sorted(required-set(organisation.columns))))
    reference=organisation.fillna('').astype(str).apply(lambda col: col.str.strip())
    if reference['OE_Kürzel'].eq('').any() or reference['OE_Kürzel'].duplicated().any():
        raise ValueError('Die OE-Liste muss pro OE-Kürzel genau einen nicht leeren Eintrag enthalten.')
    lookup=reference.set_index('OE_Kürzel').to_dict('index')
    codes=[str(code).strip() for code in employee_codes]
    if not codes or any(not code for code in codes):
        raise ValueError('Die Mitarbeitendenliste ist leer oder enthält Zeilen ohne OE-Kürzel.')
    unknown=set(codes)-lookup.keys()
    if unknown:
        raise ValueError(f'{len(unknown)} OE-Kürzel aus der Mitarbeitendenliste fehlen im OE-Verzeichnis. '
                         'Die Grundmengen wurden nicht übernommen: '+', '.join(sorted(unknown)))
    if any(not lookup[code]['Amt'] for code in codes):
        raise ValueError('Mindestens eine besetzte OE hat in der OE-Liste kein Amt.')
    rows=[lookup[code] for code in codes if lookup[code]['Amt']==amt]
    if not rows:
        raise ValueError('Die Mitarbeitendenliste enthält keine zugeordneten Personen für das gewählte Amt.')
    target=reference[reference['Amt'].eq(amt)]
    grounds=[dict(dimension='',unit='',total=len(rows))]
    missing={}
    for dimension,column in POPULATION_FIELDS.items():
        counts=Counter(row[column] for row in rows if row[column])
        for unit in sorted(set(target[column])-{''}):
            grounds.append(dict(dimension=dimension,unit=unit,total=counts[unit]))
        missing[dimension]=sum(not row[column] for row in rows)
    direct=Counter(code for code in codes if lookup[code]['Amt']==amt)
    return dict(total=len(rows),input_rows=len(codes),
                by_amt=dict(Counter(lookup[code]['Amt'] for code in codes)),
                missing=missing,grounds=grounds,
                oe_counts={code:direct[code] for code in sorted(target['OE_Kürzel'])})
