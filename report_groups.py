"""Additional report cohorts without changing OE totals or source assignments."""
from core import aggregate, mapped_dimensions
from organisation import oe_path


def leadership_team(sources, children, wave, parent_path=(), dimensions=None):
    records,questions,mappings,aliases,_,exclusions=sources
    people=set()
    paths={tuple(child['path']) for child in children}
    for r in records:
        if r['wave']!=wave:
            continue
        raw=r['raw']
        if str(raw.get('Kadertyp (subject)',raw.get('Kadertyp',''))).strip()=='100':
            person=(wave,r['feedback'])
            dims=dimensions[person] if dimensions is not None else mapped_dimensions(r,mappings,aliases)
            if oe_path(dims) in paths:
                people.add(person)
    selected=[r for r in records if (r['wave'],r['feedback']) in people]
    # Members head the child OEs, not this synthetic comparison group.
    rows,participation=aggregate(selected,questions,mappings,aliases,exclusions=exclusions,dimensions=dimensions)
    node=dict(id='leadership-team',unit='Führungsteam',dimension='__leadership_team__',
              path=[*parent_path,('__leadership_team__','Führungsteam')],group_kind='leadership_team')
    return node,rows,people,participation.get(wave,0)
