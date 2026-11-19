"""AFA-Grundmengen 2024–2026 aus der Mitarbeitendenliste übernehmen."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
import pandas as pd

from core import content_hash, read_table
from organisation import oe_path
from population import POPULATION_FIELDS, population_from_oe

YEARS = ('2024', '2025', '2026')
DATABASE = Path(__file__).resolve().parent / 'instance' / 'studio.sqlite3'


def read_employees(data):
    workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        populations = {}
        for year in YEARS:
            sheet_name = f'10-{year}'
            if sheet_name not in workbook.sheetnames:
                raise ValueError(f'Tabellenblatt {sheet_name} fehlt.')
            sheet = workbook[sheet_name]
            # Die Quelle enthält formatierte Leerzeilen bis weit unter den Datenbereich.
            sheet.reset_dimensions()
            rows = sheet.iter_rows(max_col=2, values_only=True)
            header = tuple(str(value or '').strip() for value in next(rows, ()))
            if header != (f'OE 10.{year}', 'Kadertyp'):
                raise ValueError(f'{sheet_name}: Erwartet werden die Spalten OE 10.{year} und Kadertyp.')
            employees = []
            for line, (code, cadre) in enumerate(rows, start=2):
                code = str(code or '').strip()
                cadre = '' if cadre is None else str(cadre).strip()
                if not code and not cadre:
                    continue
                if not code or (cadre and cadre not in {'100', '110', '120'}):
                    raise ValueError(f'{sheet_name}, Zeile {line}: OE-Kürzel oder Kadertyp ungültig.')
                employees.append((code, cadre))
            populations[year] = employees
        return populations
    finally:
        workbook.close()


def find_waves(connection):
    surveys = defaultdict(set)
    for project, survey in connection.execute(
        """SELECT DISTINCT project, CAST(json_extract(raw, '$."Survey ID"') AS TEXT)
           FROM answers"""
    ):
        surveys[project].add(survey)
    candidates = [pid for pid, ids in surveys.items() if '2330' in ids]
    if len(candidates) != 1 or surveys[candidates[0]] != {'2330'}:
        raise ValueError('Es muss genau ein Projekt mit ausschliesslich der AFA-Befragung 2330 geben.')
    pid = candidates[0]
    periods = defaultdict(set)
    dates = {}
    for wave, month, first_date in connection.execute(
        'SELECT wave, substr(date,1,7), MIN(date) FROM answers WHERE project=? GROUP BY wave, substr(date,1,7)',
        (pid,),
    ):
        periods[wave].add(month)
        if first_date:
            dates[wave] = min(dates.get(wave, first_date), first_date)
    waves = {}
    for year in YEARS:
        months = {f'{year}-10', f'{year}-11'}
        matched = [wave for wave, months_in_wave in periods.items() if months & months_in_wave]
        if len(matched) != 1 or not periods[matched[0]].issubset(months):
            raise ValueError(f'Oktober/November {year} muss im AFA-Projekt genau einer Welle entsprechen.')
        wave = matched[0]
        waves[year] = (wave, dates[wave][:10])
    return pid, waves


def reference_for_date(connection, date):
    version = connection.execute(
        'SELECT entries FROM organisation_history WHERE valid_from<=? ORDER BY valid_from DESC LIMIT 1', (date,)
    ).fetchone()
    if version:
        rows = json.loads(version[0])
    else:
        rows = [json.loads(row[0]) for row in connection.execute('SELECT attributes FROM organisation ORDER BY code')]
    if not rows:
        raise ValueError('Kein OE-Verzeichnis vorhanden. Bitte die OE-Liste mit --oe-liste angeben.')
    return pd.DataFrame(rows).fillna('')


def count_population(employees, reference):
    population = population_from_oe((code for code, _ in employees), reference, 'AFA')
    if population['total'] != len(employees):
        raise ValueError('Die AFA-Mitarbeitendenliste enthält OE-Kürzel ausserhalb des AFA.')
    dimensions = {column: name for name, column in POPULATION_FIELDS.items()}
    paths = {
        row['OE_Kürzel'].strip(): oe_path({name: row[column].strip() for column, name in dimensions.items()})
        for row in reference.to_dict('records')
    }
    own_leaders = Counter()
    for code, cadre in employees:
        if cadre == '100':
            path = paths[code]
            own_leaders[path[-1]] += 1
            if len(path) == 1:
                own_leaders['', ''] += 1
    grounds = [
        (row['dimension'], row['unit'], row['total'], own_leaders[row['dimension'], row['unit']])
        for row in population['grounds']
    ]
    return population, grounds


def save_wave(connection, pid, wave, grounds, population, source, source_hash, reference_hash):
    for table, column in [('grounds', 2), ('ground_leaders', 3)]:
        connection.executemany(
            f"""INSERT INTO {table} VALUES(?,?,?,?,?)
                ON CONFLICT(project,wave,dimension,unit) DO UPDATE SET total=excluded.total
                WHERE total<>excluded.total""",
            [(pid, wave, dimension, unit, row[column]) for row in grounds for dimension, unit in [row[:2]]],
        )
    connection.execute('DELETE FROM population_oe WHERE project=? AND wave=?', (pid, wave))
    connection.executemany('INSERT INTO population_oe VALUES(?,?,?,?)',
                           [(pid, wave, code, n) for code, n in population['oe_counts'].items()])
    details = {key: population[key] for key in ('total', 'input_rows', 'by_amt', 'missing')}
    connection.execute(
        """INSERT INTO population_snapshots VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(project,wave) DO UPDATE SET source=excluded.source,source_hash=excluded.source_hash,
           reference_hash=excluded.reference_hash,details=excluded.details,created=excluded.created
           WHERE source<>excluded.source OR source_hash<>excluded.source_hash
              OR reference_hash<>excluded.reference_hash OR details<>excluded.details""",
        (pid, wave, source, source_hash, reference_hash, json.dumps(details, sort_keys=True, ensure_ascii=False),
         datetime.now().isoformat(timespec='seconds')),
    )


def run(workbook_path, database, oe_file=None, apply=False):
    uri = database.resolve().as_uri()
    data = workbook_path.read_bytes()
    employees = read_employees(data)
    source_hash = content_hash(data)
    if oe_file:
        reference_data = oe_file.read_bytes()
        override = read_table(reference_data, oe_file.name, sheet='OE Liste')
    with closing(sqlite3.connect(uri + ('?mode=rw' if apply else '?mode=ro'), uri=True)) as connection, connection:
        connection.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
        pid, waves = find_waves(connection)
        prepared = []
        print('Import mit --apply' if apply else 'Vorschau: Es wird nichts gespeichert.')
        for year, (wave, first_date) in waves.items():
            reference = override if oe_file else reference_for_date(connection, first_date)
            try:
                population, grounds = count_population(employees[year], reference)
            except ValueError as exc:
                raise ValueError(f'{year} ({wave}): {exc}') from exc
            digest = content_hash(reference_data if oe_file else
                                  reference.to_json(orient='records', force_ascii=False).encode())
            prepared.append((wave, grounds, population, digest))
            existing = {(d, u): (total, leaders) for d, u, total, leaders in connection.execute(
                """SELECT g.dimension,g.unit,g.total,l.total FROM grounds g
                   LEFT JOIN ground_leaders l USING (project,wave,dimension,unit)
                   WHERE g.project=? AND g.wave=?""", (pid, wave)
            )}
            changed = sum((d, u) in existing and existing[d, u] != (n, heads) for d, u, n, heads in grounds)
            new = sum((d, u) not in existing for d, u, _, _ in grounds)
            _, _, total, heads = grounds[0]
            print(f'{wave}: {total} eingeladen, {heads} eigene Amtsleitung, {total-heads} nach Abzug. '
                  f'{new} Grundmengen neu, {changed} vorhandene Werte mit Änderungen.')
        if apply:
            backup = database.parent / 'backups' / f'vor-afa-grundmengen-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
            backup.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(uri + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(backup)) as destination:
                    source.backup(destination)
            print(f'Sicherung: {backup}')
            for wave, grounds, population, digest in prepared:
                save_wave(connection, pid, wave, grounds, population, workbook_path.name, source_hash, digest)
    if apply:
        print('Grundmengen und Leitungsanteile für alle drei AFA-Wellen gespeichert.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xlsx', type=Path, help='Grundmenge_AFA_2024_bis_2026.XLSX')
    parser.add_argument('--db', type=Path, default=DATABASE, help='Pfad zu studio.sqlite3')
    parser.add_argument('--oe-liste', type=Path, help='Alternative OE_Liste.xlsx statt des gespeicherten OE-Verzeichnisses')
    parser.add_argument('--apply', action='store_true', help='Werte nach Sicherung speichern und vorhandene Einträge aktualisieren')
    args = parser.parse_args()
    try:
        run(args.xlsx, args.db, args.oe_liste, args.apply)
    except (ValueError, OSError, sqlite3.Error, BadZipFile, InvalidFileException) as exc:
        parser.exit(1, f'Import abgebrochen: {exc}\n')
