import copy
import io
import json
import re
import unittest
import zipfile
import test_text_analysis as legacy
import test_wave_texts as wave
import wave_synthesis as ws
from text_analysis import digest


class SynthesisTests(unittest.TestCase):
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

    def overall(self):
        job,url=self.make_wave()
        results=[self.export_part(p)[1] for p in self.parts()]
        concerns={}
        for result in results:
            for answer in result['antworten']:
                key=result['frage']
                c=concerns.setdefault(key,dict(id='A'+str(len(concerns)),frage=key,thema='Abläufe konkretisieren',
                    aussage='Gemeinsames Anliegen',art='key',prioritaet=10,begruendung='Bündelt inhaltlich gleichgerichtete Hinweise.',quellen=[]))
                c['quellen'].append(dict(teil=result['teil'],antwort=answer['id'],aussage=1))
        value=dict(version=3,auftrag=job['id'],teile=results,anliegen=list(concerns.values()))
        return job,url,value

    def synth(self):
        with self.db() as c:
            c.row_factory=__import__('sqlite3').Row
            row=c.execute('SELECT * FROM wave_syntheses ORDER BY rowid DESC LIMIT 1').fetchone()
            return dict(row) if row else None

    def upload(self,url,value,**kw):
        return self.post(url+'/synthesis',action=kw.pop('action','import'),revision=str(self.synth()['revision'] if self.synth() else 0),
                         file=(io.BytesIO(json.dumps(value).encode()),'gesamt_ergebnis.json'),**kw)

    def approve(self,url):
        html=self.client.get(url+'/synthesis').text
        token=re.search(r'name="review_hash" value="([a-f0-9]+)"',html)[1]
        return self.post(url+'/synthesis',action='approve',revision=str(self.synth()['revision']),review_hash=token,supported='on')

    def test_complete_export_contains_manifest_all_parts_and_no_private_mapping(self):
        job,url=self.make_wave()
        self.export_part(self.parts()[0])
        self.assertEqual(self.client.get(url+'/overall-download').status_code,400)
        for p in self.parts()[1:]:self.export_part(p)
        response=self.client.get(url+'/overall-download');self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertEqual(len(manifest['teile']),len(self.parts()))
            self.assertEqual(sum(p['antworten'] for p in manifest['teile']),6)
            self.assertEqual(z.read('standardprompt.txt').decode(),ws.PROMPT)
            for entry in manifest['teile']:
                data=json.loads(z.read(entry['datei']));self.assertEqual(data['teil'],entry['teil'])
                for private in ('person-a','person-b','leader-a','Kadertyp','Bereich','feedback'):
                    self.assertNotIn(private,json.dumps(data))
            self.assertEqual(json.loads(z.read('gesamt_ergebnis_vorlage.json'))['version'],3)

    def test_single_import_review_approval_and_local_counts(self):
        _,url,value=self.overall()
        self.assertEqual(self.upload(url,value).status_code,302)
        self.assertTrue(all(p['state']=='imported' for p in self.parts()))
        self.assertEqual(self.client.get(url+'/synthesis').status_code,200)
        self.assertIn('3 von 3 Textantwortenden',self.client.get(url+'/synthesis').text)
        report='/p/1/report?'+self.query+'&profile=gl'
        self.assertNotIn('Gemeinsames Anliegen',self.client.get(report).text)
        self.assertEqual(self.approve(url).status_code,302)
        html=self.client.get(report).text
        self.assertIn('Gemeinsames Anliegen',html)
        self.assertIn('1 von 1 Textantwortenden',html)
        self.assertIn('Aussage person-a',html)
        self.assertNotIn('Aussage leader-a',html);self.assertNotIn('Aussage person-b',html)
        overall=self.client.get('/p/1/report?focus_wave=2026&profile=gl&min_n=1').text
        self.assertIn('3 von 3 Textantwortenden',overall)
        before=self.parts()
        self.assertEqual(self.upload(url,value).status_code,302)
        self.assertEqual(before,self.parts());self.assertEqual(self.synth()['state'],'approved')
        csv=self.client.get(url+'/synthesis.csv')
        self.assertEqual(csv.status_code,200)
        self.assertTrue(csv.data.startswith(b'\xef\xbb\xbf'))
        self.assertIn('Textantwortende Anliegen;Textantwortende Frage',csv.data.decode('utf-8-sig'))
        self.assertNotIn('person-a',csv.data.decode('utf-8-sig'))

    def test_validation_is_atomic_for_missing_parts_sources_duplicate_or_foreign(self):
        job,url,value=self.overall();parts=self.parts()
        cases=[]
        bad=copy.deepcopy(value);bad['teile'].pop();cases.append(bad)
        bad=copy.deepcopy(value);bad['teile'][0]['antworten'].pop();cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['quellen']=[];cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['quellen'].append(bad['anliegen'][0]['quellen'][0]);cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['quellen'][0]['antwort']='unknown';cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['quellen'][0]['aussage']=0;cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['quellen'][0]['aussage']=True;cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['frage']=bad['anliegen'][1]['frage'];cases.append(bad)
        bad=copy.deepcopy(value);bad['anliegen'][0]['anzahl']=99;cases.append(bad)
        for bad in cases:
            self.assertEqual(self.upload(url,bad).status_code,400)
            self.assertEqual(self.parts(),parts)
            self.assertIsNone(self.synth())
        self.assertEqual(self.upload(url,value).status_code,302)

    def test_import_accepts_unassigned_statements_without_losing_them(self):
        _,url,value=self.overall()
        value['anliegen'][0]['quellen'].pop()
        self.assertEqual(self.upload(url,value).status_code,302)
        self.assertEqual(self.approve(url).status_code,302)
        html=self.client.get('/p/1/report?focus_wave=2026&profile=oe&min_n=1').text
        self.assertIn('Einzelaussagen',html)

    def test_counts_deduplicate_people_and_include_non_evaluable_denominator(self):
        _,url,value=self.overall()
        first=value['teile'][0];answer=first['antworten'][0]
        answer['aussagen'].append(dict(thema='Abläufe',aussage='Weiterer Aspekt desselben Anliegens'))
        concern=next(a for a in value['anliegen'] if a['frage']==first['frage'])
        concern['quellen'].append(dict(teil=first['teil'],antwort=answer['id'],aussage=2))
        self.assertEqual(self.upload(url,value).status_code,302)
        self.assertIn('3 von 3 Textantwortenden',self.client.get(url+'/synthesis').text)
        # Turn a different source into a justified non-evaluable reply. It remains in the denominator.
        other=first['antworten'][1]
        other['aussagen']=[];other['grund']='Keine inhaltliche Konkretisierung'
        concern['quellen']=[s for s in concern['quellen'] if not (s['teil']==first['teil'] and s['antwort']==other['id'])]
        self.assertEqual(self.upload(url,value,replace_checked='on').status_code,302)
        review=self.client.get(url+'/synthesis').text
        self.assertIn('2 von 3 Textantwortenden',review)
        self.assertIn('1 als nicht auswertbar eingeordnete Antworten',review)
        self.assertIn('Keine inhaltliche Konkretisierung',review)

    def test_replacement_and_review_versions_and_withdrawal(self):
        _,url,value=self.overall();self.upload(url,value)
        html=self.client.get(url+'/synthesis').text
        token=re.search(r'name="review_hash" value="([a-f0-9]+)"',html)[1]
        with self.db() as c:c.execute("UPDATE text_concerns SET body='Redaktionell geändert',revision=revision+1")
        self.assertEqual(self.post(url+'/synthesis',action='approve',revision='0',review_hash=token,supported='on').status_code,400)
        self.assertEqual(self.approve(url).status_code,302)
        altered=copy.deepcopy(value);altered['anliegen'][0]['aussage']='Neuer Vorschlag'
        self.assertEqual(self.upload(url,altered).status_code,400)
        self.assertEqual(self.synth()['state'],'approved')
        self.assertEqual(self.upload(url,altered,replace_checked='on').status_code,302)
        self.assertEqual(self.synth()['state'],'imported')
        self.assertEqual(self.approve(url).status_code,302)
        html=self.client.get(url+'/synthesis').text
        token=re.search(r'name="review_hash" value="([a-f0-9]+)"',html)[1]
        self.assertEqual(self.post(url+'/synthesis',action='reopen',revision=str(self.synth()['revision']),review_hash=token).status_code,302)
        self.assertTrue(all(p['state']=='imported' for p in self.parts()))
        self.assertNotIn('Neuer Vorschlag',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)

    def test_part_reopening_invalidates_the_global_approval(self):
        _,url,value=self.overall();self.upload(url,value);self.approve(url)
        part=self.parts()[0]
        self.assertEqual(self.post(self.part_url(part),action='reopen',revision=str(part['revision'])).status_code,302)
        self.assertEqual(self.synth()['state'],'imported')
        self.assertNotIn('Gemeinsames Anliegen',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)
        self.assertEqual(self.approve(url).status_code,302)
        self.assertIn('Gemeinsames Anliegen',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)

    def test_proposals_editable_before_global_approval_but_part_approval_is_insufficient(self):
        _,url,value=self.overall();self.upload(url,value)
        with self.db() as c:
            c.row_factory=__import__('sqlite3').Row
            concern=dict(c.execute('SELECT * FROM text_concerns LIMIT 1').fetchone())
        edit_url=url+'/concerns?question='+concern['canonical']
        self.assertEqual(self.client.get(edit_url).status_code,200)
        self.assertEqual(self.post(edit_url,action='edit',concern=concern['id'],revision=str(concern['revision']),
            topic='Geprüftes Thema',body='Geprüfter Vorschlag',kind='key',order='1',supported='on').status_code,302)
        for p in self.parts():self.approve_part(p)
        self.assertNotIn('Geprüfter Vorschlag',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)
        self.assertEqual(self.approve(url).status_code,302)
        self.assertIn('Geprüfter Vorschlag',self.client.get('/p/1/report?'+self.query+'&profile=gl').text)


    def test_new_wave_opens_fast_workflow(self):
        response=self.post('/p/1/wave-texts?'+self.query,question=['q','t'],workflow='fast')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.location.endswith('/synthesis'))
        html=self.client.get(response.location).text
        self.assertIn('Gesamtpaket mit Prompt herunterladen',html)
        self.assertIn('Importieren und für alle Berichte verwenden',html)
        self.assertNotIn('müssen alle Exporttexte',html)

    def test_fast_export_import_ready_without_individual_reviews(self):
        job,url=self.make_wave()
        response=self.post(url+'/overall-download')
        self.assertEqual(response.status_code,200)
        self.assertTrue(all(p['state']=='exported' for p in self.parts()))
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            manifest=json.loads(z.read('manifest.json'));results=[];concerns={}
            for item in manifest['teile']:
                data=json.loads(z.read(item['datei']))
                for a in data['antworten']:
                    self.assertNotIn('mail@example.org',a['text'])
                self.assertNotIn('feedback',data)
                result=dict(version=2,auftrag=job['id'],teil=data['teil'],frage=data['frage']['id'],antworten=[])
                c=concerns.setdefault(result['frage'],dict(id='C'+str(len(concerns)),frage=result['frage'],
                    thema='Konkrete Arbeitsabläufe',aussage='Gemeinsames Anliegen',art='key',prioritaet=10,
                    begruendung='Wiederkehrender Inhalt',quellen=[]))
                for a in data['antworten']:
                    result['antworten'].append(dict(id=a['id'],aussagen=[dict(thema=c['thema'],aussage='Gemeinsames Anliegen')],grund=''))
                    c['quellen'].append(dict(teil=result['teil'],antwort=a['id'],aussage=1))
                results.append(result)
        value=dict(version=3,auftrag=job['id'],teile=results,anliegen=list(concerns.values()))
        bad=copy.deepcopy(value);bad['teile'].pop()
        self.assertEqual(self.upload(url,bad,action='import_use').status_code,400)
        self.assertIsNone(self.synth())
        self.assertEqual(self.upload(url,value,action='import_use').status_code,302)
        self.assertEqual(self.synth()['state'],'approved')
        self.assertTrue(all(p['state']=='approved' for p in self.parts()))
        html=self.client.get(url+'/synthesis').text
        self.assertIn('Bereit für Berichte',html)
        self.assertIn('/p/1/results?focus_wave=2026',html)
        report=self.client.get('/p/1/report?focus_wave=2026&profile=gl&min_n=1').text
        self.assertIn('Gemeinsames Anliegen',report)
        before=self.parts();self.post(url+'/overall-download')
        self.assertEqual(before,self.parts())

    def test_fast_export_preserves_edited_text_and_is_atomic_on_package_error(self):
        _,url=self.make_wave()
        first=self.parts()[0];items=json.loads(first['records'])
        self.export_part(first)
        response=self.post(url+'/overall-download')
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            data=json.loads(z.read('Teil_001/daten.json'))
            self.assertEqual(data['antworten'][0]['text'],'Bereinigter Text')
        with self.db() as c:c.execute("UPDATE wave_text_parts SET state='draft',exported=NULL")
        parts=self.parts();last=parts[-1];items=json.loads(last['records'])
        items[0]['export_text']='x'*400000
        with self.db() as c:c.execute('UPDATE wave_text_parts SET records=? WHERE id=?',(json.dumps(items),last['id']))
        before=self.parts()
        self.assertEqual(self.post(url+'/overall-download').status_code,400)
        self.assertEqual(before,self.parts())

    def test_same_result_can_be_activated_without_overwriting_editorial_changes(self):
        _,url,value=self.overall();self.upload(url,value)
        with self.db() as c:c.execute("UPDATE text_concerns SET body='Redaktionelle Formulierung'")
        self.assertEqual(self.upload(url,value,action='import_use').status_code,302)
        self.assertEqual(self.synth()['state'],'approved')
        html=self.client.get('/p/1/report?focus_wave=2026&profile=gl&min_n=1').text
        self.assertIn('Redaktionelle Formulierung',html)


class SynthesisScaleTests(unittest.TestCase):
    def test_ten_thousand_answers_cross_batch_concerns_and_single_person_counting(self):
        parts=[];results=[];sources=[]
        for partno in range(100):
            records=[];answers=[];input_rows=[]
            for i in range(partno*100,(partno+1)*100):
                records.append(dict(id=str(i),key=['2026',str(i),'q'],text='Original'))
                input_rows.append(dict(id=str(i),text='Bereinigt'))
                answers.append(dict(id=str(i),aussagen=[dict(thema='Abläufe',aussage='Anliegen')],grund=''))
                sources.append(dict(teil=str(partno),antwort=str(i),aussage=1))
            exported=dict(version=2,auftrag='j',teil=str(partno),frage=dict(id='q',text='Frage'),antworten=input_rows)
            parts.append(dict(id=str(partno),canonical='q',question_id='q',label='Frage',records=json.dumps(records),exported=json.dumps(exported)))
            results.append(dict(version=2,auftrag='j',teil=str(partno),frage='q',antworten=answers))
        value=dict(version=3,auftrag='j',teile=results,anliegen=[dict(id='A',frage='q',thema='Abläufe',aussage='Anliegen',art='key',prioritaet=1,begruendung='Wiederkehrendes Anliegen',quellen=sources)])
        validated,concerns,index=ws.validate(value,'j',parts)
        self.assertEqual(len(validated),100);self.assertEqual(len(index),10000)
        self.assertEqual(len(json.loads(concerns[0]['sources'])),10000)
        from report_editorial import project_concerns
        eligible={('2026',str(i),'q') for i in range(80)}
        grouped=project_concerns(index,concerns,eligible,{})
        self.assertEqual(grouped['q'][0]['statements'][0]['count'],80)





if __name__=='__main__':unittest.main()
