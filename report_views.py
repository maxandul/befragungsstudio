"""Presentation only: source filters and numerical calculations remain unchanged."""
import re

KINDS={'key':'Kernaussage','difference':'Abweichende Sichtweise','single':'Besonderer Hinweis','normal':''}
GL_MAX_HIGHLIGHTS=3
GL_EXCERPT_CHARS=300


def normalized(text):
    return ' '.join(re.findall(r'\w+',text.casefold()))


def excerpt(text):
    if len(text)<=GL_EXCERPT_CHARS:return text
    cut=text[:GL_EXCERPT_CHARS-1].rsplit(' ',1)[0].rstrip(' ,;:')
    return cut+'…'


def ranking(entry):
    # Real, OE-filtered number of respondents first; imported priority is only a tie-break.
    return (-entry.get('count',0),0 if entry['kind']=='key' else 1,entry.get('order',100),entry['text'].casefold())


def prepare_text_views(summaries,profile):
    output={}
    for canonical,topics in summaries.items():
        prepared=[];flat=[];singles=[]
        for topic in topics:
            entries=topic.get('statements')
            if entries is None:
                entries=[dict(text=topic['aussage'],kind='normal',order=100,details=[],
                              origins=topic.get('origins',[]),people=topic.get('people',set()),
                              pooled=topic.get('pooled',False))] if topic.get('aussage') else []
            bundled=[]
            for entry in entries:
                e=dict(entry,kind=entry.get('kind','normal'),kind_label=KINDS.get(entry.get('kind','normal'),''),
                       details=entry.get('details',[]),display_text=excerpt(entry['text']))
                if 'people' in e:
                    e.setdefault('count',len(e['people']))
                if e.get('count')==1 or ('people' in e and not e.get('reviewed',True)):
                    singles.append(e)
                else:
                    bundled.append(e)
            if bundled:
                bundled.sort(key=ranking)
                people=set().union(*(e.get('people',set()) for e in bundled))
                pooled=any(e.get('pooled') for e in bundled)
                show_title=not pooled and len(topic['titel'])<=80 and (len(bundled)>1 or 'people' not in bundled[0]
                           and normalized(topic['titel'])!=normalized(bundled[0]['text']))
                prepared.append(dict(title=topic['titel'],all=bundled,show_title=show_title,
                                     count=None if pooled else len(people),
                                     rank_count=len(people)))
                flat.extend(bundled)
        prepared.sort(key=lambda topic: (-topic['rank_count'],topic['title'].casefold()))
        if singles:
            singles.sort(key=ranking)
            prepared.append(dict(title='Einzelaussagen',all=singles,show_title=True,singles=True))
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
            remaining=[] if profile=='oe' else [e for e in entries if id(e) not in selected]
            result.append(dict(t,main=main,remaining=remaining,collapse=profile=='oe' and len(entries)>8))
        output[canonical]=result
    return output


def gl_highlights(views):
    return {canonical:sorted([e for topic in topics for e in topic['main']],key=ranking)
            for canonical,topics in views.items()}


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
