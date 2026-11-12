import io
import json
import re
import sqlite3
import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path

from app import create_app, DEFAULT_MISSING
from organisation import tree
from report_themes import topic_overviews


class OrganisationReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=create_app(self.root).test_client()
        self.entries=[dict(OE_Kürzel='a',Amt='AFA',Bereich='A',Team='Gleich'),
                      dict(OE_Kürzel='b',Amt='AFA',Bereich='B',Team='Gleich')]
        self.nodes=tree(self.entries)
        with self.db() as c:
            c.execute("INSERT INTO projects(id,name,kind,min_n) VALUES(1,'Puls AFA','echonovum',2)")
            for e in self.entries:
                c.execute('INSERT INTO organisation VALUES(?,?)',(e['OE_Kürzel'],json.dumps(e)))
            for dimension in ['Amt','Bereich','Team']:
                c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES(1,'*',?,?)",(dimension,dimension))
            for source,typ in [('q','scale'),('txt','text')]:
                c.execute('INSERT INTO questions(project,source,canonical,label,type,theme,missing) VALUES(1,?,?,?,?,?,?)',
                          (source,source,source,typ,'Thema',DEFAULT_MISSING))
            for wave in ['2024','2026']:
                for i,(area,value) in enumerate([('A','1'),('A','1'),('B','5'),('B','5'),('B','5')]):
                    raw=dict(Amt='AFA',Bereich=area,Team='Gleich',Question='Vollständiger Fragewortlaut',**{'Survey ID':'2330'})
                    for source,answer in [('q',value),('txt','Vertraulicher Text '+str(i))]:
                        c.execute('INSERT INTO answers VALUES(1,?,?,?,?,?,?)',
                                  (wave,str(i),source,answer,wave+'-10-01',json.dumps(raw)))
                for d,u,total in [('', '',5),('Amt','AFA',5),('Bereich','A',2),('Bereich','B',3),('Team','Gleich',5)]:
                    c.execute('INSERT INTO grounds VALUES(1,?,?,?,?)',(wave,d,u,total))
        self.csrf=self.client.get('/session/csrf').json['csrf']

    def db(self):
        return sqlite3.connect(self.root/'studio.sqlite3')

    def node(self,dimension,unit,parent=None):
        return next(n for n in self.nodes if n['dimension']==dimension and n['unit']==unit and (not parent or ('Bereich',parent) in n['path']))

    def payload(self,query=''):
        r=self.client.get('/p/1/report?focus_wave=2026&'+query)
        self.assertEqual(r.status_code,200,r.data[:1000])
        payload=json.loads(re.search(rb'<script id="chart-data" type="application/json">(.*?)</script>',r.data,re.S)[1])
        return r,payload

    def test_path_filter_separates_identical_team_names_and_ambiguous_denominators(self):
        team=self.node('Team','Gleich','A')
        response,payload=self.payload('oe='+team['id'])
        self.assertEqual(payload['cards'][0]['rows'][-1]['n'],2)
        self.assertEqual(payload['cards'][0]['rows'][-1]['mean'],1)
        self.assertIn(b'Nicht hinterlegt',response.data)
        self.assertEqual(self.client.get('/p/1/report?oe=unknown').status_code,400)

    def test_weighted_parent_children_and_suppression(self):
        _,payload=self.payload()
        card=payload['cards'][0]
        self.assertEqual(card['rows'][-1]['mean'],3.4)
        self.assertEqual({r['unit']:r['n'] for r in card['children']},{'A':2,'B':3})
        _,payload=self.payload('min_n=3')
        self.assertEqual([r['unit'] for r in payload['cards'][0]['children']],['B'])
        _,payload=self.payload('oe='+self.node('Bereich','A')['id'])
        self.assertEqual(payload['cards'][0]['comparisons'][0]['rows'][-1]['mean'],3.4)
        self.assertEqual(payload['cards'][0]['wording'],'Vollständiger Fragewortlaut')

    def test_texts_opt_in_notes_are_scoped_and_escaped(self):
        response,_=self.payload()
        self.assertNotIn(b'Vertraulicher Text',response.data)
        response,_=self.payload('include_texts=1')
        self.assertIn(b'Vertraulicher Text',response.data)
        response,_=self.payload('include_texts=1&min_n=6')
        self.assertNotIn(b'Vertraulicher Text',response.data)
        query='focus_wave=2026&oe='+self.node('Bereich','A')['id']
        r=self.client.post('/p/1/report/notes?'+query,data=dict(csrf=self.csrf,theme='Thema',body='<script>redaktionell</script>'))
        self.assertEqual(r.status_code,302)
        response,_=self.payload('oe='+self.node('Bereich','A')['id'])
        self.assertIn(b'&lt;script&gt;redaktionell&lt;/script&gt;',response.data)
        response,_=self.payload('oe='+self.node('Bereich','B')['id'])
        self.assertNotIn(b'redaktionell',response.data)

    def test_organisation_snapshots_preserve_previous_tree(self):
        csv='OE_Kürzel,Amt,Bereich,Team\na,AFA,Neu,Gleich\n'
        response=self.client.post('/organisation',data=dict(csrf=self.csrf,valid_from='2027-01-01',file=(io.BytesIO(csv.encode()),'oe.csv')))
        self.assertEqual(response.status_code,302)
        response,_=self.payload('oe='+self.node('Bereich','A')['id'])
        self.assertIn(b'Direktunterstellte Einheiten',response.data)
        with self.db() as c:
            old=json.loads(c.execute("SELECT entries FROM organisation_history WHERE valid_from='' ").fetchone()[0])
            self.assertEqual(len(old),2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM answers').fetchone()[0],20)
        # Anlegen eines Eintrags mit ungültigem Datum ist atomar.
        bad=self.client.post('/organisation',data=dict(csrf=self.csrf,action='entry',OE_Kürzel='z',Amt='AFA',valid_from='invalid'))
        self.assertEqual(bad.status_code,400)

    def test_results_have_oe_selection_new_tab_and_editable_notes(self):
        r=self.client.get('/p/1/results?focus_wave=2026')
        self.assertEqual(r.status_code,200)
        self.assertIn(b'name="oe"',r.data)
        self.assertNotIn(b'name="dimension"',r.data)
        self.assertIn(b'target="_blank"',r.data)
        self.assertIn(b'Textantworten sichten',r.data)
        self.assertEqual(self.client.get('/organisation').status_code,200)

    def test_theme_proposal_preserves_existing_assignments(self):
        with self.db() as c:
            c.execute("UPDATE questions SET label='Informationsfluss',theme='' WHERE source='q'")
        r=self.client.post('/p/1/report/themes?focus_wave=2026',data=dict(csrf=self.csrf))
        self.assertEqual(r.status_code,302)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT theme FROM questions WHERE source='q'").fetchone()[0],'Information und Orientierung')
            self.assertEqual(c.execute("SELECT theme FROM questions WHERE source='txt'").fetchone()[0],'Thema')

    def test_topic_overviews_keep_suppressed_current_results_empty(self):
        # Die Frage hat historisch genügend Antworten, aktuell aber nur eine.
        with self.db() as c:
            c.execute("DELETE FROM answers WHERE source='q' AND wave='2026' AND feedback!='0'")
        response,payload=self.payload()
        self.assertEqual(payload['overviews'][0]['reference_wave'],'2026')
        self.assertEqual(payload['overviews'][0]['indices'],[0])
        self.assertEqual([r['wave'] for r in payload['cards'][0]['rows']],['2024'])
        self.assertEqual(payload['cards'][0]['children'],[])
        self.assertNotIn(b'Vertraulicher Text',response.data)
        self.assertIn(b'data-topic="0"',response.data)
        self.assertIn(b'<details class="question-details">',response.data)
        self.assertIn(b'Einzelfragen und Details',response.data)

    def test_topic_overviews_separate_scales_and_limit_slide_size(self):
        def card(minimum=1,maximum=5,typ='scale'):
            return dict(theme='Thema',rows=[dict(type=typ,minimum=minimum,maximum=maximum)])
        cards=[card() for _ in range(7)]+[card(0,10),card(typ='choice_single')]
        cards.append(dict(theme='Thema',rows=[dict(type='scale',minimum=1,maximum=5),dict(type='scale',minimum=0,maximum=10)]))
        groups=topic_overviews(cards,'2026')
        self.assertEqual([o['indices'] for o in groups],[[0,1,2,3,4],[5,6],[7]])
        self.assertEqual([(o['part'],o['parts']) for o in groups],[(1,2),(2,2),(1,1)])

    @unittest.skipUnless(shutil.which('node'),'Optionaler Entwicklungstest benötigt Node.js')
    def test_topic_export_metrics_missing_values_and_legend_visibility(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('check_topic_exports.cjs'))],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def evidence_token(self,query='',text=None):
        page=self.client.get('/p/1/results?focus_wave=2026&'+query).data.decode()
        tokens=re.findall(r'name="evidence" value="([a-f0-9]{64})"',page)
        self.assertTrue(tokens)
        return tokens[0]

    def save_evidence(self,tokens,query='',body='Redaktionelle Zusammenfassung'):
        return self.client.post('/p/1/report/notes?focus_wave=2026&'+query,
                                data=dict(csrf=self.csrf,theme='Thema',body=body,evidence=tokens))

    def test_selected_evidence_is_opt_in_and_excludes_other_comments(self):
        token=self.evidence_token()
        self.assertEqual(self.save_evidence([token]).status_code,302)
        response,payload=self.payload()
        self.assertIn(b'Redaktionelle Zusammenfassung',response.data)
        self.assertNotIn(b'Vertraulicher Text',response.data)
        response,payload=self.payload('include_evidence=1')
        self.assertIn(b'Vertraulicher Text 0',response.data)
        self.assertNotIn(b'Vertraulicher Text 1',response.data)
        self.assertNotIn('Vertraulicher Text',json.dumps(payload))
        response,_=self.payload('include_texts=1')
        self.assertIn(b'Vertraulicher Text 1',response.data)

    def test_evidence_is_scoped_to_oe_wave_theme_and_minimum(self):
        area_a='oe='+self.node('Bereich','A')['id']
        area_b='oe='+self.node('Bereich','B')['id']
        token=self.evidence_token(area_a)
        self.assertEqual(self.save_evidence([token],area_a).status_code,302)
        response,_=self.payload(area_a+'&include_evidence=1')
        self.assertIn(b'Vertraulicher Text 0',response.data)
        response,_=self.payload(area_b+'&include_evidence=1')
        self.assertNotIn(b'Vertraulicher Text',response.data)
        response,_=self.payload(area_a+'&include_evidence=1&min_n=3')
        self.assertNotIn(b'Vertraulicher Text',response.data)
        response=self.client.get('/p/1/report?focus_wave=2024&'+area_a+'&include_evidence=1')
        self.assertNotIn(b'Vertraulicher Text',response.data)
        # Fremde/unterdrückte Referenzen dürfen auch nicht gespeichert werden.
        self.assertEqual(self.save_evidence([token],area_b).status_code,400)
        self.assertEqual(self.save_evidence([token],area_a+'&min_n=3').status_code,400)

    def test_changed_evidence_disappears_and_rejected_save_is_atomic(self):
        token=self.evidence_token()
        self.save_evidence([token])
        with self.db() as c:
            c.execute("UPDATE answers SET answer='Geänderter Text' WHERE wave='2026' AND source='txt' AND feedback='0'")
        response,_=self.payload('include_evidence=1')
        self.assertNotIn(b'Vertraulicher Text 0',response.data)
        self.assertNotIn('Geänderter Text'.encode(),response.data)
        page=self.client.get('/p/1/results?focus_wave=2026').data
        self.assertIn(b'bisher ausgew',page)
        self.assertEqual(self.save_evidence([token],body='Nicht speichern').status_code,400)
        with self.db() as c:
            self.assertEqual(c.execute('SELECT body FROM report_notes').fetchone()[0],'Redaktionelle Zusammenfassung')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM report_evidence').fetchone()[0],1)
        self.assertEqual(self.save_evidence([]).status_code,302)
        with self.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM report_evidence').fetchone()[0],0)

    def test_evidence_html_is_escaped_and_duplicate_quotes_are_single_choices(self):
        with self.db() as c:
            c.execute("UPDATE answers SET answer='<script>Zitat</script>' WHERE wave='2026' AND source='txt'")
        page=self.client.get('/p/1/results?focus_wave=2026').data.decode()
        tokens=re.findall(r'name="evidence" value="([a-f0-9]{64})"',page)
        self.assertEqual(len(tokens),1)
        self.save_evidence(tokens)
        # Die Referenzen überleben einen erneuten App-Start ohne neue Duplikate.
        client=create_app(self.root).test_client()
        response=client.get('/p/1/report?focus_wave=2026&include_evidence=1')
        self.assertIn(b'&lt;script&gt;Zitat&lt;/script&gt;',response.data)
        self.assertNotIn(b'<script>Zitat</script>',response.data)
