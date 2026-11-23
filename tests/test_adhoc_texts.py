import json
import hashlib
import sqlite3
import unittest

import test_oe_reports as report_fixture
from report_editorial import project_concerns
from report_text_privacy import TextDisclosure
from report_views import prepare_text_views
import text_analysis as ta


class AdHocTextTests(unittest.TestCase):
    setUp=report_fixture.OrganisationReportTests.setUp
    db=report_fixture.OrganisationReportTests.db
    payload=report_fixture.OrganisationReportTests.payload
    node=report_fixture.OrganisationReportTests.node

    def sources(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            records=[dict(r) for r in c.execute('SELECT * FROM answers')]
            for r in records:r['raw']=json.loads(r['raw'])
            questions={r['source']:dict(r) for r in c.execute('SELECT * FROM questions')}
            mappings=[dict(r) for r in c.execute('SELECT * FROM mappings')]
        return records,questions,mappings,[],[],set()

    def test_raw_cohort_is_fixed_and_only_adds_a_participation_row_when_used(self):
        before,payload_before=self.payload('min_n=5')
        self.assertNotIn('<td>ad hoc (Freitext)</td>',before.text)
        for suffix in ('','&include_children=0','&download=1&print_mode=full'):
            report,payload=self.payload('min_n=5&include_texts=1'+suffix)
            self.assertEqual(payload['cards'],payload_before['cards'])
            self.assertIn('<tr><td>ad hoc (Freitext)</td><td>5</td><td>–</td><td>–</td></tr>',report.text)
            self.assertIn('<summary>ad hoc <span class="answer-count">5 Beiträge</span>',report.text)
            for i in range(5):self.assertIn('Vertraulicher Text '+str(i),report.text)
            self.assertNotIn('<summary>A <span',report.text)
            self.assertNotIn('<summary>B <span',report.text)
            for card in payload['cards']:
                self.assertNotIn('ad hoc',[r['unit'] for r in card['children']])
        # A scope below the threshold must not inherit the parent's larger cohort.
        report,_=self.payload('min_n=5&include_texts=1&oe='+self.node('Bereich','A')['id'])
        self.assertNotIn('<td>ad hoc (Freitext)</td>',report.text)
        self.assertNotIn('Vertraulicher Text',report.text)

    def test_participation_basis_includes_non_writers_and_never_crosses_waves(self):
        with self.db() as c:
            # C is a sufficiently large ordinary unit, outside the ad hoc cohort.
            c.execute('INSERT INTO organisation VALUES(?,?)',('c',json.dumps(dict(OE_Kürzel='c',Amt='AFA',Bereich='C'))))
            for i in range(5):
                raw=json.dumps(dict(Amt='AFA',Bereich='C'))
                for source,answer in [('q','3'),('txt','Grosse Einheit '+str(i))]:
                    c.execute("INSERT INTO answers VALUES(1,'2026',?,?,?,'2026-10-01',?)",('C'+str(i),source,answer,raw))
            c.execute("UPDATE answers SET answer='' WHERE wave='2026' AND source='txt' AND feedback IN ('1','2','3','4')")
        report,_=self.payload('min_n=5&include_texts=1')
        self.assertIn('<tr><td>ad hoc (Freitext)</td><td>5</td>',report.text)
        self.assertIn('<summary>ad hoc <span class="answer-count">1 Beiträge</span>',report.text)
        self.assertIn('Vertraulicher Text 0',report.text)
        with self.db() as c:
            c.execute("UPDATE answers SET answer='' WHERE wave='2026' AND source='txt' AND feedback='0'")
        report,_=self.payload('min_n=5&include_texts=1')
        self.assertNotIn('<td>ad hoc (Freitext)</td>',report.text)
        with self.db() as c:
            c.execute("DELETE FROM answers WHERE wave='2026' AND feedback='4'")
        report,_=self.payload('min_n=5&include_texts=1')
        self.assertNotIn('Vertraulicher Text 0',report.text)
        self.assertNotIn('<td>ad hoc (Freitext)</td>',report.text)

    def test_origins_and_distinct_counts_at_all_levels_without_changing_the_import(self):
        sources=self.sources()
        disclosure=TextDisclosure(sources,'2026',5,[],True,scope=[('Amt','AFA')])
        self.assertEqual(len(disclosure.adhoc_people),5)
        index={str(i):dict(canonical='txt',key=['2026',str(i),'txt'],topic='Thema',
                           text='Nuance A' if i<2 else 'Nuance B',hash='h'+str(i)) for i in range(5)}
        concern=dict(canonical='txt',topic='Thema',body='Gemeinsame Kernaussage',kind='key',sort_order=1,
                     sources=json.dumps({str(i):'h'+str(i) for i in range(5)}))
        result=project_concerns(index,[concern],{tuple(v['key']) for v in index.values()},{},disclosure)
        statement=result['txt'][0]['statements'][0]
        self.assertEqual((statement['origins'],statement['count']),(['ad hoc'],5))
        self.assertEqual([(n['origins'],n['count']) for n in statement['details']],[(['ad hoc'],3),(['ad hoc'],2)])
        # The same people can support another claim; a theme counts each only once.
        for i in (0,1):
            index['extra'+str(i)]=dict(index[str(i)],text='Weiterer Aspekt',hash='extra'+str(i))
        extra=dict(concern,body='Zweite Kernaussage',sources=json.dumps({'extra0':'extra0','extra1':'extra1'}))
        result=project_concerns(index,[concern,extra],{tuple(v['key']) for v in index.values()},{},disclosure)
        view=prepare_text_views(result,'oe',disclosure)['txt'][0]
        self.assertEqual((view['origins'],view['count']),(['ad hoc'],5))
        single=project_concerns({'0':index['0']},[],{tuple(index['0']['key'])},{},disclosure)
        single_view=prepare_text_views(single,'oe',disclosure)['txt'][0]['all'][0]
        self.assertEqual((single_view['origins'],single_view['count'],single_view['kind_label']),(['ad hoc'],1,'Einzelaussage'))

    def test_selected_evidence_alone_adds_the_row_only_when_included(self):
        token=hashlib.sha256(json.dumps(['txt','Vertraulicher Text 0']).encode()).hexdigest()
        with self.db() as c:
            c.execute("INSERT INTO report_evidence VALUES(1,'','2026','Thema',?)",(token,))
        report,_=self.payload('min_n=5&include_evidence=1')
        self.assertIn('Vertraulicher Text 0',report.text)
        self.assertIn('<td>ad hoc (Freitext)</td><td>5</td>',report.text)
        report,_=self.payload('min_n=5&include_evidence=0')
        self.assertNotIn('<td>ad hoc (Freitext)</td>',report.text)

    def test_direct_parent_residual_joins_the_same_fixed_cohort(self):
        with self.db() as c:
            raw=json.dumps(dict(Amt='AFA'))
            for source,answer in [('q','3'),('txt','Privater Resthinweis')]:
                c.execute("INSERT INTO answers VALUES(1,'2026','direct',?,?,'2026-10-01',?)",(source,answer,raw))
        report,_=self.payload('min_n=5&include_texts=1')
        self.assertIn('Privater Resthinweis',report.text)
        self.assertIn('<td>ad hoc (Freitext)</td><td>6</td>',report.text)
        disclosure=TextDisclosure(self.sources(),'2026',5,[],True,scope=[('Amt','AFA')])
        self.assertEqual(disclosure.summarise({('2026','direct')}),dict(origins=['ad hoc']))
        combined=disclosure.summarise(disclosure.adhoc_people|{('2026','direct')},bundled=True)
        self.assertEqual(combined,dict(origins=['ad hoc']))
        for area in ('A','B'):
            lower,_=self.payload('min_n=5&include_texts=1&oe='+self.node('Bereich',area)['id'])
            self.assertNotIn('Privater Resthinweis',lower.text)
            self.assertNotIn('Vertraulicher Text',lower.text)

    def test_approved_summaries_reuse_existing_sources_and_only_display_safe_cohort(self):
        records=ta.collect(self.sources(),'2026',canonicals=['txt'],exclude_leaders=False)
        draft=ta.make_draft(records)
        selection=dict(wave='2026',canonicals=['txt'],exclude_leaders=False)
        result=dict(antworten=[dict(id=r['id'],aussagen=[dict(thema='Arbeitsalltag',aussage='Wiederkehrende Erfahrung')]) for r in draft])
        with self.db() as c:
            c.execute("INSERT INTO wave_text_jobs(id,project,wave,selection,fingerprint) VALUES('adhoc',1,'2026',?,?)",(json.dumps(selection),ta.digest(records)))
            c.execute("""INSERT INTO wave_text_parts(id,job,position,canonical,question_id,wording,label,count,state,records,result)
                      VALUES('part','adhoc',1,'txt','question','Frage','Text',5,'approved',?,?)""",(json.dumps(draft),json.dumps(result)))
        report,_=self.payload('min_n=5&include_summaries=1&profile=oe')
        self.assertIn('Wiederkehrende Erfahrung',report.text)
        self.assertIn('Herkunft ad hoc · 5 Textantworten',report.text)
        self.assertIn('<td>ad hoc (Freitext)</td><td>5</td>',report.text)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT state FROM wave_text_parts WHERE id='part'").fetchone()[0],'approved')
        report,_=self.payload('min_n=5&include_summaries=0&include_texts=0')
        self.assertNotIn('<td>ad hoc (Freitext)</td>',report.text)
