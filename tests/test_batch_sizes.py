import io
import json
import sqlite3
import unittest
import test_text_analysis as legacy
import wave_analysis as wa


class BatchSizeTests(unittest.TestCase):
    def records(self,count=501,length=10):
        return [dict(id=str(i),canonical='q',export_text='x'*length) for i in range(count)]

    def test_answer_boundaries_and_complete_coverage_for_every_profile(self):
        records=self.records()
        for size,maximum,expected in [('small',50,11),('standard',150,4),('large',250,3)]:
            chunks=wa.batches(records,size)
            self.assertEqual(len(chunks),expected)
            self.assertTrue(all(len(items)<=maximum for _,items in chunks))
            self.assertEqual([r['id'] for _,items in chunks for r in items],[r['id'] for r in records])
            for i,(_,items) in enumerate(chunks):
                data,_=wa.package('j',str(i),'q','Frage',items,size)
                self.assertEqual(len(data['antworten']),len(items))
        for count in (149,150,151):
            self.assertEqual(len(wa.batches(self.records(count),'standard')),1 if count<=150 else 2)

    def test_character_limit_wins_before_answer_limit(self):
        records=self.records(200,5000)
        for size in wa.BATCH_SIZES:
            count_limit,char_limit=wa.batch_limits(size)
            chunks=wa.batches(records,size)
            self.assertGreater(len(chunks),1)
            for i,(_,items) in enumerate(chunks):
                self.assertLess(len(items),count_limit)
                cost=sum(len(json.dumps(dict(id=r['id'],text=r['export_text']),ensure_ascii=False))+2 for r in items)
                self.assertLessEqual(cost,char_limit)
                data,_=wa.package('j',str(i),'q','Frage',items,size)
                self.assertLessEqual(len(json.dumps(data,ensure_ascii=False)),char_limit+4000)
            self.assertEqual(sum(len(items) for _,items in chunks),200)

    def test_question_boundaries_invalid_profile_and_oversized_edits(self):
        records=self.records(2)
        records[1]['canonical']='other'
        self.assertEqual(len(wa.batches(records,'large')),2)
        with self.assertRaises(ValueError):wa.batches(records,'invalid')
        with self.assertRaises(ValueError):wa.package('j','p','q','Frage',self.records(151),'standard')
        with self.assertRaises(ValueError):wa.package('j','p','q','Frage',self.records(1,65000),'standard')
        self.assertEqual(len(wa.package('j','p','q','Frage',self.records(1,65000),'large')[0]['antworten']),1)


class BatchSizeRouteTests(unittest.TestCase):
    setUp=legacy.TextAnalysisTests.setUp
    db=legacy.TextAnalysisTests.db
    post=legacy.TextAnalysisTests.post

    def add_records(self):
        with self.db() as c:
            raw=json.dumps({'Amt':'AFA','Bereich':'A','Question':'Frage'})
            c.executemany('INSERT INTO answers VALUES(1,?,?,?,?,?,?)',[
                ('2026','load-'+str(i),'q','Kurzer Text','2026-10-01',raw) for i in range(300)])

    def latest(self):
        with self.db() as c:
            c.row_factory=sqlite3.Row
            job=dict(c.execute('SELECT * FROM wave_text_jobs ORDER BY rowid DESC LIMIT 1').fetchone())
            parts=[dict(p) for p in c.execute('SELECT * FROM wave_text_parts WHERE job=? ORDER BY position',(job['id'],))]
        return job,parts

    def test_new_default_and_old_jobs_preserve_their_parts(self):
        self.add_records()
        self.assertEqual(self.post('/p/1/wave-texts?focus_wave=2026',question='q',batch_size='small').status_code,302)
        old_job,old_parts=self.latest();self.assertEqual(len(old_parts),7)
        # Omitting the field creates a new Standard job.
        r=self.post('/p/1/wave-texts?focus_wave=2026',question='q')
        self.assertEqual(r.status_code,302)
        new_job,new_parts=self.latest()
        self.assertEqual(new_job['batch_size'],'standard');self.assertEqual(len(new_parts),3)
        self.assertEqual([p['count'] for p in new_parts],[150,150,3])
        with self.db() as c:
            ids=[p[0] for p in c.execute('SELECT id FROM wave_text_parts WHERE job=? ORDER BY position',(old_job['id'],))]
        self.assertEqual(ids,[p['id'] for p in old_parts])
        self.assertIn('Paketgrösse: Standard',self.client.get(r.location).text)
        first=new_parts[0]
        data=dict(action='export',revision='0',privacy_checked='on',wording='Frage')
        for item in json.loads(first['records']):data['text_'+item['id']]='Bereinigter Text'
        part_url=f"/p/1/wave-texts/{new_job['id']}/{first['id']}"
        self.assertEqual(self.post(part_url,**data).status_code,302)
        self.assertEqual(self.client.get(part_url+'/download').status_code,200)
        exported=json.loads(next(p for p in self.latest()[1] if p['id']==first['id'])['exported'])
        result=dict(version=2,auftrag=new_job['id'],teil=first['id'],frage=first['question_id'],antworten=[
            dict(id=a['id'],aussagen=[dict(thema='Thema',aussage='Anliegen')],grund='') for a in exported['antworten']])
        self.assertEqual(self.post(r.location,action='import',revision='0',files=(io.BytesIO(json.dumps(result).encode()),'result.json')).status_code,302)
        imported=next(p for p in self.latest()[1] if p['id']==first['id'])
        self.assertEqual(imported['state'],'imported')
        self.assertEqual(len(json.loads(imported['result'])['antworten']),150)
        self.assertEqual(self.post('/p/1/wave-texts?focus_wave=2026',question='q',batch_size='invalid').status_code,400)
        with self.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM wave_text_jobs').fetchone()[0],2)

    def test_migration_labels_existing_jobs_small_without_touching_ids(self):
        self.post('/p/1/wave-texts?focus_wave=2026',question='q',batch_size='small')
        job,parts=self.latest()
        # Simulate the pre-update table while preserving the existing job and part data.
        with self.db() as c:c.execute('ALTER TABLE wave_text_jobs DROP COLUMN batch_size')
        from app import create_app
        create_app(self.root)
        migrated,after=self.latest()
        self.assertEqual(migrated['batch_size'],'small')
        self.assertEqual(migrated['fingerprint'],job['fingerprint'])
        self.assertEqual([(p['id'],p['records']) for p in parts],[(p['id'],p['records']) for p in after])


if __name__=='__main__':unittest.main()
