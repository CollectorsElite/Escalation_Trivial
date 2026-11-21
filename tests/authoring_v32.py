"""Authoring, optimistic concurrency, class isolation and restart on the same SQLite volume."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QUESTION_KEY = '2' * 32
SET_KEY = '3' * 32
QID = 'DOC-' + QUESTION_KEY
SID = 'SET-' + SET_KEY
SETS, CATALOG = '/api/admin/sets', '/api/admin/catalogue'
BASE_PATH = CATALOG + '/AUT-001'
BASE_EDIT = dict(text='Come scegli la password per un nuovo servizio?',
                 options=['Riutilizzo la password della posta', 'Uso una password lunga, casuale e unica'],
                 correct=1, explanation='Una password unica protegge gli altri account se questa credenziale viene esposta.',
                 difficulty='Base', categoryId='AUT')


def data(response):
    response.raise_for_status()
    return response.json()


def logged_in(client):
    data(client.post('/api/admin/login', json={'password':os.environ['ADMIN_PASSWORD']}))


def write_phase(client):
    assert client.get(SETS).status_code == 401
    assert client.post(CATALOG, json={}).status_code == 401
    assert client.put(BASE_PATH, json=BASE_EDIT | {'expectedRevision':0}).status_code == 401
    logged_in(client)
    official = data(client.get(CATALOG + '/AUT-001'))
    original = dict(text='Quale controllo misura il risultato di una modifica?', options=['Un confronto', 'Un promemoria'],
                    correct=0, difficulty='Avanzato', explanation='Si confronta lo stesso indicatore prima e dopo.',
                    newCategory='Qualità', creationKey=QUESTION_KEY)
    for invalid in [{'options':['A',' a ']}, {'correct':True}, {'correct':2}, {'options':['A','B','C']},
                    {'text':' '}, {'explanation':''}, {'newCategory':' '}]:
        assert client.post(CATALOG, json=original | invalid).status_code == 400
    question = data(client.post(CATALOG, json=original))
    assert question['revision'] == 1 and question['id'] == QID
    assert data(client.post(CATALOG, json=original)) == question
    assert client.post(CATALOG, json=original | {'creationKey':'4'*32}).status_code == 409
    assert client.put(BASE_PATH, json=original | {'expectedRevision':0}).status_code == 409
    fork = dict(text=official['text'], categoryId=official['category_id'], difficulty=official['difficulty'],
                options=official['options'], correct=official['correct'], explanation='Spiegazione personalizzata per il corso.',
                creationKey='5'*32)
    saved_fork = data(client.post(CATALOG, json=fork))
    assert saved_fork['id'] != official['id']
    assert data(client.get(CATALOG+'/AUT-001')) == official
    spec = dict(name='Aula formatori', creationKey=SET_KEY, title='Classe A', ids=[QID,'AUT-001'], duration=45,
                shuffle=False, revealOnComplete=False, bets=True, multipliers={QID:3})
    for invalid in [{'ids':['assente']}, {'ids':[QID,QID]}, {'ids':[]}, {'multipliers':{QID:4}}, {'shuffle':1}, {'name':'  '}]:
        assert client.post(SETS, json=spec | invalid).status_code == 400
    saved = data(client.post(SETS, json=spec))
    assert data(client.post(SETS, json=spec)) == saved
    deck = saved['deck']
    assert deck == {k:v for k,v in spec.items() if k not in ('name','creationKey')}
    summary = data(client.get(SETS))[0]
    assert summary['count']==2 and set(summary['categories']) == {'Qualità', official['category']}
    duplicate = data(client.post(SETS, json=spec | {'name':'Seconda classe', 'creationKey':'6'*32}))
    assert duplicate['deck']==deck and duplicate['id']!=SID
    path=SETS+'/'+duplicate['id']
    def compete(replacement):
        return client.patch(path, json=spec | {'name':replacement, 'expectedRevision':1})
    with ThreadPoolExecutor(2) as pool:
        changes=list(pool.map(compete,['Revisione A','Revisione B']))
    assert sorted(r.status_code for r in changes)==[200,409]
    assert next(r.json()['detail']['code'] for r in changes if r.status_code==409)=='set_changed'
    data(client.patch(path, json={'expectedRevision':2,'archived':True}))
    assert [s['id'] for s in data(client.get(SETS))]==[SID]
    assert data(client.get(SETS+'?archived=true'))[0]['id']==duplicate['id']
    data(client.patch(path, json={'expectedRevision':3,'archived':False}))
    assert data(client.get(SETS+'/'+SID))['deck']==deck
    # A saved set keeps referring to the original question when its text and format change.
    unchanged = dict(official, categoryId=official['category_id'], expectedRevision=0)
    assert data(client.put(BASE_PATH, json=unchanged)) == official
    invalid = BASE_EDIT | {'expectedRevision':0, 'correct':2}
    assert client.put(BASE_PATH, json=invalid).status_code == 400
    assert data(client.get(BASE_PATH)) == official
    changed = data(client.put(BASE_PATH, json=BASE_EDIT | {'expectedRevision':0}))
    assert changed['id'] == official['id'] and changed['revision'] == 1 and changed['type'] == 'AB'
    assert changed['text'] == BASE_EDIT['text'] and changed['options'] == BASE_EDIT['options']
    assert changed['correct'] == BASE_EDIT['correct'] and changed['explanation'] == BASE_EDIT['explanation']
    assert data(client.put(BASE_PATH, json=BASE_EDIT | {'expectedRevision':1})) == changed
    stale = client.put(BASE_PATH, json=unchanged)
    assert stale.status_code == 409 and stale.json()['detail']['code'] == 'question_changed'
    assert data(client.get(SETS+'/'+SID))['deck'] == deck
    assert data(client.get(CATALOG+'/'+saved_fork['id'])) == saved_fork
    # An ad-hoc change belongs only to the opened game.
    lobby=data(client.post('/api/admin/create',json=deck | {'title':'Classe A di prova'}))['game']
    assert set(lobby['areas'])==set(summary['categories'])
    player=data(client.post('/api/join',json={'pin':lobby['pin'],'nickname':'Primo gruppo'}))
    updated=original | {'text':'Testo rivisto per la classe successiva','correct':1,'expectedRevision':1,
                        'categoryId':question['category_id']}
    assert data(client.put(CATALOG+'/'+QID,json=updated))['revision']==2
    assert client.put(CATALOG+'/'+QID,json=updated).json()['detail']['code']=='question_changed'
    overview=data(client.get('/api/admin/overview'))
    frozen=next(q for q in overview['questions'] if q['id']==QID)
    assert frozen['text']==original['text'] and frozen['frozen']
    def action(name): return data(client.post('/api/admin/action',json={'action':name}))
    action('start')
    assert data(client.get('/api/screen'))['question']['text']==original['text']
    assert 'correct' not in data(client.get('/api/screen'))['question']
    action('reveal')
    assert data(client.get('/api/screen'))['question']['correct']==0
    action('finish')
    review=data(client.post('/api/player/review',json={**player,'pin':lobby['pin']}))
    assert review['rounds'][0]['text']==original['text'] and review['rounds'][0]['correct']==0
    assert 'Qualità' in data(client.get('/api/admin/overview'))['snapshot']['lesson']['areas']
    assert data(client.get(SETS+'/'+SID))['deck']==deck


def restart_phase(client):
    logged_in(client)
    catalog=data(client.get('/api/admin/overview'))
    first_game=catalog['game']
    assert first_game['status']=='finished' and first_game['players']==1
    q = data(client.get(CATALOG+'/'+QID))
    assert q['text']=='Testo rivisto per la classe successiva' and q['revision']==2 and q['correct']==1
    edited_base = data(client.get(BASE_PATH))
    assert edited_base['revision'] == 1 and edited_base['id'] == 'AUT-001'
    assert edited_base['options'] == BASE_EDIT['options'] and edited_base['correct'] == BASE_EDIT['correct']
    assert edited_base['text'] == BASE_EDIT['text'] and edited_base['explanation'] == BASE_EDIT['explanation']
    saved=data(client.get(SETS+'/'+SID))
    assert saved['revision']==1 and saved['deck']['multipliers']=={QID:3}
    lobby=data(client.post('/api/admin/create',json=saved['deck']))['game']
    assert lobby['pin']!=first_game['pin'] and lobby['players']==0 and lobby['duration']==45
    assert data(client.get('/api/admin/overview'))['selected']==[QID,'AUT-001']
    data(client.post('/api/join',json={'pin':lobby['pin'],'nickname':'Secondo gruppo'}))
    data(client.post('/api/admin/action',json={'action':'start'}))
    current=data(client.get('/api/screen'))['question']
    assert current['text']==q['text'] and current['multiplier']==3
    data(client.post('/api/admin/action',json={'action':'reveal'}))
    data(client.post('/api/admin/action',json={'action':'next'}))
    shown = data(client.get('/api/screen'))['question']
    assert shown['text'] == BASE_EDIT['text'] and shown['options'] == BASE_EDIT['options']
    data(client.post('/api/admin/action',json={'action':'reveal'}))
    revealed = data(client.get('/api/screen'))['question']
    assert revealed['correct'] == BASE_EDIT['correct'] and revealed['explanation'] == BASE_EDIT['explanation']
    data(client.post('/api/admin/action',json={'action':'cancel'}))
    # Catalogue capacity is independent of the original 210-question bank.
    ids = [item['id'] for item in catalog['questions']]
    assert len(ids)==212
    assert data(client.post('/api/admin/create',json={'ids':ids}))['game']['total']==212
    assert data(client.patch('/api/admin/questions',json={'ids':ids[::-1],'duration':30}))['ok']
    assert data(client.get('/api/admin/overview'))['selected']==ids[::-1]


if __name__ == '__main__':
    if len(sys.argv)==1:
        with tempfile.TemporaryDirectory(prefix='escalation-authoring-') as volume:
            env=dict(os.environ,DATA_DIR=volume,ADMIN_PASSWORD=secrets.token_hex(16),SESSION_SECRET=secrets.token_hex(32))
            for phase in ('write','restart'):
                subprocess.run([sys.executable,__file__,phase],env=env,check=True)
        print('OK: modifica diretta dei quesiti di base, copia, set, riavvio e proiezione della versione corretta')
    else:
        from app import app
        with TestClient(app) as client:
            (write_phase if sys.argv[1]=='write' else restart_phase)(client)
