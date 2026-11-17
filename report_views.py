"""Presentation only: profiles never change the underlying source filters or calculations."""
KINDS={'key':'Kernaussage','difference':'Abweichende Sichtweise','single':'Besonderer Hinweis','normal':''}


def prepare_text_views(summaries,profile):
    output={}
    for canonical,topics in summaries.items():
        result=[]
        for topic in topics:
            entries=topic.get('statements')
            if entries is None:
                entries=[dict(text=topic['aussage'],kind='normal',order=100,details=[])] if topic.get('aussage') else []
            entries=[dict(e,kind=e.get('kind','normal'),kind_label=KINDS.get(e.get('kind','normal'),''),
                          details=e.get('details',[])) for e in entries]
            main=entries if profile=='oe' else [e for e in entries if e['kind']!='normal']
            remaining=[] if profile=='oe' else [e for e in entries if e['kind']=='normal']
            if entries:result.append(dict(title=topic['titel'],all=entries,main=main,remaining=remaining,
                                         collapse=profile=='oe' and len(entries)>8))
        output[canonical]=result
    return output
