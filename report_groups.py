"""Additional report cohorts without changing OE totals or source assignments."""
from core import aggregate, oe_leaders


def leadership_team(sources, children, wave, parent_path=()):
    records,questions,mappings,aliases,_,exclusions=sources
    people=set()
    for child in children:
        people.update(oe_leaders(records,mappings,aliases,path=child['path']))
    people={person for person in people if person[0]==wave}
    selected=[r for r in records if (r['wave'],r['feedback']) in people]
    # Members head the child OEs, not this synthetic comparison group.
    rows,participation=aggregate(selected,questions,mappings,aliases,exclusions=exclusions)
    node=dict(id='leadership-team',unit='Führungsteam',dimension='__leadership_team__',
              path=[*parent_path,('__leadership_team__','Führungsteam')],group_kind='leadership_team')
    return node,rows,people,participation.get(wave,0)
