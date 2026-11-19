import re
import unittest
import test_report_editorial as editorial
from report_views import prepare_text_views,gl_highlights,GL_MAX_HIGHLIGHTS,GL_EXCERPT_CHARS


class CompactSelectionTests(unittest.TestCase):
    def entry(self,text,count,kind='single',order=10):
        return dict(text=text,count=count,denominator=30,kind=kind,order=order,details=[])

    def test_one_hundred_single_hints_are_not_one_hundred_highlights(self):
        entries=[self.entry('Einzelhinweis '+str(i),1,'key' if i%2 else 'single') for i in range(100)]
        views=prepare_text_views({'q':[dict(titel='Führungsrolle',statements=entries)]},'gl')
        self.assertEqual(gl_highlights(views)['q'],[])
        self.assertEqual(sum(len(t['all']) for t in views['q']),100)
        self.assertEqual(sum(len(t['remaining']) for t in views['q']),100)

    def test_frequency_wins_over_kind_and_priority_and_is_capped_per_question(self):
        entries=[self.entry('A',14,'normal',999),self.entry('B',10,'single',999),
                 self.entry('C',5,'normal',999),self.entry('D',4,'key',0),self.entry('E',1,'key',0)]
        data={'q':[dict(titel=str(i),statements=[e]) for i,e in enumerate(entries)]}
        views=prepare_text_views(data,'gl');selected=gl_highlights(views)['q']
        self.assertEqual([e['text'] for e in selected],['A','B','C'])
        self.assertEqual(len(selected),GL_MAX_HIGHLIGHTS)
        self.assertEqual(sum(len(t['all']) for t in views['q']),5)
        smaller={'q':[dict(titel='OE',statements=[dict(e,count=1) for e in entries])]}
        self.assertEqual(gl_highlights(prepare_text_views(smaller,'gl'))['q'],[])

    def test_duplicates_not_double_counted_and_long_excerpts_stay_bounded(self):
        long='Ein langes Anliegen '+('mit weiteren Details '*40)
        entries=[self.entry('Gleiches Anliegen.',9),self.entry('gleiches  Anliegen',8),self.entry(long,4)]
        views=prepare_text_views({'q':[dict(titel='Thema',statements=entries)]},'gl')
        highlights=gl_highlights(views)['q']
        self.assertEqual(len(highlights),2)
        self.assertEqual(highlights[0]['count'],9)  # Do not add possibly overlapping source groups.
        self.assertLessEqual(len(highlights[1]['display_text']),GL_EXCERPT_CHARS)
        self.assertTrue(highlights[1]['display_text'].endswith('…'))
        self.assertEqual(highlights[1]['text'],long)

    def test_topics_count_people_once_and_singles_stay_last(self):
        def entry(text, people):
            return dict(self.entry(text,len(people)),people=set(people),reviewed=True)

        data={'q':[
            dict(titel='Zusammenarbeit',statements=[
                entry('Gemeinsame Abläufe beibehalten', ['a','b']),
                entry('Übergaben vereinfachen', ['a','c'])]),
            dict(titel='Information',statements=[
                entry('Früher informieren', ['a','b','c','d']),
                entry('Rollen erläutern', ['a'])])]}
        topics=prepare_text_views(data,'oe')['q']
        self.assertEqual([t['title'] for t in topics],['Information','Zusammenarbeit','Einzelaussagen'])
        self.assertEqual([t.get('count') for t in topics],[4,3,None])
        self.assertEqual(topics[-1]['all'][0]['text'],'Rollen erläutern')

    def test_repeated_sentence_heading_is_suppressed_and_oe_keeps_all(self):
        body='Viele Termine und Hektik erschweren den Alltag.'
        data={'q':[dict(titel=body,statements=[self.entry(body,1)])]}
        views=prepare_text_views(data,'oe')
        self.assertEqual(views['q'][0]['title'],'Einzelaussagen')
        self.assertEqual(views['q'][0]['main'][0]['text'],body)


class CompactReportTests(unittest.TestCase):
    setUp=editorial.ReportEditorialTests.setUp
    db=editorial.ReportEditorialTests.db
    post=editorial.ReportEditorialTests.post
    wave_job=editorial.ReportEditorialTests.wave_job
    parts=editorial.ReportEditorialTests.parts
    make_wave=editorial.ReportEditorialTests.make_wave
    part_url=editorial.ReportEditorialTests.part_url
    export_part=editorial.ReportEditorialTests.export_part
    import_files=editorial.ReportEditorialTests.import_files
    approve_part=editorial.ReportEditorialTests.approve_part
    ready=editorial.ReportEditorialTests.ready
    create=editorial.ReportEditorialTests.create

    def test_charts_before_texts_and_single_disclosure_without_duplicate_heading(self):
        _,url,index=self.ready()
        body='Administration begrenzt Zeit für Beratung.'
        self.assertEqual(self.create(url,index,topic=body,body=body).status_code,302)
        with self.db() as c:
            c.execute("INSERT INTO questions(project,source,canonical,label,type,theme,missing) VALUES(1,'score','score','Score','scale','Thema','')")
            import json
            raw=json.dumps({'Amt':'AFA','Bereich':'A','Kadertyp':'','Question':'Skalenfrage'})
            c.execute("INSERT INTO answers VALUES(1,'2026','person-a','score','3','2026-10-01',?)",(raw,))
        html=self.client.get('/p/1/report?focus_wave=2026&profile=gl&min_n=1').text
        self.assertLess(html.index('class="overview-chart"'),html.index('class="gl-highlights"'))
        self.assertNotIn('<h4>'+body+'</h4>',html)
        self.assertIn('2 von 3 Textantwortenden',html)
        self.assertIn('<details class="gl-text-details"><summary>Alle Anliegen',html)
        # No default-open qualitative disclosure; no individual hint promotion.
        self.assertNotIn('<details class="gl-text-details" open',html)
        self.assertNotIn('Besonderer Hinweis:</strong> '+body,html)
        print_blocks=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',html,re.S))
        self.assertIn(body,print_blocks)

    def test_editor_explains_disabled_sources_and_places_optional_work_last(self):
        _,url,index=self.ready();self.create(url,index)
        html=self.client.get(url).text
        self.assertIn('keine zusätzlichen Pflichtschritte',html)
        self.assertIn('keine Gewichtung',html)
        self.assertIn('Bereits zugeordnete Aussagen sind ausgegraut',html)
        self.assertIn('Zum Anliegen',html)
        self.assertLess(html.index('Berichtsanliegen ·'),html.index('Erweiterte Quellenprüfung und neue Bündelungen (optional)'))


if __name__=='__main__':unittest.main()
