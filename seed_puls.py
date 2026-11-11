"""Lokale Puls-Einrichtung. Keine Antworten oder Personenkennungen im Quellcode."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from app import create_app, ROOT, DEFAULT_MISSING, DIMENSIONS
from core import read_table, normalize, content_hash, date_value

PRESETS = {
    '2234': ('AWI', [('2024-07','2024-07-01','2024-07-31'),
                     ('2025-01','2025-01-01','2025-01-31'),
                     ('2025-07','2025-06-01','2025-07-31'),
                     ('2026-01','2026-01-01','2026-01-31'),
                     ('2026-07','2026-06-01','2026-07-31')]),
    '2330': ('AFA', [('2024-10','2024-10-01','2024-11-30'),
                     ('2025-10','2025-10-01','2025-11-30'),
                     ('2026-10','2026-10-01','2026-11-30')]),
    '2272': ('GS', [('2024-09','2024-09-01','2024-09-30'),
                    ('2026-08','2026-08-01','2026-08-31')]),
}
# Geprüft anhand von Titel, Fragetyp und vollständigem Wortlaut der gelieferten Exporte.
LINKS = {
    'AFA': [('121868','145757'), ('121869','145760'), ('121871','123139'),
            ('121872','145770'), ('121873','145779'), ('121874','145782'),
            ('121876','145783'), ('121877','145773'), ('121880','145776'),
            ('121882','145789'), ('121883','145794'), ('121884','145786'),
            ('121886','145795'), ('143714','145787'), ('144875','145767')],
    'GS': [('118022','166053')], 'AWI': [],
}
AWI_EXTRA = {'114621','114624','114628','114629','114631','115184'}
REASON = 'AWI Januar 2025: einmalig zusätzlich erhobene Frage; übrige Teilnahme bleibt enthalten.'
SEED_VERSION = 'puls-2026-v1'

# Berichtsausschlüsse gemäss der vom Nutzer geprüften Fragenliste vom 11.11.2026.
REPORT_EXCLUSIONS = {'AWI': {'AWI-06': ('114643',),
         'AWI-07': ('114647',),
         'AWI-08': ('115935',),
         'AWI-09': ('115936',),
         'AWI-17': ('114660',),
         'AWI-18': ('114669',),
         'AWI-19': ('114663',),
         'AWI-20': ('114665',),
         'AWI-21': ('114661',),
         'AWI-22': ('114667',),
         'AWI-23': ('114658',),
         'AWI-24': ('114670',),
         'AWI-25': ('114664',),
         'AWI-26': ('114666',),
         'AWI-27': ('114662',),
         'AWI-28': ('114668',),
         'AWI-36': ('114654',),
         'AWI-37': ('114653',),
         'AWI-51': ('114640',),
         'AWI-52': ('114645',),
         'AWI-53': ('114648',),
         'AWI-54': ('114639',),
         'AWI-55': ('114655',),
         'AWI-56': ('114656',),
         'AWI-57': ('114652',),
         'AWI-58': ('114651',),
         'AWI-59': ('114650',),
         'AWI-60': ('114649',),
         'AWI-75': ('115111',)},
 'AFA': {'AFA-36': ('145098',),
         'AFA-37': ('145115',),
         'AFA-38': ('145120',),
         'AFA-39': ('145121',),
         'AFA-40': ('145116',),
         'AFA-41': ('145117',),
         'AFA-43': ('145118',),
         'AFA-44': ('145119',)}}
EXCLUSIONS_VERSION = 'report-exclusions-2026-v1'



def clean(value):
    return ' '.join(value.replace('\u200b','').replace('\ufeff','').split())


def report_label(value, org):
    label = re.sub(r'\s*\(P(?:AFA|AWI|AFM|GS)\)\s*$', '', clean(value))
    if org == 'GS':
        label = {'Initiative':'Leistungsbereitschaft',
                 'Führungskultur im AWI':'Führungskultur im GS'}.get(label,label)
    return label


def seed_file(c, path, messages):
    data = path.read_bytes()
    df = read_table(data,path.name)
    required = {'Survey ID','Feedback ID','Question ID','Question title','Question type','Question','Answer','Answer given at'}
    if not required.issubset(df.columns):
        messages.append(f'{path.name}: kein Puls-Export, übersprungen.')
        return 0
    surveys = set(df['Survey ID'])
    if len(surveys)!=1 or next(iter(surveys)) not in PRESETS:
        messages.append(f'{path.name}: keine bekannte einzelne Pulsbefragung, übersprungen.')
        return 0
    survey = next(iter(surveys)); org,periods = PRESETS[survey]
    cfg = dict(mode='long',feedback='Feedback ID',qid='Question ID',title='Question title',
               type='Question type',answer='Answer',date='Answer given at',wave='Befragung (object)',
               wave_mode='periods',periods='\n'.join(' | '.join(p) for p in periods))
    records = normalize(df,cfg,content_hash(data))
    # Identifikation auch bei selbst gewähltem Projektnamen; niemals ein anderes Projekt überschreiben.
    candidates = []
    for p in c.execute('SELECT * FROM projects'):
        ids = set()
        for a in c.execute('SELECT raw FROM answers WHERE project=?',(p['id'],)):
            ids.add(json.loads(a['raw']).get('Survey ID',''))
        if survey in ids:
            if ids!={survey}:
                raise ValueError(f'{org}: Projekt enthält mehrere Befragungen. Bitte vor der Einrichtung trennen.')
            candidates.append(p)
    if not candidates:
        candidates = list(c.execute('SELECT * FROM projects WHERE name=?',('Puls '+org,)))
        if any(c.execute('SELECT 1 FROM answers WHERE project=? LIMIT 1',(p['id'],)).fetchone() for p in candidates):
            raise ValueError(f'{org}: gleichnamiges Projekt enthält andere Daten.')
    if len(candidates)>1:
        raise ValueError(f'{org}: mehrere passende Projekte. Bitte vor der Einrichtung zusammenführen oder umbenennen.')
    if candidates:
        p = candidates[0]; pid = p['id']
    else:
        pid = c.execute('INSERT INTO projects(name,kind) VALUES(?,?)',('Puls '+org,'echonovum')).lastrowid
    done = c.execute('SELECT 1 FROM seed_runs WHERE project=? AND version=?',(pid,SEED_VERSION)).fetchone()
    # Bestehende Wellenbezeichnungen übernehmen, sofern die Zuordnung eindeutig ist.
    known = defaultdict(set)
    for a in c.execute('SELECT DISTINCT feedback,wave FROM answers WHERE project=?',(pid,)):
        known[a['feedback']].add(a['wave'])
    wave_map = {}
    for wave,_,_ in periods:
        names = set().union(*(known[r['feedback']] for r in records if r['wave']==wave))
        if len(names)>1:
            raise ValueError(f'{org} {wave}: bereits auf mehrere Wellen verteilt. Bitte zuerst Wellen bereinigen; es wurden keine Seed-Änderungen übernommen.')
        wave_map[wave] = next(iter(names)) if names else wave
    active_waves={r['wave'] for r in records}
    mapped=[wave_map[w] for w in active_waves]
    if len(set(mapped))!=len(mapped):
        raise ValueError(f'{org}: mehrere Erhebungszeiträume liegen bereits in derselben Welle. Bitte zuerst trennen.')
    cfg['periods']='\n'.join(' | '.join([wave_map[w],a,b]) for w,a,b in periods)
    excluded_sources={source for sources in REPORT_EXCLUSIONS.get(org,{}).values() for source in sources}
    excluded_done=c.execute('SELECT 1 FROM seed_runs WHERE project=? AND version=?',(pid,EXCLUSIONS_VERSION)).fetchone()
    messages.append(f'\nPuls {org} (Projekt {pid})')
    for r in records:
        r['wave']=wave_map[r['wave']]
        c.execute('INSERT OR IGNORE INTO questions(project,source,canonical,label,type,missing,include) VALUES(?,?,?,?,?,?,?)',
                  (pid,r['source'],r['source'],r['title'],r['type'],DEFAULT_MISSING,int(r['source'] not in excluded_sources)))
        # Seed ergänzt; ein erneuter Lauf überschreibt keine schon gespeicherten Antworten.
        c.execute('INSERT OR IGNORE INTO answers VALUES(?,?,?,?,?,?,?)',
                  (pid,r['wave'],r['feedback'],r['source'],r['answer'],r['date'],json.dumps(r['raw'],ensure_ascii=False)))
    c.execute("UPDATE projects SET config=? WHERE id=? AND config='{}'",(json.dumps(cfg,ensure_ascii=False),pid))
    if not c.execute('SELECT 1 FROM imports WHERE project=? AND hash=?',(pid,content_hash(data))).fetchone():
        c.execute('INSERT INTO imports(project,filename,hash,rows) VALUES(?,?,?,?)',(pid,path.name,content_hash(data),len(records)))
    # Nur unveränderte Originalbezeichnungen bereinigen. Eigene Berichtstitel bleiben erhalten.
    for source,g in df.groupby('Question ID',sort=False):
        q = c.execute('SELECT * FROM questions WHERE project=? AND source=?',(pid,source)).fetchone()
        original_titles = set(g['Question title'])
        if q['label'] in original_titles:
            latest=g.assign(_date=g['Answer given at'].map(date_value)).sort_values('_date').iloc[-1]
            c.execute('UPDATE questions SET label=? WHERE project=? AND source=?',
                      (report_label(latest['Question title'],org),pid,source))
    for a,b in LINKS[org]:
        members=list(c.execute('SELECT * FROM questions WHERE project=? AND source IN (?,?) ORDER BY source',(pid,a,b)))
        if len(members)!=2 or members[0]['canonical']==members[1]['canonical']:
            continue
        # Eigene Gruppen und abweichende Berechnungs-/Berichtseinstellungen erhalten.
        fields=('label','type','theme','minimum','maximum','top_from','missing','missing_override','options','include')
        if any(q['canonical']!=q['source'] for q in members) or any(members[0][k]!=members[1][k] for k in fields):
            messages.append(f'  Verknüpfung {a}/{b}: eigene Einstellungen, bitte prüfen.'); continue
        left={clean(v) for v in df.loc[df['Question ID'].eq(a),'Question']}
        right={clean(v) for v in df.loc[df['Question ID'].eq(b),'Question']}
        if not left.intersection(right):
            messages.append(f'  Verknüpfung {a}/{b}: Wortlaut nicht bestätigt, bitte prüfen.'); continue
        overlap=c.execute('SELECT 1 FROM answers WHERE project=? AND source IN (?,?) GROUP BY wave,feedback HAVING COUNT(*)>1 LIMIT 1',(pid,a,b)).fetchone()
        if overlap:
            messages.append(f'  Verknüpfung {a}/{b}: gleichzeitige Antworten, getrennt belassen.'); continue
        c.execute('UPDATE questions SET canonical=? WHERE project=? AND source=?',(a,pid,b))
        messages.append(f'  Verknüpft: {members[0]["label"]} ({a}, {b}).')
    if excluded_sources and not excluded_done:
        canonical={q['canonical'] for q in c.execute('SELECT source,canonical FROM questions WHERE project=?',(pid,)) if q['source'] in excluded_sources}
        for key in canonical:
            c.execute('UPDATE questions SET include=0 WHERE project=? AND canonical=?',(pid,key))
        c.execute('INSERT OR IGNORE INTO seed_runs VALUES(?,?,?)',(pid,EXCLUSIONS_VERSION,datetime.now().isoformat()))
        messages.append(f'  Berichtsausschlüsse übernommen: {len(canonical)} vorhandene Berichtsfragen; Rohdaten erhalten.')
    # Nur der geprüfte Ausnahmefall, nicht generell alle kleinen Stichproben.
    if org=='AWI' and not done:
        wave=wave_map['2025-01']
        counts={r['source']:r['n'] for r in c.execute('SELECT source,COUNT(DISTINCT feedback) n FROM answers WHERE project=? AND wave=? GROUP BY source',(pid,wave))}
        people={r['feedback'] for r in c.execute('SELECT source,feedback FROM answers WHERE project=? AND wave=?',(pid,wave)) if r['source'] in AWI_EXTRA}
        if all(counts.get(s)==1 for s in AWI_EXTRA) and len(people)==1:
            for source in sorted(AWI_EXTRA):
                c.execute('INSERT OR IGNORE INTO question_exclusions VALUES(?,?,?,?)',(pid,source,wave,REASON))
            messages.append(f'  {wave}: sechs Zusatzfragen der einzelnen Teilnahme ausgeschlossen; Rücklauf unverändert.')
        else:
            messages.append('  Januar-Ausnahme nicht eindeutig bestätigt: kein automatischer Ausschluss.')
    # Benannte Merkmale als sichere Ausgangsbasis; keine pauschale HS-Spaltenlogik/AI-AZ-Umbenennung.
    for wave in sorted(set(mapped)):
        sample=[r for r in records if r['wave']==wave]
        for dimension in DIMENSIONS:
            source=dimension+' (subject)'
            if any(r['raw'].get(source,'').strip() for r in sample):
                c.execute('INSERT OR IGNORE INTO mappings(project,wave,dimension,source) VALUES(?,?,?,?)',(pid,wave,dimension,source))
        messages.append(f'  {wave}: {len({r["feedback"] for r in sample})} abgeschlossene Teilnahmen im Export.')
    missing_options=c.execute("SELECT COUNT(DISTINCT canonical) FROM questions WHERE project=? AND type='choice_multiple' AND options=''",(pid,)).fetchone()[0]
    if missing_options:
        messages.append(f'  Offen: Antwortoptionen für {missing_options} Mehrfachauswahlfragen; Export enthält keinen verlässlichen Optionskatalog.')
    messages.append('  Offen: historische OE-Konflikte/HS-Felder prüfen; heutige OE-Liste ersetzt keine historische Zuordnung.')
    c.execute('INSERT OR IGNORE INTO seed_runs VALUES(?,?,?)',(pid,SEED_VERSION,datetime.now().isoformat()))
    return 1



def reset_projects(c, paths, messages):
    """Nur Pulsprojekte löschen, für die im selben Lauf ein geprüfter Export vorliegt."""
    surveys=set()
    for path in paths:
        data=read_table(path.read_bytes(),path.name)
        if 'Survey ID' not in data:
            continue
        ids=set(data['Survey ID'])
        if len(ids)==1 and next(iter(ids)) in PRESETS:
            # Vor dem Zurücksetzen auch Wellen/IDs/Zeilen prüfen.
            survey=next(iter(ids))
            _,periods=PRESETS[survey]
            cfg=dict(mode='long',feedback='Feedback ID',qid='Question ID',title='Question title',
                     type='Question type',answer='Answer',date='Answer given at',wave_mode='periods',
                     periods='\n'.join(' | '.join(p) for p in periods))
            required={'Feedback ID','Question ID','Question title','Question type','Question','Answer','Answer given at'}
            if not required.issubset(data.columns):
                raise ValueError(f'{path.name}: unvollständiger Puls-Export; kein Neustart.')
            if not normalize(data,cfg,content_hash(path.read_bytes())):
                raise ValueError(f'{path.name}: leerer Export; kein Neustart.')
            surveys.add(survey)
    if not surveys:
        raise ValueError('Keine gültigen Puls-Exporte für einen Neustart gefunden.')
    names={'Puls '+PRESETS[s][0] for s in surveys}
    if '2330' in surveys:
        names.add('Puls AWA')
    targets=[]
    for project in c.execute('SELECT * FROM projects'):
        ids={json.loads(a['raw']).get('Survey ID','') for a in c.execute('SELECT raw FROM answers WHERE project=?',(project['id'],))}
        if ids & surveys:
            if not ids.issubset(surveys):
                raise ValueError('Ein Pulsprojekt enthält zusätzliche Befragungen. Kein automatischer Neustart.')
            targets.append(project)
        elif not ids and project['kind']=='echonovum' and project['name'].strip().casefold() in {n.casefold() for n in names}:
            targets.append(project)
    for project in targets:
        pid=project['id']
        for table in ('staged','answers','questions','mappings','aliases','grounds','imports',
                      'question_settings','question_exclusions','seed_runs'):
            c.execute(f'DELETE FROM {table} WHERE project=?',(pid,))
        c.execute('DELETE FROM projects WHERE id=?',(pid,))
        messages.append(f'Zurückgesetzt: {project["name"]} (Projekt {pid}).')
    messages.append('Neustart: nur die mitgelieferten Pulsreihen; andere Projekte und OE-Verzeichnis bleiben erhalten.')


def run(input_dir, instance, dry_run=False, reset_puls=False):
    input_dir=Path(input_dir);instance=Path(instance)
    paths=sorted(input_dir.glob('*.csv'))
    if not paths: raise ValueError('Im gewählten Ordner sind keine CSV-Dateien.')
    messages=[]
    # Vorschau arbeitet mit einer Kopie; selbst Migrationen verändern die Originaldatenbank nicht.
    with tempfile.TemporaryDirectory() as tmp:
        target=Path(tmp) if dry_run else instance
        dbpath=instance/'studio.sqlite3'
        if dbpath.exists():
            backup=Path(tmp)/'studio.sqlite3' if dry_run else instance/'backups'/('vor-puls-seed-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
            backup.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(dbpath) as src, sqlite3.connect(backup) as dest: src.backup(dest)
            if not dry_run:messages.append('Sicherung: '+str(backup))
        create_app(target)
        with sqlite3.connect(target/'studio.sqlite3') as c:
            c.row_factory=sqlite3.Row
            c.execute('CREATE TABLE IF NOT EXISTS seed_runs(project INTEGER,version TEXT,created TEXT,PRIMARY KEY(project,version))')
            if reset_puls:
                # Schema-DDL vorher; danach Reset und Neueinrichtung in einer Transaktion.
                c.execute('BEGIN')
                reset_projects(c,paths,messages)
            count=sum(seed_file(c,p,messages) for p in paths)
            oe=input_dir/'OE_Liste.xlsx'
            if oe.exists() and count:
                frame=read_table(oe.read_bytes(),oe.name,sheet='OE Liste')
                if 'OE_Kürzel' not in frame: raise ValueError('OE-Liste: Spalte OE_Kürzel fehlt.')
                for row in frame.to_dict('records'):
                    if row['OE_Kürzel'].strip():
                        c.execute('INSERT OR IGNORE INTO organisation VALUES(?,?)',(row['OE_Kürzel'],json.dumps(row,ensure_ascii=False)))
                messages.append('OE-Liste als Referenz ergänzt; vorhandene Einträge erhalten.')
            if not count: raise ValueError('Keine der drei bekannten Pulsbefragungen im Ordner gefunden.')
        text=('VORSCHAU – keine Änderungen gespeichert.\n' if dry_run else 'Puls-Einrichtung gespeichert.\n')+'\n'.join(messages)
        if not dry_run:(instance/'seed_puls_report.txt').write_text(text,encoding='utf-8')
        return text


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Drei bestehende Pulsreihen vorbereiten; App vorher beenden.')
    parser.add_argument('--input-dir',type=Path,help='Ordner mit CSV-Exporten und optional OE_Liste.xlsx')
    parser.add_argument('--instance',type=Path,default=ROOT/'instance')
    parser.add_argument('--reset-puls',action='store_true',help='Mitgelieferte Pulsreihen nach Sicherung löschen und neu einrichten')
    parser.add_argument('--dry-run',action='store_true',help='Vorschau ohne Änderung der Datenbank')
    args=parser.parse_args()
    try:
        folder=args.input_dir or Path(input('Ordner mit den Puls-Exporten: ').strip().strip('"'))
        print(run(folder,args.instance,args.dry_run,args.reset_puls))
    except (ValueError,sqlite3.Error,OSError) as e:
        parser.exit(1,'Einrichtung abgebrochen: '+str(e)+'\n')
