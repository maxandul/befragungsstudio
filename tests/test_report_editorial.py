import io
import json
import re
import unittest
import zipfile
import test_text_analysis as legacy
import test_wave_texts as wave
from report_editorial import statement_index, project_concerns
from report_views import prepare_text_views


class ReportEditorialTests(unittest.TestCase):
    setUp=legacy.TextAnalysisTests.setUp
    db=legacy.TextAnalysisTests.db
    post=legacy.TextAnalysisTests.post
    wave_job=wave.WaveTextTests.wave_job
    parts=wave.WaveTextTests.parts
    make_wave=wave.WaveTextTests.make_wave
    part_url=wave.WaveTextTests.part_url
    export_part=wave.WaveTextTests.export_part
    import_files=wave.WaveTextTests.import_files
    approve_part=wave.WaveTextTests.approve_part

    def ready(self):
        job,url=self.make_wave()
        results=[self.export_part(p)[1] for p in self.parts()]
        self.assertEqual(self.import_files(url,results).status_code,302)
        for p in self.parts():self.approve_part(p)
        return job,url+'/concerns?question=q',statement_index(self.parts())

    def create(self,url,index,refs=None,**overrides):
        refs=refs or [ref for ref,s in index.items() if s['canonical']=='q' and s['key'][1] in ('person-a','person-b')]
        data=dict(action='create',source=refs,topic='Zusammenarbeit',body='Gemeinsames Anliegen',kind='key',order='10',supported='on')
        data.update({'hash_'+ref:index[ref]['hash'] for ref in refs});data.update(overrides)
        return self.post(url,**data)

    def concern(self):
        with self.db() as c:
            c.row_factory=__import__('sqlite3').Row
            return dict(c.execute('SELECT * FROM text_concerns ORDER BY rowid DESC LIMIT 1').fetchone())

    def test_bundles_filter_sources_before_rendering_for_each_oe(self):
        _,url,index=self.ready()
        self.assertEqual(self.create(url,index).status_code,302)
        self.assertEqual(self.client.get(url).status_code,200)
        html=self.client.get('/p/1/report?'+self.query+'&profile=oe').text
        self.assertIn('Gemeinsames Anliegen',html)
        self.assertNotIn('Aussage person-b',html)
        self.assertNotIn('Aussage leader-a',html)
        self.assertNotIn('mail@example.org',html)
        editor=self.client.get('/p/1/report/editor?'+self.query+'&include_summaries=0').text
        self.assertIn('Gemeinsames Anliegen',editor)
        self.assertNotIn('Aussage person-b',editor)
        self.assertNotIn('Aussage leader-a',editor)
        # A team with no supporting source must not see this concern.
        with self.db() as c:
            c.execute("UPDATE answers SET raw=REPLACE(raw,'\"A\"','\"C\"') WHERE wave='2026' AND feedback='person-a'")
        html=self.client.get('/p/1/report?'+self.query+'&profile=oe').text
        self.assertNotIn('Gemeinsames Anliegen',html)

    def test_reviewed_origins_follow_report_level_and_disclosure_controls(self):
        with self.db() as c:
            c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES(1,'*','Team','Team')")
            rows=c.execute("SELECT wave,feedback,source,raw FROM answers WHERE feedback IN ('person-a','leader-a')").fetchall()
            for wave_id,feedback,source,raw in rows:
                dims=dict(json.loads(raw),Team='Nord')
                c.execute("UPDATE answers SET raw=? WHERE wave=? AND feedback=? AND source=?",
                          (json.dumps(dims),wave_id,feedback,source))
        _,url,index=self.ready()
        people={'person-a','person-b','leader-a'}
        for canonical,kind in [('q','key'),('t','single')]:
            refs=[ref for ref,entry in index.items() if entry['canonical']==canonical and entry['key'][1] in people]
            self.assertEqual(self.create(url.replace('question=q','question='+canonical),index,refs,
                                         kind=kind,body='Geprüft '+canonical).status_code,302)

        root='/p/1/report?focus_wave=2026&profile=gl'
        html=self.client.get(root).text
        printed=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',html,re.S))
        self.assertIn('Herkunft A, B · 3 Textantworten',printed)
        single=re.search(r'<summary>\s*<strong class="concern-label">Besonderer Hinweis</strong> <span class="concern-text">Geprüft t.*?</summary>',html,re.S)
        self.assertIsNotNone(single)
        self.assertIn('Herkunft A, B · 3 Textantworten',single[0])
        self.assertNotIn('Herkunft Nord',html)
        area=self.client.get('/p/1/report?'+self.query+'&profile=oe&download=1').text
        self.assertIn('Herkunft Führungsteam, Nord · 2 Textantworten',area)
        self.assertNotIn('Herkunft A, B',area)
        for suffix in ('','&include_children=0'):
            filtered=self.client.get(root+'&min_n=2&print_mode=full&download=1'+suffix).text
            self.assertIn('Geprüft q',filtered)
            self.assertIn('<summary>Thema · Zusammenarbeit',filtered)
            self.assertRegex(filtered,r'Geprüft q</span>\s*<small class="concern-origin">Herkunft ad hoc · 2 Textantworten</small>')
            self.assertIn('Zum Schutz kleiner Gruppen',filtered)
            self.assertNotIn('Aussage person-b',filtered)
            self.assertNotIn('Herkunft B',filtered)
        self.assertNotIn('Genannt in',self.client.get(root+'&include_summaries=0').text)

    def test_small_unit_single_is_withheld_and_single_section_is_last(self):
        _,url,index=self.ready()
        self.assertEqual(self.create(url,index).status_code,302)
        with self.db() as c:
            c.execute("INSERT INTO answers SELECT project,wave,'participant-without-text',source,'',date,raw "
                      "FROM answers WHERE feedback='person-a' AND wave='2026' AND source='q'")
        root='/p/1/report?focus_wave=2026&profile=oe&min_n=2&download=1'
        html=self.client.get(root).text
        self.assertIn('Gemeinsames Anliegen',html)
        self.assertIn('Einzelaussagen',html)
        self.assertIn('Aussage person-a',html)
        self.assertIn('Aussage person-b',html)  # The small residual now joins a fixed cohort.
        self.assertLess(html.index('Gemeinsames Anliegen'),html.index('<h4>Einzelaussagen'))
        self.assertNotIn('n &lt; 2)',html)

    def test_pool_uses_only_participation_in_contributing_groups(self):
        from report_text_privacy import TextDisclosure

        records=[]
        for group,n in [('A',2),('B',2),('C',8)]:
            for number in range(n):
                records.append(dict(wave='2026',feedback=f'{group}{number}',raw=dict(Amt='AFA',Bereich=group)))
        mappings=[dict(wave='*',dimension=d,source=d) for d in ('Amt','Bereich')]
        disclosure=TextDisclosure((records,{},mappings,[],[],[]),'2026',5,[],False)
        source=lambda name: ('2026',name)
        self.assertIsNone(disclosure.summarise({source('A0'),source('B0')},bundled=True))
        self.assertIsNone(disclosure.summarise({source('A0'),source('A1')},bundled=True))
        self.assertIsNone(disclosure.summarise({source('A0'),source('C0')},bundled=True))

    def test_fixed_cohort_counts_never_depend_on_statement_support(self):
        from report_text_privacy import TextDisclosure

        records=[dict(wave='2026',feedback=f'{group}{n}',raw=dict(Amt='AFA',Bereich=group))
                 for group in ('A','B') for n in range(4)]
        mappings=[dict(wave='*',dimension=d,source=d) for d in ('Amt','Bereich')]
        disclosure=TextDisclosure((records,{},mappings,[],[],[]),'2026',5,[],True)
        people=set(disclosure.paths)
        safe=people-{('2026','A3'),('2026','B3'),('2026','B2')}
        for selected in (safe,people,safe-{('2026','A2')}):
            self.assertEqual(disclosure.summarise(selected,bundled=True),dict(origins=['ad hoc']))
        lower=TextDisclosure((records,{},mappings,[],[],[]),'2026',5,[],True,
                             scope=[('Amt','AFA'),('Bereich','A')])
        self.assertIsNone(lower.summarise({('2026','A0')},bundled=True))

    def test_profiles_and_deterministic_print_content(self):
        _,url,index=self.ready();self.create(url,index)
        normal=[ref for ref,s in index.items() if s['canonical']=='t' and s['key'][1]=='person-a']
        second_url=url.replace('question=q','question=t')
        self.assertEqual(self.create(second_url,index,normal,kind='single',body='Besonderer Einzelhinweis').status_code,302)
        compact=self.client.get('/p/1/report?'+self.query+'&profile=gl&print_mode=compact').text
        printed=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',compact,re.S))
        self.assertNotIn('Gemeinsames Anliegen',printed)  # Only one supporting person in this OE.
        self.assertNotIn('Besonderer Einzelhinweis',printed)
        self.assertIn('Besonderer Einzelhinweis',compact)  # Retained behind the detail disclosure.
        global_html=self.client.get('/p/1/report?focus_wave=2026&min_n=1&profile=gl&print_mode=compact').text
        global_print=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',global_html,re.S))
        self.assertIn('Gemeinsames Anliegen',global_print)
        self.assertNotIn('Besonderer Einzelhinweis',global_print)
        self.assertNotIn('Aussage person-a',printed)  # Nuance not in compact print.
        full=self.client.get('/p/1/report?'+self.query+'&profile=gl&print_mode=full').text
        printed=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',full,re.S))
        self.assertNotIn('Aussage person-a',printed)
        self.assertIn('Gemeinsames Anliegen',printed)
        self.assertNotIn('Aussage person-b',printed)
        self.assertNotIn('mail@example.org',printed)
        # Full raw text remains a separate explicit opt-in.
        raw=self.client.get('/p/1/report?'+self.query+'&profile=oe&include_texts=1&print_mode=full').text
        self.assertIn('mail@example.org',raw)
        self.assertNotIn('mail@example.org',self.client.get('/p/1/report?'+self.query+'&profile=oe').text)
        self.assertNotIn('Gemeinsames Anliegen',self.client.get('/p/1/report?'+self.query+'&profile=oe&text_options_set=1').text)
        self.assertEqual(self.client.get('/p/1/report?profile=invalid').status_code,400)
        self.assertEqual(self.client.get('/p/1/results?'+self.query+'&profile=gl').status_code,200)

    def test_no_arbitrary_top_three_or_fabricated_compact_summary(self):
        topics={'q':[dict(titel='Thema',statements=[dict(text='Punkt '+str(i),kind='normal',details=[]) for i in range(12)])]}
        oe=prepare_text_views(topics,'oe')['q'][0]
        self.assertEqual(len(oe['main']),12)
        gl=prepare_text_views(topics,'gl')['q'][0]
        self.assertEqual(gl['main'],[]);self.assertEqual(len(gl['all']),12)

    def test_rejects_cross_question_duplicate_assignments_and_stale_sources(self):
        _,url,index=self.ready()
        refs=list(index)[:1]+[ref for ref,s in index.items() if s['canonical']=='t'][:1]
        self.assertEqual(self.create(url,index,refs).status_code,400)
        self.assertEqual(self.create(url,index,supported='').status_code,400)
        ref=next(ref for ref,s in index.items() if s['canonical']=='q')
        self.assertEqual(self.create(url,index,[ref],**{'hash_'+ref:'old'}).status_code,400)
        self.assertEqual(self.create(url,index).status_code,302)
        self.assertEqual(self.create(url,index).status_code,400)
        c=self.concern()
        self.assertEqual(self.post(url,action='edit',concern=c['id'],revision='99',supported='on').status_code,400)
        # Changed part statements invalidate just this bundle, not the reviewed source contents.
        with self.db() as conn:
            p=next(p for p in self.parts() if p['canonical']=='q' and any(r['key'][1]=='person-a' for r in json.loads(p['records'])))
            rid=next(r['id'] for r in json.loads(p['records']) if r['key'][1]=='person-a')
            result=json.loads(p['result'])
            next(a for a in result['antworten'] if a['id']==rid)['aussagen'][0]['aussage']='Redigierte Aussage'
            conn.execute('UPDATE wave_text_parts SET result=? WHERE id=?',(json.dumps(result),p['id']))
        html=self.client.get('/p/1/report?'+self.query+'&profile=oe').text
        self.assertNotIn('Gemeinsames Anliegen',html)
        self.assertIn('Quellen verändert',self.client.get(url).text)

    def test_delete_retains_statements_and_escaping(self):
        _,url,index=self.ready()
        self.create(url,index,body='<script>gemeinsamer Text</script>')
        html=self.client.get('/p/1/report?'+self.query+'&profile=gl').text
        self.assertIn('&lt;script&gt;gemeinsamer Text&lt;/script&gt;',html)
        self.assertNotIn('<script>gemeinsamer Text</script>',html)
        c=self.concern()
        self.assertEqual(self.post(url,action='delete',concern=c['id'],revision=str(c['revision'])).status_code,302)
        html=self.client.get('/p/1/report?'+self.query+'&profile=oe').text
        self.assertIn('Aussage person-a',html)
        self.assertNotIn('gemeinsamer Text',html)

    def test_report_package_generates_scoped_html_files(self):
        _,url,index=self.ready();self.create(url,index)
        from organisation import tree
        nodes=tree([], [dict(Amt='AFA',Bereich='A'),dict(Amt='AFA',Bereich='B')])
        b=next(n['id'] for n in nodes if n['dimension']=='Bereich' and n['unit']=='B')
        query='focus_wave=2026&min_n=1&profile=oe'
        response=self.post('/p/1/reports.zip?'+query,report_oe=[self.oe,b])
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            self.assertEqual(len(z.namelist()),2)
            a_html=z.read('01_A.html').decode();b_html=z.read('02_B.html').decode()
            self.assertIn('Aussage person-a',a_html);self.assertNotIn('Aussage person-b',a_html)
            self.assertIn('Aussage person-b',b_html);self.assertNotIn('Aussage person-a',b_html)
            self.assertNotIn('Zur App',a_html)
            self.assertNotIn('mail@example.org',a_html)
        self.assertEqual(self.post('/p/1/reports.zip?'+query,report_oe=['unknown']).status_code,400)
        self.assertEqual(self.post('/p/1/reports.zip?'+query+'&oe='+self.oe,report_oe=[b]).status_code,400)

    def test_profiles_leave_quantitative_results_and_oe_notes_unchanged(self):
        self.ready()
        with self.db() as c:
            c.execute("INSERT INTO questions(project,source,canonical,label,type,theme,missing) VALUES(1,'score','score','Score','scale','Thema','')")
            for feedback,area,value,role in [('person-a','A','1',''),('person-b','B','5',''),('leader-a','A','3','100')]:
                raw=json.dumps({'Amt':'AFA','Bereich':area,'Kadertyp':role,'Question':'Skalenfrage'})
                c.execute("INSERT INTO answers VALUES(1,'2026',?,'score',?,'2026-10-01',?)",(feedback,value,raw))
        payloads=[]
        for profile in ('gl','oe'):
            html=self.client.get('/p/1/report?'+self.query+'&profile='+profile).text
            payloads.append(json.loads(re.search(r'<script id="chart-data" type="application/json">(.*?)</script>',html,re.S)[1]))
        self.assertEqual(payloads[0]['cards'],payloads[1]['cards'])
        self.assertEqual(payloads[0]['cards'][0]['rows'][-1]['mean'],1)
        self.assertEqual(self.post('/p/1/report/notes?'+self.query,theme='Erkenntnisse auf einen Blick',body='Nur diese OE').status_code,302)
        self.assertIn('Nur diese OE',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)
        self.assertNotIn('Nur diese OE',self.client.get('/p/1/report?focus_wave=2026&profile=gl&min_n=1').text)

    def test_add_sources_across_pages_preserves_review_and_uniqueness(self):
        _,url,index=self.ready()
        refs=[ref for ref,s in index.items() if s['canonical']=='q' and s['key'][1] in ('person-a','person-b')]
        self.assertEqual(self.create(url,index,[refs[0]]).status_code,302)
        c=self.concern()
        self.assertEqual(self.create(url,index,[refs[1]],action='add',concern=c['id'],revision=str(c['revision'])).status_code,302)
        self.assertEqual(len(json.loads(self.concern()['sources'])),2)


class EditorialScaleTests(unittest.TestCase):
    def test_ten_thousand_statements_remain_source_scoped(self):
        parts=[]
        for part_number in range(200):
            records=[];answers=[]
            for i in range(part_number*50,(part_number+1)*50):
                records.append(dict(id=str(i),key=['2026',str(i),'q'],text='Original '+str(i)))
                answers.append(dict(id=str(i),aussagen=[dict(thema='Abläufe',aussage='Detail '+str(i))],grund=''))
            parts.append(dict(id=str(part_number),canonical='q',label='Frage',
                              records=json.dumps(records),result=json.dumps(dict(antworten=answers))))
        index=statement_index(parts)
        self.assertEqual(len(index),10000)
        refs={ref:s['hash'] for ref,s in index.items()}
        concern=dict(canonical='q',topic='Abläufe',body='Gemeinsames Anliegen',kind='key',sort_order=1,sources=json.dumps(refs))
        eligible={('2026',str(i),'q') for i in range(100)}
        output=project_concerns(index,[concern],eligible,{})
        entries=output['q'][0]['statements']
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]['count'],100)
        self.assertEqual(len(entries[0]['details']),100)
        self.assertNotIn('Detail 9999',{n['text'] for n in entries[0]['details']})


if __name__=='__main__':unittest.main()
