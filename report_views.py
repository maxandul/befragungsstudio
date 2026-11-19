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
        prepared=[];flat=[]
        for topic in topics:
            entries=topic.get('statements')
            if entries is None:
                entries=[dict(text=topic['aussage'],kind='normal',order=100,details=[],origins=topic.get('origins',[]))] if topic.get('aussage') else []
            entries=[dict(e,kind=e.get('kind','normal'),kind_label=KINDS.get(e.get('kind','normal'),''),
                          details=e.get('details',[]),display_text=excerpt(e['text'])) for e in entries]
            if entries:
                show_title=len(topic['titel'])<=80 and not (len(entries)==1 and normalized(topic['titel'])==normalized(entries[0]['text']))
                prepared.append(dict(title=topic['titel'],all=entries,show_title=show_title))
                flat.extend(entries)
        selected=set();seen=set()
        if profile=='gl':
            for e in sorted(flat,key=ranking):
                # A lone statement is a detail, regardless of its AI-assigned label.
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


def concern_origins(people, source_oes):
    if len(people) < 2 or not source_oes:
        return []
    labels = {source_oes.get(person) for person in people}
    # Omit the attribution if identifying the other sources would single out an unnamed group.
    if None in labels:
        return []
    return sorted(labels, key=str.casefold)
