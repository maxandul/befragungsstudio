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

    def test_afa_bgm_catalog_and_text_links_work_without_reimport(self):
        from report_themes import AFA_BGM_OPTIONS
        from core import aggregate
        rows=[self.row('121873','p','2026-10-10','2330','Entwicklungsmöglichkeiten (PAFA)'),
              self.row('144795','p','2026-10-10','2330','Detail Entwicklungsmöglichkeiten (PAFA)','text'),
              self.row('145767','p','2026-10-10','2330','BGM2 (PAFA)','choice_multiple')]
        rows[-1]['Answer']='Physische Arbeitsbedingungen (z. B. Raumklima, Luft, Lärm, Licht, Möbel), Hohe Arbeitsmenge oder Zeitdruck'
        rows.append({**rows[-1],'Feedback ID':'p2','Answer':'Nein, aktuell wirkt sich kein Aspekt negativ auf meine Gesundheit aus'})
        self.write('afa.csv',rows);run(self.inputs,self.instance)
        with self.connection() as c:
            qs={r['source']:dict(r) for r in c.execute('SELECT * FROM questions')}
            self.assertEqual(qs['144795']['text_parent'],'121873')
            self.assertEqual(qs['121873']['theme'],'Arbeitsbedingungen und Gesundheit')
            self.assertEqual(qs['145767']['options'].splitlines(),AFA_BGM_OPTIONS)
            records=[dict(r) for r in c.execute('SELECT * FROM answers')]
            for r in records:r['raw']=json.loads(r['raw'])
            result,_=aggregate(records,qs)
            bgm=next(r for r in result if r['canonical']=='145767')
            self.assertEqual((bgm['n'],bgm['invalid'],len(bgm['counts'])),(2,0,3))
            self.assertNotIn('Nein',bgm['counts'])
            self.assertEqual(bgm['counts']['Nein, aktuell wirkt sich kein Aspekt negativ auf meine Gesundheit aus'],1)
            c.execute("UPDATE questions SET theme='Eigener Abschnitt',sort_order=77 WHERE source='121873'")
        create_app(self.instance)
        with self.connection() as c:
            self.assertEqual(tuple(c.execute("SELECT theme,sort_order FROM questions WHERE source='121873'").fetchone()),('Eigener Abschnitt',77))
        # Simuliert die bisherige Einrichtung: Optionen fehlen und Entwicklung liegt im alten Abschnitt.
        with self.connection() as c:
            c.execute('DELETE FROM report_migrations')
            c.execute("UPDATE questions SET options='' WHERE source='145767'")
            c.execute("UPDATE questions SET theme='Engagement und Entwicklung' WHERE source='121873'")
        create_app(self.instance)
        with self.connection() as c:
            self.assertTrue(c.execute("SELECT options FROM questions WHERE source='145767'").fetchone()[0])
            self.assertEqual(c.execute("SELECT theme FROM questions WHERE source='121873'").fetchone()[0],'Arbeitsbedingungen und Gesundheit')

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
        self.assertTrue(any(r['wave']=='2025-07' and r['canonical']=='114621' for r in rows))
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

    def test_reset_rebuilds_only_supplied_pulses_and_backs_up(self):
        self.sample();run(self.inputs,self.instance)
        with self.connection() as c:
            awi=c.execute("SELECT id FROM projects WHERE name='Puls AWI'").fetchone()[0]
            gs=c.execute("SELECT id FROM projects WHERE name='Puls GS'").fetchone()[0]
            c.execute("UPDATE projects SET name='Meine alte AWI-Einrichtung' WHERE id=?",(awi,))
            c.execute("UPDATE questions SET label='Angefangen' WHERE project=?",(awi,))
            c.execute("UPDATE answers SET wave='Falsch aufgeteilt' WHERE project=? AND feedback='regular'",(awi,))
            c.execute("INSERT INTO projects(name,kind) VALUES('Kundenbefragung','other')")
            other=c.execute("SELECT id FROM projects WHERE name='Kundenbefragung'").fetchone()[0]
            c.execute("INSERT INTO questions(project,source,canonical,label,type) VALUES(?,'other','other','Erhalten','text')",(other,))
            c.execute("INSERT INTO grounds VALUES(?,'Alt','','',100)",(awi,))
            c.execute("INSERT INTO organisation VALUES('TEST','{}')")
            for pid in [awi,other]:
                c.execute("INSERT INTO report_notes VALUES(?,'','2026','Thema','Berichtstext')",(pid,))
                c.execute("INSERT INTO report_evidence VALUES(?,'','2026','Thema','Referenz')",(pid,))
        # Nur AWI mitliefern: GS und andere Projekte bleiben unangetastet.
        (self.inputs/'gs.csv').unlink()
        before=(self.instance/'studio.sqlite3').read_bytes()
        preview=run(self.inputs,self.instance,True,True)
        self.assertIn('Zurückgesetzt: Meine alte AWI-Einrichtung',preview)
        self.assertEqual(before,(self.instance/'studio.sqlite3').read_bytes())
        text=run(self.inputs,self.instance,reset_puls=True)
        self.assertIn('Neustart:',text)
        with self.connection() as c:
            names={r[0] for r in c.execute('SELECT name FROM projects')}
            self.assertEqual(names,{'Puls AWI','Puls GS','Kundenbefragung'})
            self.assertEqual(c.execute('SELECT label FROM questions WHERE project=?',(other,)).fetchone()[0],'Erhalten')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM answers WHERE project=?',(gs,)).fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM grounds').fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM organisation WHERE code='TEST'").fetchone()[0],1)
            for table in ['report_notes','report_evidence']:
                self.assertEqual([r[0] for r in c.execute(f'SELECT project FROM {table}')],[other])
            new_awi=c.execute("SELECT id FROM projects WHERE name='Puls AWI'").fetchone()[0]
            waves={r[0] for r in c.execute('SELECT DISTINCT wave FROM answers WHERE project=?',(new_awi,))}
            self.assertEqual(waves,{'2025-01','2025-07'})
            self.assertEqual(c.execute('SELECT COUNT(*) FROM question_exclusions WHERE project=?',(new_awi,)).fetchone()[0],6)
        backups=list((self.instance/'backups').glob('*.sqlite3'))
        self.assertTrue(backups)
        with sqlite3.connect(backups[-1]) as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM projects WHERE name='Meine alte AWI-Einrichtung'").fetchone())

    def test_reset_rolls_back_if_new_setup_fails(self):
        from unittest.mock import patch
        self.sample();run(self.inputs,self.instance)
        before=(self.instance/'studio.sqlite3').read_bytes()
        with patch('seed_puls.seed_file',side_effect=ValueError('Einrichtung fehlgeschlagen')):
            with self.assertRaisesRegex(ValueError,'fehlgeschlagen'):
                run(self.inputs,self.instance,reset_puls=True)
        self.assertEqual(before,(self.instance/'studio.sqlite3').read_bytes())

    def test_requested_report_exclusions_keep_raw_data_and_user_reenable(self):
        from seed_puls import REPORT_EXCLUSIONS
        awi_sources={s for sources in REPORT_EXCLUSIONS['AWI'].values() for s in sources}
        afa_sources={s for sources in REPORT_EXCLUSIONS['AFA'].values() for s in sources}
        self.assertEqual(len(awi_sources),29);self.assertEqual(len(afa_sources),8)
        source=next(iter(awi_sources))
        self.write('awi.csv',[self.row(source,'a','2025-01-15'),self.row('keep','a','2025-01-15')])
        run(self.inputs,self.instance)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT include FROM questions WHERE source=?',(source,)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT include FROM questions WHERE source='keep'").fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM answers').fetchone()[0],2)
            c.execute('UPDATE questions SET include=1 WHERE source=?',(source,))
        run(self.inputs,self.instance)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT include FROM questions WHERE source=?',(source,)).fetchone()[0],1)
        run(self.inputs,self.instance,reset_puls=True)
        with self.connection() as c:
            self.assertEqual(c.execute('SELECT include FROM questions WHERE source=?',(source,)).fetchone()[0],0)
