"""One whole-wave export, import and review. No model API and no model-generated counts."""
import csv
import io
import json
import zipfile
from collections import defaultdict
from flask import flash, redirect, render_template, request, send_file, url_for
import text_analysis as ta
import wave_analysis as wa
import wave_synthesis as ws
from report_editorial import statement_index,valid_concern,EDITOR_KINDS


def register(app,db,project,job_for,is_current):
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS wave_syntheses(
          job TEXT PRIMARY KEY,state TEXT NOT NULL,result_hash TEXT NOT NULL,result TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 0)''')
        if 'rationale' not in [r[1] for r in c.execute('PRAGMA table_info(text_concerns)')]:
            c.execute("ALTER TABLE text_concerns ADD COLUMN rationale TEXT NOT NULL DEFAULT ''")

    def load(c,jid):
        parts=[dict(p) for p in c.execute('SELECT * FROM wave_text_parts WHERE job=? ORDER BY position',(jid,))]
        concerns=[dict(r) for r in c.execute('SELECT * FROM text_concerns WHERE job=? ORDER BY sort_order,id',(jid,))]
        synthesis=c.execute('SELECT * FROM wave_syntheses WHERE job=?',(jid,)).fetchone()
        return parts,concerns,dict(synthesis) if synthesis else None

    def review_hash(parts,concerns):
        return ta.digest([[(p['id'],p['revision'],p['result'],p['exported']) for p in parts],concerns])

    def summaries(parts,concerns,index):
        denominators=defaultdict(set)
        for p in parts:
            for r in json.loads(p['records']):denominators[p['canonical']].add(tuple(r['key'][:2]))
        rows=[]
        for a in concerns:
            valid=valid_concern(a,index)
            refs=json.loads(a['sources']);members=[index[ref] for ref in refs if ref in index]
            n=len({tuple(s['key'][:2]) for s in members});total=len(denominators[a['canonical']])
            rows.append(dict(a,valid=valid,count=n,total=total,percent=100*n/total if total else None,
                             references=members[:50],source_count=len(refs),label=members[0]['label'] if members else a['canonical']))
        return rows

    @app.route('/p/<int:pid>/wave-texts/<jid>/overall-download',methods=['GET','POST'])
    def synthesis_download(pid,jid):
        job=job_for(pid,jid)
        if not is_current(pid,job):raise ValueError('Dieser Wellenauftrag ist veraltet.')
        with db() as c:parts,_,_=load(c,jid)
        if request.method=='POST':
            # Prepare all remaining drafts atomically; preserve individually edited/exported text.
            before=review_hash(parts,[])
            pending=[]
            for p in parts:
                if not p['exported']:
                    data,_=wa.package(jid,p['id'],p['question_id'],p['wording'],json.loads(p['records']),job['batch_size'])
                    pending.append((json.dumps(data),p['id']))
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                fresh,_,_=load(c,jid)
                if review_hash(fresh,[])!=before:
                    raise ValueError('Exporttexte wurden inzwischen geändert. Bitte neu laden.')
                c.executemany("UPDATE wave_text_parts SET exported=?,state='exported',revision=revision+1 WHERE id=?",pending)
                parts,_,_=load(c,jid)
        if not parts or any(not p['exported'] for p in parts):
            raise ValueError('Für den Gesamtauftrag müssen zuerst alle Exporttexte auf Personenbezüge geprüft und festgehalten werden. Einzelne fertige Pakete bleiben separat verfügbar.')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('standardprompt.txt',ws.PROMPT)
            z.writestr('teilprompt.txt',wa.PROMPT)
            manifest=dict(version=3,auftrag=jid,teile=[dict(teil=p['id'],frage=p['question_id'],antworten=p['count'],
                              datei=f'Teil_{p["position"]:03d}/daten.json') for p in parts])
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            z.writestr('gesamt_ergebnis_vorlage.json',json.dumps(ws.template(jid,parts),ensure_ascii=False,indent=2))
            for p in parts:
                data=json.loads(p['exported']);prefix=f'Teil_{p["position"]:03d}/'
                z.writestr(prefix+'daten.json',json.dumps(data,ensure_ascii=False,indent=2))
                template=dict(version=2,auftrag=jid,teil=p['id'],frage=p['question_id'],
                              antworten=[dict(id=a['id'],aussagen=[],grund='') for a in data['antworten']])
                z.writestr(prefix+'rueckgabe_vorlage.json',json.dumps(template,ensure_ascii=False,indent=2))
                if p['result']:
                    # Existing checkpoints have random IDs and processed text, no local raw metadata.
                    z.writestr(prefix+'vorhandenes_ergebnis.json',p['result'])
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name=f'Gesamtauftrag_{jid[:8]}.zip')

    @app.route('/p/<int:pid>/wave-texts/<jid>/synthesis',methods=['GET','POST'])
    def synthesis_review(pid,jid):
        job=job_for(pid,jid);stale=not is_current(pid,job)
        with db() as c:parts,concerns,synthesis=load(c,jid)
        if request.method=='POST':
            if stale:raise ValueError('Die Datenbasis ist veraltet. Bitte einen neuen Auftrag erstellen.')
            if request.form.get('revision')!=str(synthesis['revision'] if synthesis else 0):
                raise ValueError('Die Gesamtauswertung wurde inzwischen geändert. Bitte neu laden.')
            action=request.form.get('action')
            if action in ('import','import_use'):
                use_immediately=action=='import_use'
                upload=request.files.get('file')
                if not upload or not upload.filename:raise ValueError('Bitte die Gesamtdatei auswählen.')
                value=ta.load_json(upload.read(50*1024*1024+1),max_bytes=50*1024*1024)
                results,proposals,_=ws.validate(value,jid,parts)
                result_hash=ta.digest(value)
                if synthesis and synthesis['result_hash']==result_hash:
                    if use_immediately and synthesis['state']!='approved':
                        index=statement_index(parts)
                        if any(not valid_concern(a,index) for a in concerns):
                            raise ValueError('Quellen wurden geändert. Bitte die Bündelung zuerst korrigieren oder auflösen.')
                        with db() as c:
                            c.execute('BEGIN IMMEDIATE')
                            fresh,current_concerns,current_synthesis=load(c,jid)
                            if review_hash(fresh,current_concerns)!=review_hash(parts,concerns) or current_synthesis['revision']!=synthesis['revision']:
                                raise ValueError('Die Auswertung wurde inzwischen geändert. Bitte neu laden.')
                            c.execute("UPDATE wave_syntheses SET state='approved',revision=revision+1 WHERE job=?",(jid,))
                            c.execute("UPDATE wave_text_parts SET state='approved',revision=revision+1 WHERE job=?",(jid,))
                        flash('Vorhandene Auswertung für Berichte aktiviert. Ihre Redaktion bleibt erhalten.')
                    else:
                        flash('Identische Gesamtrückgabe bereits vorhanden. Ihre Redaktion und Freigaben bleiben unverändert.')
                    return redirect(url_for('synthesis_review',pid=pid,jid=jid))
                replacing=bool(synthesis or concerns or any(p['state']=='approved' or (p['result'] and ta.digest(json.loads(p['result']))!=ta.digest(results[p['id']])) for p in parts))
                if replacing and request.form.get('replace_checked')!='on':
                    raise ValueError('Die Rückgabe ersetzt vorhandene Bearbeitungen und Freigaben. Bitte das Ersetzen ausdrücklich bestätigen.')
                before=review_hash(parts,concerns)
                with db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    fresh,old_concerns,old_synthesis=load(c,jid)
                    if review_hash(fresh,old_concerns)!=before or (old_synthesis['revision'] if old_synthesis else 0)!=(synthesis['revision'] if synthesis else 0):
                        raise ValueError('Teilpakete oder Redaktion wurden inzwischen geändert. Bitte neu laden.')
                    state='approved' if use_immediately else 'imported'
                    for p in parts:
                        c.execute("UPDATE wave_text_parts SET result=?,state=?,revision=revision+1 WHERE id=?",(json.dumps(results[p['id']]),state,p['id']))
                    c.execute('DELETE FROM text_concerns WHERE job=?',(jid,))
                    c.executemany('''INSERT INTO text_concerns(id,job,canonical,topic,body,kind,sort_order,sources,rationale)
                        VALUES(:id,:job,:canonical,:topic,:body,:kind,:sort_order,:sources,:rationale)''',proposals)
                    c.execute('''INSERT INTO wave_syntheses(job,state,result_hash,result) VALUES(?,?,?,?)
                        ON CONFLICT(job) DO UPDATE SET state=excluded.state,result_hash=excluded.result_hash,result=excluded.result,revision=wave_syntheses.revision+1''',
                        (jid,state,result_hash,json.dumps(value)))
                flash('Import vollständig geprüft. Textauswertung ist jetzt für alle passenden OE-Berichte verfügbar; redaktionelle Prüfung bei Bedarf.' if use_immediately else 'Die gesamte Welle ist vollständig zugeordnet. Optionale Redaktion öffnen oder gemeinsam für Berichte aktivieren.')
            elif action in ('approve','reopen'):
                if not synthesis:raise ValueError('Bitte zuerst eine Gesamtrückgabe importieren.')
                if request.form.get('review_hash')!=review_hash(parts,concerns):
                    raise ValueError('Aussagen oder Anliegen wurden inzwischen geändert. Bitte die aktuelle Übersicht prüfen.')
                if action=='approve':
                    if request.form.get('supported')!='on':raise ValueError('Bitte die inhaltliche Prüfung und Quellenstützung der Vorschläge bestätigen.')
                    index=statement_index(parts)
                    if any(not valid_concern(a,index) for a in concerns):raise ValueError('Quellen eines Anliegens wurden geändert. Bitte die Bündelung zuerst korrigieren oder auflösen.')
                with db() as c:
                    c.execute('BEGIN IMMEDIATE');fresh,old_concerns,old_synthesis=load(c,jid)
                    if review_hash(fresh,old_concerns)!=review_hash(parts,concerns) or old_synthesis['revision']!=synthesis['revision']:
                        raise ValueError('Die Auswertung wurde inzwischen geändert. Bitte neu laden.')
                    state='approved' if action=='approve' else 'imported'
                    c.execute('UPDATE wave_syntheses SET state=?,revision=revision+1 WHERE job=?',(state,jid))
                    c.execute('UPDATE wave_text_parts SET state=?,revision=revision+1 WHERE job=?',(state,jid))
                flash('Gesamte Welle für Berichte freigegeben.' if action=='approve' else 'Gesamtfreigabe zurückgenommen. Alle Bearbeitungen bleiben erhalten.')
            else:raise ValueError('Unbekannte Aktion.')
            return redirect(url_for('synthesis_review',pid=pid,jid=jid))
        index=statement_index(parts);rows=summaries(parts,concerns,index)
        ignored=[]
        for part in parts:
            records={r['id']:r for r in json.loads(part['records'])}
            if part['result']:
                for a in json.loads(part['result'])['antworten']:
                    if not a['aussagen']:
                        ignored.append(dict(label=part['label'],reason=a['grund'],original=records[a['id']]['text'],part=part['id']))
        try:ignored_page=max(1,int(request.args.get('ignored_page','1')))
        except ValueError:raise ValueError('Ungültige Seitennummer der nicht ausgewerteten Antworten.') from None
        ignored_pages=max(1,(len(ignored)+49)//50);ignored_page=min(ignored_page,ignored_pages)
        try:page=max(1,int(request.args.get('page','1')))
        except ValueError:raise ValueError('Ungültige Seitennummer.') from None
        pages=max(1,(len(rows)+49)//50);page=min(page,pages)
        return render_template('synthesis.html',p=project(pid),job=job,synthesis=synthesis,stale=stale,
            rows=rows[(page-1)*50:page*50],total=len(rows),page=page,pages=pages,
            review_hash=review_hash(parts,concerns),answer_count=sum(p['count'] for p in parts),
            ignored=ignored[(ignored_page-1)*50:ignored_page*50],ignored_count=len(ignored),
            ignored_page=ignored_page,ignored_pages=ignored_pages,editor_kinds=EDITOR_KINDS,tab='texts')

    @app.get('/p/<int:pid>/wave-texts/<jid>/synthesis.csv')
    def synthesis_csv(pid,jid):
        job=job_for(pid,jid)
        if not is_current(pid,job):raise ValueError('Dieser Wellenauftrag ist veraltet.')
        with db() as c:parts,concerns,synthesis=load(c,jid)
        if not synthesis:raise ValueError('Noch keine Gesamtauswertung vorhanden.')
        rows=summaries(parts,concerns,statement_index(parts));stream=io.StringIO()
        writer=csv.writer(stream,delimiter=';')
        writer.writerow(['Frage','Thema','Kernaussage oder Nuance','Einordnung','Begründung','Textantwortende Aussage','Textantwortende Frage','Anteil (%)','Status'])
        def safe(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value
        for r in rows:
            writer.writerow([safe(r['label']),safe(r['topic']),safe(r['body']),EDITOR_KINDS[r['kind']],safe(r['rationale'])]+[r['count'],r['total'],
                (f"{r['percent']:.1f}".replace('.',',') if r['percent'] is not None else ''),'aktuell' if r['valid'] else 'Quellen verändert'])
        return send_file(io.BytesIO(stream.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name=f'Textauswertung_{jid[:8]}.csv')
