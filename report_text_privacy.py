"""Participation-based disclosure rules shared by report text outputs."""
from collections import Counter

from core import mapped_dimensions
from organisation import oe_path


class TextDisclosure:
    def __init__(self, sources, wave, minimum, visible_children, include_children, leadership=None):
        records, _, mappings, aliases, _, _ = sources
        self.minimum = minimum
        self.labels = {tuple(child['path']): child['unit'] for child in visible_children}
        self.include_children = include_children
        self.paths = {}
        self.team_people=leadership['people'] if leadership else set()
        self.team_path=tuple(leadership['node']['path']) if leadership else None
        self.team_questions=leadership['text_questions'] if leadership else set()
        leaders = set()
        for record in records:
            if record['wave'] != wave:
                continue
            person = (wave, record['feedback'])
            if person not in self.paths:
                self.paths[person] = self.team_path if person in self.team_people else oe_path(mapped_dimensions(record, mappings, aliases))
            raw = record['raw']
            if person not in self.team_people and str(raw.get('Kadertyp (subject)', raw.get('Kadertyp', ''))).strip() == '100':
                leaders.add(person)
        self.child_depth = len(next(iter(self.labels), ()))
        self.has_organisations = any(self.paths.values())
        self.participants = Counter()
        self.direct_participants = Counter(path for person, path in self.paths.items() if person not in leaders)
        for person, path in self.paths.items():
            for depth in range(len(path) + 1):
                if person in leaders and (depth == len(path) or (depth == 0 and len(path) == 1)):
                    continue
                self.participants[path[:depth]] += 1

    def allows_source(self, person, canonical):
        return person not in self.team_people or canonical in self.team_questions

    def allows_detail(self, path, canonical=None):
        if path==self.team_path and canonical not in self.team_questions:
            return False
        return (bool(path) or not self.has_organisations) and self.participants[path] >= self.minimum

    def summarise(self, people, *, bundled=False, canonical=None):
        if not people or any(person not in self.paths for person in people):
            return None
        if any(not self.allows_source(person,canonical) for person in people):
            return None
        paths = {self.paths[person] for person in people}
        if all(self.allows_detail(path,canonical) for path in paths):
            labels = {self.labels.get(path[:self.child_depth]) for path in paths}
            if self.include_children and None not in labels:
                return dict(origins=sorted(labels, key=str.casefold))
            return dict(origins=[])
        if not bundled or len(paths) < 2 or () in paths:
            return None
        # Count only the groups that actually supplied sources. Where one source is
        # assigned directly to a parent, count its own peers without its child units.
        population = 0
        for path in paths:
            has_source_below = any(other != path and other[:len(path)] == path for other in paths)
            population += (self.direct_participants if has_source_below else self.participants)[path]
        if population < self.minimum:
            return None
        return dict(pooled=True, origins=[], show_count=self.pooled_count_is_safe(people,canonical))

    def pooled_count_is_safe(self, people, canonical=None):
        """Allow totals only when a residual still spans several protected groups."""
        protected = [self.paths[person] for person in people if not self.allows_detail(self.paths[person],canonical)]
        if len(protected) < self.minimum:
            return False
        source_counts = Counter(protected)
        paths = set(source_counts)
        if len(paths) < 2 or len({path[:-1] for path in paths}) != 1:
            return False
        capacity = {path: self.participants[path] for path in paths}
        if any(source_counts[path] > limit for path, limit in capacity.items()):
            return False
        total_capacity = sum(capacity.values())
        # Even if the contribution from larger OEs is known, the residual must
        # admit multiple source counts for every protected OE.
        return all(max(0, len(protected) - (total_capacity - size)) < min(size, len(protected))
                   for size in capacity.values())
