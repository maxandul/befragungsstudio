"""Report design, saved project configurations and scoped editorial changes."""
import hashlib
import json
from collections import defaultdict
from urllib.parse import urlencode

from flask import abort, flash, redirect, render_template, request, url_for

from report_views import prepare_text_views


def display_options(args):
    profile=args.get('profile','gl')
    print_mode=args.get('print_mode','full' if profile=='oe' else 'compact')
    if profile not in ('gl','oe') or print_mode not in ('compact','full'):
        raise ValueError('Bitte eine vorhandene Berichtsvorlage und Druckansicht wählen.')
    summaries=args.get('include_summaries')=='1' or (
        'profile' in args and 'text_options_set' not in args and 'include_summaries' not in args)
    return dict(profile=profile,print_mode=print_mode,include_summaries=summaries,
                include_evidence=args.get('include_evidence')=='1',include_texts=args.get('include_texts')=='1',
                include_children=args.get('include_children','1')=='1')


def revision(body,tokens):
    return hashlib.sha256(json.dumps([body,sorted(tokens)],ensure_ascii=False).encode()).hexdigest()


def editorial_values(c,pid,scope,wave,root_scope):
    def values(table,fields,key):
        return c.execute(f'SELECT {fields} FROM {table} WHERE project=? AND scope=? AND wave=?',(pid,key,wave))
    notes=dict(values('report_notes','theme,body',scope))
    evidence=defaultdict(list)
    for theme,token in values('report_evidence','theme,token',scope):
        evidence[theme].append(token)
    if root_scope and scope:
        for theme,token in values('report_evidence','theme,token',''):
            if theme not in notes:
                evidence[theme].append(token)
        for theme,body in values('report_notes','theme,body',''):
            notes.setdefault(theme,body)
    return notes,evidence


def register(app,db,project,report_outline,report_scope,report_data,approved_summaries):
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS report_presets(
            id INTEGER PRIMARY KEY AUTOINCREMENT, project INTEGER NOT NULL, name TEXT NOT NULL,
            settings TEXT NOT NULL, updated INTEGER NOT NULL, UNIQUE(project,name))""")

    def settings(fields):
        keys=('profile','print_mode','focus_wave','oe','dimension','unit','min_n','include_children',
              'text_options_set','include_summaries','include_evidence','include_texts','wave')
        return {key:fields.getlist(key) for key in keys if key in fields}

    def link(endpoint,pid,params,**extra):
        return url_for(endpoint,pid=pid)+'?'+urlencode({**params,**extra},doseq=True)

    @app.get('/p/<int:pid>/results')
    def view_results(pid):
        with db() as c:
            presets=c.execute('SELECT id,name,updated FROM report_presets WHERE project=? ORDER BY name COLLATE NOCASE',(pid,)).fetchall()
            if 'load' in request.args or (not request.args and presets):
                if 'load' in request.args:
                    saved=c.execute('SELECT * FROM report_presets WHERE project=? AND id=?',(pid,request.args['load'])).fetchone()
                else:
                    saved=c.execute('SELECT * FROM report_presets WHERE project=? ORDER BY updated DESC LIMIT 1',(pid,)).fetchone()
                if saved is None:
                    abort(404)
                return redirect(link('view_results',pid,json.loads(saved['settings']),preset=saved['id']))
        try:
            selection=report_outline(pid,request.args)
            node,dimension,unit=report_scope(selection.nodes,request.args)
            options=display_options(request.args)
        except ValueError:
            if not request.args.get('preset') or request.args.get('fresh'):
                raise
            flash('Die gespeicherte Auswahl ist nicht mehr verfügbar. Bitte Welle und OE neu wählen.')
            return redirect(url_for('view_results',pid=pid,fresh=1,preset=request.args['preset']))
        branches=defaultdict(list)
        for n in selection.nodes:
            branches[n['parent']].append(n)
        for siblings in branches.values():
            siblings.sort(key=lambda n:n['unit'].casefold())
        batch=set(request.args.getlist('report_oe'))
        allowed={n['id'] for n in selection.nodes if not node or n['path'][:len(node['path'])]==node['path']}
        if batch-allowed:
            flash('Einzelne Paket-OEs sind in dieser Auswahl nicht mehr verfügbar.')
        roots=[n for n in selection.reference_nodes if not n['parent']]
        selected_preset=next((r for r in presets if str(r['id'])==request.args.get('preset')),None)
        return render_template('results.html',p=selection.project,tab='results',available=selection.available,
            selected=selection.selected,focus_wave=selection.focus_wave,minimum=selection.minimum,
            single_root=roots[0] if len(roots)==1 else None,
            node=node,dimension=dimension,unit=unit,branches=branches,batch=batch & allowed,
            presets=presets,selected_preset=selected_preset,**options)

    @app.post('/p/<int:pid>/report/design')
    def report_design(pid):
        project(pid)
        form=request.form
        params=settings(form)
        # The legacy dimension filter can be replaced by picking a concrete path.
        if form.get('oe'):
            params.pop('dimension',None)
            params.pop('unit',None)
        batch=list(dict.fromkeys(form.getlist('report_oe')))
        action=form.get('action','preview')
        if action=='package':
            return redirect(link('report_package',pid,params),code=307)
        if action=='preview':
            return redirect(link('report',pid,params,preparing=1))
        if action=='html':
            return redirect(link('report',pid,params,download=1))
        if action=='charts':
            return redirect(link('charts',pid,params,preparing=1))
        if action=='editor':
            return redirect(link('report_editor',pid,params,report_oe=batch,preset=form.get('preset','')))
        if action=='delete_preset':
            with db() as c:
                changed=c.execute('DELETE FROM report_presets WHERE project=? AND id=? AND updated=?',
                                  (pid,form.get('preset'),form.get('preset_version')))
                if not changed.rowcount:
                    raise ValueError('Die Konfiguration wurde inzwischen geändert oder gelöscht. Bitte neu laden.')
            flash('Konfiguration gelöscht.')
            return redirect(url_for('view_results',pid=pid))
        if action!='save':
            abort(400)
        name=form.get('preset_name','').strip()
        if not name or len(name)>100:
            raise ValueError('Bitte einen Namen mit 1 bis 100 Zeichen für die Konfiguration angeben.')
        selection=report_outline(pid,form)
        node,_,_=report_scope(selection.nodes,form)
        display_options(form)
        allowed={n['id'] for n in selection.nodes if not node or n['path'][:len(node['path'])]==node['path']}
        if len(batch)>50 or set(batch)-allowed:
            raise ValueError('Bitte höchstens 50 Paket-OEs aus dem gewählten Organisationszweig auswählen.')
        params['report_oe']=batch
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            existing=c.execute('SELECT id,updated FROM report_presets WHERE project=? AND name=?',(pid,name)).fetchone()
            if existing and str(existing['id'])!=form.get('preset',''):
                raise ValueError('Dieser Name ist bereits vergeben. Laden Sie die Konfiguration zum Aktualisieren oder wählen Sie einen anderen Namen.')
            if existing and str(existing['updated'])!=form.get('preset_version'):
                raise ValueError('Die Konfiguration wurde inzwischen geändert. Bitte neu laden.')
            updated=c.execute('SELECT coalesce(max(updated),0)+1 FROM report_presets WHERE project=?',(pid,)).fetchone()[0]
            c.execute('''INSERT INTO report_presets(project,name,settings,updated) VALUES(?,?,?,?)
                         ON CONFLICT(project,name) DO UPDATE SET settings=excluded.settings,updated=excluded.updated''',
                      (pid,name,json.dumps(params),updated))
            saved=c.execute('SELECT id FROM report_presets WHERE project=? AND name=?',(pid,name)).fetchone()[0]
        flash('Berichtskonfiguration gespeichert.')
        return redirect(url_for('view_results',pid=pid,load=saved))

    def editor_context(pid):
        return report_data(pid,group_text_origins=True,for_editor=True)

    @app.get('/p/<int:pid>/report/editor')
    def report_editor(pid):
        ctx=editor_context(pid)
        summaries=approved_summaries(pid,dict(ctx,include_summaries=True))
        views=prepare_text_views(summaries,'oe',ctx['text_disclosure'])
        return render_template('report_editor.html',**ctx,text_views=views,tab='results',revision=revision)

    @app.post('/p/<int:pid>/report/notes')
    def report_notes(pid):
        ctx=editor_context(pid)
        bulk=request.form.get('bulk')=='1'
        if bulk and (request.form.get('scope')!=ctx['scope'] or request.form.get('reference_wave')!=ctx['reference_wave']):
            raise ValueError('Die Berichtsauswahl hat sich geändert. Bitte die Textredaktion erneut öffnen.')
        themes=request.form.getlist('theme')
        if not themes or len(themes)!=len(set(themes)) or (not bulk and len(themes)!=1):
            raise ValueError('Bitte die Textredaktion erneut öffnen.')
        updates=[]
        for i,theme in enumerate(themes):
            suffix=f'_{i}' if bulk else ''
            body=request.form.get('body'+suffix)
            tokens=set(request.form.getlist('evidence'+suffix))
            if theme not in ctx['note_themes'] or body is None or not tokens.issubset(ctx['evidence_options'].get(theme,{})):
                raise ValueError('Ein Abschnitt oder Textbeleg ist für diese Auswahl nicht mehr verfügbar. Bitte die Textredaktion erneut öffnen.')
            updates.append((theme,body.strip(),tokens,request.form.get('revision'+suffix)))
        scope,wave=ctx['scope'],ctx['reference_wave']
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            current,quotes=editorial_values(c,pid,scope,wave,ctx['root_scope'])
            for theme,body,tokens,original in updates:
                if bulk and original!=revision(current.get(theme,''),quotes.get(theme,[])):
                    raise ValueError('Die Berichtstexte wurden inzwischen geändert. Bitte die Textredaktion erneut öffnen.')
                if body==current.get(theme,'') and tokens==set(quotes.get(theme,[])):
                    continue
                c.execute('INSERT INTO report_notes VALUES(?,?,?,?,?) ON CONFLICT(project,scope,wave,theme) DO UPDATE SET body=excluded.body',
                          (pid,scope,wave,theme,body))
                c.execute('DELETE FROM report_evidence WHERE project=? AND scope=? AND wave=? AND theme=?',(pid,scope,wave,theme))
                c.executemany('INSERT INTO report_evidence VALUES(?,?,?,?,?)',[(pid,scope,wave,theme,t) for t in tokens])
        flash('Berichtstexte und Belege gespeichert.')
        return redirect(url_for('report_editor' if bulk else 'view_results',pid=pid)+'?'+request.query_string.decode())
