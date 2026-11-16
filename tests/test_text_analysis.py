import copy
import io
import json
import re
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from app import create_app, DEFAULT_MISSING
from organisation import tree
import text_analysis as ta


class TextAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.app=create_app(self.root);self.app.testing=True
        self.client=self.app.test_client()
        with self.db() as c:
            c.execute("INSERT INTO projects(id,name,kind,min_n) VALUES(1,'Puls','other',1)")
            for dimension in ('Amt','Bereich'):
                c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES(1,'*',?,?)",(dimension,dimension))
            for source in ('q','t'):
                c.execute('INSERT INTO questions(project,source,canonical,label,type,theme,missing) VALUES(1,?,?,?,?,?,?)',(source,source,source,'text','Thema',DEFAULT_MISSING))
            for wave in ('2025','2026'):
                for feedback,area,role in [('person-a','A',''),('leader-a','A','100'),('person-b','B','')]:
                    for source in ('q','t'):
                        raw={'Amt':'AFA','Bereich':area,'Kadertyp':role,'Question':'Ihre Anmerkungen?'}
                        c.execute('INSERT INTO answers VALUES(1,?,?,?,?,?,?)',(wave,feedback,source,'Text '+feedback+' mail@example.org',wave+'-10-01',json.dumps(raw)))
        self.csrf=self.client.get('/session/csrf').json['csrf']
        nodes=tree([], [dict(Amt='AFA',Bereich='A'),dict(Amt='AFA',Bereich='B')])
        self.oe=next(n['id'] for n in nodes if n['dimension']=='Bereich' and n['unit']=='A')
        self.query=urlencode(dict(focus_wave='2026',oe=self.oe,min_n=1))

    def db(self):
        return sqlite3.connect(self.root/'studio.sqlite3')

    def job(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            return dict(c.execute('SELECT * FROM text_jobs ORDER BY rowid DESC LIMIT 1').fetchone())

    def post(self,url,**data):
        return self.client.post(url,data=dict(csrf=self.csrf,**data))

    def export(self):
        response=self.post('/p/1/texts?'+self.query,question=['q','t'])
        self.assertEqual(response.status_code,302)
        url=response.location
        self.assertEqual(self.client.get(url).status_code,200)
        job=self.job();records=json.loads(job['records'])
        self.assertEqual(len(records),2)  # Own OE leader excluded, other area and wave excluded.
        data=dict(action='export',revision='0',privacy_checked='on')
        for r in records:
            data['text_'+r['id']]=r['export_text'].replace('person-a','[Name entfernt]')
            data['wording_'+r['canonical']]='Bereinigte Frage'
        self.assertEqual(self.post(url,**data).status_code,302)
        archive=self.client.get(url+'/download')
        self.assertEqual(archive.status_code,200)
        with zipfile.ZipFile(io.BytesIO(archive.data)) as z:
            self.assertEqual(set(z.namelist()),{'daten.json','standardprompt.txt','rueckgabe_vorlage.json'})
            combined=b''.join(z.read(n) for n in z.namelist()).decode()
            for private in ('person-a','person-b','leader-a','mail@example.org','feedback','Kadertyp','AFA'):
                self.assertNotIn(private,combined)
            exported=json.loads(z.read('daten.json'))
        result=dict(version=1,auftrag=job['id'],fragen=[dict(id=q['id'],themen=[dict(titel='Thema',aussage='Zusammenfassung <script>fremd</script>',quellen=[a['id'] for a in q['antworten']])],nicht_auswertbar=[]) for q in exported['fragen']])
        return url,exported,result

    def upload(self,url,result):
        return self.post(url,action='import',revision=str(self.job()['revision']),file=(io.BytesIO(json.dumps(result).encode()),'ergebnis.json'))

    def approve(self,url):
        job=self.job();result=json.loads(job['result'])
        data=dict(action='approve',revision=str(job['revision']),content_checked='on')
        for qi,q in enumerate(result['fragen']):
            for ti,t in enumerate(q['themen']):
                data[f'title_{qi}_{ti}']=t['titel'];data[f'body_{qi}_{ti}']=t['aussage']
        self.assertEqual(self.post(url,**data).status_code,302)

    def test_roundtrip_report_optin_scope_escaping_and_staleness(self):
        url,exported,result=self.export()
        report='/p/1/report?'+self.query
        self.assertEqual(self.upload(url,result).status_code,302)
        self.assertNotIn('Zusammenfassung',self.client.get(report+'&include_summaries=1').text)
        self.assertEqual(self.client.get(url).status_code,200)
        self.approve(url)
        self.assertNotIn('Zusammenfassung',self.client.get(report).text)
        html=self.client.get(report+'&include_summaries=1&download=1').text
        self.assertIn('Zusammenfassung &lt;script&gt;',html)
        self.assertNotIn('mail@example.org',html)
        self.assertNotIn('<script>fremd</script>',html)
        self.assertNotIn('Zusammenfassung',self.client.get('/p/1/report?focus_wave=2026&include_summaries=1&min_n=1').text)
        self.assertNotIn('Zusammenfassung',self.client.get(report.replace('min_n=1','min_n=2')+'&include_summaries=1').text)
        with self.db() as c:
            c.execute("UPDATE answers SET answer='Neue Antwort' WHERE feedback='person-a' AND wave='2026' AND source='q'")
        self.assertNotIn('Zusammenfassung',self.client.get(report+'&include_summaries=1').text)
        self.assertIn('veraltet',self.client.get(url).text)
        self.assertEqual(self.client.get(url+'/download').status_code,400)

    def test_import_rejects_foreign_missing_duplicate_cross_question_and_malformed(self):
        url,exported,result=self.export()
        cases=[]
        bad=copy.deepcopy(result);bad['auftrag']='foreign';cases.append(bad)
        bad=copy.deepcopy(result);bad['fragen'][0]['themen']=[];cases.append(bad)
        bad=copy.deepcopy(result);bad['fragen'][0]['themen'][0]['quellen']=['unknown'];cases.append(bad)
        bad=copy.deepcopy(result);bad['fragen'][0]['themen'][0]['quellen']=[exported['fragen'][1]['antworten'][0]['id']];cases.append(bad)
        bad=copy.deepcopy(result);bad['fragen'].append(bad['fragen'][0]);cases.append(bad)
        bad=copy.deepcopy(result);bad['fragen'][0]['themen'][0]['quellen']=[{}];cases.append(bad)
        for bad in cases:
            self.assertEqual(self.upload(url,bad).status_code,400)
            self.assertEqual(self.job()['state'],'exported')
        self.assertEqual(self.upload(url,result).status_code,302)
        # Re-import cannot silently replace the pending or approved review.
        self.assertEqual(self.upload(url,result).status_code,400)

    def test_consent_csrf_and_revision(self):
        self.assertEqual(self.client.post('/p/1/texts?'+self.query,data=dict(question='q')).status_code,400)
        r=self.post('/p/1/texts?'+self.query,question='q');url=r.location
        self.assertEqual(self.post(url,action='export',revision='0').status_code,400)
        self.assertEqual(self.post(url,action='export',revision='99',privacy_checked='on').status_code,400)
        self.assertEqual(self.job()['state'],'draft')

    def test_approval_can_be_withdrawn_and_retained(self):
        url,_,result=self.export();self.upload(url,result);self.approve(url)
        self.assertEqual(self.post(url,action='reopen',revision=str(self.job()['revision'])).status_code,302)
        self.assertEqual(self.job()['state'],'imported')
        self.assertNotIn('Zusammenfassung',self.client.get('/p/1/report?'+self.query+'&include_summaries=1').text)
        self.assertIsNotNone(self.job()['result'])

    def test_non_evaluable_answers_and_json_integrity(self):
        _,exported,result=self.export()
        q=result['fragen'][0];rid=q['themen'][0]['quellen'][0]
        q['nicht_auswertbar']=[dict(id=rid,grund='Kein verständlicher Inhalt')]
        with self.assertRaises(ValueError):ta.validate_result(result,exported)
        q['themen']=[]
        self.assertEqual(ta.validate_result(result,exported),result)
        for raw in [b'{"version":1,"version":2}',b'```json\n{}\n```',b'\xff']:
            with self.assertRaises(ValueError):ta.load_json(raw)

    def test_index_and_raw_text_optin_still_work(self):
        self.assertEqual(self.client.get('/p/1/texts?'+self.query).status_code,200)
        self.assertIn('person-a',self.client.get('/p/1/report?'+self.query+'&include_texts=1').text)
        self.assertNotIn('leader-a',self.client.get('/p/1/report?'+self.query+'&include_texts=1').text)


if __name__=='__main__':unittest.main()
