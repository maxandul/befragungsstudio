import io
import re
import unittest
import zipfile
from urllib.parse import parse_qs, urlsplit

from app import create_app
from report_cockpit import revision
import test_oe_reports as fixtures


class ReportCockpitTests(unittest.TestCase):
    setUp=fixtures.OrganisationReportTests.setUp
    db=fixtures.OrganisationReportTests.db
    node=fixtures.OrganisationReportTests.node

    def submit(self,action,**changes):
        data=dict(csrf=self.csrf,action=action,profile='oe',focus_wave='2026',min_n='2',
                  include_children='0',text_options_set='1',include_summaries='1')
        return self.client.post('/p/1/report/design',data={**data,**changes})

    def test_presets_restore_settings_and_package_across_sessions(self):
        a,b=[self.node('Bereich',area)['id'] for area in ('A','B')]
        saved=self.submit('save',preset_name='Bereiche',report_oe=[a,b])
        self.assertEqual(saved.status_code,302)
        other_client=create_app(self.root).test_client()
        opened=other_client.get('/p/1/results',follow_redirects=True)
        selection=parse_qs(opened.request.query_string.decode())
        self.assertEqual(selection['report_oe'],[a,b])
        self.assertEqual(selection['focus_wave'],['2026'])
        self.assertIn(b'value="0" selected>Weglassen',opened.data)
        self.assertNotIn('csrf',selection)
        self.assertEqual(self.submit('save',preset_name='Bereiche').status_code,400)
        with self.db() as c:
            c.execute("INSERT INTO projects(id,name,kind,min_n) VALUES(2,'Andere','other',2)")
        self.assertEqual(other_client.get('/p/2/results?load='+selection['preset'][0]).status_code,404)
        version=re.search(r'name="preset_version" value="(\d+)"',opened.text)[1]
        edited=self.submit('save',preset_name='Bereiche',preset=selection['preset'][0],
                           preset_version=version,report_oe=[b])
        self.assertEqual(edited.status_code,302)
        self.assertEqual(self.submit('delete_preset',preset=selection['preset'][0],preset_version=version).status_code,400)
        reopened=other_client.get('/p/1/results',follow_redirects=True)
        self.assertEqual(parse_qs(reopened.request.query_string.decode())['report_oe'],[b])
        version=re.search(r'name="preset_version" value="(\d+)"',reopened.text)[1]
        self.assertEqual(self.submit('delete_preset',preset=selection['preset'][0],preset_version=version).status_code,302)
        self.assertEqual(other_client.get('/p/1/results').status_code,200)

    def test_retired_scope_can_be_reconfigured_or_deleted(self):
        node=self.node('Team','Gleich','B')['id']
        self.assertEqual(self.submit('save',oe=node,preset_name='Früheres Team').status_code,302)
        with self.db() as c:
            c.execute("DELETE FROM organisation WHERE code='b'")
            c.execute("DELETE FROM answers WHERE json_extract(raw,'$.Bereich')='B'")
        opened=self.client.get('/p/1/results',follow_redirects=True)
        self.assertEqual(opened.status_code,200)
        self.assertIn('Bitte Welle und OE neu wählen',opened.text)
        self.assertIn('Früheres Team',opened.text)
        self.assertIn('value="delete_preset"',opened.text)

    def test_exports_use_submitted_options_and_reject_outside_branch(self):
        a,b=[self.node('Bereich',area)['id'] for area in ('A','B')]
        for action,endpoint in [('preview','report'),('html','report'),('charts','charts.zip'),('editor','report/editor')]:
            response=self.submit(action,oe=a,print_mode='full',include_texts='1')
            target=urlsplit(response.location)
            self.assertEqual(target.path,'/p/1/'+endpoint)
            params=parse_qs(target.query)
            self.assertEqual([params[k][0] for k in ('oe','include_texts','print_mode')],[a,'1','full'])
            self.assertNotIn('csrf',params)
        response=self.submit('package',report_oe=[a,b])
        self.assertEqual(response.status_code,307)
        archive=self.client.post(response.location,data=dict(csrf=self.csrf,report_oe=[a,b]))
        self.assertEqual(zipfile.ZipFile(io.BytesIO(archive.data)).namelist(),['01_A.html','02_B.html'])
        self.assertEqual(self.submit('save',oe=a,report_oe=[b],preset_name='Ausserhalb').status_code,400)
        restricted=self.submit('package',oe=a,report_oe=[b])
        self.assertEqual(self.client.post(restricted.location,data=dict(csrf=self.csrf,report_oe=[b])).status_code,400)

    def test_bulk_editor_is_atomic_and_detects_stale_text(self):
        root=self.node('Amt','AFA')['id']
        url='/p/1/report/notes?focus_wave=2026&oe='+root
        data=dict(csrf=self.csrf,bulk='1',scope=root,reference_wave='2026',
                  theme=['Erkenntnisse auf einen Blick','Nächste Schritte'],
                  body_0='Erkenntnis',body_1='Schritt',revision_0=revision('',[]),revision_1=revision('',[]))
        self.assertEqual(self.client.post(url,data=data).status_code,302)
        changed={**data,'body_0':'Unerwartet','revision_0':revision('Erkenntnis',[])}
        self.assertEqual(self.client.post(url,data=changed).status_code,400)
        with self.db() as c:
            self.assertEqual(dict(c.execute('SELECT theme,body FROM report_notes')),
                             {'Erkenntnisse auf einen Blick':'Erkenntnis','Nächste Schritte':'Schritt'})
