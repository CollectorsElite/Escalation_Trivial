"""Shared teacher sets and editable questions, stored on the game's SQLite volume."""
from contextlib import contextmanager
import json
import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from catalogue import decode_question, normalized, question_values, validate_question


@contextmanager
def transaction(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.execute('COMMIT')
    except Exception:
        db.execute('ROLLBACK')
        raise


async def read_object(request):
    try:
        body = await request.json()
    except (ValueError, UnicodeError):
        raise HTTPException(400, detail='La richiesta non contiene dati validi.')
    if not isinstance(body, dict):
        raise HTTPException(400, detail='Formato della richiesta non valido.')
    return body


def checked_ids(db, ids):
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids):
        raise HTTPException(400, detail='Seleziona almeno una domanda dal catalogo.')
    distinct = set(ids)
    if len(distinct) != len(ids):
        raise HTTPException(400, detail='La stessa domanda non può comparire due volte.')
    if not distinct.issubset(r[0] for r in db.execute('SELECT id FROM questions')):
        raise HTTPException(400, detail='Una o più domande non sono presenti nel catalogo.')
    return ids


def quiz_options(body, ids, previous):
    title, bets = body.get('title', previous['title']), body.get('bets', previous['bets'])
    bonuses = body.get('multipliers', previous['multipliers'])
    if not isinstance(title, str) or len(title) > 90 or type(bets) is not bool or not isinstance(bonuses, dict):
        raise HTTPException(400, detail='Impostazioni del quiz non valide.')
    if any(type(n) is not int or n not in (1, 2, 3) for n in bonuses.values()):
        raise HTTPException(400, detail='Moltiplicatore non valido.')
    selected = set(ids)
    return dict(title=title.strip(), bets=bets, multipliers={k:v for k,v in bonuses.items() if k in selected and v>1})


def set_deck(db, body):
    ids = checked_ids(db, body.get('ids'))
    options = quiz_options(body, ids, dict(title='', bets=True, multipliers={}))
    duration = body.get('duration', 30)
    shuffle, reveal = body.get('shuffle', False), body.get('revealOnComplete', True)
    if type(duration) is not int or not 10 <= duration <= 120 or type(shuffle) is not bool or type(reveal) is not bool:
        raise HTTPException(400, detail='Controlla la durata e le impostazioni dei round.')
    return dict(**options, ids=ids, duration=duration, shuffle=shuffle, revealOnComplete=reveal)


def short_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise HTTPException(400, detail=f'{label}: inserisci da 1 a {limit} caratteri.')
    return value.strip()


def new_id(body, prefix):
    key = body.get('creationKey')
    if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
        raise HTTPException(400, detail='Identificativo di creazione non valido.')
    return prefix + key


def check_revision(stored, body, code):
    if type(body.get('expectedRevision')) is not int or body['expectedRevision'] != stored['revision']:
        raise HTTPException(409, detail={'code':code, 'message':'Un altro docente ha modificato questa voce. La tua bozza è ancora disponibile.'})


def install_authoring(db):
    if 'revision' not in {r['name'] for r in db.execute('PRAGMA table_info(questions)')}:
        db.execute('ALTER TABLE questions ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
    db.execute("""CREATE TABLE IF NOT EXISTS quiz_sets (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, deck TEXT NOT NULL, revision INTEGER NOT NULL,
        archived INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL)""")
    # Previously saved lobby headings used broad areas. Rebuild names from each game's frozen questions.
    for game in db.execute('SELECT g.id,g.selected_json,s.config FROM games g LEFT JOIN quiz_settings s ON s.game_id=g.id').fetchall():
        config = json.loads(game['config']) if game['config'] else dict(title='', bets=False, multipliers={})
        config['areas'] = game_categories(db, game['id'], json.loads(game['selected_json']))
        db.execute('INSERT OR REPLACE INTO quiz_settings(game_id,config) VALUES (?,?)', (game['id'], json.dumps(config)))


def game_categories(db, game_id, ids):
    selected = set(ids)
    return sorted({json.loads(r['payload'])['category'] for r in db.execute(
        'SELECT question_id,payload FROM game_questions WHERE game_id=?', (game_id,)) if r['question_id'] in selected}, key=str.casefold)


def category_for(db, body):
    if body.get('categoryId'):
        category = db.execute('SELECT category_id,category FROM questions WHERE category_id=? LIMIT 1',
                              (short_text(body['categoryId'], 'Categoria', 100),)).fetchone()
        if not category:
            raise HTTPException(400, detail='Categoria sconosciuta.')
        return category['category_id'], category['category']
    name = ' '.join(short_text(body.get('newCategory'), 'Nome della categoria', 80).split())
    for cid, existing in db.execute('SELECT DISTINCT category_id,category FROM questions'):
        if normalized(existing) == normalized(name):
            return cid, existing
    return 'CAT-' + secrets.token_hex(8), name


def editor_question(db, body, qid):
    cid, name = category_for(db, body)
    options = body.get('options')
    if not isinstance(options, list) or len(options) not in (2, 4):
        raise HTTPException(400, detail='Inserisci due o quattro alternative.')
    q = dict(id=qid, category_id=cid, category=name, difficulty=body.get('difficulty'),
             question=short_text(body.get('text'), 'Domanda', 600),
             options=[short_text(v, 'Alternativa', 240) for v in options],
             correct=body.get('correct'), explanation=short_text(body.get('explanation'), 'Spiegazione', 1200),
             type='AB' if len(options)==2 else 'MULTI')
    try:
        validate_question(q)
    except ValueError as error:
        raise HTTPException(400, detail=str(error))
    # Teachers may adapt an official question's alternatives or explanation while keeping its stem.
    for stored in db.execute('SELECT * FROM questions WHERE id<>?', (qid,)):
        if (normalized(stored['question']) == normalized(q['question']) and
                stored['category_id'] == cid and stored['difficulty'] == q['difficulty'] and
                stored['correct'] == q['correct'] and normalized(stored['explanation']) == normalized(q['explanation']) and
                [normalized(v) for v in json.loads(stored['options_json'])] == [normalized(v) for v in q['options']]):
            raise HTTPException(409, detail='Il catalogo contiene già una domanda identica. Personalizza il contenuto della copia.')
    return q


def teacher_routes(db, require_admin, lock):
    router = APIRouter(prefix='/api/admin')

    def fetch_question(qid):
        q = db.execute('SELECT * FROM questions WHERE id=?', (qid,)).fetchone()
        if not q:
            raise HTTPException(404, detail='Domanda non trovata.')
        return dict(**decode_question(q), revision=q['revision'])

    def fetch_set(sid):
        item = db.execute('SELECT * FROM quiz_sets WHERE id=?', (sid,)).fetchone()
        if not item:
            raise HTTPException(404, detail='Set non trovato.')
        return item

    def details(item):
        return dict(id=item['id'], name=item['name'], revision=item['revision'], archived=bool(item['archived']),
                    updatedAt=item['updated_at'], deck=json.loads(item['deck']))

    @router.get('/sets')
    async def list_sets(request: Request, archived: bool = False):
        require_admin(request)
        rows = db.execute('SELECT * FROM quiz_sets WHERE archived=? ORDER BY updated_at DESC,id', (int(archived),))
        names = dict(db.execute('SELECT id,category FROM questions').fetchall())
        result = []
        for r in rows:
            item = details(r)
            ids = item.pop('deck')['ids']
            result.append(dict(**item, count=len(ids), categories=sorted({names[k] for k in ids if k in names}, key=str.casefold)))
        return result

    @router.get('/sets/{sid}')
    async def get_set(sid: str, request: Request):
        require_admin(request)
        return details(fetch_set(sid))

    @router.post('/sets')
    async def create_set(request: Request):
        require_admin(request)
        body = await read_object(request)
        sid = new_id(body, 'SET-')
        name = short_text(body.get('name'), 'Nome del set', 90)
        async with lock:
            with transaction(db):
                deck = json.dumps(set_deck(db, body), ensure_ascii=False, sort_keys=True)
                existing = db.execute('SELECT * FROM quiz_sets WHERE id=?', (sid,)).fetchone()
                if existing:
                    if existing['name'] != name or existing['deck'] != deck or existing['archived']:
                        raise HTTPException(409, detail='Salvataggio già utilizzato. Riapri il set salvato.')
                else:
                    db.execute('INSERT INTO quiz_sets(id,name,deck,revision,updated_at) VALUES (?,?,?,1,?)',
                               (sid, name, deck, time.time()))
            return details(fetch_set(sid))

    @router.patch('/sets/{sid}')
    async def update_set(sid: str, request: Request):
        require_admin(request)
        body = await read_object(request)
        async with lock:
            with transaction(db):
                item = fetch_set(sid)
                check_revision(item, body, 'set_changed')
                if 'archived' in body:
                    if type(body['archived']) is not bool:
                        raise HTTPException(400, detail='Stato del set non valido.')
                    db.execute('UPDATE quiz_sets SET archived=?,updated_at=?,revision=revision+1 WHERE id=?',
                               (int(body['archived']), time.time(), sid))
                else:
                    if item['archived']:
                        raise HTTPException(409, detail='Ripristina il set prima di aggiornarlo.')
                    deck = json.dumps(set_deck(db, body), ensure_ascii=False, sort_keys=True)
                    name = short_text(body.get('name'), 'Nome del set', 90)
                    db.execute('UPDATE quiz_sets SET name=?,deck=?,updated_at=?,revision=revision+1 WHERE id=?',
                               (name, deck, time.time(), sid))
            return details(fetch_set(sid))

    @router.get('/catalogue/{qid}')
    async def get_question(qid: str, request: Request):
        require_admin(request)
        return fetch_question(qid)

    @router.post('/catalogue')
    async def create_question(request: Request):
        require_admin(request)
        body = await read_object(request)
        qid = new_id(body, 'DOC-')
        async with lock:
            with transaction(db):
                q = editor_question(db, body, qid)
                existing = db.execute('SELECT * FROM questions WHERE id=?', (qid,)).fetchone()
                if existing:
                    stored = decode_question(existing)
                    expected = dict(id=qid, category_id=q['category_id'], category=q['category'], text=q['question'],
                                    options=q['options'], correct=q['correct'], explanation=q['explanation'],
                                    difficulty=q['difficulty'], type=q['type'])
                    if not existing['revision'] or stored != expected:
                        raise HTTPException(409, detail='Questa domanda è già stata salvata e modificata.')
                else:
                    db.execute('''INSERT INTO questions(id,category_id,category,question,options_json,correct,explanation,
                        difficulty,type,revision) VALUES (?,?,?,?,?,?,?,?,?,1)''', question_values(q))
            return fetch_question(qid)

    @router.put('/catalogue/{qid}')
    async def update_question(qid: str, request: Request):
        require_admin(request)
        body = await read_object(request)
        async with lock:
            with transaction(db):
                current = fetch_question(qid)
                if not current['revision']:
                    raise HTTPException(400, detail='Per personalizzare una domanda di base, creane una copia.')
                check_revision(current, body, 'question_changed')
                q = editor_question(db, body, qid)
                db.execute('''UPDATE questions SET category_id=?,category=?,question=?,options_json=?,correct=?,
                    explanation=?,difficulty=?,type=?,revision=revision+1 WHERE id=?''', (*question_values(q)[1:], qid))
            return fetch_question(qid)

    return router
