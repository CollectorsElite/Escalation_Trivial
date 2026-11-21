"""Validation and representation shared by the bundled catalogue and the editor."""
import json
import unicodedata
from pathlib import Path

LEVELS = ('Base', 'Intermedio', 'Avanzato')


def normalized(value):
    return unicodedata.normalize('NFC',' '.join(value.casefold().split()))


def validate_question(q):
    fields = ('id', 'category_id', 'category', 'question', 'explanation')
    if not isinstance(q, dict) or any(not isinstance(q.get(k), str) or not q[k].strip() for k in fields):
        raise ValueError('Completa il testo della domanda, la categoria e la spiegazione.')
    if q.get('difficulty') not in LEVELS:
        raise ValueError('Scegli un livello di difficoltà valido.')
    options = q.get('options')
    size = 2 if q.get('type') == 'AB' else 4 if q.get('type') == 'MULTI' else 0
    if not size or not isinstance(options, list) or len(options) != size:
        raise ValueError('Una domanda richiede due o quattro alternative.')
    if any(not isinstance(o, str) or not o.strip() for o in options):
        raise ValueError('Inserisci il testo di tutte le alternative.')
    if len({normalized(o) for o in options}) != size:
        raise ValueError('Le alternative devono essere distinte.')
    if type(q.get('correct')) is not int or not 0 <= q['correct'] < size:
        raise ValueError('Indica una risposta corretta.')


def load_catalogue(path: Path):
    questions = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(questions, list) or not questions:
        raise ValueError('Il catalogo deve contenere almeno una domanda.')
    ids, texts, categories = set(), set(), {}
    for q in questions:
        validate_question(q)
        text = normalized(q['question'])
        if q['id'] in ids or text in texts:
            raise ValueError(f"Domanda duplicata: {q['id']}")
        if categories.setdefault(q['category_id'], q['category']) != q['category']:
            raise ValueError(f"Nome di categoria incoerente: {q['category_id']}")
        ids.add(q['id'])
        texts.add(text)
    return questions


def question_values(q):
    return (q['id'], q['category_id'], q['category'], q['question'], json.dumps(q['options'], ensure_ascii=False),
            q['correct'], q['explanation'], q['difficulty'], q['type'])


def decode_question(q):
    return dict(id=q['id'], category_id=q['category_id'], category=q['category'],
                text=q['question'], options=json.loads(q['options_json']), correct=q['correct'],
                explanation=q['explanation'], difficulty=q['difficulty'], type=q['type'])
