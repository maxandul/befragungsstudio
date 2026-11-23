"""Wave-wide, disjoint text cohorts shared by every report and output format."""
from collections import Counter, defaultdict

from core import mapped_dimensions
from organisation import oe_path


class TextPartition:
    """Keep safe cohorts; pass small residuals up to their common ancestor.

    Membership uses participation, never text contents, report scope or switches.
    A leader belongs at least one level above their own OE. Sufficiently large
    sibling leadership teams remain separate and keep their per-question rule.
    """
    def __init__(self, origins, leaders, minimum):
        self.cohorts = {}
        self.kinds = {}
        self.membership = {}
        direct = defaultdict(set)
        heads = defaultdict(set)
        children = defaultdict(set)
        for person, path in origins.items():
            for depth in range(len(path)):
                children[path[:depth]].add(path[:depth + 1])
            if person in leaders:
                # The head of a root OE is excluded from all OE reports.
                if len(path) > 1:
                    heads[path[:-1]].add(person)
            else:
                direct[path].add(person)

        def save(path, people, kind):
            self.cohorts[path] = frozenset(people)
            self.kinds[path] = kind
            for person in people:
                self.membership[person] = path

        def visit(path):
            residual = set()
            if len(direct[path]) >= minimum:
                save(path, direct[path], 'ordinary')
            else:
                residual.update(direct[path])
            if len(heads[path]) >= minimum:
                save(path + (('__leadership_team__', 'Führungsteam'),), heads[path], 'leadership')
            else:
                residual.update(heads[path])
            for child in sorted(children[path]):
                residual.update(visit(child))
            if len(residual) >= minimum:
                save(path + (('__adhoc__', 'ad hoc'),), residual, 'adhoc')
                return set()
            return residual

        # Unknown origins form their own cohort and never borrow known OEs.
        unknown = direct.pop((), set())
        if len(unknown) >= minimum:
            save((), unknown, 'ordinary')
        for root in sorted(children[()]):
            visit(root)


class TextDisclosure:
    def __init__(self, sources, wave, minimum, visible_children, include_children, leadership=None,
                 scope=(), dimension='', unit=''):
        records, questions, mappings, aliases, _, exclusions = sources
        self.minimum = minimum
        self.scope = tuple(scope)
        self.labels = {tuple(child['path']): child['unit'] for child in visible_children}
        self.child_depth = len(next(iter(self.labels), ()))
        self.include_children = include_children
        self.team_people = leadership['people'] if leadership else set()
        self.team_path = tuple(leadership['node']['path']) if leadership else None
        self.team_questions = leadership['text_questions'] if leadership else set()
        origins = {}
        leaders = set()
        writers = defaultdict(set)
        for record in records:
            if record['wave'] != wave:
                continue
            person = (wave, record['feedback'])
            origins.setdefault(person, oe_path(mapped_dimensions(record, mappings, aliases)))
            raw = record['raw']
            if str(raw.get('Kadertyp (subject)', raw.get('Kadertyp', ''))).strip() == '100':
                leaders.add(person)
            question = questions.get(record.get('source'), {})
            answer = str(record.get('answer', '')).strip()
            if (question.get('type') == 'text' and question.get('include', 1)
                    and (record.get('source'), wave) not in exclusions
                    and answer and answer not in (question.get('missing') or '').splitlines()):
                writers[question['canonical']].add(person)

        self.partition = TextPartition(origins, leaders, minimum)
        self.active = set()
        self.adhoc_people = set()
        self.leadership_questions = {}
        for path, people in self.partition.cohorts.items():
            kind = self.partition.kinds[path]
            anchor = path[:-1] if kind != 'ordinary' else path
            # Only full cohorts may appear: descendants must never see a slice.
            if anchor[:len(self.scope)] != self.scope:
                continue
            # Legacy dimension filters can span branches with identical labels.
            # They must also contain every member, including the leader exclusion.
            if dimension and any((dimension, unit) not in origins[person]
                                 or person in leaders and origins[person][-1] == (dimension, unit)
                                 for person in people):
                continue
            self.active.add(path)
            if kind == 'adhoc':
                self.adhoc_people.update(people)
            elif kind == 'leadership':
                self.leadership_questions[path] = {
                    canonical for canonical, respondents in writers.items()
                    if len(people & respondents) >= minimum}

        self.adhoc_node = None
        if self.adhoc_people:
            path = self.scope + (('__adhoc__', 'ad hoc'),)
            self.adhoc_node = dict(unit='ad hoc', path=list(path))
            self.labels[path] = 'ad hoc'
        # Display all whole ad hoc cohorts together, preserving their fixed
        # membership and earliest permitted scope in partition/active above.
        self.paths = dict(origins)
        self.direct_participants = Counter()
        for path in self.active:
            display = tuple(self.adhoc_node['path']) if self.partition.kinds[path] == 'adhoc' else path
            self.direct_participants[display] += len(self.partition.cohorts[path])
            for person in self.partition.cohorts[path]:
                self.paths[person] = display

    def allows_source(self, person, canonical):
        cohort = self.partition.membership.get(person)
        if cohort not in self.active:
            return False
        if person in self.team_people and canonical not in self.team_questions:
            return False
        return (self.partition.kinds[cohort] != 'leadership'
                or canonical in self.leadership_questions[cohort]
                or cohort == self.team_path and canonical in self.team_questions)

    def allows_detail(self, path, canonical=None):
        if path == self.team_path and canonical not in self.team_questions:
            return False
        if path in self.leadership_questions and canonical not in self.leadership_questions[path]:
            return path == self.team_path and canonical in self.team_questions
        return self.direct_participants[path] >= self.minimum

    def summarise(self, people, *, bundled=False, canonical=None):
        if not people or any(not self.allows_source(person, canonical) for person in people):
            return None
        paths = {self.paths[person] for person in people}
        if self.adhoc_node and paths == {tuple(self.adhoc_node['path'])}:
            return dict(origins=['ad hoc'])
        adhoc_path = tuple(self.adhoc_node['path']) if self.adhoc_node else None
        labels = {'ad hoc' if path == adhoc_path else self.labels.get(path[:self.child_depth])
                  for path in paths}
        if self.include_children and None not in labels:
            return dict(origins=sorted(labels, key=str.casefold))
        return dict(origins=[])
