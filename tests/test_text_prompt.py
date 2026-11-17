import io
import json
import unittest
import zipfile
import test_text_analysis as legacy
import test_wave_texts as wave
import wave_analysis as wa


class TextPromptTests(unittest.TestCase):
    setUp=legacy.TextAnalysisTests.setUp
    db=legacy.TextAnalysisTests.db
    post=legacy.TextAnalysisTests.post
    wave_job=wave.WaveTextTests.wave_job
    parts=wave.WaveTextTests.parts
    make_wave=wave.WaveTextTests.make_wave
    part_url=wave.WaveTextTests.part_url
    export_part=wave.WaveTextTests.export_part
    import_files=wave.WaveTextTests.import_files

    def test_updated_prompt_is_delivered_without_changing_export_or_import_format(self):
        _,url=self.make_wave()
        part=self.parts()[0]
        data,result=self.export_part(part)
        before=next(p for p in self.parts() if p['id']==part['id'])
        download=self.client.get(self.part_url(part)+'/download')
        with zipfile.ZipFile(io.BytesIO(download.data)) as z:
            self.assertEqual(z.read('standardprompt.txt').decode(),wa.PROMPT)
            self.assertEqual(json.loads(z.read('daten.json')),data)
            template=json.loads(z.read('rueckgabe_vorlage.json'))
            self.assertEqual(template['version'],2)
            self.assertEqual(template['teil'],part['id'])
            self.assertEqual({a['id'] for a in template['antworten']},{a['id'] for a in data['antworten']})
        combined=self.client.get(url+'/download')
        self.assertEqual(combined.status_code,200)
        with zipfile.ZipFile(io.BytesIO(combined.data)) as z:
            self.assertEqual(z.read('standardprompt.txt').decode(),wa.PROMPT)
            self.assertEqual(json.loads(z.read('Teil_001/daten.json')),data)
        after=next(p for p in self.parts() if p['id']==part['id'])
        self.assertEqual(before,after)
        self.assertEqual(self.import_files(url,[result]).status_code,302)
        imported=next(p for p in self.parts() if p['id']==part['id'])
        self.assertEqual(imported['state'],'imported')
        self.assertEqual(json.loads(imported['result']),result)


if __name__=='__main__':unittest.main()
