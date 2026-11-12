import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from app import create_app
from population import population_from_oe
from seed_puls import seed_afa_population


def reference():
    columns=['OE_Kürzel','Amt','Bereich','Abteilung','RAV_Gruppe','RAV','Team']
    rows=[['a','AFA','','','','',''],
          ['team','AFA','Bereich','Abteilung','','','Team'],
          ['rav','AFA','Beratung','','Gruppe','RAV','RAV Team'],
          ['empty','AFA','Beratung','','Gruppe','RAV','Unbesetzt'],
          ['other','Anderes Amt','','','','','']]
    return pd.DataFrame(rows,columns=columns)


class PopulationTests(unittest.TestCase):
    def test_count_rows_and_roll_up_each_dimension_without_double_counting(self):
        result=population_from_oe(['a','team','team','rav','other'],reference(),'AFA')
        values={(r['dimension'],r['unit']):r['total'] for r in result['grounds']}
        self.assertEqual(result['total'],4)
        self.assertEqual(result['input_rows'],5)
        self.assertEqual(values['',''],4)
        self.assertEqual(values['Amt','AFA'],4)
        self.assertEqual(values['Bereich','Bereich'],2)
        self.assertEqual(values['RAV Gruppe','Gruppe'],1)
        self.assertEqual(values['RAV','RAV'],1)
        self.assertEqual(values['Team','Unbesetzt'],0)
        self.assertEqual(result['oe_counts'],{'a':1,'empty':0,'rav':1,'team':2})
        self.assertEqual(sum(result['oe_counts'].values()),4)
        self.assertEqual(result['missing']['Bereich'],1)
        self.assertNotIn(('Amt','Anderes Amt'),values)

    def test_missing_or_ambiguous_lookup_aborts_instead_of_undercounting(self):
        with self.assertRaisesRegex(ValueError,'fehlen im OE-Verzeichnis'):
            population_from_oe(['unknown'],reference(),'AFA')
        with self.assertRaisesRegex(ValueError,'ohne OE-Kürzel'):
            population_from_oe([''],reference(),'AFA')
        with self.assertRaisesRegex(ValueError,'genau einen'):
            population_from_oe(['team'],pd.concat([reference(),reference().iloc[[0]]]),'AFA')
        with self.assertRaisesRegex(ValueError,'keine zugeordneten'):
            population_from_oe(['other'],reference(),'AFA')

    def test_seed_scope_snapshot_repeat_and_manual_ground_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);create_app(root/'instance')
            folder=root/'exports';folder.mkdir()
            # XLSX-I/O wird hier durch Tabellen ersetzt; echte Exporte werden zusätzlich separat geprüft.
            (folder/'EXPORT_Sendout.XLSX').write_bytes(b'source')
            (folder/'OE_Liste.xlsx').write_bytes(b'reference')
            def read(data,name,**kwargs):
                if name.casefold()=='export_sendout.xlsx':
                    return pd.DataFrame({'OE':['a','team','team','rav','other']})
                return reference()
            c=sqlite3.connect(root/'instance/studio.sqlite3');c.row_factory=sqlite3.Row
            self.addCleanup(c.close)
            c.execute("INSERT INTO projects(id,name,kind) VALUES(1,'Pulse','echonovum')")
            c.execute("INSERT INTO answers VALUES(1,'Oktober','person','q','4','2026-10-20',?)",(json.dumps({'Survey ID':'2330'}),))
            c.execute("INSERT INTO grounds VALUES(1,'2025','','',99)")
            c.execute("INSERT INTO grounds VALUES(1,'Oktober','Bereich','Bereich',42)")
            with patch('seed_puls.read_table',side_effect=read):
                messages=[];seed_afa_population(c,folder,messages)
                seed_afa_population(c,folder,messages)
            self.assertTrue(any('abweichende vorhandene' in m for m in messages))
            self.assertEqual(c.execute("SELECT total FROM grounds WHERE wave='2025'").fetchone()[0],99)
            self.assertEqual(c.execute("SELECT total FROM grounds WHERE wave='Oktober' AND dimension='Bereich' AND unit='Bereich'").fetchone()[0],42)
            self.assertEqual(c.execute("SELECT total FROM grounds WHERE wave='Oktober' AND dimension='' ").fetchone()[0],4)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM population_oe').fetchone()[0],4)
            self.assertEqual(c.execute('SELECT SUM(total) FROM population_oe').fetchone()[0],4)
            snapshot=c.execute('SELECT * FROM population_snapshots').fetchone()
            self.assertEqual(snapshot['wave'],'Oktober')
            self.assertEqual(json.loads(snapshot['details'])['total'],4)
            self.assertEqual(json.loads(snapshot['details'])['grounds_preserved'],1)
            self.assertTrue(snapshot['source_hash'])
            c.commit()
            page=create_app(root/'instance').test_client().get('/p/1/grounds')
            self.assertEqual(page.status_code,200)
            self.assertIn(b'Mitarbeitendenbasis Oktober',page.data)
            self.assertIn('Direkte Besetzung aller 4'.encode(),page.data)

    def test_split_wave_does_not_receive_duplicate_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);create_app(root/'instance')
            (root/'EXPORT_Sendout.XLSX').write_bytes(b'source')
            (root/'OE_Liste.xlsx').write_bytes(b'reference')
            with sqlite3.connect(root/'instance/studio.sqlite3') as c:
                c.row_factory=sqlite3.Row
                c.execute("INSERT INTO projects(id,name,kind) VALUES(1,'Pulse','echonovum')")
                for wave,date in [('Oktober','2026-10-20'),('November','2026-11-01')]:
                    c.execute('INSERT INTO answers VALUES(?,?,?,?,?,?,?)',(1,wave,'a','q','4',date,json.dumps({'Survey ID':'2330'})))
                def read(data,name,**kwargs):
                    return pd.DataFrame({'OE':['a']}) if name.startswith('EXPORT') else reference()
                with patch('seed_puls.read_table',side_effect=read):
                    with self.assertRaisesRegex(ValueError,'mehrere Projekte/Wellen'):
                        seed_afa_population(c,root,[])
                self.assertEqual(c.execute('SELECT COUNT(*) FROM grounds').fetchone()[0],0)
