"""Load and validate the quiz bank before it enters SQLite."""
import json
from pathlib import Path


LEVELS = ('Base', 'Intermedio', 'Avanzato')


def load_catalogue(path: Path):
    questions = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(questions, list) or not questions:
        raise ValueError('Il catalogo deve contenere almeno una domanda.')
    ids, texts, categories = set(), set(), {}
    for q in questions:
        if not isinstance(q, dict) or any(not isinstance(q.get(k), str) or not q[k].strip()
                for k in ('id', 'category_id', 'category', 'question', 'explanation')):
            raise ValueError('Mancano i dati identificativi o la spiegazione di una domanda.')
        text = ' '.join(q['question'].casefold().split())
        options = q.get('options')
        size = {'AB': 2, 'MULTI': 4}.get(q.get('type'))
        if (q['id'] in ids or text in texts or q['difficulty'] not in LEVELS or not size
                or not isinstance(options, list) or len(options) != size
                or any(not isinstance(o, str) or not o.strip() for o in options)
                or len({o.strip().casefold() for o in options}) != size
                or type(q.get('correct')) is not int or not 0 <= q['correct'] < size):
            raise ValueError(f"Domanda non valida o duplicata: {q['id']}")
        if categories.setdefault(q['category_id'], q['category']) != q['category']:
            raise ValueError(f"Nome di categoria incoerente: {q['category_id']}")
        ids.add(q['id'])
        texts.add(text)
    return questions
