"""Local review and exchange workflow; all mutations are covered by app CSRF protection."""
import io
import json
import secrets
import zipfile
from flask import abort, flash, redirect, render_template, request, send_file, url_for
from core import mapped_dimensions
from organisation import oe_path
from report_views import concern_origins
import text_analysis as ta


def report_source_oes(sources, wave, children):
    if not children:
        return {}
    labels = {tuple(child['path']): child['unit'] for child, _ in children}
    depth = len(next(iter(labels)))
    records, _, mappings, aliases, _, _ = sources
    people = {}
    for record in records:
        person = (record['wave'], record['feedback'])
        if record['wave'] == wave and person not in people:
            path = oe_path(mapped_dimensions(record, mappings, aliases))[:depth]
            people[person] = labels.get(path)
    return people


def register(app, db, project, report_data, result_sources):
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS text_jobs(
          id TEXT PRIMARY KEY,project INTEGER NOT NULL,scope TEXT NOT NULL,wave TEXT NOT NULL,
          state TEXT NOT NULL,selection TEXT NOT NULL,fingerprint TEXT NOT NULL,
          records TEXT NOT NULL,exported TEXT,result TEXT,revision INTEGER NOT NULL DEFAULT 0,
          created TEXT DEFAULT CURRENT_TIMESTAMP)''')

    def get_job(pid,jid):
        project(pid)
        with db() as c:
            r=c.execute('SELECT * FROM text_jobs WHERE id=? AND project=?',(jid,pid)).fetchone()
        if not r:
            abort(404)
        return dict(r)

    def current(pid,job):
        selection=json.loads(job['selection'])
        records=ta.collect(result_sources(pid),**selection)
        return ta.digest(records)==job['fingerprint']

    def update(pid,job,**values):
        with db() as c:
            assignments=','.join(k+'=?' for k in values)
            cursor=c.execute('UPDATE text_jobs SET '+assignments+',revision=revision+1 WHERE id=? AND project=? AND revision=?',
                             (*values.values(),job['id'],pid,job['revision']))
            if cursor.rowcount!=1:
                raise ValueError('Dieser Auftrag wurde inzwischen geändert. Bitte Seite neu laden.')

    def detail_url(pid,jid):
        return url_for('text_job',pid=pid,jid=jid)

    @app.get('/p/<int:pid>/texts')
    def text_analysis(pid):
        return wave_home(pid)

    @app.post('/p/<int:pid>/texts')
    def text_create(pid):
        ctx=report_data(pid)
        choices={r['canonical'] for group in ctx['text_groups'].values() for r in group}
        selected=request.form.getlist('question')
        if not selected or not set(selected)<=choices:
            raise ValueError('Bitte mindestens eine verfügbare Textfrage auswählen.')
        selection=dict(wave=ctx['reference_wave'],dimension=ctx['dimension'],unit=ctx['unit'],
                       path=ctx['node']['path'] if ctx['node'] else [],canonicals=sorted(set(selected)),minimum=ctx['minimum'])
        records=ta.collect(result_sources(pid),**selection)
        if not records:
            raise ValueError('Für diese Auswahl sind keine auswertbaren Textantworten vorhanden.')
        jid=secrets.token_hex(16)
        with db() as c:
            c.execute('INSERT INTO text_jobs(id,project,scope,wave,state,selection,fingerprint,records) VALUES(?,?,?,?,?,?,?,?)',
                      (jid,pid,ctx['scope'],ctx['reference_wave'],'draft',json.dumps(selection),ta.digest(records),json.dumps(ta.make_draft(records))))
        return redirect(detail_url(pid,jid))

    @app.route('/p/<int:pid>/texts/<jid>',methods=['GET','POST'])
    def text_job(pid,jid):
        job=get_job(pid,jid)
        records=json.loads(job['records'])
        stale=not current(pid,job)
        exported=json.loads(job['exported']) if job['exported'] else None
        result=json.loads(job['result']) if job['result'] else None
        if request.method=='POST':
            if request.form.get('revision')!=str(job['revision']):
                raise ValueError('Dieser Auftrag wurde inzwischen geändert. Bitte Seite neu laden.')
            if stale:
                raise ValueError('Daten oder Fragen wurden geändert. Bitte einen neuen Auftrag erstellen.')
            action=request.form.get('action')
            if action=='export' and job['state']=='draft':
                if request.form.get('privacy_checked')!='on':
                    raise ValueError('Bitte Texte und Fragetexte vor dem Export auf Personenbezüge prüfen und bestätigen.')
                wordings={}
                for r in records:
                    r['export_text']=request.form.get('text_'+r['id'],'').strip()
                    if not r['export_text']:
                        raise ValueError('Exporttexte dürfen nicht leer sein. Nutzen Sie bei Bedarf [Inhalt entfernt].')
                    wordings[r['canonical']]=request.form.get('wording_'+r['canonical'],'').strip()
                    if not wordings[r['canonical']]:
                        raise ValueError('Bitte die Fragetexte ausfüllen.')
                exported,template=ta.package(jid,records,wordings)
                update(pid,job,state='exported',records=json.dumps(records),exported=json.dumps(exported))
                return redirect(detail_url(pid,jid))
            if action=='import' and job['state']=='exported':
                upload=request.files.get('file')
                if not upload or not upload.filename:
                    raise ValueError('Bitte die Ergebnisdatei auswählen.')
                result=ta.validate_result(ta.load_json(upload.read(10*1024*1024+1)),exported)
                update(pid,job,state='imported',result=json.dumps(result))
                flash('Rückgabe vollständig zugeordnet. Bitte Aussagen und Originale inhaltlich prüfen.')
                return redirect(detail_url(pid,jid))
            if action in ('save','approve','reopen') and job['state'] in ('imported','approved'):
                if job['state']=='approved' and action!='reopen':
                    raise ValueError('Bitte zuerst die Freigabe zurücknehmen, um die Fassung zu bearbeiten.')
                if action=='reopen':
                    update(pid,job,state='imported')
                else:
                    for qi,q in enumerate(result['fragen']):
                        for ti,t in enumerate(q['themen']):
                            t['titel']=request.form.get(f'title_{qi}_{ti}','').strip()
                            t['aussage']=request.form.get(f'body_{qi}_{ti}','').strip()
                    result=ta.validate_result(result,exported)
                    if action=='approve' and request.form.get('content_checked')!='on':
                        raise ValueError('Bitte die inhaltliche Prüfung einschliesslich Einzelhinweisen bestätigen.')
                    update(pid,job,state='approved' if action=='approve' else 'imported',result=json.dumps(result))
                flash('Freigabe zurückgenommen.' if action=='reopen' else 'Geprüfte Fassung gespeichert.' if action=='approve' else 'Entwurf gespeichert.')
                return redirect(detail_url(pid,jid))
            raise ValueError('Diese Aktion ist im aktuellen Auftragsstatus nicht möglich.')
        groups=[]
        by_id={r['id']:r for r in records}
        for canonical in dict.fromkeys(r['canonical'] for r in records):
            group=[r for r in records if r['canonical']==canonical]
            groups.append(dict(canonical=canonical,label=group[0]['label'],wording=group[0]['wording'],records=group))
        return render_template('text_job.html',p=project(pid),job=job,groups=groups,by_id=by_id,
                               result=result,stale=stale,selection=json.loads(job['selection']),tab='texts')

    @app.get('/p/<int:pid>/texts/<jid>/download')
    def text_download(pid,jid):
        job=get_job(pid,jid)
        if job['state']=='draft' or not current(pid,job):
            raise ValueError('Der Export ist noch nicht geprüft oder nicht mehr aktuell.')
        exported=json.loads(job['exported'])
        template=dict(version=ta.VERSION,auftrag=jid,fragen=[dict(id=q['id'],themen=[],nicht_auswertbar=[]) for q in exported['fragen']])
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('daten.json',json.dumps(exported,ensure_ascii=False,indent=2))
            z.writestr('standardprompt.txt',ta.PROMPT)
            z.writestr('rueckgabe_vorlage.json',json.dumps(template,ensure_ascii=False,indent=2))
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name='Textauswertung_'+jid[:8]+'.zip')

    def summaries(pid,ctx,source_oes):
        with db() as c:
            jobs=[dict(r) for r in c.execute("SELECT * FROM text_jobs WHERE project=? AND scope=? AND wave=? AND state='approved' ORDER BY rowid DESC",
                                           (pid,ctx['scope'],ctx['reference_wave']))]
        output={}
        for job in jobs:
            if not current(pid,job):
                continue
            records=json.loads(job['records'])
            by_id={r['id']:r for r in records}
            for q in json.loads(job['result'])['fragen']:
                canonical=by_id[q['id']]['canonical']
                if canonical not in output:
                    output[canonical]=[
                        dict(topic,origins=concern_origins(
                            {tuple(by_id[ref]['key'][:2]) for ref in topic['quellen']},source_oes))
                        for topic in q['themen']]
        return output
    from wave_routes import register as register_wave
    wave_home,wave_summaries=register_wave(app,db,project,report_data,result_sources)

    def combined_summaries(pid,ctx):
        if not ctx.get('include_summaries'):
            return {}
        source_oes=report_source_oes(result_sources(pid),ctx['reference_wave'],ctx['child_results'])
        legacy=summaries(pid,ctx,source_oes)
        legacy.update(wave_summaries(pid,ctx,source_oes))
        return legacy
    return combined_summaries
