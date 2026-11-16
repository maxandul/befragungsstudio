"""Bounded, resumable offline wave analysis. Legacy scope jobs remain readable."""
import io
import json
import secrets
import zipfile
from flask import abort, flash, g, redirect, render_template, request, send_file, url_for
import text_analysis as ta
import wave_analysis as wa


def register(app,db,project,report_data,result_sources):
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS wave_text_jobs(
          id TEXT PRIMARY KEY,project INTEGER NOT NULL,wave TEXT NOT NULL,selection TEXT NOT NULL,
          fingerprint TEXT NOT NULL,aliases TEXT NOT NULL DEFAULT '{}',revision INTEGER NOT NULL DEFAULT 0,
          created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS wave_text_parts(
          id TEXT PRIMARY KEY,job TEXT NOT NULL,position INTEGER NOT NULL,canonical TEXT NOT NULL,
          question_id TEXT NOT NULL,wording TEXT NOT NULL,label TEXT NOT NULL,count INTEGER NOT NULL,
          state TEXT NOT NULL DEFAULT 'draft',records TEXT NOT NULL,exported TEXT,result TEXT,
          revision INTEGER NOT NULL DEFAULT 0,UNIQUE(job,position));
        CREATE INDEX IF NOT EXISTS wave_parts_job ON wave_text_parts(job,position);''')

    def job_for(pid,jid):
        project(pid)
        with db() as c:
            row=c.execute('SELECT * FROM wave_text_jobs WHERE id=? AND project=?',(jid,pid)).fetchone()
        if not row:abort(404)
        return dict(row)

    def is_current(pid,job):
        if not hasattr(g,'wave_text_fingerprints'):g.wave_text_fingerprints={}
        key=(pid,job['selection'])
        if key not in g.wave_text_fingerprints:
            g.wave_text_fingerprints[key]=ta.digest(wa.contextual_records(result_sources(pid),**json.loads(job['selection'])))
        return g.wave_text_fingerprints[key]==job['fingerprint']

    def part_for(pid,jid,bid):
        job=job_for(pid,jid)
        with db() as c:
            r=c.execute('SELECT * FROM wave_text_parts WHERE id=? AND job=?',(bid,jid)).fetchone()
        if not r:abort(404)
        return job,dict(r)

    def save_part(c,part,**values):
        keys=','.join(k+'=?' for k in values)
        cursor=c.execute('UPDATE wave_text_parts SET '+keys+',revision=revision+1 WHERE id=? AND revision=?',
                         (*values.values(),part['id'],part['revision']))
        if cursor.rowcount!=1:
            raise ValueError('Dieses Teilpaket wurde inzwischen geändert. Bitte neu laden.')

    def wave_context(pid):
        # Do not calculate charts or all OE comparisons just to prepare text packages.
        p=project(pid)
        with db() as c:
            dated={r[0]:r[1] for r in c.execute("SELECT wave,MIN(NULLIF(date,'')) FROM answers WHERE project=? GROUP BY wave",(pid,))}
        available=sorted(dated,key=lambda w:(dated.get(w) or '9999',w))
        wave=request.args.get('focus_wave','').strip() or (available[-1] if available else '')
        if wave and wave not in available:raise ValueError('Diese Welle ist nicht vorhanden.')
        return dict(p=p,available=available,reference_wave=wave)

    def home(pid):
        # OE/report filters intentionally do not constrain a wave preparation.
        ctx=wave_context(pid)
        records=ta.collect(result_sources(pid),ctx['reference_wave'],exclude_leaders=False)
        counts={}
        for r in records:
            q=counts.setdefault(r['canonical'],dict(canonical=r['canonical'],label=r['label'],count=0))
            q['count']+=1
        with db() as c:
            jobs=[dict(r) for r in c.execute('''SELECT j.id,j.wave,j.created,COUNT(p.id) parts,
              SUM(p.state='approved') approved,SUM(p.count) answers FROM wave_text_jobs j
              JOIN wave_text_parts p ON p.job=j.id WHERE j.project=? GROUP BY j.id ORDER BY j.rowid DESC''',(pid,))]
            legacy=[dict(r) for r in c.execute('SELECT id,wave,state FROM text_jobs WHERE project=? ORDER BY rowid DESC',(pid,))]
        return render_template('wave_texts.html',**ctx,questions=list(counts.values()),jobs=jobs,legacy=legacy,tab='texts')

    @app.post('/p/<int:pid>/wave-texts')
    def wave_text_create(pid):
        ctx=wave_context(pid)
        all_records=wa.contextual_records(result_sources(pid),wave=ctx['reference_wave'],exclude_leaders=False)
        selected=set(request.form.getlist('question'))
        available={r['canonical'] for r in all_records}
        if not selected or not selected<=available:
            raise ValueError('Bitte vorhandene Textfragen der Welle auswählen.')
        records=[r for r in all_records if r['canonical'] in selected]
        selection=dict(wave=ctx['reference_wave'],canonicals=sorted(selected),exclude_leaders=False)
        jid=secrets.token_hex(16)
        draft=ta.make_draft(records)
        qids={canonical:secrets.token_hex(12) for canonical in selected}
        with db() as c:
            c.execute('INSERT INTO wave_text_jobs(id,project,wave,selection,fingerprint) VALUES(?,?,?,?,?)',
                      (jid,pid,ctx['reference_wave'],json.dumps(selection),ta.digest(records)))
            for i,(canonical,items) in enumerate(wa.batches(draft),1):
                c.execute('''INSERT INTO wave_text_parts(id,job,position,canonical,question_id,wording,label,count,records)
                  VALUES(?,?,?,?,?,?,?,?,?)''',(secrets.token_hex(16),jid,i,canonical,qids[canonical],
                  items[0]['wording'],items[0]['label'],len(items),json.dumps(items)))
        return redirect(url_for('wave_text_job',pid=pid,jid=jid))

    @app.route('/p/<int:pid>/wave-texts/<jid>',methods=['GET','POST'])
    def wave_text_job(pid,jid):
        job=job_for(pid,jid);stale=not is_current(pid,job)
        with db() as c:
            parts=[dict(r) for r in c.execute('SELECT id,position,label,count,state FROM wave_text_parts WHERE job=? ORDER BY position',(jid,))]
            results=[json.loads(r[0]) for r in c.execute('SELECT result FROM wave_text_parts WHERE job=? AND result IS NOT NULL',(jid,))]
        topics=sorted({s['thema'] for result in results for a in result['antworten'] for s in a['aussagen']})
        aliases=json.loads(job['aliases'])
        if request.method=='POST':
            if stale:raise ValueError('Der Datenstand ist veraltet. Bitte einen neuen Wellenauftrag erstellen.')
            if request.form.get('revision')!=str(job['revision']):
                raise ValueError('Der Auftrag wurde inzwischen geändert. Bitte neu laden.')
            if request.form.get('action')=='aliases':
                if request.form.get('topics_hash')!=ta.digest(topics):
                    raise ValueError('Die Themenliste hat sich inzwischen geändert. Bitte neu laden.')
                aliases={t:request.form.get('topic_'+str(i),'').strip() for i,t in enumerate(topics)}
                if any(not target or len(target)>160 for target in aliases.values()):
                    raise ValueError('Bitte für jedes Thema eine Bezeichnung mit höchstens 160 Zeichen angeben.')
                with db() as c:
                    cursor=c.execute('UPDATE wave_text_jobs SET aliases=?,revision=revision+1 WHERE id=? AND revision=?',
                                     (json.dumps(aliases),jid,job['revision']))
                    if cursor.rowcount!=1:raise ValueError('Der Auftrag wurde inzwischen geändert. Bitte neu laden.')
                flash('Themenbezeichnungen vereinheitlicht. Inhalte und Quellen bleiben erhalten.')
            elif request.form.get('action')=='import':
                uploads=request.files.getlist('files')
                if not uploads or any(not u.filename for u in uploads):raise ValueError('Bitte JSON-Rückgaben auswählen.')
                if len(uploads)>100:raise ValueError('Bitte höchstens 100 Rückgaben gemeinsam importieren.')
                # Validate the complete upload batch before committing any part.
                pending=[];seen=set()
                with db() as c:
                    for upload in uploads:
                        value=ta.load_json(upload.read(10*1024*1024+1))
                        bid=value.get('teil') if isinstance(value,dict) else None
                        if not isinstance(bid,str) or bid in seen:
                            raise ValueError('Fehlende oder doppelte Teilpaketkennung im Upload.')
                        seen.add(bid)
                        r=c.execute('SELECT * FROM wave_text_parts WHERE id=? AND job=?',(bid,jid)).fetchone()
                        if not r or not r['exported']:raise ValueError('Rückgabe gehört nicht zu einem exportierten Teilpaket dieses Auftrags.')
                        part=dict(r);value=wa.validate(value,json.loads(part['exported']))
                        if part['result'] and ta.digest(json.loads(part['result']))==ta.digest(value):
                            continue  # Safe retry: identical uploads do not disturb review/approval.
                        if part['state']!='exported':
                            raise ValueError('Eine abweichende Rückgabe würde eine Prüfung überschreiben. Bitte das Teilpaket öffnen und die Rückgabe dort ausdrücklich ersetzen.')
                        pending.append((part,value))
                    for part,value in pending:save_part(c,part,state='imported',result=json.dumps(value))
                flash(f'{len(pending)} neue Teilpakete importiert. Bereits identische Rückgaben bleiben unverändert.')
            else:raise ValueError('Unbekannte Aktion.')
            return redirect(url_for('wave_text_job',pid=pid,jid=jid))
        return render_template('wave_text_job.html',p=project(pid),job=job,parts=parts,stale=stale,
                               topics=topics,topics_hash=ta.digest(topics),aliases=aliases,tab='texts')

    @app.route('/p/<int:pid>/wave-texts/<jid>/<bid>',methods=['GET','POST'])
    def wave_text_part(pid,jid,bid):
        job,part=part_for(pid,jid,bid);stale=not is_current(pid,job)
        items=json.loads(part['records']);by_id={r['id']:r for r in items}
        result=json.loads(part['result']) if part['result'] else None
        if request.method=='POST':
            if stale:raise ValueError('Dieser Wellenauftrag ist veraltet. Bitte neu erstellen.')
            if request.form.get('revision')!=str(part['revision']):raise ValueError('Das Teilpaket wurde inzwischen geändert. Bitte neu laden.')
            action=request.form.get('action');values={}
            if action in ('draft','export') and part['state']=='draft':
                for r in items:
                    r['export_text']=request.form.get('text_'+r['id'],'').strip()
                    if not r['export_text']:raise ValueError('Exporttext darf nicht leer sein. Nutzen Sie bei Bedarf [Inhalt entfernt].')
                wording=request.form.get('wording','').strip()
                if not wording or len(wording)>4000:raise ValueError('Bitte einen Fragetext mit höchstens 4000 Zeichen angeben.')
                values=dict(records=json.dumps(items),wording=wording)
                if action=='export':
                    if request.form.get('privacy_checked')!='on':raise ValueError('Bitte die Prüfung auf Personenbezüge bestätigen.')
                    data,_=wa.package(jid,bid,part['question_id'],wording,items)
                    values.update(state='exported',exported=json.dumps(data))
            elif action=='replace' and part['state']=='imported':
                upload=request.files.get('file')
                if not upload or not upload.filename or request.form.get('replace_checked')!='on':raise ValueError('Bitte eine korrigierte Rückgabe auswählen und das Ersetzen bestätigen.')
                value=wa.validate(ta.load_json(upload.read(10*1024*1024+1)),json.loads(part['exported']))
                values=dict(result=json.dumps(value))
            elif action=='reopen' and part['state']=='approved':
                values=dict(state='imported')
            elif action in ('save','approve') and part['state']=='imported':
                for ai,a in enumerate(result['antworten']):
                    for si,s in enumerate(a['aussagen']):
                        s['thema']=request.form.get(f'topic_{ai}_{si}','').strip()
                        s['aussage']=request.form.get(f'body_{ai}_{si}','').strip()
                    if not a['aussagen']:a['grund']=request.form.get(f'reason_{ai}','').strip()
                result=wa.validate(result,json.loads(part['exported']))
                if action=='approve' and request.form.get('content_checked')!='on':raise ValueError('Bitte die inhaltliche Prüfung bestätigen.')
                values=dict(state='approved' if action=='approve' else 'imported',result=json.dumps(result))
            else:raise ValueError('Diese Aktion ist im aktuellen Status nicht möglich.')
            with db() as c:save_part(c,part,**values)
            flash('Teilpaket gespeichert. Der Fortschritt bleibt erhalten.')
            return redirect(url_for('wave_text_part',pid=pid,jid=jid,bid=bid))
        return render_template('wave_text_part.html',p=project(pid),job=job,part=part,items=items,
                               by_id=by_id,result=result,stale=stale,tab='texts')

    @app.get('/p/<int:pid>/wave-texts/<jid>/<bid>/download')
    def wave_text_download(pid,jid,bid):
        job,part=part_for(pid,jid,bid)
        if not part['exported'] or not is_current(pid,job):raise ValueError('Dieses Teilpaket ist ungeprüft oder veraltet.')
        data=json.loads(part['exported'])
        template=dict(version=2,auftrag=jid,teil=bid,frage=part['question_id'],
                      antworten=[dict(id=a['id'],aussagen=[],grund='') for a in data['antworten']])
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('daten.json',json.dumps(data,ensure_ascii=False,indent=2))
            z.writestr('standardprompt.txt',wa.PROMPT)
            z.writestr('rueckgabe_vorlage.json',json.dumps(template,ensure_ascii=False,indent=2))
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name=f'Textauswertung_{jid[:8]}_Teil_{part["position"]:03d}.zip')

    @app.get('/p/<int:pid>/wave-texts/<jid>/download')
    def wave_text_download_all(pid,jid):
        job=job_for(pid,jid)
        if not is_current(pid,job):raise ValueError('Dieser Wellenauftrag ist veraltet.')
        with db() as c:
            parts=[dict(r) for r in c.execute('SELECT position,question_id,exported FROM wave_text_parts WHERE job=? AND exported IS NOT NULL ORDER BY position',(jid,))]
        if not parts:raise ValueError('Bitte zuerst mindestens ein Teilpaket auf Personenbezüge prüfen und festhalten.')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('standardprompt.txt',wa.PROMPT)
            z.writestr('LESEN.txt','Dieses Paket enthält '+str(len(parts))+' bereits bereinigte Teilpakete.\n'
                'Jedes Teilpaket mit standardprompt.txt getrennt auswerten. Bei Verarbeitung des ganzen ZIPs '
                'alle Teile nacheinander bearbeiten und je Teil eine eigene ergebnis_Teil_NNN.json liefern. '
                'Keine Antworten zwischen Teilen zusammenfassen. Abgebrochene oder fehlende Teile später separat fortsetzen. '
                'Die Rückgaben gemeinsam in der App hochladen. Noch ungeprüfte Exportteile fehlen in diesem ZIP.\n')
            for part in parts:
                data=json.loads(part['exported'])
                template=dict(version=2,auftrag=jid,teil=data['teil'],frage=part['question_id'],
                              antworten=[dict(id=a['id'],aussagen=[],grund='') for a in data['antworten']])
                prefix=f'Teil_{part["position"]:03d}/'
                z.writestr(prefix+'daten.json',json.dumps(data,ensure_ascii=False,indent=2))
                z.writestr(prefix+'rueckgabe_vorlage.json',json.dumps(template,ensure_ascii=False,indent=2))
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name=f'Wellenauswertung_{jid[:8]}.zip')

    def summaries(pid,ctx):
        if not ctx.get('include_summaries'):return {}
        with db() as c:
            jobs=[dict(r) for r in c.execute('''SELECT j.* FROM wave_text_jobs j WHERE j.project=? AND j.wave=?
              AND EXISTS(SELECT 1 FROM wave_text_parts p WHERE p.job=j.id)
              AND NOT EXISTS(SELECT 1 FROM wave_text_parts p WHERE p.job=j.id AND p.state!='approved')
              ORDER BY j.rowid DESC''',(pid,ctx['reference_wave']))]
        if not jobs:return {}
        sources=result_sources(pid)
        eligible={tuple(r['key']) for r in ta.collect(sources,ctx['reference_wave'],ctx['dimension'],ctx['unit'],
                  ctx['node']['path'] if ctx['node'] else [],minimum=ctx['minimum'])}
        output={};claimed=set()
        for job in jobs:
            if not is_current(pid,job):continue
            with db() as c:
                parts=[(json.loads(p['records']),json.loads(p['result']),p['canonical'])
                       for p in c.execute('SELECT records,result,canonical FROM wave_text_parts WHERE job=? ORDER BY position',(job['id'],))]
            grouped=wa.group_statements(parts,eligible,json.loads(job['aliases']))
            for canonical in json.loads(job['selection'])['canonicals']:
                if canonical not in claimed:
                    claimed.add(canonical)
                    output[canonical]=grouped.get(canonical,[])
        return output
    return home,summaries
