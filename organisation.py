"""Organisationspfade aus der gemeinsamen Lookup-Liste, ohne Antwortdaten umzuschreiben."""
import hashlib
import json

# Fachliche Reihenfolge: RAV-Gruppen stehen oberhalb ihrer Abteilungen/RAV.
LEVELS = [('Amt','Amt'), ('Bereich','Bereich'), ('RAV Gruppe','RAV_Gruppe'),
          ('Abteilung','Abteilung'), ('RAV','RAV'), ('Team','Team')]


def tree(entries, observed=()):
    nodes = {}
    for entry in list(entries) + list(observed):
        path = []
        for dimension, column in LEVELS:
            value = str(entry.get(column, entry.get(dimension, ''))).strip()
            if not value:
                continue
            path.append((dimension, value))
            token = hashlib.sha256(json.dumps(path, ensure_ascii=False).encode()).hexdigest()[:24]
            parent_path = path[:-1]
            parent = hashlib.sha256(json.dumps(parent_path, ensure_ascii=False).encode()).hexdigest()[:24] if parent_path else ''
            nodes.setdefault(token, dict(id=token, parent=parent, dimension=dimension, unit=value,
                                        path=list(path), label=' / '.join(v for _,v in path), depth=len(path)-1))
    return sorted(nodes.values(), key=lambda n: n['path'])


def matches(dims, path):
    return all(dims.get(dimension) == value for dimension, value in path)
