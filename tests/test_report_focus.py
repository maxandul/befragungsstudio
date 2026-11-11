import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest

from app import create_app, DEFAULT_MISSING


class ReportFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=create_app(self.root).test_client()
        with sqlite3.connect(self.root/'studio.sqlite3') as c:
            c.execute("INSERT INTO projects(id,name,kind) VALUES(1,'Testbefragung','echonovum')")
            definitions=[('old','common',1),('new','common',1),('retired','retired',1),
                         ('fresh','fresh',1),('future','future',1),('except','except',1),('off','off',0)]
            for source,canonical,include in definitions:
                c.execute('INSERT INTO questions(project,source,canonical,label,type,missing,include) VALUES(?,?,?,?,?,?,?)',
                          (1,source,canonical,canonical,'scale',DEFAULT_MISSING,include))
            # Absichtlich keine alphabetische Reihenfolge der Wellennamen.
            for wave,date,sources in [('Z-alt','2024-01-01',['old','retired','except','off']),
                                       ('A-Bezug','2025-01-01',['new','fresh','except','off']),
                                       ('B-später','2026-01-01',['new','future','off'])]:
                for source in sources:
                    for person in ['x','y']:
                        c.execute('INSERT INTO answers VALUES(?,?,?,?,?,?,?)',
                                  (1,wave,person,source,'4',date,json.dumps({'unit':'eins'})))
            c.execute("INSERT INTO question_exclusions VALUES(1,'except','A-Bezug','Ausnahme')")
            c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES(1,'*','Einheit','unit')")

    def payload(self,query):
        response=self.client.get('/p/1/report?min_n=1&'+query)
        self.assertEqual(response.status_code,200,response.data)
        match=re.search(rb'<script id="chart-data" type="application/json">(.*?)</script>',response.data,re.S)
        return json.loads(match.group(1))

    def test_focus_selects_current_questions_and_keeps_linked_history(self):
        payload=self.payload('focus_wave=A-Bezug&wave=B-sp%C3%A4ter')
        self.assertEqual(payload['focus_wave'],'A-Bezug')
        cards={card['label']:card for card in payload['cards']}
        self.assertEqual(set(cards),{'common','fresh'})
        self.assertEqual([r['wave'] for r in cards['common']['rows']],['Z-alt','A-Bezug'])
        self.assertEqual([r['wave'] for r in cards['fresh']['rows']],['A-Bezug'])
        self.assertEqual(cards['common']['rows'][1]['n'],2)

    def test_overall_still_contains_retired_questions_and_all_waves(self):
        payload=self.payload('')
        cards={card['label']:card for card in payload['cards']}
        self.assertEqual(set(cards),{'common','retired','fresh','future','except'})
        self.assertEqual([r['wave'] for r in cards['common']['rows']],['Z-alt','A-Bezug','B-später'])
        self.assertEqual([r['wave'] for r in cards['except']['rows']],['Z-alt'])
        selected=self.payload('wave=Z-alt')
        self.assertEqual({c['label'] for c in selected['cards']},{'common','retired','except'})

    def test_old_focus_has_no_future_data_and_unknown_focus_is_rejected(self):
        payload=self.payload('focus_wave=Z-alt')
        self.assertEqual({c['label'] for c in payload['cards']},{'common','retired','except'})
        self.assertTrue(all(r['wave']=='Z-alt' for c in payload['cards'] for r in c['rows']))
        self.assertEqual(self.client.get('/p/1/report?focus_wave=unknown').status_code,400)

    def test_focus_respects_segment_minimum_and_download_routes(self):
        payload=self.payload('focus_wave=A-Bezug&dimension=Einheit&unit=eins')
        self.assertEqual(len(payload['cards']),2)
        small=self.client.get('/p/1/report?focus_wave=A-Bezug&min_n=3')
        self.assertEqual(small.status_code,200)
        self.assertIn(b'"cards": []',small.data)
        download=self.client.get('/p/1/report?focus_wave=A-Bezug&min_n=1&download=1')
        self.assertEqual(download.status_code,200)
        self.assertIn(b'Bericht zur Welle A-Bezug',download.data)
        zip_route=self.client.get('/p/1/charts.zip?focus_wave=A-Bezug&min_n=1')
        self.assertIn('focus_wave=A-Bezug',zip_route.location)
        page=self.client.get('/p/1/results?focus_wave=A-Bezug&min_n=1')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'name="focus_wave"',page.data)
