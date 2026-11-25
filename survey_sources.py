"""Shared read-only survey inputs. Report output and disclosure stay request-local."""
from collections import OrderedDict
from contextlib import closing
import json
from threading import Lock

from core import respondent_dimensions


def install_source_revisions(c):
    """Track committed source changes, including those made by external seed scripts."""
    c.execute('CREATE TABLE IF NOT EXISTS survey_revisions(project INTEGER PRIMARY KEY, revision INTEGER NOT NULL)')
    for table in ('answers','questions','question_settings','question_exclusions','mappings','aliases','grounds'):
        for operation, owner in [('INSERT','NEW'),('DELETE','OLD'),('UPDATE','NEW')]:
            # The table names and operations below are fixed application constants.
            c.execute(f"""CREATE TRIGGER IF NOT EXISTS survey_revision_{table}_{operation}
                AFTER {operation} ON {table} BEGIN
                  INSERT INTO survey_revisions VALUES({owner}.project,1)
                  ON CONFLICT(project) DO UPDATE SET revision=revision+1;
                END""")
        c.execute(f"""CREATE TRIGGER IF NOT EXISTS survey_revision_{table}_move
            AFTER UPDATE OF project ON {table} WHEN OLD.project != NEW.project BEGIN
              INSERT INTO survey_revisions VALUES(OLD.project,1)
              ON CONFLICT(project) DO UPDATE SET revision=revision+1;
            END""")


def load_sources(c, pid, wave, default_missing):
    qs = {r['source']: dict(r) for r in c.execute('SELECT * FROM questions WHERE project=?', (pid,))}
    setting=c.execute('SELECT missing FROM question_settings WHERE project=?',(pid,)).fetchone()
    common_missing=setting[0] if setting else default_missing
    for q in qs.values():
        if not q['missing_override']:
            q['missing']=common_missing
    parents={q['canonical']:q for q in qs.values() if q['type']!='text'}
    for q in qs.values():
        if q['type']=='text' and q['text_parent'] in parents:
            parent=parents[q['text_parent']]
            q['theme']=parent['theme']
            q['sort_order']=parent['sort_order']
    mappings = [dict(r) for r in c.execute("SELECT * FROM mappings WHERE project=? ORDER BY (wave != '*'),id", (pid,))]
    aliases = [dict(r) for r in c.execute("SELECT * FROM aliases WHERE project=? ORDER BY (wave != '*'),id", (pid,))]
    grounds = [dict(r) for r in c.execute('SELECT * FROM grounds WHERE project=?', (pid,))]
    exclusions={(r['source'],r['wave']) for r in c.execute('SELECT source,wave FROM question_exclusions WHERE project=?',(pid,))}
    # Keep only the raw fields consumed by reports and text jobs. Import data stays intact.
    fields={m['source'] for m in mappings} | {'Question','Kadertyp','Kadertyp (subject)','Survey ID'}
    records=[]
    query='SELECT wave,feedback,source,answer,raw FROM answers WHERE project=?'
    args=(pid,)
    if wave is not None:
        query+=' AND wave=?'
        args=(pid,wave)
    for row in c.execute(query,args):
        record=dict(row)
        raw=json.loads(record['raw'])
        record['raw']={field:raw[field] for field in fields if field in raw}
        records.append(record)
    sources=(records,qs,mappings,aliases,grounds,exclusions)
    dimensions=respondent_dimensions(records,mappings,aliases) if wave is None else None
    return sources,dimensions


class SurveySources:
    """Retain up to two project/wave snapshots per app, shared across Waitress threads."""
    def __init__(self, db, default_missing):
        self.db=db
        self.default_missing=default_missing
        self.entries=OrderedDict()
        self.lock=Lock()

    def get(self, pid, wave):
        with self.lock, closing(self.db()) as c, c:
            # Read the revision and inputs in the same SQLite snapshot. A writer
            # that commits later makes this entry ineligible on the next request.
            c.execute('BEGIN')
            row=c.execute('SELECT revision FROM survey_revisions WHERE project=?',(pid,)).fetchone()
            revision=row[0] if row else 0
            # Text collectors filter their target wave even when a complete snapshot exists.
            for scope in (None,wave):
                key=(pid,scope,revision)
                if key in self.entries:
                    self.entries.move_to_end(key)
                    return self.entries[key]
            snapshot=load_sources(c,pid,wave,self.default_missing)
            for key in list(self.entries):
                if key[0]==pid and (key[2]!=revision or wave is None):
                    del self.entries[key]
            self.entries[(pid,wave,revision)]=snapshot
            while len(self.entries)>2:
                self.entries.popitem(last=False)
            return snapshot
