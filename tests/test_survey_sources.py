import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import create_app
from survey_sources import SurveySources, load_sources


class SurveySourceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'studio.sqlite3'
        self.client = create_app(tmp.name).test_client()
        with closing(self.db()) as db, db:
            db.execute("INSERT INTO projects(id,name,kind) VALUES (1,'P1','other'),(2,'P2','other')")
            for pid in (1, 2):
                db.execute("INSERT INTO questions(project,source,canonical,label,type,missing) VALUES (?,'q','q','Frage','text','')",(pid,))
                for wave in ('W1','W2'):
                    db.execute("INSERT INTO answers VALUES (?,?,'p','q',?,'','{}')",(pid,wave,f'{pid}/{wave}'))
        self.cache = SurveySources(self.db, '')

    def db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_scoped_loads_are_reused_and_project_isolation_survives_external_writes(self):
        with patch('survey_sources.load_sources', wraps=load_sources) as loader:
            wave = self.cache.get(1, 'W1')
            self.assertEqual([r['answer'] for r in wave[0][0]], ['1/W1'])
            self.assertIs(self.cache.get(1, 'W1'), wave)
            project = self.cache.get(1, None)
            self.assertIs(self.cache.get(1, 'W2'), project)
            other = self.cache.get(2, None)
            with closing(self.db()) as writer:
                writer.execute("UPDATE answers SET answer='Neu' WHERE project=1 AND wave='W1'")
                self.assertIs(self.cache.get(1, None), project)
                writer.rollback()
                self.assertIs(self.cache.get(1, None), project)
                writer.execute("UPDATE answers SET answer='Neu' WHERE project=1 AND wave='W1'")
                writer.commit()
            fresh = self.cache.get(1, 'W1')
            self.assertEqual(fresh[0][0][0]['answer'], 'Neu')
            self.assertIs(self.cache.get(2, None), other)
            self.assertEqual(loader.call_count, 4)

    def test_report_and_text_routes_use_current_data_after_configuration_changes(self):
        url='/p/1/report?min_n=1&include_texts=1'
        self.assertIn('1/W2', self.client.get(url).text)
        with closing(self.db()) as writer, writer:
            writer.execute("INSERT INTO question_settings VALUES (1,'1/W2')")
        self.assertNotIn('1/W2', self.client.get(url).text)
        with closing(self.db()) as writer, writer:
            writer.execute("DELETE FROM question_settings WHERE project=1")
        self.assertIn('1/W2', self.client.get(url).text)
        with patch('survey_sources.load_sources', wraps=load_sources) as loader:
            with closing(self.db()) as writer, writer:
                writer.execute("INSERT INTO question_exclusions VALUES (1,'q','W1','Test')")
            self.assertEqual(self.client.get('/p/1/texts?focus_wave=W1').status_code,200)
            self.assertEqual(loader.call_args.args[2], 'W1')

    def test_readers_share_complete_snapshot_and_get_fresh_mappings(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            snapshots=list(pool.map(lambda _: self.cache.get(1,None), range(4)))
        self.assertTrue(all(snapshot is snapshots[0] for snapshot in snapshots))
        with closing(self.db()) as writer, writer:
            writer.execute("""UPDATE answers SET raw='{"team":"A"}' WHERE project=1""")
            writer.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES (1,'*','Team','team')")
        self.assertEqual(self.cache.get(1,None)[1][('W1','p')], {'Team':'A'})
        with closing(self.db()) as writer, writer:
            writer.execute("INSERT INTO aliases(project,wave,dimension,source,target) VALUES (1,'W1','Team','A','B')")
        dims=self.cache.get(1,None)[1]
        self.assertEqual(dims[('W1','p')], {'Team':'B'})
        self.assertEqual(dims[('W2','p')], {'Team':'A'})
