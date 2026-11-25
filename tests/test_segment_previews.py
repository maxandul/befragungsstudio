import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import create_app
from segment_preview import prepare_preview


class SegmentPreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'studio.sqlite3'
        self.client = create_app(tmp.name).test_client()
        with closing(sqlite3.connect(self.path)) as c, c:
            for pid in (1, 2):
                c.execute("INSERT INTO projects(id,name,kind) VALUES (?,?,'other')", (pid, str(pid)))
                c.execute("INSERT INTO mappings(project,wave,dimension,source) VALUES (?,'*','Team','org')",(pid,))
            rows = [(1,'W1','p','1','A'),(1,'W1','p','2','B'),(1,'W2','p','1','A'),(2,'W1','p','1','C')]
            for pid,wave,feedback,source,value in rows:
                raw = json.dumps(dict(org=value, empty=''))
                c.execute("INSERT INTO answers VALUES (?,?,?,?,'','',?)",
                          (pid,wave,feedback,source,raw))

    def preview(self, pid=1, **kwargs):
        args = dict(wave='*', dimension='Team', source='org')
        args.update(kwargs)
        response = self.client.get(f'/p/{pid}/segments/preview', query_string=args)
        self.assertEqual(response.status_code, 200)
        return response.json

    def test_saved_aliases_and_simulations_reuse_counts_without_double_counting(self):
        with patch('segment_preview.prepare_preview', wraps=prepare_preview) as scan:
            first = self.preview()
            self.assertEqual(first['mapping_conflicts'],1)
            self.assertEqual(first['total'],2)
            merged = self.preview(original='B',target='A')
            self.assertEqual(merged['resulting'],[dict(value='A',n=2)])
            with closing(sqlite3.connect(self.path)) as c,c:
                c.execute("INSERT INTO aliases(project,wave,dimension,source,target) VALUES (1,'W2','Team','A','')")
            cleared = self.preview(original='A',target='new')
            self.assertEqual(cleared['resulting'],[dict(value='',n=1),dict(value='B',n=1),dict(value='new',n=1)])
            self.assertEqual(scan.call_count,1)
            switched = self.preview(source='empty')
            self.assertEqual(switched['filled'],0)
            self.assertEqual(first['columns'],switched['columns'])
            self.assertFalse(scan.call_args.kwargs['collect_columns'])

    def test_external_commits_rollback_mapping_change_and_project_switch(self):
        first = self.preview()
        with closing(sqlite3.connect(self.path)) as c:
            c.execute("DELETE FROM answers WHERE project=1")
            self.assertEqual(first,self.preview())
            c.rollback()
            c.execute("UPDATE answers SET raw=? WHERE project=1 AND wave='W2'",(json.dumps(dict(org='D', extra='')),))
            c.commit()
            updated = self.preview()
            self.assertIn(dict(value='D',n=1),updated['values'])
            self.assertIn(b'>extra</option>',self.client.get('/p/1/segments').data)
            c.execute("UPDATE mappings SET source='extra' WHERE project=1")
            c.commit()
            self.assertEqual(self.preview()['mapped'],0)
        self.assertEqual(self.preview(2)['values'],[dict(value='C',n=1)])
        self.assertEqual(self.preview(wave='absent')['total'],0)
