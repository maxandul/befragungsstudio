import copy
import io
import json
import sqlite3
import unittest
import zipfile
from unittest.mock import patch
import test_text_analysis as legacy
import text_analysis as ta
import wave_analysis as wa


class WaveTextTests(legacy.TextAnalysisTests):
    # Reuse the established synthetic fixture, not the legacy workflow tests.
    test_roundtrip_report_optin_scope_escaping_and_staleness=None
    test_import_rejects_foreign_missing_duplicate_cross_question_and_malformed=None
    test_consent_csrf_and_revision=None
    test_approval_can_be_withdrawn_and_retained=None
    test_non_evaluable_answers_and_json_integrity=None
    test_index_and_raw_text_optin_still_work=None

    def wave_job(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            return dict(c.execute('SELECT * FROM wave_text_jobs ORDER BY rowid DESC LIMIT 1').fetchone())

    def parts(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            return [dict(p) for p in c.execute('SELECT * FROM wave_text_parts ORDER BY position')]

    def make_wave(self):
        with patch.object(wa,'MAX_ANSWERS',2):
            # The OE in the query must not limit a wave job.
            r=self.post('/p/1/wave-texts?'+self.query,question=['q','t'],batch_size='small')
        self.assertEqual(r.status_code,302)
        job=self.wave_job();self.assertEqual(job['wave'],'2026')
        parts=self.parts();self.assertEqual(len(parts),4)
        self.assertEqual(sum(p['count'] for p in parts),6)
        self.assertEqual(self.client.get(r.location).status_code,200)
        return job,r.location

    def part_url(self,p):
        return '/p/1/wave-texts/'+p['job']+'/'+p['id']

    def export_part(self,p):
        items=json.loads(p['records'])
        data=dict(action='export',revision=str(p['revision']),privacy_checked='on',wording='Bereinigte Frage')
        for r in items:data['text_'+r['id']]='Bereinigter Text'
        response=self.post(self.part_url(p),**data);self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get(response.location).status_code,200)
        response=self.client.get(self.part_url(p)+'/download');self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            raw=z.read('daten.json');data=json.loads(raw)
            for private in ('person-a','person-b','leader-a','mail@example.org','AFA','canonical','feedback'):
                self.assertNotIn(private,raw.decode())
        result=dict(version=2,auftrag=p['job'],teil=p['id'],frage=p['question_id'],antworten=[])
        for r in items:
            name=r['key'][1]
            result['antworten'].append(dict(id=r['id'],aussagen=[dict(thema='Arbeitsabläufe',aussage='Aussage '+name)],grund=''))
        return data,result

    def import_files(self,url,results):
        return self.post(url,action='import',revision=str(self.wave_job()['revision']),
                         files=[(io.BytesIO(json.dumps(r).encode()),f'{i}.json') for i,r in enumerate(results)])

    def approve_part(self,p):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            p=dict(c.execute('SELECT * FROM wave_text_parts WHERE id=?',(p['id'],)).fetchone())
        result=json.loads(p['result'])
        data=dict(action='approve',revision=str(p['revision']),content_checked='on')
        for ai,a in enumerate(result['antworten']):
            for si,s in enumerate(a['aussagen']):
                data[f'topic_{ai}_{si}']=s['thema'];data[f'body_{ai}_{si}']=s['aussage']
            if not a['aussagen']:data[f'reason_{ai}']=a['grund']
        response=self.post(self.part_url(p),**data);self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get(response.location).status_code,200)

    def test_wave_reuse_filters_sources_and_waits_for_complete_review(self):
        job,url=self.make_wave();results=[]
        for part in self.parts():results.append(self.export_part(part)[1])
        # Exporting a part does not change its IDs on repeated download.
        first=self.parts()[0]
        self.assertEqual(self.client.get(self.part_url(first)+'/download').data,
                         self.client.get(self.part_url(first)+'/download').data)
        self.assertEqual(self.import_files(url,results[:1]).status_code,302)
        self.approve_part(self.parts()[0])
        report='/p/1/report?'+self.query+'&include_summaries=1'
        self.assertNotIn('Aussage person-a',self.client.get(report).text)
        self.assertEqual(self.import_files(url,results[1:]).status_code,302)
        for p in self.parts()[1:]:self.approve_part(p)
        html=self.client.get(report).text
        self.assertIn('Aussage person-a',html)
        self.assertNotIn('Aussage leader-a',html)
        self.assertNotIn('Aussage person-b',html)
        overall=self.client.get('/p/1/report?focus_wave=2026&include_summaries=1&min_n=1').text
        for name in ('person-a','leader-a','person-b'):self.assertIn('Aussage '+name,overall)
        self.assertNotIn('Aussage person-a',self.client.get(report.replace('min_n=1','min_n=2')).text)
        # Safe retry preserves approvals and edited state.
        revisions=[p['revision'] for p in self.parts()]
        self.assertEqual(self.import_files(url,results).status_code,302)
        self.assertEqual(revisions,[p['revision'] for p in self.parts()])
        # Changing organisational membership needs no repeated KI processing.
        with self.db() as c:
            for source in ('q','t'):
                raw=json.loads(c.execute("SELECT raw FROM answers WHERE wave='2026' AND feedback='person-b' AND source=?",(source,)).fetchone()[0]);raw['Bereich']='A'
                c.execute("UPDATE answers SET raw=? WHERE wave='2026' AND feedback='person-b' AND source=?",(json.dumps(raw),source))
        html=self.client.get(report).text
        self.assertIn('Aussage person-b',html)
        self.assertNotIn('Aussage leader-a',html)
        # Changed source text invalidates the wave for every OE.
        with self.db() as c:c.execute("UPDATE answers SET answer='Geändert' WHERE wave='2026' AND feedback='person-b' AND source='q'")
        self.assertNotIn('Aussage person-a',self.client.get(report).text)
        self.assertIn('veraltet',self.client.get(url).text)

    def test_batch_import_is_atomic_and_rejects_cross_part_or_missing_sources(self):
        _,url=self.make_wave();results=[self.export_part(p)[1] for p in self.parts()]
        bad=copy.deepcopy(results[1]);bad['antworten'][0]['id']=results[0]['antworten'][0]['id']
        self.assertEqual(self.import_files(url,[results[0],bad]).status_code,400)
        self.assertTrue(all(p['state']=='exported' for p in self.parts()))
        for change in ('missing','duplicate','foreign','shape'):
            bad=copy.deepcopy(results[0])
            if change=='missing':bad['antworten'].pop()
            if change=='duplicate':bad['antworten'].append(bad['antworten'][0])
            if change=='foreign':bad['auftrag']='other'
            if change=='shape':bad['antworten'][0]['aussagen']=[dict(thema='Thema',aussage={})]
            self.assertEqual(self.import_files(url,[bad]).status_code,400)
        self.assertEqual(self.import_files(url,results).status_code,302)
        changed=copy.deepcopy(results[0]);changed['antworten'][0]['aussagen'][0]['aussage']='Andere Rückgabe'
        self.assertEqual(self.import_files(url,[changed]).status_code,400)
        self.assertNotIn('Andere Rückgabe',self.parts()[0]['result'])

    def test_draft_resume_consent_and_explicit_replacement(self):
        _,url=self.make_wave();p=self.parts()[0];part_url=self.part_url(p)
        data=dict(action='draft',revision=str(p['revision']),wording='Anonyme Frage')
        for r in json.loads(p['records']):data['text_'+r['id']]='Manuell bereinigt'
        self.assertEqual(self.post(part_url,**data).status_code,302)
        self.assertIn('Manuell bereinigt',self.client.get(part_url).text)
        data.update(action='export',revision=str(self.parts()[0]['revision']))
        self.assertEqual(self.post(part_url,**data).status_code,400)
        self.assertEqual(self.client.get(part_url+'/download').status_code,400)
        _,result=self.export_part(self.parts()[0]);self.import_files(url,[result])
        result['antworten'][0]['aussagen'][0]['aussage']='Korrigierter Inhalt'
        p=self.parts()[0]
        replace=dict(action='replace',revision=str(p['revision']),replace_checked='on',file=(io.BytesIO(json.dumps(result).encode()),'r.json'))
        self.assertEqual(self.post(part_url,**replace).status_code,302)
        self.assertIn('Korrigierter Inhalt',self.client.get(part_url).text)
        self.assertEqual(self.post(part_url,action='reopen',revision='0').status_code,400)

    def test_linked_scale_question_is_reviewable_exported_and_versioned(self):
        with self.db() as c:
            c.execute("INSERT INTO questions(project,source,canonical,label,type,missing) VALUES(1,'scale','scale','Abläufe','scale','')")
            c.execute("UPDATE questions SET text_parent='scale' WHERE source='q'")
            raw=json.dumps({'Amt':'AFA','Bereich':'A','Question':'Unsere Abläufe sind gut abgestimmt.'})
            c.execute("INSERT INTO answers VALUES(1,'2026','person-a','scale','2','2026-10-01',?)",(raw,))
        _,url=self.make_wave()
        part=next(p for p in self.parts() if p['canonical']=='q')
        self.assertIn('Unsere Abläufe sind gut abgestimmt.',part['wording'])
        self.assertIn('Freitextfrage:',part['wording'])
        self.assertIn('Unsere Abläufe sind gut abgestimmt.',self.client.get(self.part_url(part)).text)
        items=json.loads(part['records'])
        data=dict(action='export',revision=str(part['revision']),privacy_checked='on',wording=part['wording'])
        for r in items:data['text_'+r['id']]='Kurze Antwort'
        self.assertEqual(self.post(self.part_url(part),**data).status_code,302)
        exported=json.loads(next(p for p in self.parts() if p['id']==part['id'])['exported'])
        self.assertIn('Unsere Abläufe sind gut abgestimmt.',exported['frage']['text'])
        self.assertNotIn('scale',json.dumps(exported))
        with self.db() as c:
            raw=json.dumps({'Amt':'AFA','Bereich':'A','Question':'Geänderter übergeordneter Wortlaut'})
            c.execute("UPDATE answers SET raw=? WHERE source='scale'",(raw,))
        self.assertIn('veraltet',self.client.get(url).text)

    def test_bulk_download_only_contains_privacy_checked_parts(self):
        _,url=self.make_wave()
        self.assertEqual(self.client.get(url+'/download').status_code,400)
        self.export_part(self.parts()[0])
        r=self.client.get(url+'/download');self.assertEqual(r.status_code,200)
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('daten.json')]),1)
            combined=b''.join(z.read(n) for n in z.namelist()).decode()
            self.assertNotIn('person-a',combined)
            self.assertIn('standardprompt.txt',z.namelist())

    def test_large_database_uses_bounded_review_pages(self):
        with self.db() as c:
            raw=json.dumps({'Amt':'AFA','Bereich':'A','Question':'Frage'})
            c.executemany('INSERT INTO answers VALUES(1,?,?,?,?,?,?)',[
                ('2026','load-'+str(i),'q','Inhalt '+('Text '*100),'2026-10-01',raw) for i in range(4000)])
        r=self.post('/p/1/wave-texts?focus_wave=2026',question='q',batch_size='small')
        self.assertEqual(r.status_code,302)
        parts=self.parts()
        self.assertEqual(sum(p['count'] for p in parts),4003)
        self.assertGreaterEqual(len(parts),81)
        html=self.client.get(self.part_url(parts[0])).text
        self.assertLessEqual(html.count('<textarea'),51)
        self.assertLess(len(html),120000)
        self.assertEqual(self.client.get(r.location).status_code,200)
        self.assertEqual(self.client.get('/p/1/texts?focus_wave=2026').status_code,200)

    def test_topics_can_be_unified_without_mixing_sources(self):
        _,url=self.make_wave();results=[self.export_part(p)[1] for p in self.parts()]
        results[0]['antworten'][0]['aussagen'][0]['thema']='Prozesse'
        self.import_files(url,results)
        for p in self.parts():self.approve_part(p)
        topics=['Arbeitsabläufe','Prozesse']
        job=self.wave_job()
        data=dict(action='aliases',revision=str(job['revision']),topics_hash=ta.digest(topics),topic_0='Abläufe',topic_1='Abläufe')
        self.assertEqual(self.post(url,**data).status_code,302)
        html=self.client.get('/p/1/report?'+self.query+'&include_summaries=1').text
        self.assertIn('<h4>Abläufe</h4>',html)
        self.assertNotIn('Aussage person-b',html)
        data.update(revision=str(self.wave_job()['revision']),topics_hash='old')
        self.assertEqual(self.post(url,**data).status_code,400)


class WaveScaleTests(unittest.TestCase):
    def test_ten_thousand_answers_partitioned_without_loss_and_bounded_groups(self):
        records=[dict(id=f'r{i}',canonical='q'+str(i%5),export_text='Hinweis '+('Text '*180),
                      key=['2026',str(i),'source'],text='Original',label='Frage',wording='Frage') for i in range(10000)]
        chunks=wa.batches(records)
        self.assertGreater(len(chunks),200)
        self.assertEqual(sum(len(items) for _,items in chunks),10000)
        exported_ids=[];parts=[]
        for i,(q,items) in enumerate(chunks):
            self.assertLessEqual(len(items),50)
            data,_=wa.package('job',str(i),q,'Frage',items)
            self.assertLessEqual(len(json.dumps(data,ensure_ascii=False)),wa.MAX_CHARS+4000)
            result=dict(version=2,auftrag='job',teil=str(i),frage=q,antworten=[
                dict(id=r['id'],aussagen=[dict(thema='Thema',aussage='Identisches Anliegen')],grund='') for r in items])
            wa.validate(result,data);exported_ids.extend(a['id'] for a in data['antworten'])
            parts.append((items,result,q))
        self.assertEqual(len(set(exported_ids)),10000)
        eligible={tuple(r['key']) for r in records[:100]}
        grouped=wa.group_statements(parts,eligible,{})
        self.assertEqual(sum(t['statements'][0]['count'] for topics in grouped.values() for t in topics),100)
        self.assertEqual(sum(len(t['statements']) for topics in grouped.values() for t in topics),5)

    def test_single_oversized_answer_not_silently_truncated(self):
        items=[dict(id='a',canonical='q',export_text='x'*40000)]
        with self.assertRaises(ValueError):wa.package('j','p','q','Frage',items)
        self.assertEqual(len(items[0]['export_text']),40000)
