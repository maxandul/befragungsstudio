"""Presentation only: source filters and numerical calculations remain unchanged."""
import re

KINDS={'key':'Kernaussage','difference':'Nuance','single':'Besonderer Hinweis','normal':'Kernaussage'}
GL_MAX_HIGHLIGHTS=3


def normalized(text):
    return ' '.join(re.findall(r'\w+',text.casefold()))


def ranking(entry):
    # Real, OE-filtered number of respondents first; imported priority is only a tie-break.
    return (-entry.get('count',0),0 if entry['kind']=='key' else 1,entry.get('order',100),entry['text'].casefold())


def topic_view(title, entries, disclosure=None):
    entries.sort(key=ranking)
    people=set().union(*(entry.get('people',set()) for entry in entries))
    attribution=disclosure.summarise(people,bundled=True) if disclosure and people else {}
    attribution=attribution or {}
    # A topic total must not reveal a subtotal withheld on a lower level.
    if any(entry.get('pooled') and not entry.get('show_count') for entry in entries):
        attribution.update(pooled=True,show_count=False)
    elif not disclosure:
        attribution['origins']=sorted({origin for entry in entries for origin in entry.get('origins',[])},key=str.casefold)
    return dict(title=title,all=entries,count=len(people) or None,rank_count=len(people),**attribution)


def prepare_text_views(summaries,profile,disclosure=None):
    output={}
    for canonical,topics in summaries.items():
        prepared=[];singles=[]
        for topic in topics:
            entries=topic.get('statements')
            if entries is None:
                entries=[dict(topic,text=topic['aussage'],kind='normal',order=100,details=[])] if topic.get('aussage') else []
            concerns=[];direct=[]
            for entry in entries:
                e=dict(entry,kind=entry.get('kind','normal'),
                       kind_label=KINDS.get(entry.get('kind','normal'),''),details=entry.get('details',[]))
                if 'people' in e:
                    e.setdefault('count',len(e['people']))
                if e.get('count')==1 or ('people' in e and not e.get('reviewed',True)):
                    e['details']=[]
                    direct.append(e)
                else:
                    concerns.append(e)
            # An existing shared subject is enough for a direct theme-to-nuance path.
            direct_people=set().union(*(entry.get('people',set()) for entry in direct))
            if len(direct_people)<2:
                for entry in direct:
                    entry['kind_label']='Einzelaussage'
                singles.extend(direct)
                direct=[]
            for entry in direct:
                entry['kind_label']='Nuance'
            items=concerns+direct
            if items:
                title=topic['titel']
                if len(items)==1 and normalized(title)==normalized(items[0]['text']):
                    title='Weitere Rückmeldungen'
                prepared.append(topic_view(title,items,disclosure))
        prepared.sort(key=lambda topic: (-topic['rank_count'],topic['title'].casefold()))
        if singles:
            prepared.append(topic_view('Einzelaussagen',singles,disclosure))
        selected=set();seen=set()
        if profile=='gl':
            for e in sorted((e for t in prepared for e in t['all']),key=ranking):
                if e.get('count',0)<2:continue
                key=normalized(e['text'])
                if key in seen:continue
                seen.add(key);selected.add(id(e))
                if len(selected)>=GL_MAX_HIGHLIGHTS:break
        output[canonical]=[dict(t,main=t['all'] if profile=='oe' else [e for e in t['all'] if id(e) in selected])
                           for t in prepared]
    return output


def group_original_texts(texts_by_path, visible_children):
    """Group original answers from the selected report scope by direct OE."""
    named = {tuple(child['path']): child['unit'] for child in visible_children}
    remaining = [texts for path, texts in texts_by_path.items() if path not in named]
    # A single remaining origin could be identified by excluding the named OEs.
    if len(remaining) == 1:
        return []
    groups = [dict(label=label, texts=texts_by_path[path])
              for path, label in named.items() if path in texts_by_path]
    if groups and remaining:
        groups.append(dict(label='Ohne OE-Angabe', texts=[text for texts in remaining for text in texts]))
    return groups
