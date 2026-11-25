"""Streaming participation counts for the segment editor."""
from collections import Counter, defaultdict, OrderedDict
from contextlib import closing, contextmanager
from dataclasses import dataclass
from heapq import nsmallest
import json
from threading import Lock

from core import mapped_dimensions, renamed_dimensions


@dataclass
class PreviewBasis:
    counts: dict
    members: dict

    def render(self, columns, aliases, wave, dimension, original, target, clear):
        current = [a for a in aliases if a['dimension'] == dimension]
        proposed = current
        if dimension and original and (target or clear):
            replacement = dict(wave=wave, dimension=dimension, source=original, target='' if clear else target)
            proposed = [a for a in current if (a['wave'], a['source']) != (wave, original)]
            proposed.append(replacement)
            proposed.sort(key=lambda a: a['wave'] != '*')
        effective = Counter()
        resulting = defaultdict(set)
        for (w, raw), people in self.members.items():
            dims = {dimension: raw}
            before = renamed_dimensions(dims, w, current).get(dimension, '')
            after = renamed_dimensions(dims, w, proposed).get(dimension, '') if proposed is not current else before
            effective[raw, before, after] += len(people)
            resulting[after].update(people)
        return dict(self.counts, columns=columns,
                    effective=[dict(source=a, current=b, after=c, n=count)
                               for (a,b,c), count in sorted(effective.items())],
                    resulting=[dict(value=v, n=len(ids)) for v,ids in sorted(resulting.items())])


def prepare_preview(records, mappings, wave, source, dimension, collect_columns=True):
    """Consume even unordered rows once. Count each (wave, feedback) once per value."""
    people = set()
    source_values = defaultdict(set)
    source_people = defaultdict(set)
    dim_people = defaultdict(set)
    members = defaultdict(set)
    column_people = defaultdict(set)
    column_values = defaultdict(set)
    rules = [m for m in mappings if m['dimension'] == dimension] if dimension else []
    for r in records:
        w = r['wave']
        if wave != '*' and w != wave:
            continue
        person = (w, r['feedback'])
        people.add(person)
        raw = r['raw']
        if collect_columns:
            for col, cell in raw.items():
                values = column_values[col]  # Retain names of entirely empty columns.
                value = str(cell).strip()
                if value:
                    values.add(value)
                    column_people[col].add(person)
        value = str(raw.get(source, '')).strip()
        if value:
            source_values[value].add(person)
            source_people[person].add(value)
        if rules:
            value = mapped_dimensions(r, rules, ()).get(dimension)
            if value:
                members[w, value].add(person)
                dim_people[person].add(value)
    counts = dict(total=len(people), filled=len(source_people), empty=len(people)-len(source_people),
                  conflicts=sum(len(v)>1 for v in source_people.values()),
                  values=[dict(value=v,n=len(ids)) for v,ids in sorted(source_values.items())],
                  mapped=len(dim_people), unmapped=len(people)-len(dim_people),
                  mapping_conflicts=sum(len(v)>1 for v in dim_people.values()))
    names = sorted(column_values)
    columns = [dict(name=col, filled=len(column_people[col]), distinct=len(column_values[col]),
                    examples=[v[:100] for v in nsmallest(5,column_values[col])])
               for col in names if column_values[col]]
    return PreviewBasis(counts, members), columns, names


class SegmentPreviews:
    """Keep column summaries and the last selected fields for up to two wave selections."""
    def __init__(self, db):
        self.db = db
        self.lock = Lock()
        self.version = None
        self.names = None
        self.waves = OrderedDict()

    @contextmanager
    def snapshot(self, pid):
        with self.lock, closing(self.db()) as c, c:
            c.execute('BEGIN')
            revision = c.execute('SELECT revision FROM segment_revisions WHERE project=?',(pid,)).fetchone()
            version = (pid, revision[0] if revision else 0)
            if self.version != version:
                self.names = None
                self.waves.clear()
                self.version = version
            yield c

    def column_names(self, pid):
        with self.snapshot(pid) as c:
            if self.names is None:
                names = set()
                for row in c.execute('SELECT raw FROM answers WHERE project=?',(pid,)):
                    names.update(json.loads(row[0]))
                self.names = sorted(names)
            return self.names

    def preview(self, pid, wave, source, dimension, original, target, clear):
        with self.snapshot(pid) as c:
            mappings = c.execute("""SELECT wave,source,dimension FROM mappings
                WHERE project=? AND dimension=? ORDER BY (wave!='*'),id""",(pid,dimension)).fetchall()
            aliases = c.execute("""SELECT wave,source,dimension,target FROM aliases
                WHERE project=? AND dimension=? ORDER BY (wave!='*'),id""",(pid,dimension)).fetchall()
            selection = (source, dimension, tuple((m['wave'],m['source']) for m in mappings))
            old = self.waves.get(wave)
            if old is None or old[0] != selection:
                query = 'SELECT wave,feedback,raw FROM answers WHERE project=?'
                args = (pid,)
                if wave != '*':
                    query += ' AND wave=?'
                    args = (pid,wave)
                records = (dict(wave=r[0], feedback=r[1], raw=json.loads(r[2])) for r in c.execute(query,args))
                basis, columns, names = prepare_preview(records,mappings,wave,source,dimension,collect_columns=old is None)
                if old is not None:
                    columns = old[2]
                elif wave == '*':
                    self.names = names
                self.waves[wave] = (selection,basis,columns)
            self.waves.move_to_end(wave)
            if len(self.waves) > 2:
                self.waves.popitem(last=False)
            _, basis, columns = self.waves[wave]
        return basis.render(columns,aliases,wave,dimension,original,target,clear)
