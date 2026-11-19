"""Presentation only: source filters and numerical calculations remain unchanged."""
import re

KINDS={'key':'','difference':'Abweichende Sichtweise','single':'Besonderer Hinweis','normal':''}
GL_MAX_HIGHLIGHTS=3


def normalized(text):
    return ' '.join(re.findall(r'\w+',text.casefold()))


def ranking(entry):
    # Real, OE-filtered number of respondents first; imported priority is only a tie-break.
    return (-entry.get('count',0),0 if entry['kind']=='key' else 1,entry.get('order',100),entry['text'].casefold())


def prepare_text_views(summaries,profile):
    output={}
    for canonical,topics in summaries.items():
        prepared=[];flat=[];singles=[];pooled_entries=[]
        for topic in topics:
            entries=topic.get('statements')
            if entries is None:
                entries=[dict(text=topic['aussage'],kind='normal',order=100,details=[],
                              origins=topic.get('origins',[]),people=topic.get('people',set()),
                              denominator=topic.get('denominator',0),pooled=topic.get('pooled',False))] if topic.get('aussage') else []
            bundled=[]
            for entry in entries:
                e=dict(entry,kind=entry.get('kind','normal'),kind_label=KINDS.get(entry.get('kind','normal'),''),
                       details=entry.get('details',[]))
                if 'people' in e:
                    e.setdefault('count',len(e['people']))
                if e.get('count')==1 or ('people' in e and not e.get('reviewed',True)):
                    singles.append(e)
                elif e.get('pooled'):
                    pooled_entries.append(e)
                else:
                    bundled.append(e)
            if bundled:
                bundled.sort(key=ranking)
                people=set().union(*(e.get('people',set()) for e in bundled))
                duplicate_title=len(bundled)==1 and normalized(topic['titel'])==normalized(bundled[0]['text'])
                prepared.append(dict(title='Anliegen' if duplicate_title else topic['titel'],all=bundled,
                                     count=len(people) or None,rank_count=len(people),
                                     denominator=bundled[0].get('denominator',0)))
                flat.extend(bundled)
        if pooled_entries:
            pooled_entries.sort(key=ranking)
            people=set().union(*(e['people'] for e in pooled_entries))
            prepared.append(dict(title='Zusammengefasste Anliegen',all=pooled_entries,
                                 pooled=True,rank_count=len(people)))
            flat.extend(pooled_entries)
        prepared.sort(key=lambda topic: (-topic['rank_count'],topic['title'].casefold()))
        if singles:
            singles.sort(key=ranking)
            people=set().union(*(e.get('people',set()) for e in singles))
            prepared.append(dict(title='Einzelaussagen',all=singles,singles=True,
                                 count=len(people) or None,denominator=singles[0].get('denominator',0)))
        selected=set();seen=set()
        if profile=='gl':
            for e in sorted(flat,key=ranking):
                if e.get('count',0)<2:continue
                key=normalized(e['text'])
                if key in seen:continue
                seen.add(key);selected.add(id(e))
                if len(selected)>=GL_MAX_HIGHLIGHTS:break
        result=[]
        for t in prepared:
            entries=t['all']
            main=entries if profile=='oe' else [e for e in entries if id(e) in selected]
            result.append(dict(t,main=main))
        output[canonical]=result
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
