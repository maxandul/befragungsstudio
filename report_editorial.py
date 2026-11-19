"""Reviewed wave-level concerns projected only after filtering their individual sources."""
import json
import secrets
from collections import defaultdict
from flask import abort, flash, g, redirect, render_template, request, url_for
from text_analysis import digest
from wave_analysis import normalized

KINDS={'key':'Kernaussage','difference':'Abweichende Sichtweise','single':'Besonderer Hinweis','normal':'Weiteres Anliegen'}


def statement_index(parts):
    result={}
    for p in parts:
        if not p['result']:continue
        records={r['id']:r for r in json.loads(p['records'])}
        for a in json.loads(p['result'])['antworten']:
            r=records[a['id']]
            for i,s in enumerate(a['aussagen']):
                ref=digest([p['id'],a['id'],i])
                value=dict(ref=ref,canonical=p['canonical'],topic=s['thema'],text=s['aussage'],
                           key=r['key'],label=p['label'],original=r['text'])
                value['hash']=digest([value['canonical'],value['topic'],value['text'],value['key']])
                result[ref]=value
    return result


def valid_concern(concern,index):
    refs=json.loads(concern['sources'])
    return bool(refs) and all(ref in index and index[ref]['hash']==h and index[ref]['canonical']==concern['canonical'] for ref,h in refs.items())


def project_concerns(index,concerns,eligible,aliases,disclosure=None):
    """A reviewed sentence must be supported by EACH source; never concatenate narratives."""
    grouped=defaultdict(dict);assigned=set()
    def add(canonical,topic,entry):
        bucket=grouped[canonical].setdefault(normalized(topic),dict(titel=topic,statements=[]))
        bucket['statements'].append(entry)
    for c in concerns:
        if not valid_concern(c,index):continue
        refs=json.loads(c['sources']);assigned.update(refs)
        visible=[index[ref] for ref in refs if tuple(index[ref]['key']) in eligible]
        if not visible:continue
        people={tuple(v['key'][:2]) for v in visible}
        attribution=disclosure.summarise(people,bundled=True) if disclosure else {}
        if attribution is None:
            continue
        topic=aliases.get(c['topic'],c['topic'])
        nuances={}
        if not attribution.get('pooled'):
            concern_text=normalized(c['body'])
            for source in visible:
                key=normalized(source['text'])
                if key==concern_text:
                    continue
                nuance=nuances.setdefault(key, dict(text=source['text'],people=set()))
                nuance['people'].add(tuple(source['key'][:2]))
        details=sorted(
            (dict(text=nuance['text'],count=len(nuance['people'])) for nuance in nuances.values()),
            key=lambda nuance: (-nuance['count'],nuance['text'].casefold()),
        )
        add(c['canonical'],topic,dict(text=c['body'],kind=c['kind'],order=c['sort_order'],reviewed=True,
            details=details,count=len(people),people=people,**attribution))
    ungrouped={}
    for ref,s in index.items():
        if ref in assigned or tuple(s['key']) not in eligible:continue
        person=tuple(s['key'][:2])
        if disclosure and disclosure.summarise({person}) is None:
            continue
        topic=aliases.get(s['topic'],s['topic'])
        key=(s['canonical'],normalized(topic),normalized(s['text']))
        item=ungrouped.setdefault(key,dict(canonical=s['canonical'],topic=topic,text=s['text'],people=set()))
        item['people'].add(person)
    for s in ungrouped.values():
        attribution=disclosure.summarise(s['people']) if disclosure else {}
        add(s['canonical'],s['topic'],dict(text=s['text'],kind='normal',order=100,reviewed=False,
            details=[],count=len(s['people']),people=s['people'],**attribution))
    output={}
    for canonical,topics in grouped.items():
        output[canonical]=[]
        for bucket in sorted(topics.values(),key=lambda b:b['titel'].casefold()):
            bucket['statements'].sort(key=lambda s:(s['order'],s['text'].casefold()))
            bucket['aussage']=''
            output[canonical].append(bucket)
    return output


def register(app,db,project,job_for,is_current):
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS text_concerns(
          id TEXT PRIMARY KEY,job TEXT NOT NULL,canonical TEXT NOT NULL,topic TEXT NOT NULL,
          body TEXT NOT NULL,kind TEXT NOT NULL,sort_order INTEGER NOT NULL DEFAULT 100,
          sources TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0)''')
        c.execute('CREATE INDEX IF NOT EXISTS concerns_job ON text_concerns(job,canonical)')

    def load(jid):
        if not hasattr(g,'editorial_index'):g.editorial_index={}
        if jid not in g.editorial_index:
            with db() as c:
                parts=[dict(r) for r in c.execute('SELECT * FROM wave_text_parts WHERE job=? ORDER BY position',(jid,))]
            g.editorial_index[jid]=statement_index(parts)
        with db() as c:
            concerns=[dict(r) for r in c.execute('SELECT * FROM text_concerns WHERE job=? ORDER BY sort_order,rowid',(jid,))]
        return g.editorial_index[jid],concerns

    @app.route('/p/<int:pid>/wave-texts/<jid>/concerns',methods=['GET','POST'])
    def text_concerns(pid,jid):
        job=job_for(pid,jid);stale=not is_current(pid,job)
        index,concerns=load(jid)
        with db() as c:
            ready=c.execute("SELECT COUNT(*) FROM wave_text_parts WHERE job=? AND state!='approved'",(jid,)).fetchone()[0]==0
            synthesis_pending=c.execute("SELECT 1 FROM wave_syntheses WHERE job=? AND state='imported'",(jid,)).fetchone() is not None
            ready=ready or synthesis_pending
        canonical=request.args.get('question','')
        questions={s['canonical']:s['label'] for s in index.values()}
        canonical=canonical or next(iter(questions),'')
        if canonical and canonical not in questions:raise ValueError('Diese Textfrage ist nicht vorhanden.')
        if request.method=='POST':
            if stale or not ready:raise ValueError('Bitte zuerst alle Teilpakete auf aktuellem Datenstand freigeben.')
            action=request.form.get('action');cid=request.form.get('concern','')
            existing=next((c for c in concerns if c['id']==cid),None)
            if action in ('edit','delete','add'):
                if not existing:raise ValueError('Das Anliegen ist nicht mehr vorhanden.')
                if request.form.get('revision')!=str(existing['revision']):raise ValueError('Das Anliegen wurde inzwischen geändert. Bitte neu laden.')
            if action=='delete':
                with db() as c:
                    cursor=c.execute('DELETE FROM text_concerns WHERE id=? AND job=? AND revision=?',(cid,jid,existing['revision']))
                    if cursor.rowcount!=1:raise ValueError('Das Anliegen wurde inzwischen geändert. Bitte neu laden.')
                flash('Bündelung aufgelöst. Die Einzelaussagen bleiben erhalten.')
            elif action in ('create','edit','add'):
                if request.form.get('supported')!='on':raise ValueError('Bitte bestätigen, dass jede Quelle die gemeinsame Formulierung stützt.')
                if existing and not valid_concern(existing,index):raise ValueError('Quellen des Anliegens wurden verändert. Bitte die Bündelung auflösen und neu prüfen.')
                refs=set(json.loads(existing['sources'])) if existing else set()
                if action!='edit':refs.update(request.form.getlist('source'))
                if not refs or any(ref not in index for ref in refs):raise ValueError('Bitte vorhandene Aussagen auswählen.')
                canonicals={index[ref]['canonical'] for ref in refs}
                if len(canonicals)!=1 or canonical not in canonicals:raise ValueError('Ein Anliegen darf nur Aussagen derselben Frage enthalten.')
                occupied={ref for concern in concerns if concern['id']!=cid and valid_concern(concern,index) for ref in json.loads(concern['sources'])}
                if refs & occupied:raise ValueError('Eine Aussage gehört bereits zu einem anderen Anliegen. Bitte diese Bündelung zuerst auflösen.')
                # Source hashes prevent a stale selection from binding changed statements.
                for ref in refs:
                    if ref not in (json.loads(existing['sources']) if existing else {}) and request.form.get('hash_'+ref)!=index[ref]['hash']:
                        raise ValueError('Eine ausgewählte Aussage wurde geändert. Bitte neu laden.')
                topic=request.form.get('topic','').strip();body=request.form.get('body','').strip()
                rationale=request.form.get('rationale',existing.get('rationale','') if existing else '').strip()
                kind=request.form.get('kind','normal')
                try:order=int(request.form.get('order','100'))
                except ValueError:raise ValueError('Die Reihenfolge muss eine ganze Zahl sein.') from None
                if not topic or len(topic)>160 or not body or len(body)>4000 or kind not in KINDS or not 0<=order<=10000 or len(rationale)>2000:
                    raise ValueError('Bitte Thema, Formulierung, Darstellung und Reihenfolge prüfen.')
                sources=json.dumps({ref:index[ref]['hash'] for ref in sorted(refs)})
                with db() as c:
                    # Recheck assignments inside the same write transaction (parallel editors).
                    c.execute('BEGIN IMMEDIATE')
                    parts=[dict(r) for r in c.execute('SELECT * FROM wave_text_parts WHERE job=?',(jid,))]
                    fresh=statement_index(parts)
                    if (not synthesis_pending and any(p['state']!='approved' for p in parts)) or any(ref not in fresh or fresh[ref]['hash']!=index[ref]['hash'] for ref in refs):
                        raise ValueError('Quellen oder Freigaben wurden inzwischen geändert. Bitte neu laden.')
                    latest=[dict(r) for r in c.execute('SELECT * FROM text_concerns WHERE job=?',(jid,))]
                    used={ref for other in latest if other['id']!=cid and valid_concern(other,index) for ref in json.loads(other['sources'])}
                    if refs & used:raise ValueError('Eine Quelle wurde inzwischen einem anderen Anliegen zugeordnet. Bitte neu laden.')
                    if existing:
                        cursor=c.execute('UPDATE text_concerns SET topic=?,body=?,kind=?,sort_order=?,sources=?,rationale=?,revision=revision+1 WHERE id=? AND job=? AND revision=?',
                                         (topic,body,kind,order,sources,rationale,cid,jid,existing['revision']))
                        if cursor.rowcount!=1:raise ValueError('Das Anliegen wurde inzwischen geändert. Bitte neu laden.')
                    else:
                        c.execute('INSERT INTO text_concerns(id,job,canonical,topic,body,kind,sort_order,sources,rationale) VALUES(?,?,?,?,?,?,?,?,?)',
                                  (secrets.token_hex(16),jid,canonical,topic,body,kind,order,sources,rationale))
                flash('Anliegen für diese Welle gespeichert. Die Quellen werden pro OE gefiltert.')
            else:raise ValueError('Unbekannte Aktion.')
            return redirect(url_for('text_concerns',pid=pid,jid=jid,question=canonical))
        search=request.args.get('search','').strip().casefold()
        rows=[s for s in index.values() if s['canonical']==canonical and (not search or search in (s['topic']+' '+s['text']).casefold())]
        rows.sort(key=lambda s:(s['topic'].casefold(),s['text'].casefold(),s['ref']))
        try:page=max(1,int(request.args.get('page','1')))
        except ValueError:raise ValueError('Ungültige Seitennummer.') from None
        pages=max(1,(len(rows)+49)//50);page=min(page,pages)
        occupied={ref:c['id'] for c in concerns if valid_concern(c,index) for ref in json.loads(c['sources'])}
        items=[dict(c,valid=valid_concern(c,index),references=[index[ref] for ref in json.loads(c['sources']) if ref in index])
               for c in concerns if c['canonical']==canonical]
        for item in items:
            item['person_count']=len({tuple(ref['key'][:2]) for ref in item['references']})
        items.sort(key=lambda c:(-c['person_count'],c['sort_order'],c['body'].casefold()))
        concern_locations={c['id']:i//50+1 for i,c in enumerate(items)}
        options=[{key:c[key] for key in ('id','revision','topic','body','kind','sort_order','rationale')} for c in items if c['valid']]
        try:concern_page=max(1,int(request.args.get('concern_page','1')))
        except ValueError:raise ValueError('Ungültige Anliegenseite.') from None
        concern_pages=max(1,(len(items)+49)//50);concern_page=min(concern_page,concern_pages)
        concern_total=len(items)
        items=items[(concern_page-1)*50:concern_page*50]
        return render_template('concerns.html',p=project(pid),job=job,questions=questions,canonical=canonical,
            rows=rows[(page-1)*50:page*50],page=page,pages=pages,total=len(rows),search=request.args.get('search',''),
            concerns=items,concern_options=options,concern_locations=concern_locations,
            unassigned=sum(s['canonical']==canonical and ref not in occupied for ref,s in index.items()),concern_total=concern_total,concern_page=concern_page,concern_pages=concern_pages,
            occupied=occupied,kinds=KINDS,stale=stale,ready=ready,tab='texts')

    def project_job(jid,eligible,aliases,disclosure=None):
        index,concerns=load(jid)
        return project_concerns(index,concerns,eligible,aliases,disclosure)
    return project_job
