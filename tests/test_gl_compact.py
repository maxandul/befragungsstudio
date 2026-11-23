import re
import unittest
import test_report_editorial as editorial
from report_views import prepare_text_views,ranking,GL_MAX_HIGHLIGHTS


def compact_entries(views):
    return sorted((e for topic in views['q'] for e in topic['main']),key=ranking)


class CompactSelectionTests(unittest.TestCase):
    def entry(self,text,count,kind='single',order=10):
        return dict(text=text,count=count,denominator=30,kind=kind,order=order,details=[])

    def test_one_hundred_single_hints_are_not_one_hundred_highlights(self):
        entries=[self.entry('Einzelhinweis '+str(i),1,'key' if i%2 else 'single') for i in range(100)]
        views=prepare_text_views({'q':[dict(titel='Führungsrolle',statements=entries)]},'gl')
        self.assertEqual(compact_entries(views),[])
        self.assertEqual(sum(len(t['all']) for t in views['q']),100)

    def test_frequency_wins_over_kind_and_priority_and_is_capped_per_question(self):
        entries=[self.entry('A',14,'normal',999),self.entry('B',10,'single',999),
                 self.entry('C',5,'normal',999),self.entry('D',4,'key',0),self.entry('E',1,'key',0)]
        data={'q':[dict(titel=str(i),statements=[e]) for i,e in enumerate(entries)]}
        views=prepare_text_views(data,'gl');selected=compact_entries(views)
        self.assertEqual([e['text'] for e in selected],['A','B','C'])
        self.assertEqual(len(selected),GL_MAX_HIGHLIGHTS)
        self.assertEqual(sum(len(t['all']) for t in views['q']),5)
        smaller={'q':[dict(titel='OE',statements=[dict(e,count=1) for e in entries])]}
        self.assertEqual(compact_entries(prepare_text_views(smaller,'gl')),[])

    def test_duplicate_concerns_do_not_inflate_compact_print_selection(self):
        long='Ein langes Anliegen '+('mit weiteren Details '*40)
        entries=[self.entry('Gleiches Anliegen.',9),self.entry('gleiches  Anliegen',8),self.entry(long,4)]
        views=prepare_text_views({'q':[dict(titel='Thema',statements=entries)]},'gl')
        highlights=compact_entries(views)
        self.assertEqual(len(highlights),2)
        self.assertEqual(highlights[0]['count'],9)  # Do not add possibly overlapping source groups.
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
        self.assertEqual([t.get('count') for t in topics],[4,3,1])
        self.assertEqual(topics[-1]['all'][0]['text'],'Rollen erläutern')

    def test_several_unbundled_statements_with_shared_theme_become_direct_nuances(self):
        statements=[dict(self.entry('Information kommt früh',1),people={'a'},reviewed=False),
                    dict(self.entry('Information kommt spät',1),people={'b'},reviewed=False)]
        isolated=dict(self.entry('Ein anderer Aspekt',1),people={'c'},reviewed=False)
        themes=prepare_text_views({'q':[dict(titel='Informationsfluss',statements=statements),
                                         dict(titel='Anderes Thema',statements=[isolated])]},'oe')['q']
        self.assertEqual([theme['title'] for theme in themes],['Informationsfluss','Einzelaussagen'])
        self.assertEqual(themes[0]['count'],2)
        self.assertTrue(all(not entry['details'] for entry in themes[0]['all']))

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
        self.assertLess(html.index('class="overview-chart"'),html.index('class="qual-topic"'))
        screen=html.split('<div class="qual-print">',1)[0]
        self.assertEqual(screen.count(body),1)
        self.assertIn('<summary>Thema · Weitere Rückmeldungen',screen)
        self.assertRegex(screen,r'<summary>Thema · Weitere Rückmeldungen\s*'
                         r'<small class="concern-origin">Herkunft A, B · 2 Textantworten</small>')
        self.assertRegex(screen,r'<summary>\s*<strong class="concern-label">Kernaussage</strong> <span class="concern-text">'
                         +re.escape(body)+r'</span>\s*<small class="concern-origin">Herkunft A, B · 2 Textantworten</small>')
        self.assertIn('<strong class="concern-label">Nuance</strong> <span class="concern-text">Aussage person-a</span> '
                      '<small class="concern-origin">Herkunft A · 1 Textantwort</small>',screen)
        self.assertNotIn('class="qual-topic" open',screen)
        self.assertNotIn('class="qual-nuances" open',screen)
        self.assertIn('<ul class="concern-list">',screen)
        self.assertIn('.qual-nuances>summary>.concern-label{display:inline}',screen)
        self.assertIn('list-style:none',screen)
        print_blocks=''.join(re.findall(r'<div class="qual-print">(.*?)</div>',html,re.S))
        self.assertIn(body,print_blocks)

    def test_selected_unit_is_origin_when_children_are_hidden(self):
        _,url,index=self.ready()
        self.create(url,index)
        html=self.client.get('/p/1/report?focus_wave=2026&profile=oe&min_n=1&include_children=0').text
        self.assertRegex(html,r'<summary>Thema · Zusammenarbeit\s*'
                         r'<small class="concern-origin">Herkunft AFA · 2 Textantworten</small>')
        self.assertIn('Herkunft AFA · 1 Textantwort',html)
        guide=html.split('<summary>So liest du die Ergebnisse</summary>',1)[1].split('</details>',1)[0]
        self.assertIn('<p><strong>Textantworten</strong>',guide)
        self.assertNotIn('<h3>Textantworten</h3>',guide)
        self.assertIn('<div class="concern-body">',html)
        self.assertNotIn('<p>\n<strong class="concern-label">',html)

    def test_editor_explains_disabled_sources_and_places_optional_work_last(self):
        _,url,index=self.ready();self.create(url,index)
        html=self.client.get(url).text
        self.assertIn('keine zusätzlichen Pflichtschritte',html)
        self.assertIn('keine Gewichtung',html)
        self.assertIn('Bereits zugeordnete Aussagen sind ausgegraut',html)
        self.assertIn('Zur Zusammenfassung',html)
        self.assertLess(html.index('Kernaussagen und Nuancen ·'),html.index('Erweiterte Quellenprüfung und neue Bündelungen (optional)'))


if __name__=='__main__':unittest.main()
