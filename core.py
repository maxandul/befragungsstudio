"""Import und Berechnung ohne Web-Abhängigkeiten."""
from __future__ import annotations
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime

import pandas as pd


def read_table(data: bytes, filename: str, sheet=0) -> pd.DataFrame:
    if filename.lower().endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, dtype=str, keep_default_na=False)
    elif filename.lower().endswith('.csv'):
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('cp1252')
        df = pd.read_csv(io.StringIO(text), sep=None, engine='python', dtype=str,
                         keep_default_na=False)
    else:
        raise ValueError('Bitte eine CSV- oder XLSX-Datei auswählen.')
    df.columns = [str(c).lstrip('\ufeff').strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError('Die Datei enthält nach Bereinigung doppelte Spaltennamen.')
    return df.fillna('')


def date_value(value: str) -> str:
    if not value:
        return ''
    try:
        return pd.to_datetime(value, format='mixed', dayfirst=True).isoformat()
    except (ValueError, TypeError):
        raise ValueError(f'Ungültiges Datum: {value}')


def parse_rules(text: str) -> list:
    """Zeilen: Wellenname | Beginn | Ende. Grenzen inklusive, Datum ohne Uhrzeit."""
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [v.strip() for v in line.split('|')]
        if len(parts) != 3:
            raise ValueError('Zeiträume bitte als Welle | Beginn | Ende angeben.')
        name, start, end = parts
        a, b = date_value(start)[:10], date_value(end)[:10]
        if not name or not a or not b or a > b:
            raise ValueError('Wellenname und gültiger Zeitraum sind erforderlich.')
        if any(a <= old[2] and b >= old[1] for old in result):
            raise ValueError('Erhebungszeiträume dürfen sich nicht überschneiden.')
        result.append((name, a, b))
    return result


def normalize(df, cfg, file_hash):
    """Ein Fragebogen pro Welle; Quellwerte bleiben in raw erhalten."""
    out = []
    wave_mode = cfg.get('wave_mode') or 'legacy'
    rules = parse_rules(cfg.get('periods', '')) if wave_mode in ('periods', 'legacy') else []
    if wave_mode not in ('legacy','month','periods','field','fixed'):
        raise ValueError('Bitte eine gültige Methode zur Erhebungszuordnung auswählen.')
    seen = set()
    for row_index, row in enumerate(df.to_dict('records')):
        def val(key):
            return str(row.get(cfg.get(key, ''), '')).strip()
        date = date_value(val('date'))
        if wave_mode == 'month':
            wave = date[:7] if date else ''
        elif wave_mode == 'field':
            wave = val('wave')
        elif wave_mode == 'fixed':
            wave = cfg.get('fixed_wave', '').strip()
        elif wave_mode == 'periods':
            wave = ''
        else:
            wave = cfg.get('fixed_wave', '').strip() or val('wave')
        if not wave and date and wave_mode in ('periods','legacy'):
            matches = [n for n, a, b in rules if a <= date[:10] <= b]
            wave = matches[0] if matches else ''
        if not wave:
            raise ValueError(f'Zeile {row_index + 2}: Keine Erhebung zugeordnet. '
                             'Bitte Datum, Zeitraum oder gewählte Quellspalte prüfen.')
        feedback = val('feedback')
        if not feedback:
            if cfg['mode'] == 'long':
                raise ValueError(f'Zeile {row_index + 2}: Teilnahme-ID fehlt.')
            feedback = f'{file_hash}:{row_index}'
        if cfg['mode'] == 'long':
            qid = val('qid')
            if not qid:
                raise ValueError(f'Zeile {row_index + 2}: Fragenkennung fehlt.')
            questions = [(qid, val('title') or qid, val('type') or 'text', val('answer'))]
        else:
            questions = [(c, c, typ, str(row.get(c, '')).strip())
                         for c, typ in cfg['questions'].items() if typ != 'ignore']
        for qid, title, typ, answer in questions:
            key = (wave, feedback, qid)
            if key in seen:
                raise ValueError(f'Mehrere Antworten für denselben Fragebogen und dieselbe Frage: {qid}. '
                                 'Mehrfachauswahl mit mehreren Zeilen benötigt eine eigene Importregel.')
            seen.add(key)
            out.append(dict(wave=wave, feedback=feedback, source=qid, title=title,
                            type=typ, answer=answer, date=date, raw=row))
    if not out:
        raise ValueError('Keine auszuwertenden Fragen ausgewählt.')
    return out


def mapped_dimensions(record, mappings, aliases):
    dims = {}
    for mapping in mappings:
        if mapping['wave'] not in ('*', record['wave']):
            continue
        # Wellenbezogene Regeln werden nach allgemeinen Regeln angewendet.
        value = str(record['raw'].get(mapping['source'], '')).strip()
        if value:
            dims[mapping['dimension']] = value
    # Namensregeln beziehen sich auf den ursprünglichen Merkmalswert, nicht auf
    # das Ergebnis einer vorherigen Umbenennung. So kann eine Wellenregel eine
    # allgemeine Namensregel zuverlässig überschreiben.
    original_dims=dict(dims)
    for a in aliases:
        if a['wave'] in ('*', record['wave']) and original_dims.get(a['dimension']) == a['source']:
            dims[a['dimension']] = a['target']
    return dims


def segment_preview(records, mappings=(), aliases=(), wave='*', source='', dimension='',
                    original='', target=''):
    """Teilnahmen statt Antwortzeilen zählen; widersprüchliche Werte sichtbar machen."""
    records=[r for r in records if wave=='*' or r['wave']==wave]
    proposed=[dict(a) for a in aliases]
    if dimension and original and target:
        existing=next((a for a in proposed if a['wave']==wave and a['dimension']==dimension and a['source']==original),None)
        if existing is not None:
            existing['target']=target
        else:
            proposed.append(dict(wave=wave,dimension=dimension,source=original,target=target))
        proposed.sort(key=lambda a:a['wave']!='*')
    people={(r['wave'],r['feedback']) for r in records}
    column_people=defaultdict(set)
    column_values=defaultdict(set)
    source_values=defaultdict(set)
    source_people=defaultdict(set)
    pairs=defaultdict(set)
    dim_people=defaultdict(set)
    for r in records:
        person=(r['wave'],r['feedback'])
        for col,value in r['raw'].items():
            value=str(value).strip()
            if value:
                column_people[col].add(person)
                column_values[col].add(value)
        value=str(r['raw'].get(source,'')).strip()
        if value:
            source_values[value].add(person)
            source_people[person].add(value)
        if dimension:
            raw=mapped_dimensions(r,mappings,[]).get(dimension,'')
            current=mapped_dimensions(r,mappings,aliases).get(dimension,'')
            if raw:
                after=mapped_dimensions(r,mappings,proposed).get(dimension,'')
                pairs[(raw,current,after)].add(person)
                dim_people[person].add(raw)
    columns=[]
    for col in sorted(column_people):
        examples=sorted(column_values[col])
        columns.append(dict(name=col,filled=len(column_people[col]),distinct=len(examples),
                            examples=[v[:100] for v in examples[:5]]))
    values=[dict(value=v,n=len(ids)) for v,ids in sorted(source_values.items())]
    effective=[dict(source=a,current=b,after=c,n=len(ids)) for (a,b,c),ids in sorted(pairs.items())]
    target_people=defaultdict(set)
    for (_,_,after),ids in pairs.items():
        target_people[after].update(ids)
    return dict(total=len(people),columns=columns,values=values,
                filled=len(source_people),empty=len(people)-len(source_people),
                conflicts=sum(len(v)>1 for v in source_people.values()),
                mapped=len(dim_people),unmapped=len(people)-len(dim_people),
                mapping_conflicts=sum(len(v)>1 for v in dim_people.values()),effective=effective,
                resulting=[dict(value=v,n=len(ids)) for v,ids in sorted(target_people.items())])


def number(value):
    try:
        n = float(str(value).replace(',', '.'))
        return n if pd.notna(n) and abs(n) != float('inf') else None
    except (ValueError, TypeError):
        return None


def aggregate(records, questions, mappings=(), aliases=(), dimension='', unit=''):
    by_question = defaultdict(dict)
    participation = defaultdict(set)
    dim_cache = {}
    for r in records:
        cache_key = (r['wave'], r['feedback'])
        dims = mapped_dimensions(r, mappings, aliases)
        # Inkonsistente Merkmale innerhalb eines Fragebogens müssen vor Bericht behoben werden.
        if cache_key in dim_cache and dim_cache[cache_key] != dims:
            raise ValueError('Widersprüchliche Segmentmerkmale innerhalb eines Fragebogens.')
        dim_cache[cache_key] = dims
        if dimension and dims.get(dimension) != unit:
            continue
        participation[r['wave']].add(r['feedback'])
        q = questions[r['source']]
        if not q.get('include', 1):
            continue
        key = (r['wave'], q['canonical'])
        if r['feedback'] in by_question[key]:
            raise ValueError('Zwei Quellfragen sind innerhalb einer Welle derselben gemeinsamen Frage '
                             'zugeordnet. Bitte Fragenzuordnung prüfen.')
        by_question[key][r['feedback']] = (r, q)
    rows = []
    for (wave, canonical), answers in by_question.items():
        r, q = next(iter(answers.values()))
        values, counts, missing, invalid, texts = [], defaultdict(int), 0, 0, []
        valid_people = 0
        for r, source_q in answers.values():
            value = r['answer'].strip()
            if not value or value in source_q['missing'].splitlines():
                missing += 1
                continue
            if q['type'] == 'scale':
                n = number(value)
                if n is None or not q['minimum'] <= n <= q['maximum']:
                    invalid += 1
                    continue
                values.append(n)
                counts[str(n).removesuffix('.0')] += 1
            elif q['type'] == 'choice_multiple':
                # Exakte Optionen mit längsten Treffern; unaufgelöste Inhalte werden nicht geraten.
                options = [o.strip() for o in q['options'].splitlines() if o.strip()]
                if not options:
                    invalid += 1
                    continue
                remaining = value
                selected = []
                for option in sorted(options, key=len, reverse=True):
                    pattern = r'(^|,\s*)' + re.escape(option) + r'(?=\s*,|$)'
                    if re.search(pattern, remaining):
                        selected.append(option)
                        remaining = re.sub(pattern, '', remaining, count=1).strip(' ,')
                if remaining or not selected:
                    invalid += 1
                    continue
                for option in selected:
                    counts[option] += 1
            elif q['type'] == 'text':
                texts.append(value)
            else:
                counts[value] += 1
            valid_people += 1
        rows.append(dict(wave=wave, canonical=canonical, label=q['label'], type=q['type'],
                         theme=q['theme'], n=valid_people, missing=missing, invalid=invalid,
                         mean=sum(values)/len(values) if values else None,
                         top2=100*sum(n >= q['top_from'] for n in values)/len(values) if values else None,
                         counts=dict(counts), texts=texts, minimum=q['minimum'], maximum=q['maximum']))
    return sorted(rows, key=lambda x: (x['theme'], x['label'], x['wave'])), {
        wave: len(ids) for wave, ids in participation.items()}


def content_hash(data):
    return hashlib.sha256(data).hexdigest()
