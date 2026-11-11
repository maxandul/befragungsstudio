import io
import tempfile
import unittest
from pathlib import Path
import sys
import shutil
import subprocess
import zipfile
import sqlite3
from unittest.mock import patch, MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from core import read_table,normalize,aggregate,parse_rules,segment_preview


class StudioTests(unittest.TestCase):
    def test_segment_dimensions_are_complete_unique_and_extensible(self):
        from html.parser import HTMLParser
        class Selects(HTMLParser):
            def __init__(self):
                super().__init__();self.current=None;self.options={}
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if tag=='select':
                    self.current=a.get('id');self.options[self.current]=[]
                if tag=='option' and self.current:
                    self.options[self.current].append(a.get('value',''))
            def handle_endtag(self,tag):
                if tag=='select':self.current=None
        self.question_setup()
        for wave in ['*','Juni']:
            r=self.post('/p/1/segments',dict(action='mapping',wave=wave,dimension='Bereich',source='Question title'))
            self.assertEqual(r.status_code,302)
        r=self.post('/p/1/segments',dict(action='mapping',wave='*',dimension='__custom__',
                    custom_dimension='Dienstjahresgruppe',source='Question title'))
        self.assertEqual(r.status_code,302)
        page=self.client.get(r.location)
        parser=Selects();parser.feed(page.data.decode())
        for name in ['mapping-dimension','alias-dimension']:
            values=parser.options[name]
            self.assertEqual(values.count('Bereich'),1)
            self.assertEqual(len(values),len(set(values)))
            for value in ['Amt','Bereich','Abteilung','RAV Gruppe','RAV','Team','Dienstjahresgruppe','__custom__']:
                self.assertIn(value,values)
        self.assertNotIn(b'list="dims"',page.data)
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM mappings WHERE dimension=?',('__custom__',)).fetchone()[0],0)
        bad=self.post('/p/1/segments',dict(action='mapping',wave='*',dimension='__custom__',custom_dimension='',source='Question title'))
        self.assertEqual(bad.status_code,400)

    def test_segment_preview_counts_participations_and_applies_rules(self):
        first=dict(wave='2024',feedback='a',raw={'HS2':'Stab','Bereich':''})
        records=[first,dict(first),dict(wave='2024',feedback='b',raw={'HS2':'AI','Bereich':''}),
                 dict(wave='2026',feedback='a',raw={'HS2':'','Bereich':'AWI Stab'})]
        mappings=[dict(wave='*',dimension='Bereich',source='Bereich'),dict(wave='2024',dimension='Bereich',source='HS2')]
        aliases=[dict(wave='*',dimension='Bereich',source='Stab',target='AWI Stab')]
        preview=segment_preview(records,mappings,aliases,wave='2024',source='HS2',dimension='Bereich',original='Stab',target='Neuer Stab')
        self.assertEqual(preview['total'],2)
        self.assertEqual(preview['filled'],2)
        self.assertEqual(preview['values'],[dict(value='AI',n=1),dict(value='Stab',n=1)])
        self.assertIn(dict(source='Stab',current='AWI Stab',after='Neuer Stab',n=1),preview['effective'])
        self.assertEqual(aliases[0]['target'],'AWI Stab')
        preview=segment_preview(records,mappings,aliases,wave='2026',source='HS2',dimension='Bereich')
        self.assertEqual(preview['total'],1)
        self.assertEqual(preview['empty'],1)
        self.assertEqual(preview['mapped'],1)
        self.assertNotIn('HS2',[c['name'] for c in preview['columns']])
        preview=segment_preview(records,mappings,aliases)
        self.assertEqual(preview['total'],3)

    def test_segment_preview_conflicts_and_endpoint_is_readonly(self):
        records=[dict(wave='W',feedback='a',raw={'Bereich':'A'}),dict(wave='W',feedback='a',raw={'Bereich':'B'})]
        preview=segment_preview(records,source='Bereich')
        self.assertEqual(preview['filled'],1)
        self.assertEqual(preview['conflicts'],1)
        self.question_setup()
        self.post('/p/1/segments',dict(action='mapping',wave='*',dimension='Bereich',source='Question title'))
        r=self.client.get('/p/1/segments/preview?wave=Juni&source=Question+title&dimension=Bereich&original=Frage+alt&target=Gemeinsam')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['total'],2)
        self.assertIn(dict(source='Frage alt',current='Frage alt',after='Gemeinsam',n=1),r.json['effective'])
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM aliases').fetchone()[0],0)
        r=self.client.get('/p/1/segments?wave=Juni')
        self.assertIn(b'id="candidate-columns"',r.data)
        self.assertIn(b'segments.js',r.data)

    @unittest.skipUnless(shutil.which('node'), 'Optionaler Entwicklungstest benötigt Node.js')
    def test_question_save_url_and_csrf_retry(self):
        subprocess.run(['node',str(Path(__file__).with_name('check_question_save.cjs'))],check=True,capture_output=True)
    def test_question_session_isolated_and_renewable(self):
        self.question_setup()
        f=self.question_form()
        # Andere localhost-Apps verwenden oft denselben Standardnamen "session".
        self.client.set_cookie('session','other-local-app-cookie')
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,200,r.data)
        self.client.set_cookie('befragungsstudio_session','expired-cookie')
        f['label_0']='Erhaltene Änderung'
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,400)
        self.assertEqual(r.json['code'],'csrf_expired')
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM questions WHERE label=?',('Erhaltene Änderung',)).fetchone()[0],0)
        token=self.client.get('/session/csrf')
        self.assertIn('no-store',token.headers['Cache-Control'])
        f['csrf']=token.json['csrf']
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,200,r.data)

    def test_ajax_errors_are_specific_json(self):
        r=self.client.get('/missing-page',headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,404)
        self.assertEqual(r.json['code'],'http_error')
        fresh_app=create_app(self.temp.name)
        @fresh_app.get('/test-error')
        def fail():
            raise RuntimeError('Synthetic error for diagnostics')
        with self.assertLogs(fresh_app.logger,level='ERROR'):
            r=fresh_app.test_client().get('/test-error',headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,500)
        self.assertEqual(r.json['code'],'server_error')
        log=(Path(self.temp.name)/'app.log').read_text()
        self.assertIn(r.json['reference'],log)
        self.assertNotIn('Synthetic error',r.json['error'])

    def question_setup(self, overlap=False):
        self.post('/projects',dict(name='Puls',kind='echonovum'))
        data='Feedback ID,Question ID,Question title,Question type,Answer,Answer given at,Welle\na,old,Frage alt,scale,4,2026-06-01,Juni\nb,new,Frage neu,scale,5,2026-06-02,Juni\n'
        if overlap:
            data+='a,new,Frage neu,scale,5,2026-06-01,Juni\n'
        r=self.post('/p/1/upload',{'file':(io.BytesIO(data.encode()),'test.csv')})
        self.post(r.location,dict(mode='long',feedback='Feedback ID',qid='Question ID',title='Question title',type='Question type',answer='Answer',date='Answer given at',wave='Welle',commit='yes'))

    def question_form(self):
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            c.row_factory=sqlite3.Row
            rows=c.execute('SELECT * FROM questions ORDER BY source').fetchall()
        data=dict(csrf=self.csrf,action='save',group_key=[q['canonical'] for q in rows],common_missing='Keine Antwort\nKeine Ahnung')
        for i,q in enumerate(rows):
            for field in ['label','type','theme','minimum','maximum','top_from','options','missing']:
                data[f'{field}_{i}']=str(q[field])
            data[f'include_{i}']='on'
        return data

    def test_question_bulk_save_link_split_and_global_missing(self):
        self.question_setup()
        f=self.question_form();f['label_0']='Gemeinsame Frage';f.update(action='link',selected_group=['old'],link_target='new')
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,200,r.data)
        self.assertTrue(r.json['reload'])
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(DISTINCT canonical) FROM questions').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT missing FROM question_settings').fetchone()[0],'Keine Antwort\nKeine Ahnung')
        r=self.client.get('/p/1/results?min_n=1')
        self.assertIn(b'4.50',r.data)
        self.assertIn(b'Gemeinsame Frage',r.data)
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            c.execute('UPDATE answers SET answer=? WHERE feedback=?',('Keine Ahnung','b'))
        r=self.client.get('/p/1/results?min_n=1')
        self.assertIn(b'4.00',r.data)
        self.assertNotIn(b'4.50',r.data)
        f=self.question_form()
        # Das echte Formular enthält nur eine Karte pro gemeinsamer Frage.
        f['group_key']=['new'];f['split_source']='old'
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,200,r.data)
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(DISTINCT canonical) FROM questions').fetchone()[0],2)

    def test_link_overlap_rejected_without_partial_save(self):
        self.question_setup(overlap=True)
        f=self.question_form();f.update(action='link',selected_group=['old'],link_target='new')
        f['label_0']='Nicht speichern'
        r=self.client.post('/p/1/questions',data=f,headers={'Accept':'application/json'})
        self.assertEqual(r.status_code,400)
        self.assertIn('doppelt',r.json['error'])
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT COUNT(DISTINCT canonical) FROM questions').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM questions WHERE label=?',('Nicht speichern',)).fetchone()[0],0)

    def test_missing_rules_migration_and_per_source_calculation(self):
        self.question_setup()
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            c.execute('UPDATE questions SET missing=? WHERE source=?',('Sonderfall','old'))
            c.execute('ALTER TABLE questions DROP COLUMN missing_override')
        create_app(self.temp.name)
        with sqlite3.connect(Path(self.temp.name)/'studio.sqlite3') as c:
            self.assertEqual(c.execute('SELECT missing_override FROM questions WHERE source=?',('old',)).fetchone()[0],1)
            self.assertEqual(c.execute('SELECT missing_override FROM questions WHERE source=?',('new',)).fetchone()[0],0)
        q=dict(canonical='q',label='Q',type='scale',theme='',minimum=1,maximum=5,top_from=4,missing='4',options='',include=1)
        r=dict(wave='W',feedback='a',source='a',answer='4',raw={})
        r2=dict(wave='W',feedback='b',source='b',answer='4',raw={})
        rows,_=aggregate([r,r2],{'a':q,'b':{**q,'missing':''}})
        self.assertEqual(rows[0]['n'],1)
        self.assertEqual(rows[0]['missing'],1)

    def test_launcher_progress_and_missing_package(self):
        import run_web
        target=str(Path(self.temp.name)/'run_web.py')
        output=io.StringIO()
        server=MagicMock(effective_port=5051)
        with patch.object(run_web,'__file__',target), patch.object(sys,'argv',['run_web.py']), \
             patch.object(sys,'stdout',output), patch.object(sys,'stderr',output), \
             patch('app.create_app',return_value=object()), \
             patch('waitress.create_server',return_value=server):
            self.assertEqual(run_web.main(),0)
        self.assertIn('Befragungsstudio ist bereit: http://127.0.0.1:5051',output.getvalue())
        server.close.assert_called_once()
        output=io.StringIO()
        with patch.object(run_web,'__file__',target), patch.object(sys,'argv',['run_web.py']), \
             patch.object(sys,'stdout',output), patch.object(sys,'stderr',output), \
             patch.object(run_web.importlib,'import_module',side_effect=ModuleNotFoundError(name='flask')):
            self.assertEqual(run_web.main(),1)
        self.assertIn('Python-Paket fehlt: flask',output.getvalue())
        self.assertIn('FEHLER',(Path(self.temp.name)/'instance/start.log').read_text())

    @unittest.skipUnless(shutil.which('node'), 'Optionaler Entwicklungstest benötigt Node.js')
    def test_browser_export_orchestration(self):
        archive=Path(self.temp.name)/'charts.zip'
        subprocess.run(['node',str(Path(__file__).with_name('check_exports.cjs')),str(archive)],check=True,capture_output=True)
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()),3)
            self.assertEqual(z.read(z.namelist()[0]),b'PNG:1920x1080')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app(self.temp.name)
        self.client=self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as s:
            self.csrf=s['csrf']

    def tearDown(self):
        self.temp.cleanup()

    def post(self,path,data):
        return self.client.post(path,data={'csrf':self.csrf,**data})

    def test_full_import_repeat_and_report(self):
        r=self.post('/projects',dict(name='Test Puls',kind='echonovum'))
        pid=int(r.location.rsplit('/',1)[-1])
        data=b'Feedback ID,Question ID,Question title,Question type,Answer,Answer given at,Befragung (object),Bereich\na,q,Zufriedenheit,scale,5,2026-01-01,Puls 2026,AI\nb,q,Zufriedenheit,scale,3,2026-01-01,Puls 2026,AI\n'
        cfg=dict(mode='long',feedback='Feedback ID',qid='Question ID',title='Question title',type='Question type',answer='Answer',date='Answer given at',wave='Befragung (object)',commit='yes')
        for _ in range(2):
            r=self.post(f'/p/{pid}/upload',{'file':(io.BytesIO(data),'test.csv')})
            self.assertEqual(r.status_code,302)
            r=self.post(r.location,cfg)
            self.assertEqual(r.status_code,302,r.data)
        self.post(f'/p/{pid}/segments',dict(action='mapping',wave='*',dimension='Bereich',source='Bereich'))
        self.post(f'/p/{pid}/grounds',dict(wave='Puls 2026',dimension='Bereich',unit='AI',total='4'))
        r=self.client.get(f'/p/{pid}/results?dimension=Bereich&unit=AI&min_n=1')
        self.assertEqual(r.status_code,200,r.data)
        self.assertIn(b'50.0 %',r.data)
        self.assertIn(b'4.00',r.data)
        suppressed=self.client.get(f'/p/{pid}/report?min_n=5')
        self.assertNotIn(b'<canvas id="chart-',suppressed.data)
        r=self.client.get(f'/p/{pid}/report?min_n=1&download=1')
        self.assertEqual(r.status_code,200,r.data)
        self.assertIn(b'<canvas id="chart-0"',r.data)
        self.assertIn(b'Chart.js v4.4.8',r.data)
        self.assertNotIn(b'<script src=',r.data)
        r=self.client.get(f'/p/{pid}/charts.zip?min_n=1',follow_redirects=True)
        self.assertEqual(r.status_code,200)
        self.assertIn(b'data-auto-zip="true"',r.data)
        for endpoint in ['questions','segments','grounds','results','']:
            self.assertEqual(self.client.get(f'/p/{pid}/{endpoint}'.rstrip('/')).status_code,200)

    def test_missing_and_minimum(self):
        self.post('/projects',dict(name='Test',kind='echonovum'))
        r=self.client.get('/p/1/results')
        self.assertEqual(r.status_code,200)
        self.assertNotIn(b'data:image/png',r.data)
        self.assertEqual(self.client.post('/projects',data={'name':'x'}).status_code,400)

    def test_bom_and_periods(self):
        df=read_table(b'\xef\xbb\xbfID;A\n1;4\n','test.csv')
        self.assertEqual(df.columns.tolist(),['ID','A'])
        r=normalize(df,dict(mode='wide',feedback='ID',fixed_wave='2026',questions={'A':'scale'}),'hash')
        self.assertEqual(r[0]['answer'],'4')
        with self.assertRaises(ValueError):
            parse_rules('A | 01.01.2026 | 31.01.2026\nB | 15.01.2026 | 15.02.2026')

    def test_wave_methods_use_explicit_source(self):
        data=b'ID,Q,Antwort,Datum,Welle\na,q,4,2026-06-30,Falsch\nb,q,5,2026-07-01,Falsch\n'
        df=read_table(data,'test.csv')
        cfg=dict(mode='long',feedback='ID',qid='Q',answer='Antwort',date='Datum',wave='Welle',fixed_wave='Alt')
        r=normalize(df,{**cfg,'wave_mode':'month'},'hash')
        self.assertEqual([v['wave'] for v in r],['2026-06','2026-07'])
        r=normalize(df,{**cfg,'wave_mode':'periods','periods':'Puls Juni | 01.06.2026 | 31.07.2026'},'hash')
        self.assertEqual({v['wave'] for v in r},{'Puls Juni'})
        r=normalize(df,{**cfg,'wave_mode':'field'},'hash')
        self.assertEqual({v['wave'] for v in r},{'Falsch'})
        r=normalize(df,{**cfg,'wave_mode':'fixed'},'hash')
        self.assertEqual({v['wave'] for v in r},{'Alt'})
        with self.assertRaises(ValueError):
            normalize(df,{**cfg,'wave_mode':'periods','periods':'Juni | 01.06.2026 | 30.06.2026'},'hash')

    def test_import_form_date_range_preview(self):
        self.post('/projects',dict(name='Puls',kind='echonovum'))
        data=b'Feedback ID,Question ID,Answer,Answer given at,Befragung (object)\na,q,4,2026-06-30,Wrong\nb,q,5,2026-07-01,Wrong\n'
        r=self.post('/p/1/upload',{'file':(io.BytesIO(data),'test.csv')})
        form=self.client.get(r.location)
        self.assertIn('Teilnahme-ID'.encode(),form.data)
        self.assertIn(b'2026-06',form.data)
        preview=self.post(r.location,dict(mode='long',feedback='Feedback ID',qid='Question ID',answer='Answer',
          date='Answer given at',wave='Befragung (object)',wave_mode='periods',
          period_name=['Puls Juni',''],period_start=['2026-06-01',''],period_end=['2026-07-31','']))
        self.assertEqual(preview.status_code,200)
        self.assertIn(b'Puls Juni',preview.data)
        self.assertNotIn(b'Wrong',preview.data)

    def test_multiple_commas_and_duplicate_question_guard(self):
        q=dict(canonical='q',label='Frage',type='choice_multiple',theme='',minimum=1,maximum=5,
               top_from=4,missing='',options='A, mit Komma\nB',include=1)
        r=dict(wave='2026',feedback='a',source='q',answer='A, mit Komma, B',raw={})
        rows,_=aggregate([r],{'q':q})
        self.assertEqual(rows[0]['counts'],{'A, mit Komma':1,'B':1})
        r2={**r,'source':'q2'}
        with self.assertRaises(ValueError):
            aggregate([r,r2],{'q':q,'q2':q})


if __name__=='__main__':
    unittest.main()
