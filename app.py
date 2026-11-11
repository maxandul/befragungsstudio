from __future__ import annotations
import io
import json
import secrets
import sqlite3
from pathlib import Path
from werkzeug.exceptions import HTTPException

from flask import (Flask, abort, flash, redirect, render_template, request, send_file, jsonify,
                   session, url_for)
from core import read_table, normalize, content_hash, aggregate

ROOT = Path(__file__).resolve().parent
DIMENSIONS = ['Amt', 'Bereich', 'Abteilung', 'RAV Gruppe', 'RAV', 'Team']
TYPES = {'ignore': 'Nicht auswerten', 'scale': 'Skala', 'choice_single': 'Einfachauswahl',
         'choice_multiple': 'Mehrfachauswahl', 'yesno': 'Ja/Nein', 'text': 'Freitext'}
DEFAULT_MISSING = 'Keine Antwort\nKeine Anmerkung\nKann ich noch nicht beurteilen\nN. v.'


def create_app(instance=None):
    app = Flask(__name__)
    data_dir = Path(instance or ROOT / 'instance')
    data_dir.mkdir(parents=True, exist_ok=True)
    key = data_dir / 'secret.key'
    if not key.exists():
        key.write_text(secrets.token_hex(32))
    app.secret_key = key.read_text()
    app.config.update(MAX_CONTENT_LENGTH=60*1024*1024, SESSION_COOKIE_HTTPONLY=True,
                      MAX_FORM_PARTS=20000,MAX_FORM_MEMORY_SIZE=5*1024*1024,
                      SESSION_COOKIE_NAME='befragungsstudio_session',
                      SESSION_COOKIE_SAMESITE='Strict', DATA_DIR=data_dir)

    def db():
        conn = sqlite3.connect(data_dir / 'studio.sqlite3')
        conn.row_factory = sqlite3.Row
        return conn

    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,
          config TEXT NOT NULL DEFAULT '{}',min_n INTEGER NOT NULL DEFAULT 5);
        CREATE TABLE IF NOT EXISTS staged(id TEXT PRIMARY KEY,project INTEGER,filename TEXT,hash TEXT,content TEXT);
        CREATE TABLE IF NOT EXISTS answers(project INTEGER,wave TEXT,feedback TEXT,source TEXT,
          answer TEXT,date TEXT,raw TEXT,PRIMARY KEY(project,wave,feedback,source));
        CREATE TABLE IF NOT EXISTS questions(project INTEGER,source TEXT,canonical TEXT,label TEXT,
          type TEXT,theme TEXT DEFAULT '',minimum REAL DEFAULT 1,maximum REAL DEFAULT 5,
          top_from REAL DEFAULT 4,missing TEXT,options TEXT DEFAULT '',include INTEGER DEFAULT 1,
          PRIMARY KEY(project,source));
        CREATE TABLE IF NOT EXISTS mappings(id INTEGER PRIMARY KEY,project INTEGER,wave TEXT,
          dimension TEXT,source TEXT,UNIQUE(project,wave,dimension));
        CREATE TABLE IF NOT EXISTS aliases(id INTEGER PRIMARY KEY,project INTEGER,wave TEXT,
          dimension TEXT,source TEXT,target TEXT,UNIQUE(project,wave,dimension,source));
        CREATE TABLE IF NOT EXISTS grounds(project INTEGER,wave TEXT,dimension TEXT,unit TEXT,
          total INTEGER NOT NULL,PRIMARY KEY(project,wave,dimension,unit));
        CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,project INTEGER,filename TEXT,
          hash TEXT,rows INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS organisation(code TEXT PRIMARY KEY,attributes TEXT);
        CREATE TABLE IF NOT EXISTS question_exclusions(project INTEGER,source TEXT,wave TEXT,reason TEXT,
          PRIMARY KEY(project,source,wave));
        CREATE TABLE IF NOT EXISTS question_settings(project INTEGER PRIMARY KEY,missing TEXT NOT NULL);
        ''')
        if 'missing_override' not in [r[1] for r in c.execute('PRAGMA table_info(questions)')]:
            c.execute('ALTER TABLE questions ADD COLUMN missing_override INTEGER NOT NULL DEFAULT 0')
            c.execute('UPDATE questions SET missing_override=1 WHERE missing != ?', (DEFAULT_MISSING,))

    def project(pid):
        with db() as c:
            p = c.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
        if not p:
            abort(404)
        return dict(p)

    def context(pid):
        p = project(pid)
        with db() as c:
            waves = [r[0] for r in c.execute('SELECT DISTINCT wave FROM answers WHERE project=? ORDER BY wave', (pid,))]
            columns = set()
            for r in c.execute('SELECT DISTINCT raw FROM answers WHERE project=?', (pid,)):
                columns.update(json.loads(r[0]))
        return dict(p=p, waves=waves, columns=sorted(columns), dimensions=DIMENSIONS, types=TYPES)

    def results(pid, dimension='', unit=''):
        with db() as c:
            records = [dict(r) for r in c.execute('SELECT * FROM answers WHERE project=?', (pid,))]
            for r in records:
                r['raw'] = json.loads(r['raw'])
            qs = {r['source']: dict(r) for r in c.execute('SELECT * FROM questions WHERE project=?', (pid,))}
            setting=c.execute('SELECT missing FROM question_settings WHERE project=?',(pid,)).fetchone()
            common_missing=setting[0] if setting else DEFAULT_MISSING
            for q in qs.values():
                if not q['missing_override']:
                    q['missing']=common_missing
            mappings = [dict(r) for r in c.execute("SELECT * FROM mappings WHERE project=? ORDER BY (wave != '*'),id", (pid,))]
            aliases = [dict(r) for r in c.execute("SELECT * FROM aliases WHERE project=? ORDER BY (wave != '*'),id", (pid,))]
            grounds = [dict(r) for r in c.execute('SELECT * FROM grounds WHERE project=?', (pid,))]
            exclusions={(r['source'],r['wave']) for r in c.execute('SELECT source,wave FROM question_exclusions WHERE project=?',(pid,))}
        rows, participation = aggregate(records, qs, mappings, aliases, dimension, unit, exclusions)
        return rows, participation, grounds

    @app.before_request
    def protect():
        session.setdefault('csrf', secrets.token_hex(24))
        if request.method == 'POST' and request.form.get('csrf') != session['csrf']:
            if request.accept_mimetypes.best=='application/json':
                return jsonify(error='Die Formularsitzung wurde erneuert. Ihre Änderungen wurden noch nicht verarbeitet.',
                               code='csrf_expired'),400
            abort(400, 'Formular abgelaufen. Bitte Seite neu laden.')

    @app.get('/session/csrf')
    def session_token():
        # Gleicher Ursprung; keine Freigabe per CORS. Erlaubt die Erneuerung ohne Formularverlust.
        return jsonify(csrf=session['csrf'])

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def bad_input(error):
        if request.accept_mimetypes.best=='application/json':
            return jsonify(error=str(error)),400
        return render_template('error.html', error=str(error)), 400

    @app.errorhandler(413)
    def too_large(error):
        if request.accept_mimetypes.best=='application/json':
            return jsonify(error='Die Anfrage ist zu gross. Bitte weniger Fragen auf einmal übertragen.',code='request_too_large'),413
        return render_template('error.html', error='Die Datei ist grösser als 60 MB.'), 413

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.accept_mimetypes.best=='application/json':
            return jsonify(error=error.description,code='http_error'),error.code
        return render_template('error.html',error=error.description),error.code

    @app.errorhandler(500)
    def server_error(error):
        import traceback
        from datetime import datetime
        reference=secrets.token_hex(4)
        original=getattr(error,'original_exception',None) or error
        try:
            with (data_dir/'app.log').open('a',encoding='utf-8') as log:
                log.write(f'\n{datetime.now().isoformat()} Fehler {reference}\n')
                log.write(''.join(traceback.format_exception(original)))
        except OSError:
            pass
        message=f'Serverfehler beim Verarbeiten. Kennung: {reference}. Details stehen in instance/app.log. Ihre Eingaben bleiben im Formular.'
        if request.accept_mimetypes.best=='application/json':
            return jsonify(error=message,code='server_error',reference=reference),500
        return render_template('error.html',error=message),500

    @app.route('/')
    def home():
        with db() as c:
            projects = [dict(r) for r in c.execute('SELECT * FROM projects ORDER BY name')]
        return render_template('home.html', projects=projects, kind=request.args.get('kind', 'echonovum'))

    @app.post('/projects')
    def new_project():
        name = request.form['name'].strip()
        kind = request.form['kind']
        if not name or kind not in ('echonovum', 'other'):
            raise ValueError('Name und Bereich auswählen.')
        with db() as c:
            pid = c.execute('INSERT INTO projects(name,kind) VALUES(?,?)', (name, kind)).lastrowid
        return redirect(url_for('overview', pid=pid))

    @app.route('/p/<int:pid>')
    def overview(pid):
        ctx = context(pid)
        with db() as c:
            imports = c.execute('SELECT * FROM imports WHERE project=? ORDER BY id DESC', (pid,)).fetchall()
            counts = c.execute('SELECT wave,COUNT(DISTINCT feedback) n,COUNT(*) answers FROM answers WHERE project=? GROUP BY wave', (pid,)).fetchall()
        return render_template('overview.html', **ctx, imports=imports, counts=counts, tab='overview')

    @app.post('/p/<int:pid>/upload')
    def upload(pid):
        project(pid)
        file = request.files['file']
        if not file.filename:
            raise ValueError('Bitte eine Datei auswählen.')
        data = file.read()
        sheet = request.form.get('sheet', '').strip()
        df = read_table(data, file.filename, sheet or 0)
        token = secrets.token_hex(16)
        with db() as c:
            c.execute('INSERT INTO staged VALUES(?,?,?,?,?)',
                      (token, pid, Path(file.filename).name, content_hash(data), df.to_json(orient='split')))
        return redirect(url_for('configure', pid=pid, token=token))

    @app.route('/p/<int:pid>/import/<token>', methods=['GET', 'POST'])
    def configure(pid, token):
        import pandas as pd
        p = project(pid)
        with db() as c:
            staged = c.execute('SELECT * FROM staged WHERE id=? AND project=?', (token, pid)).fetchone()
        if not staged:
            abort(404)
        df = pd.read_json(io.StringIO(staged['content']), orient='split', dtype=False).fillna('').astype(str)
        saved = json.loads(p['config'])
        if request.method == 'POST':
            cfg = {k: request.form.get(k, '') for k in ['mode','feedback','qid','title','type','answer','date','wave','fixed_wave','periods','wave_mode']}
            if cfg['wave_mode']=='periods' and 'period_name' in request.form:
                period_rows=zip(request.form.getlist('period_name'),request.form.getlist('period_start'),request.form.getlist('period_end'))
                cfg['periods']='\n'.join(' | '.join(row) for row in period_rows if any(value.strip() for value in row))
            cfg['questions'] = {col: request.form.get(f'q_{i}', 'ignore') for i,col in enumerate(df.columns)}
            records = normalize(df, cfg, staged['hash'])
            # Erst Vorschau; Originaldaten bleiben bis zur expliziten Übernahme unberührt.
            if request.form.get('commit') != 'yes':
                return render_template('confirm.html', p=p, token=token, cfg=cfg,
                    count=len(records), feedbacks=len({(r['wave'],r['feedback']) for r in records}),
                    wave_counts={w:len({r['feedback'] for r in records if r['wave']==w}) for w in sorted({r['wave'] for r in records})}, tab='overview')
            with db() as c:
                for r in records:
                    typ = r['type'] if r['type'] in TYPES else 'text'
                    c.execute('''INSERT OR IGNORE INTO questions(project,source,canonical,label,type,missing)
                      VALUES(?,?,?,?,?,?)''', (pid,r['source'],r['source'],r['title'],typ,
                      'Keine Antwort\nKeine Anmerkung\nKann ich noch nicht beurteilen\nN. v.'))
                    c.execute('''INSERT INTO answers VALUES(?,?,?,?,?,?,?) ON CONFLICT(project,wave,feedback,source)
                      DO UPDATE SET answer=excluded.answer,date=excluded.date,raw=excluded.raw''',
                      (pid,r['wave'],r['feedback'],r['source'],r['answer'],r['date'],json.dumps(r['raw'],ensure_ascii=False)))
                c.execute('UPDATE projects SET config=? WHERE id=?', (json.dumps(cfg),pid))
                c.execute('INSERT INTO imports(project,filename,hash,rows) VALUES(?,?,?,?)',
                          (pid,staged['filename'],staged['hash'],len(records)))
                c.execute('DELETE FROM staged WHERE id=?',(token,))
            flash('Daten übernommen. Bekannte Antworten wurden aktualisiert; neue wurden ergänzt.')
            return redirect(url_for('questions', pid=pid))
        defaults = {'mode':'long' if p['kind']=='echonovum' else 'wide', 'feedback':'Feedback ID',
                    'qid':'Question ID','title':'Question title','type':'Question type','answer':'Answer',
                    'date':'Answer given at','wave':'Befragung (object)',
                    'wave_mode':'month' if p['kind']=='echonovum' else 'fixed'}
        defaults.update(saved)
        if saved and not saved.get('wave_mode'):
            defaults['wave_mode']='legacy'
        from core import parse_rules, date_value
        period_rows=[dict(name=n,start=a,end=b) for n,a,b in parse_rules(defaults.get('periods',''))]
        months={}
        if defaults.get('date') in df.columns:
            for value in df[defaults['date']].unique():
                try:
                    date=date_value(value)
                    if date:
                        months[date[:7]]=True
                except ValueError:
                    pass
        period_rows += [dict(name='',start='',end='') for _ in range(3)]
        return render_template('configure.html', p=p, columns=list(df.columns), sample=df.head(3).values.tolist(),
                               cfg=defaults, types=TYPES, filename=staged['filename'], tab='overview',
                               period_rows=period_rows, months=sorted(months))

    @app.route('/p/<int:pid>/questions', methods=['GET','POST'])
    def questions(pid):
        ctx = context(pid)
        with db() as c:
            qs = [dict(r) for r in c.execute('SELECT * FROM questions WHERE project=? ORDER BY theme,label,source', (pid,))]
            groups={}
            for q in qs:
                groups.setdefault(q['canonical'],[]).append(q)
            setting=c.execute('SELECT missing FROM question_settings WHERE project=?',(pid,)).fetchone()
            common_missing=setting[0] if setting else DEFAULT_MISSING
            if request.method == 'POST':
                f=request.form
                # Vor Änderungen wird alles geprüft; bei Fehler bleibt die Transaktion unverändert.
                pending=[]
                keys=f.getlist('group_key')
                if len(keys)!=len(set(keys)) or set(keys)!=set(groups):
                    raise ValueError('Die Fragenliste hat sich geändert. Bitte Änderungen sichern und die Seite neu laden.')
                common_missing=f.get('common_missing',common_missing).strip()
                for i,key in enumerate(keys):
                    def value(field):
                        return f.get(f'{field}_{i}','')
                    try:
                        lo,hi,top=[float(value(k)) for k in ('minimum','maximum','top_from')]
                    except ValueError:
                        raise ValueError('Bitte gültige Zahlen für die Skala angeben.')
                    import math
                    if not all(math.isfinite(n) for n in (lo,hi,top)) or lo>=hi or not lo<=top<=hi:
                        raise ValueError(f'Skalengrenzen oder Zustimmungsgrenze prüfen: {value("label")}')
                    typ,label=value('type'),value('label').strip()
                    if typ not in TYPES or typ=='ignore' or not label:
                        raise ValueError('Jede Frage benötigt eine Bezeichnung und einen gültigen Typ.')
                    pending.append(dict(canonical=key,label=label,type=typ,theme=value('theme').strip(),
                        minimum=lo,maximum=hi,top_from=top,missing=value('missing').strip(),
                        missing_override=int(value('missing_override')=='on'),options=value('options'),
                        include=int(value('include')=='on')))
                selected=set(f.getlist('selected_group'))
                action=f.get('action','save')
                split_source=f.get('split_source','')
                if action=='link':
                    target=f.get('link_target','')
                    if target not in groups or not selected or not selected.issubset(groups):
                        raise ValueError('Bitte Fragen markieren und eine gemeinsame Zielfrage auswählen.')
                    all_keys=selected|{target}
                    source_ids=[q['source'] for key in all_keys for q in groups[key]]
                    placeholders=','.join('?' for _ in source_ids)
                    overlap=c.execute(f"""SELECT wave,feedback FROM answers WHERE project=? AND source IN ({placeholders})
                        GROUP BY wave,feedback HAVING COUNT(*)>1 LIMIT 1""",(pid,*source_ids)).fetchone()
                    if overlap:
                        raise ValueError('Eine Teilnahme enthält mehrere der ausgewählten Quellfragen. '
                                         'Die Verknüpfung würde Antworten doppelt zählen. Bitte diese Fragen getrennt lassen.')
                    chosen=next(q for q in pending if q['canonical']==target)
                    for q in pending:
                        if q['canonical'] in all_keys and q['type']!=chosen['type']:
                            raise ValueError('Für eine Verknüpfung müssen die Fragetypen übereinstimmen.')
                        if q['canonical'] in all_keys and q['type']=='scale' and (q['minimum'],q['maximum'],q['top_from'])!=(chosen['minimum'],chosen['maximum'],chosen['top_from']):
                            raise ValueError('Skala und Zustimmungsgrenze müssen für verknüpfte Fragen übereinstimmen.')
                    # Zielfrage bestimmt Berichtsname und Berechnung; Rohantworten bleiben erhalten.
                    pending=[{**chosen,'old_key':q['canonical']} if q['canonical'] in all_keys else {**q,'old_key':q['canonical']} for q in pending]
                else:
                    pending=[{**q,'old_key':q['canonical']} for q in pending]
                if split_source and split_source not in {q['source'] for q in qs}:
                    raise ValueError('Die zu trennende Quellfrage wurde nicht gefunden.')
                if f.get('wave_settings_present')=='yes':
                    valid_pairs={(r['source'],r['wave']) for r in c.execute('SELECT DISTINCT source,wave FROM answers WHERE project=?',(pid,))}
                    excluded=set()
                    for encoded in f.getlist('excluded_wave'):
                        pair=tuple(json.loads(encoded))
                        if pair not in valid_pairs:
                            raise ValueError('Unbekannte Frage oder Welle beim Ausschluss.')
                        excluded.add(pair)
                    for source,wave in valid_pairs:
                        if (source,wave) in excluded:
                            c.execute('INSERT OR IGNORE INTO question_exclusions VALUES(?,?,?,?)',(pid,source,wave,'Manuell ausgeschlossen'))
                        else:
                            c.execute('DELETE FROM question_exclusions WHERE project=? AND source=? AND wave=?',(pid,source,wave))
                for q in pending:
                    c.execute("""UPDATE questions SET canonical=?,label=?,type=?,theme=?,minimum=?,maximum=?,
                      top_from=?,missing=?,options=?,include=?,missing_override=? WHERE project=? AND canonical=?""",
                      (q['canonical'],q['label'],q['type'],q['theme'],q['minimum'],q['maximum'],q['top_from'],
                       q['missing'],q['options'],q['include'],q['missing_override'],pid,q['old_key']))
                if split_source:
                    c.execute('UPDATE questions SET canonical=? WHERE project=? AND source=?',
                              ('separate_'+secrets.token_hex(8),pid,split_source))
                c.execute('INSERT INTO question_settings VALUES(?,?) ON CONFLICT(project) DO UPDATE SET missing=excluded.missing',
                          (pid,common_missing))
                if request.accept_mimetypes.best=='application/json':
                    return jsonify(message='Alle Änderungen gespeichert.',reload=action=='link' or bool(split_source))
                flash('Alle Änderungen gespeichert.')
                return redirect(url_for('questions',pid=pid))
            wave_sources={}
            for r in c.execute('SELECT source,wave,COUNT(DISTINCT feedback) n FROM answers WHERE project=? GROUP BY source,wave ORDER BY wave',(pid,)):
                wave_sources.setdefault(r['source'],[]).append(dict(r))
            exclusions={(r['source'],r['wave']):r['reason'] for r in c.execute('SELECT * FROM question_exclusions WHERE project=?',(pid,))}
            for source, waves in wave_sources.items():
                for w in waves:
                    w['excluded']=(source,w['wave']) in exclusions
                    w['reason']=exclusions.get((source,w['wave']),'')
                    w['value']=json.dumps([source,w['wave']])
            originals={}
            for r in c.execute('SELECT source,raw FROM answers WHERE project=?',(pid,)):
                raw=json.loads(r['raw'])
                text=raw.get('Question','')
                if text:
                    originals.setdefault(r['source'],set()).add(text)
            cards=[]
            for key, members in groups.items():
                q=dict(members[0])
                q['members']=members
                q['source_waves']={m['source']:wave_sources.get(m['source'],[]) for m in members}
                q['originals']={m['source']:sorted(originals.get(m['source'],[])) for m in members}
                cards.append(q)
        return render_template('questions.html', **ctx, cards=cards, common_missing=common_missing,tab='questions')

    @app.route('/p/<int:pid>/segments', methods=['GET','POST'])
    def segments(pid):
        ctx = context(pid)
        with db() as c:
            if request.method == 'POST':
                f=request.form
                dim=f['dimension'].strip()
                if dim=='__custom__':
                    dim=f.get('custom_dimension','').strip()
                if not dim or dim=='__custom__':
                    raise ValueError('Bitte eine Merkmalsbezeichnung angeben.')
                if f['action']=='mapping':
                    c.execute('INSERT INTO mappings(project,wave,dimension,source) VALUES(?,?,?,?) ON CONFLICT(project,wave,dimension) DO UPDATE SET source=excluded.source',
                              (pid,f['wave'],dim,f['source']))
                else:
                    c.execute('INSERT INTO aliases(project,wave,dimension,source,target) VALUES(?,?,?,?,?) ON CONFLICT(project,wave,dimension,source) DO UPDATE SET target=excluded.target',
                              (pid,f['wave'],dim,f['source'],f['target']))
                flash('Zuordnung gespeichert.')
                return redirect(url_for('segments',pid=pid,wave=f['wave'],dimension=dim,
                                        source=f['source'] if f['action']=='mapping' else ''))
            mappings=c.execute('SELECT * FROM mappings WHERE project=?',(pid,)).fetchall()
            aliases=c.execute('SELECT * FROM aliases WHERE project=?',(pid,)).fetchall()
        scope=request.args.get('wave') or (ctx['waves'][0] if ctx['waves'] else '*')
        selected_dimension=request.args.get('dimension','Bereich')
        dimension_options=list(dict.fromkeys([*DIMENSIONS,*[r['dimension'] for r in mappings],
                                              *[r['dimension'] for r in aliases],selected_dimension]))
        return render_template('segments.html', **ctx, mappings=mappings,aliases=aliases,tab='segments',
                               scope=scope,selected_source=request.args.get('source',''),
                               selected_dimension=selected_dimension,dimension_options=dimension_options,
                               mapping_rules=[dict(r) for r in mappings])

    @app.get('/p/<int:pid>/segments/preview')
    def preview_segments(pid):
        project(pid)
        from core import segment_preview
        scope=request.args.get('wave','*')
        with db() as c:
            query='SELECT wave,feedback,raw FROM answers WHERE project=?'
            args=[pid]
            if scope!='*':
                query+=' AND wave=?'
                args.append(scope)
            records=[]
            for row in c.execute(query,args):
                records.append(dict(wave=row['wave'],feedback=row['feedback'],raw=json.loads(row['raw'])))
            mappings=[dict(r) for r in c.execute("SELECT * FROM mappings WHERE project=? ORDER BY (wave != '*'),id",(pid,))]
            aliases=[dict(r) for r in c.execute("SELECT * FROM aliases WHERE project=? ORDER BY (wave != '*'),id",(pid,))]
        return jsonify(segment_preview(records,mappings,aliases,wave=scope,
                       source=request.args.get('source',''),dimension=request.args.get('dimension',''),
                       original=request.args.get('original',''),target=request.args.get('target','')))

    @app.post('/p/<int:pid>/rule/delete')
    def delete_rule(pid):
        project(pid)
        table=request.form['table']
        if table not in ('mappings','aliases'):
            abort(400)
        with db() as c:
            c.execute(f'DELETE FROM {table} WHERE id=? AND project=?',(request.form['id'],pid))
        return redirect(url_for('segments',pid=pid))

    @app.route('/p/<int:pid>/grounds', methods=['GET','POST'])
    def grounds(pid):
        ctx=context(pid)
        with db() as c:
            if request.method=='POST':
                f=request.form
                total=int(f['total'])
                if total<0:
                    raise ValueError('Die Grundmenge darf nicht negativ sein.')
                dim,unit=f['dimension'].strip(),f['unit'].strip()
                if bool(dim)!=bool(unit):
                    raise ValueError('Für eine Einheit sind Merkmal und Wert gemeinsam anzugeben.')
                c.execute('INSERT INTO grounds VALUES(?,?,?,?,?) ON CONFLICT(project,wave,dimension,unit) DO UPDATE SET total=excluded.total',
                          (pid,f['wave'],dim,unit,total))
                flash('Grundmenge gespeichert. Werte gelten jeweils inklusive Untereinheiten und werden nicht addiert.')
                return redirect(url_for('grounds',pid=pid))
            grounds=c.execute('SELECT * FROM grounds WHERE project=? ORDER BY wave,dimension,unit',(pid,)).fetchall()
        return render_template('grounds.html',**ctx,grounds=grounds,tab='grounds')

    @app.route('/organisation',methods=['GET','POST'])
    def organisation():
        with db() as c:
            if request.method=='POST':
                f=request.files['file']
                df=read_table(f.read(),f.filename)
                if 'OE_Kürzel' not in df:
                    raise ValueError('Die OE-Liste benötigt eine Spalte OE_Kürzel.')
                if df['OE_Kürzel'].eq('').any() or df['OE_Kürzel'].duplicated().any():
                    raise ValueError('OE-Kürzel müssen ausgefüllt und eindeutig sein.')
                for row in df.to_dict('records'):
                    c.execute('INSERT INTO organisation VALUES(?,?) ON CONFLICT(code) DO UPDATE SET attributes=excluded.attributes',
                              (row['OE_Kürzel'],json.dumps(row,ensure_ascii=False)))
                flash('OE-Verzeichnis ergänzt und aktualisiert. Befragungsdaten wurden nicht verändert.')
                return redirect(url_for('organisation'))
            entries=[json.loads(r[0]) for r in c.execute('SELECT attributes FROM organisation ORDER BY code')]
        return render_template('organisation.html',entries=entries)

    def report_data(pid):
        p=project(pid)
        dimension=request.args.get('dimension','').strip()
        unit=request.args.get('unit','').strip()
        if bool(dimension)!=bool(unit):
            raise ValueError('Merkmal und Einheit bitte gemeinsam auswählen oder beide leer lassen.')
        rows,participation,grounds=results(pid,dimension,unit)
        with db() as c:
            dated={r[0]:r[1] for r in c.execute('SELECT wave,MIN(NULLIF(date,\'\')) FROM answers WHERE project=? GROUP BY wave',(pid,))}
        available=sorted(participation,key=lambda w:(dated.get(w) or '9999',w))
        selected=request.args.getlist('wave') or available
        rows=[r for r in rows if r['wave'] in selected]
        minimum=max(1,int(request.args.get('min_n',p['min_n'])))
        rates=[]
        for wave in available:
            n=participation[wave]
            if wave not in selected:
                continue
            matches=[g for g in grounds if g['wave']==wave and g['dimension']==dimension and g['unit']==unit]
            total=matches[0]['total'] if matches else None
            rates.append(dict(wave=wave,n=n,total=total,rate=100*n/total if total else None,
                              warning=total is not None and n>total))
        # Freitexte sind in dieser Etappe nicht in Weitergabeberichten enthalten.
        grouped={}
        hidden=0
        for r in rows:
            if r['type']=='text':
                continue
            if r['n']<minimum:
                hidden+=1
                continue
            grouped.setdefault(r['canonical'],[]).append(r)
        for group in grouped.values():
            group.sort(key=lambda row:available.index(row['wave']))
        return dict(p=p,grouped=grouped,rates=rates,minimum=minimum,hidden=hidden,
                    dimension=dimension,unit=unit,selected=selected,available=available)

    @app.route('/p/<int:pid>/results')
    def view_results(pid):
        return render_template('results.html',**report_data(pid),tab='results')

    @app.route('/p/<int:pid>/report')
    def report(pid):
        ctx=report_data(pid)
        cards=[dict(label=rows[0]['label'],theme=rows[0]['theme'],rows=rows)
               for rows in ctx['grouped'].values()]
        chart_library=(ROOT/'static/vendor/chart.umd.js').read_text(encoding='utf-8')
        chart_renderer=(ROOT/'static/report-charts.js').read_text(encoding='utf-8')
        payload=dict(project=ctx['p']['name'],unit=ctx['unit'] or 'Gesamtbefragung',cards=cards)
        html=render_template('report.html',**ctx,cards=cards,chart_library=chart_library,
                             chart_renderer=chart_renderer,chart_payload=payload,
                             auto_zip=request.args.get('zip')=='1')
        if request.args.get('download'):
            return send_file(io.BytesIO(html.encode()),mimetype='text/html',as_attachment=True,
                             download_name=f'Pulsbericht_{pid}.html')
        return html

    @app.route('/p/<int:pid>/charts.zip')
    def charts(pid):
        # PNGs und ZIP entstehen im Browser. Der bisherige Einstieg bleibt erhalten.
        return redirect(url_for('report',pid=pid)+'?'+request.query_string.decode()+'&zip=1')

    return app


if __name__=='__main__':
    import argparse
    import threading
    import webbrowser
    from waitress import serve
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=5051)
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    app=create_app()
    url=f'http://127.0.0.1:{args.port}'
    print(f'Befragungsstudio läuft auf {url}. Fenster geöffnet lassen. Strg+C beendet die App.',flush=True)
    if args.open_browser:
        threading.Timer(1,lambda:webbrowser.open(url)).start()
    serve(app,host='127.0.0.1',port=args.port,threads=4)
