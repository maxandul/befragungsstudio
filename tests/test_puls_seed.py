import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app import create_app
from core import aggregate
from seed_puls import run, AWI_EXTRA


class PulsSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.inputs=self.root/'inputs';self.inputs.mkdir()
        self.instance=self.root/'instance'

    def write(self,name,rows):
        fields=['Survey ID','Feedback ID','Question ID','Question title','Question type',
                'Question','Answer','Answer given at','Bereich (subject)']
        with (self.inputs/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

    def row(self,source,feedback,date,survey='2234',title='Frage (PAWI)',typ='scale'):
        return {'Survey ID':survey,'Feedback ID':feedback,'Question ID':source,
                'Question title':title,'Question type':typ,'Question':'Identischer vollständiger Wortlaut.',
                'Answer':'4' if typ=='scale' else 'Text','Answer given at':date,'Bereich (subject)':'AI'}

    def connection(self):
        c=sqlite3.connect(self.instance/'studio.sqlite3');c.row_factory=sqlite3.Row
        return c

    def sample(self):
        self.write('awi.csv',[self.row(s,'extra','2025-01-15') for s in sorted(AWI_EXTRA)]+
                   [self.row('base',p,'2025-01-15') for p in ['extra','regular']]+
                   [self.row('114621','summer','2025-07-03')])
        self.write('gs.csv',[self.row('118022','a','2024-09-20','2272','Feedback an GL (PGS)','text'),
                             self.row('166053','b','2026-08-20','2272','Feedback an GL (PGS)','text')])

    def test_seed_preview_idempotence_and_user_changes(self):
        self.sample()
        text=run(self.inputs,self.instance,True)
        self.assertIn('VORSCHAU',text);self.assertFalse(self.instance.exists())
        run(self.inputs,self.instance)
        with self.connection() as c:
            pid=c.execute("SELECT id FROM projects WHERE name='Puls AWI'").fetchone()[0]
            gs=c.execute("SELECT id FROM projects WHERE name='Puls GS'").fetchone()[0]
            self.assertEqual(c.execute('SELECT COUNT(*) FROM question_exclusions').fetchone()[0],6)
            self.assertEqual(c.execute('SELECT COUNT(DISTINCT canonical) FROM questions WHERE project=?',(gs,)).fetchone()[0],1)
            self.assertEqual(c.execute('SELECT label FROM questions WHERE project=? AND source=?',(pid,'base')).fetchone()[0],'Frage')
            count=c.execute('SELECT COUNT(*) FROM answers').fetchone()[0]
            c.execute("UPDATE questions SET label='Eigener Titel' WHERE project=? AND source='base'",(pid,))
            c.execute("UPDATE answers SET answer='3' WHERE project=? AND source='base'",(pid,))
            c.execute('DELETE FROM question_exclusions WHERE project=?',(pid,))
            c.execute("UPDATE answers SET wave='Januar Spezial' WHERE project=? AND wave='2025-01'",(pid,))
        run(self.inputs,self.instance)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM answers').fetchone()[0],count)
            self.assertEqual(c.execute("SELECT label FROM questions WHERE project=? AND source='base'",(pid,)).fetchone()[0],'Eigener Titel')
            self.assertEqual(c.execute("SELECT answer FROM answers WHERE project=? AND source='base' LIMIT 1",(pid,)).fetchone()[0],'3')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM question_exclusions').fetchone()[0],0)
        self.assertTrue(list((self.instance/'backups').glob('*.sqlite3')))

    def test_exclusion_keeps_participation_and_can_be_restored_in_form(self):
        self.sample();run(self.inputs,self.instance)
        with self.connection() as c:
            pid=c.execute("SELECT id FROM projects WHERE name='Puls AWI'").fetchone()[0]
            records=[dict(r) for r in c.execute('SELECT * FROM answers WHERE project=?',(pid,))]
            for r in records:r['raw']=json.loads(r['raw'])
            questions={r['source']:dict(r) for r in c.execute('SELECT * FROM questions WHERE project=?',(pid,))}
            exclusions={(r['source'],r['wave']) for r in c.execute('SELECT * FROM question_exclusions WHERE project=?',(pid,))}
        rows,people=aggregate(records,questions,exclusions=exclusions)
        self.assertEqual(people['2025-01'],2)
        self.assertEqual({r['canonical'] for r in rows if r['wave']=='2025-01'},{'base'})
        self.assertTrue(any(r['wave']=='2025-06' and r['canonical']=='114621' for r in rows))
        client=create_app(self.instance).test_client()
        page=client.get(f'/p/{pid}/questions')
        self.assertEqual(page.status_code,200)
        self.assertIn('einmalig zusätzlich'.encode(),page.data)
        with client.session_transaction() as session:csrf=session['csrf']
        data=dict(csrf=csrf,action='save',wave_settings_present='yes',group_key=list(questions))
        for i,q in enumerate(questions.values()):
            for key in ['label','type','theme','minimum','maximum','top_from','missing','options']:
                data[f'{key}_{i}']=str(q[key])
            data[f'include_{i}']='on'
        response=client.post(f'/p/{pid}/questions',data=data,headers={'Accept':'application/json'})
        self.assertEqual(response.status_code,200,response.data)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM question_exclusions').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM answers WHERE project=?',(pid,)).fetchone()[0],len(records))

    def test_ambiguous_wave_aborts_without_importing_other_projects(self):
        self.sample();run(self.inputs,self.instance)
        with self.connection() as c:
            c.execute("UPDATE answers SET wave='andere Welle' WHERE feedback='regular'")
            before=c.execute('SELECT COUNT(*) FROM answers').fetchone()[0]
        with self.assertRaisesRegex(ValueError,'mehrere Wellen'):
            run(self.inputs,self.instance)
        with self.connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM answers').fetchone()[0],before)

    def test_link_does_not_merge_simultaneous_answers(self):
        self.write('afa.csv',[self.row('121868','same','2024-11-01','2330','ZHub (PAFA)'),
                              self.row('145757','same','2024-11-01','2330','ZHub (PAFA)')])
        text=run(self.inputs,self.instance)
        self.assertIn('gleichzeitige Antworten',text)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(DISTINCT canonical) FROM questions').fetchone()[0],2)
