"""Disclosure regressions across uneven hierarchies, scopes and leadership."""
import json
import unittest

from organisation import tree
from report_editorial import project_concerns
from report_text_privacy import TextDisclosure
from report_views import prepare_text_views
import test_adhoc_texts as report_fixture


class HierarchicalTextCohorts(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.mappings = [dict(wave='*', dimension=d, source=d)
                         for d in ('Amt', 'Bereich', 'RAV Gruppe', 'Abteilung', 'RAV', 'Team')]
        self.questions = {'text': dict(type='text', canonical='text', include=1, missing='Keine Antwort')}

    def add(self, count, *, wave='2026', leader=False, **dimensions):
        people = set()
        for _ in range(count):
            person = (wave, str(len(self.records)))
            self.records.append(dict(wave=wave, feedback=person[1], source='text', answer='Text '+person[1],
                                     raw=dict(Amt='AFA', **dimensions, Kadertyp='100' if leader else '')))
            people.add(person)
        return people

    def disclosure(self, scope=(), **options):
        return TextDisclosure((self.records, self.questions, self.mappings, [], [], set()),
                              '2026', 5, [], options.pop('include_children', True), scope=scope, **options)

    def test_cousins_wait_for_the_common_ancestor_and_never_reappear_below(self):
        left = self.add(4, Bereich='Service', **{'RAV Gruppe': 'G1', 'RAV': 'Center C', 'Team': 'SUP'})
        right = self.add(4, Bereich='Service', **{'RAV Gruppe': 'G1', 'RAV': 'Center D', 'Team': 'SUP'})
        root = (('Amt', 'AFA'), ('Bereich', 'Service'))
        upper = self.disclosure(root)
        self.assertEqual(upper.adhoc_people, left | right)
        cohort = upper.partition.membership[next(iter(left))]
        self.assertEqual(cohort, root + (('RAV Gruppe', 'G1'), ('__adhoc__', 'ad hoc')))
        for scope in (root, root + (('RAV Gruppe', 'G1'),)):
            disclosure = self.disclosure(scope)
            self.assertEqual(disclosure.partition.cohorts, upper.partition.cohorts)
            self.assertEqual(disclosure.summarise(left), dict(origins=['ad hoc']))
        for rav, people in (('Center C', left), ('Center D', right)):
            for suffix in ((), (('Team', 'SUP'),)):
                lower = self.disclosure(root + (('RAV Gruppe', 'G1'), ('RAV', rav)) + suffix)
                self.assertFalse(lower.adhoc_people)
                self.assertTrue(all(not lower.allows_source(p, 'text') for p in people))
                self.assertIsNone(lower.summarise(people, bundled=True, canonical='text'))

    def test_direct_assignments_join_locally_but_closed_groups_never_borrow_remainders(self):
        direct = self.add(3, Bereich='Service', RAV='Center A')
        team = self.add(4, Bereich='Service', RAV='Center A', Team='T2')
        residual = self.add(1, Bereich='Service')
        scope = (('Amt', 'AFA'), ('Bereich', 'Service'))
        disclosure = self.disclosure(scope)
        self.assertEqual(disclosure.adhoc_people, direct | team)
        self.assertIsNone(disclosure.summarise(residual, bundled=True))
        self.assertFalse(disclosure.allows_detail(scope))
        self.assertEqual(self.disclosure(scope + (('RAV', 'Center A'),)).adhoc_people, direct | team)

    def test_small_leaders_join_at_parent_and_large_leadership_teams_stay_fixed(self):
        head = self.add(1, Bereich='Service', RAV='Center A', Team='T1', leader=True)
        small = self.add(4, Bereich='Service', RAV='Center A', Team='T2')
        anchor = (('Amt', 'AFA'), ('Bereich', 'Service'), ('RAV', 'Center A'))
        self.assertEqual(self.disclosure(anchor).adhoc_people, head | small)
        self.assertFalse(self.disclosure(anchor + (('Team', 'T1'),)).allows_source(next(iter(head)), 'text'))
        heads = set()
        for n in range(5):
            heads.update(self.add(1, Bereich='Operations', Abteilung=str(n), leader=True))
        self.assertTrue(all(self.disclosure().allows_source(p, 'text') for p in heads))
        for n in range(5):
            self.assertFalse(self.disclosure((('Amt', 'AFA'), ('Bereich', 'Operations'), ('Abteilung', str(n)))).active)
        # Sparse text contributions do not change participation-based membership.
        self.records[int(next(iter(heads))[1])]['answer'] = 'Keine Antwort'
        for include_children in (False, True):
            disclosure = self.disclosure(include_children=include_children)
            self.assertTrue(all(disclosure.allows_source(p, 'text') for p in heads))
            self.assertEqual(disclosure.partition.cohorts, self.disclosure().partition.cohorts)

    def test_aliases_and_waves_determine_membership_before_the_report_selection(self):
        a = self.add(2, Bereich='Support', Team='Old')
        b = self.add(3, Bereich='Support', Abteilung='JD')
        self.add(20, wave='2025', Bereich='Support', Team='Old')
        aliases = [dict(wave='2026', dimension='Team', source='Old', target='')]
        disclosure = TextDisclosure((self.records, self.questions, self.mappings, aliases, [], set()),
                                    '2026', 5, [], False, scope=(('Amt', 'AFA'), ('Bereich', 'Support')))
        self.assertEqual(disclosure.adhoc_people, a | b)
        self.assertEqual(len(disclosure.partition.membership), 5)

    def test_legacy_dimension_filters_cannot_select_a_partial_cohort(self):
        a = self.add(4, Bereich='A', Team='Shared')
        b = self.add(4, Bereich='B', Team='Other')
        self.assertEqual(len(self.disclosure().adhoc_people), 8)
        for dimension, unit in (('Bereich', 'A'), ('Team', 'Shared')):
            filtered = self.disclosure(dimension=dimension, unit=unit)
            self.assertTrue(all(not filtered.allows_source(p, 'text') for p in a | b))
        self.assertEqual(self.disclosure(dimension='Amt', unit='AFA').adhoc_people, a | b)

    def test_reviewed_claims_filter_protected_sources_before_counts_and_nuances(self):
        a = self.add(4, Bereich='A', Team='Small')
        b = self.add(4, Bereich='B', Team='Small')
        c = self.add(5, Bereich='A', Team='Large')
        index = {p[1]: dict(key=[*p, 'text'], canonical='text', topic='Thema',
                           text='Privater Unterton' if p in a else 'Sichere Nuance', hash=p[1])
                 for p in a | b | c}
        concern = dict(canonical='text', topic='Thema', body='Gemeinsame Kernaussage', kind='key', sort_order=1,
                       sources=json.dumps({k: v['hash'] for k, v in index.items()}))
        eligible = {tuple(v['key']) for v in index.values() if tuple(v['key'][:2]) in a | c}
        lower = self.disclosure((('Amt', 'AFA'), ('Bereich', 'A')))
        output = project_concerns(index, [concern], eligible, {}, lower)
        entry = output['text'][0]['statements'][0]
        self.assertEqual(entry['people'], c)
        self.assertEqual(entry['count'], 5)
        self.assertEqual([n['text'] for n in entry['details']], ['Sichere Nuance'])
        topic = prepare_text_views(output, 'oe', lower)['text'][0]
        self.assertEqual(topic['count'], 5)
        self.assertEqual(topic['rank_count'], 5)

    def test_partition_is_disjoint_order_independent_and_does_not_use_text_contents(self):
        for area in ('Operations', 'Support', 'Service'):
            for team, n in (('A', 2), ('B', 4), ('C', 5)):
                self.add(n, Bereich=area, Team=team)
        before = self.disclosure().partition
        members = [p for people in before.cohorts.values() for p in people]
        self.assertEqual(len(members), len(set(members)))
        self.assertEqual(len(members), len(self.records))
        self.records.reverse()
        for record in self.records:
            record['answer'] = ''
        after = self.disclosure(include_children=False).partition
        self.assertEqual(before.cohorts, after.cohorts)
        self.assertEqual(before.membership, after.membership)

    def test_uneven_hierarchy_recovers_all_synthetic_small_cohorts(self):
        # Synthetic counts cover uneven branch depth and direct assignments.
        specs = [({'Abteilung': 'Admin'}, [('', 2), ('SUP', 4), ('ECTB', 4), ('ECTC', 3)]),
                 ({'Abteilung': 'Specialists'}, [('', 3), ('SMZ1', 4), ('SMZ2', 2)]),
                 ({'RAV Gruppe': 'G1', 'RAV': 'Center A'}, [('', 3), ('T2', 4)]),
                 ({'RAV Gruppe': 'G1', 'RAV': 'Center B'}, [('', 4), ('T3', 4)]),
                 ({'RAV Gruppe': 'G1', 'RAV': 'Center C'}, [('SUP', 4)]),
                 ({'RAV Gruppe': 'G1', 'RAV': 'Center D'}, [('SUP', 4)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center I'}, [('SUP', 4), ('T3', 2)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center J'}, [('SUP', 4), ('T3', 4)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center K'}, [('', 3), ('GAS', 4), ('TEC', 4)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center L'}, [('GAS', 4), ('KV', 3), ('TEC', 3)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center E'}, [('SUP', 4)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center F'}, [('', 2)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center G'}, [('KV', 4)]),
                 ({'RAV Gruppe': 'G2', 'RAV': 'Center H'}, [('T3', 4)])]
        for dims, groups in specs:
            for team, count in groups:
                self.add(count, Bereich='Service', Team=team, **dims)
        disclosure = self.disclosure((('Amt', 'AFA'), ('Bereich', 'Service')))
        self.assertEqual(len(disclosure.adhoc_people), 94)
        self.assertEqual(sorted(map(len, disclosure.partition.cohorts.values())), [6, 7, 8, 8, 8, 9, 10, 11, 13, 14])


class HierarchicalReportOutputs(unittest.TestCase):
    setUp = report_fixture.AdHocTextTests.setUp
    db = report_fixture.AdHocTextTests.db
    payload = report_fixture.AdHocTextTests.payload

    def test_cousin_texts_and_selected_evidence_are_hidden_below_the_anchor_in_all_formats(self):
        # Existing fixture: two small teams in different areas, pooled at AFA.
        import hashlib
        token = hashlib.sha256(json.dumps(['txt', 'Vertraulicher Text 0']).encode()).hexdigest()
        with self.db() as connection:
            connection.execute("INSERT INTO report_evidence VALUES(1,'','2026','Thema',?)", (token,))
            # Keep each lower report above the numerical/text-question threshold.
            for area in ('A', 'B'):
                connection.execute("INSERT INTO organisation VALUES(?,?)", (area+'large', json.dumps(dict(Amt='AFA', Bereich=area, Team='Large'))))
                for n in range(5):
                    raw = json.dumps(dict(Amt='AFA', Bereich=area, Team='Large'))
                    for source, answer in (('q', '3'), ('txt', 'Ordentlicher Text '+area+str(n))):
                        connection.execute("INSERT INTO answers VALUES(1,'2026',?,?,?,'2026-10-01',?)",
                                           (area+str(n), source, answer, raw))
        nodes = tree([], [dict(Amt='AFA', Bereich=area) for area in ('A', 'B')])
        for options in ('', '&include_children=0', '&profile=oe&download=1&print_mode=full'):
            root, _ = self.payload('min_n=5&include_texts=1&include_evidence=1'+options)
            self.assertIn('Vertraulicher Text 0', root.text[:root.text.index('<script id="chart-data"')])
            self.assertIn('<td>ad hoc (Freitext)</td><td>5</td>', root.text)
            for node in (n for n in nodes if n['dimension'] == 'Bereich'):
                lower, _ = self.payload('min_n=5&include_texts=1&include_evidence=1&oe='+node['id']+options)
                self.assertNotIn('Vertraulicher Text', lower.text)
                self.assertNotIn('<td>ad hoc (Freitext)</td>', lower.text)
                self.assertIn('Ordentlicher Text '+node['unit'], lower.text)
