import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from app import create_app, DEFAULT_MISSING
from organisation import tree
from report_editorial import project_concerns
from report_text_privacy import TextDisclosure
import text_analysis as ta


class LeadershipTeamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=create_app(self.root).test_client()
        self.entries=[dict(OE_Kürzel=area,Amt='Amt',Bereich=area,Team='Team') for area in ('A','B','C')]
        self.nodes=tree(self.entries)
        with self.db() as c:
            c.execute("INSERT INTO projects(id,name,kind,min_n) VALUES(1,'Puls','other',3)")
            for entry in self.entries:
                c.execute('INSERT INTO organisation VALUES(?,?)',(entry['OE_Kürzel'],json.dumps(entry)))
            for dim in ('Amt','Bereich','Team'):
                c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES(1,'*',?,?)",(dim,dim))
            for source,typ in [('scale','scale'),('other','scale'),('text','text')]:
                c.execute('INSERT INTO questions(project,source,canonical,label,type,theme,missing) VALUES(1,?,?,?,?,?,?)',
                          (source,source,source,typ,'Thema',DEFAULT_MISSING))
            for wave in ('2025','2026'):
                people=[('root','','','100','1'),('unknown','','','110','1')]
                for area in ('A','B','C'):
                    people.extend([(area+'-head',area,'','100','5'),
                                   (area+'-team-head',area,'Team','100','1')])
                    people.extend((area+str(i),area,'Team','','2') for i in range(3))
                for person,area,team,role,value in people:
                    raw=json.dumps(dict(Amt='Amt',Bereich=area,Team=team,Kadertyp=role))
                    for source in ('scale','other','text'):
                        answer='Text '+person if source=='text' else value
                        if source=='text' and person=='unknown':answer=''
                        # Participation threshold is met, but this question has fewer answers.
                        if source=='other' and person=='C-head' and wave=='2026':answer='Keine Antwort'
                        c.execute('INSERT INTO answers VALUES(1,?,?,?,?,?,?)',
                                  (wave,person,source,answer,wave+'-10-01',raw))

    def db(self):return sqlite3.connect(self.root/'studio.sqlite3')

    def report(self,**params):
        response=self.client.get('/p/1/report?'+urlencode({'focus_wave':'2026',**params}))
        self.assertEqual(response.status_code,200)
        payload=json.loads(re.search(r'<script id="chart-data" type="application/json">(.*?)</script>',response.text,re.S)[1])
        return response.text,payload

    def card(self,payload,canonical='scale'):
        return next(c for c in payload['cards'] if c['canonical']==canonical)

    def test_exact_child_heads_form_additional_group_with_question_threshold(self):
        html,payload=self.report()
        card=self.card(payload)
        team=next(row for row in card['children'] if row['unit']=='Führungsteam')
        self.assertEqual((team['n'],team['mean'],team['top2']),(3,5,100))
        self.assertIsNotNone(team['mean_ci95'])
        self.assertIsNotNone(team['top2_ci95'])
        self.assertFalse(team.get('complete_population',False)) # No inferred invitation count.
        self.assertEqual(card['rows'][-1]['n'],16) # Only the own root head is excluded.
        self.assertEqual(card['rows'][-1]['mean'],(3*5+3*1+9*2+1)/16)
        self.assertNotIn('Führungsteam',[r['unit'] for r in self.card(payload,'other')['children']])
        self.assertIn('<tr><td>Führungsteam</td><td>3</td><td>Leitungsanteil der Grundmenge fehlt</td><td>–</td></tr>',html)
        guide=html.split('<summary>So liest du die Ergebnisse</summary>',1)[1].split('</details>',1)[0]
        self.assertIn('Die Leitungspersonen der direktunterstellten Einheiten',guide)
        self.assertNotIn('berührer',guide)
        hidden_html,hidden=self.report(include_children=0)
        self.assertEqual(self.card(hidden)['children'],[])
        hidden_guide=hidden_html.split('<summary>So liest du die Ergebnisse</summary>',1)[1].split('</details>',1)[0]
        self.assertNotIn('Die Leitungspersonen der direktunterstellten Einheiten',hidden_guide)
        _,small=self.report(min_n=4)
        self.assertNotIn('Führungsteam',[r['unit'] for r in self.card(small)['children']])

    def test_scope_and_wave_do_not_include_other_or_deeper_leaders(self):
        area=next(n for n in self.nodes if n['dimension']=='Bereich' and n['unit']=='A')
        _,payload=self.report(oe=area['id'],min_n=1)
        team=next(r for r in self.card(payload)['children'] if r['unit']=='Führungsteam')
        self.assertEqual((team['n'],team['mean']),(1,1)) # Only A's team head, not A's own head.
        self.assertEqual(self.card(payload)['rows'][-1]['n'],4)
        # Changing the current wave never manufactures historical leadership answers.
        with self.db() as c:
            c.execute("DELETE FROM answers WHERE wave='2026' AND feedback='C-head'")
        _,payload=self.report()
        self.assertNotIn('Führungsteam',[r['unit'] for r in self.card(payload)['children']])
        _,previous=self.report(focus_wave='2025')
        self.assertIn('Führungsteam',[r['unit'] for r in self.card(previous)['children']])

    def test_invited_team_uses_confirmed_leader_counts_and_marks_complete_answers(self):
        with self.db() as c:
            for area,count in [('A',2),('B',1),('C',1)]:
                c.execute("INSERT INTO grounds VALUES(1,'2026','Bereich',?,6)",(area,))
                c.execute("INSERT INTO ground_leaders VALUES(1,'2026','Bereich',?,?)",(area,count))
        html,payload=self.report()
        self.assertIn('<tr><td>Führungsteam</td><td>3</td><td>4</td><td>75.0 %</td></tr>',html)
        team=next(r for r in self.card(payload)['children'] if r['unit']=='Führungsteam')
        self.assertFalse(team['complete_population'])
        self.assertIsNotNone(team['top2_ci95'])
        with self.db() as c:
            c.execute("UPDATE ground_leaders SET total=1 WHERE unit='A'")
        html,payload=self.report(min_n=1)
        self.assertIn('<tr><td>Führungsteam</td><td>3</td><td>3</td><td>100.0 %</td></tr>',html)
        team=next(r for r in self.card(payload)['children'] if r['unit']=='Führungsteam')
        self.assertTrue(team['complete_population'])
        self.assertIsNone(team['mean_ci95'])
        self.assertIsNone(team['top2_ci95'])
        other=next(r for r in self.card(payload,'other')['children'] if r['unit']=='Führungsteam')
        self.assertEqual(other['n'],2)
        self.assertFalse(other['complete_population'])
        self.assertIsNotNone(other['mean_ci95'])

    def test_missing_or_ambiguous_basis_never_uses_partial_sum_or_published_rate(self):
        with self.db() as c:
            for area in ('A','B','C'):
                c.execute("INSERT INTO grounds VALUES(1,'2026','Bereich',?,6)",(area,))
                c.execute("INSERT INTO ground_leaders VALUES(1,'2026','Bereich',?,1)",(area,))
            c.execute("DELETE FROM ground_leaders WHERE unit='C'")
            c.execute("INSERT INTO participation_policies VALUES(1,'2026','Bereich','C','published',100,'Historisch')")
        html,payload=self.report()
        self.assertIn('<tr><td>Führungsteam</td><td>3</td><td>Leitungsanteil der Grundmenge fehlt</td><td>–</td></tr>',html)
        team=next(r for r in self.card(payload)['children'] if r['unit']=='Führungsteam')
        self.assertFalse(team['complete_population'])
        with self.db() as c:
            c.execute("INSERT INTO ground_leaders VALUES(1,'2026','Bereich','C',1)")
            c.execute("INSERT INTO organisation VALUES('other-A',?)",(json.dumps(dict(OE_Kürzel='other-A',Amt='Other',Bereich='A')),))
            c.execute("INSERT INTO answers SELECT project,wave,'foreign',source,answer,date,? FROM answers WHERE feedback='A-head' AND wave='2026'",
                      (json.dumps(dict(Amt='Other',Bereich='A',Kadertyp='100')),))
        root=next(n for n in self.nodes if n['dimension']=='Amt')
        html,payload=self.report(oe=root['id'])
        self.assertIn('<tr><td>Führungsteam</td><td>3</td><td>Leitungsanteil der Grundmenge fehlt</td><td>–</td></tr>',html)

    def test_texts_use_collective_origin_and_require_enough_valid_answers(self):
        html,_=self.report(include_texts=1,profile='oe',download=1)
        self.assertIn('<summary>Führungsteam <span class="answer-count">3 Beiträge</span>',html)
        for area in ('A','B','C'):self.assertIn('Text '+area+'-head',html)
        with self.db() as c:
            c.execute("UPDATE answers SET answer='Keine Antwort' WHERE wave='2026' AND feedback='C-head' AND source='text'")
        html,_=self.report(include_texts=1,profile='oe')
        for area in ('A','B','C'):self.assertNotIn('Text '+area+'-head',html)
        self.assertNotIn('<summary>Führungsteam <span',html)

    def test_reviewed_summaries_use_team_origin_and_cannot_bypass_text_threshold(self):
        path=[('Amt','Amt')]
        people={('2026',area+'-head') for area in ('A','B','C')}
        node=dict(unit='Führungsteam',path=[*path,('__leadership_team__','Führungsteam')])
        records=[dict(wave='2026',feedback=person,raw=dict(Amt='Amt',Bereich=person[0],Kadertyp='100')) for _,person in people]
        mappings=[dict(wave='*',dimension=d,source=d) for d in ('Amt','Bereich')]
        disclosure=TextDisclosure((records,{},mappings,[],[],[]),'2026',3,[node],True,
                                  dict(node=node,people=people,text_questions={'text'}))
        index={person:dict(canonical='text',key=['2026',person,'text'],topic='Thema',text='Gemeinsame Aussage') for _,person in people}
        summary=project_concerns(index,[],{tuple(s['key']) for s in index.values()},{},disclosure)
        entry=summary['text'][0]['statements'][0]
        self.assertEqual(entry['origins'],['Führungsteam'])
        self.assertEqual(entry['count'],3)
        self.assertNotIn('A',entry['origins'])
        disclosure.team_questions=set()
        self.assertEqual(project_concerns(index,[],{tuple(s['key']) for s in index.values()},{},disclosure),{})

    def test_approved_wave_report_reuses_sources_with_safe_leadership_attribution(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            records=[dict(r) for r in c.execute('SELECT * FROM answers')]
            for r in records:r['raw']=json.loads(r['raw'])
            questions={r['source']:dict(r) for r in c.execute('SELECT * FROM questions')}
            mappings=[dict(r) for r in c.execute('SELECT * FROM mappings')]
            sources=ta.collect((records,questions,mappings,[],[],[]),'2026',canonicals=['text'],exclude_leaders=False)
            draft=ta.make_draft(sources)
            selection=dict(wave='2026',canonicals=['text'],exclude_leaders=False)
            result=dict(version=2,auftrag='job',teil='part',frage='question',antworten=[
                dict(id=r['id'],aussagen=[dict(thema='Zusammenarbeit',aussage='Gemeinsame Führungsperspektive')],grund='')
                for r in draft if r['key'][1] in ('A-head','B-head','C-head')])
            # Other records remain explicitly accounted for in the approved result.
            used={a['id'] for a in result['antworten']}
            result['antworten'].extend(dict(id=r['id'],aussagen=[],grund='Ohne inhaltliche Aussage') for r in draft if r['id'] not in used)
            c.execute('INSERT INTO wave_text_jobs(id,project,wave,selection,fingerprint) VALUES(?,1,?,?,?)',
                      ('job','2026',json.dumps(selection),ta.digest(sources)))
            c.execute('''INSERT INTO wave_text_parts(id,job,position,canonical,question_id,wording,label,count,state,records,result)
                         VALUES('part','job',1,'text','question','Frage','text',?,'approved',?,?)''',
                      (len(draft),json.dumps(draft),json.dumps(result)))
        html,_=self.report(include_summaries=1,profile='oe',download=1)
        self.assertIn('Gemeinsame Führungsperspektive',html)
        self.assertIn('Herkunft Führungsteam · 3 Textantworten',html)
        self.assertNotIn('Herkunft A, B, C',html)
        html,_=self.report(include_summaries=1,include_children=0,profile='oe')
        self.assertNotIn('Herkunft Führungsteam',html)
        with self.db() as c:
            c.execute("UPDATE answers SET answer='Keine Antwort' WHERE wave='2026' AND feedback='C-head' AND source='text'")
        html,_=self.report(include_summaries=1,profile='oe')
        self.assertNotIn('Gemeinsame Führungsperspektive',html)
