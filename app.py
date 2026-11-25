"""Escalation Trivial — quiz live, una sessione, fino a 400 partecipanti."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from functools import lru_cache

from PIL import Image
from reportlab.graphics.barcode import qrencoder
from catalogue import decode_question, load_catalogue, normalized, question_values
from question_media import IMAGE_ID, install_media
from authoring import checked_ids, game_categories, install_authoring, quiz_options, read_object, teacher_routes
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
DATA_DIR = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'escalation-trivial.sqlite3'
MAX_PLAYERS = 400
ADMIN_SESSION_SECONDS = 12 * 60 * 60
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
SESSION_SECRET = os.getenv('SESSION_SECRET', '')
if not ADMIN_PASSWORD:
    raise RuntimeError('Configura la variabile ADMIN_PASSWORD prima di avviare Escalation Trivial.')
if not SESSION_SECRET:
    print('ATTENZIONE: SESSION_SECRET non impostato; le sessioni docente scadranno ai riavvii.')
    SESSION_SECRET = secrets.token_hex(32)

conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False, timeout=10)
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA busy_timeout=10000')
conn.executescript('''
CREATE TABLE IF NOT EXISTS questions (
 id TEXT PRIMARY KEY, category_id TEXT NOT NULL, category TEXT NOT NULL,
 question TEXT NOT NULL, options_json TEXT NOT NULL, correct INTEGER NOT NULL,
 explanation TEXT NOT NULL, difficulty TEXT NOT NULL, type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS games (
 id TEXT PRIMARY KEY, pin TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
 selected_json TEXT NOT NULL, duration INTEGER NOT NULL,
 current_index INTEGER NOT NULL DEFAULT -1,
 opened_at REAL, deadline_at REAL, created_at REAL NOT NULL, closed_at REAL
);
CREATE TABLE IF NOT EXISTS players (
 id TEXT PRIMARY KEY, game_id TEXT NOT NULL, nickname TEXT NOT NULL,
 nickname_key TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
 score INTEGER NOT NULL DEFAULT 0, joined_at REAL NOT NULL,
 UNIQUE(game_id, nickname_key)
);
CREATE TABLE IF NOT EXISTS answers (
 game_id TEXT NOT NULL, player_id TEXT NOT NULL, question_index INTEGER NOT NULL,
 choice INTEGER NOT NULL, correct INTEGER NOT NULL, points INTEGER NOT NULL,
 answered_at REAL NOT NULL,
 PRIMARY KEY(game_id, player_id, question_index)
);
CREATE TABLE IF NOT EXISTS quiz_settings (
 game_id TEXT PRIMARY KEY, config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS score_details (
 game_id TEXT NOT NULL, player_id TEXT NOT NULL, question_index INTEGER NOT NULL,
 base INTEGER NOT NULL, bonus INTEGER NOT NULL, wager INTEGER NOT NULL, stake_delta INTEGER NOT NULL,
 PRIMARY KEY(game_id,player_id,question_index));
CREATE TABLE IF NOT EXISTS revoked_admin_sessions (
 session_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_players_game ON players(game_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(game_id,question_index);
''')
lock = asyncio.Lock()
host_clients: dict[WebSocket, str] = {}
screen_clients: dict[WebSocket, str] = {}
@dataclass
class PlayerConnections:
    game_id: str
    sockets: set[WebSocket] = field(default_factory=set)


player_clients: dict[str, PlayerConnections] = {}
count_broadcast_task: asyncio.Task | None = None
timer_task: asyncio.Task | None = None
login_failures: dict[str, list[float]] = {}


def row(sql, params=()):
    return conn.execute(sql, params).fetchone()


def active_game():
    return row("SELECT * FROM games WHERE status IN ('lobby','question','results') ORDER BY created_at DESC LIMIT 1")


def latest_game():
    return active_game() or row('SELECT * FROM games ORDER BY created_at DESC LIMIT 1')


def freeze_questions(game_id, ids):
    # A game keeps its wording and answer keys across catalogue updates.
    for qid in ids:
        item = row('SELECT * FROM questions WHERE id=?', (qid,))
        if item:
            conn.execute('INSERT OR IGNORE INTO game_questions VALUES (?,?,?)',
                         (game_id, qid, json.dumps(decode_question(item), ensure_ascii=False)))


def install_catalogue():
    catalogue = load_catalogue(ROOT / 'questions.json')
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS game_questions (
            game_id TEXT NOT NULL, question_id TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(game_id, question_id))''')
        install_media(conn, catalogue, ROOT / 'question-images')
        if conn.execute('PRAGMA user_version').fetchone()[0] < 2:
            for game in conn.execute('SELECT id, selected_json FROM games'):
                freeze_questions(game['id'], json.loads(game['selected_json']))
            conn.execute('PRAGMA user_version=2')
        if conn.execute('PRAGMA user_version').fetchone()[0] < 3:
            columns = {c['name'] for c in conn.execute('PRAGMA table_info(games)')}
            if 'reveal_on_complete' not in columns:
                conn.execute('ALTER TABLE games ADD COLUMN reveal_on_complete INTEGER NOT NULL DEFAULT 0')
            conn.execute('PRAGMA user_version=3')
        if conn.execute('PRAGMA user_version').fetchone()[0] < 4:
            install_authoring(conn)
            conn.execute('PRAGMA user_version=4')
        conn.executemany('''INSERT INTO questions(id,category_id,category,question,options_json,correct,explanation,difficulty,type,image_id,image_alt)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET category_id=excluded.category_id, category=excluded.category,
            question=excluded.question, options_json=excluded.options_json, correct=excluded.correct,
            explanation=excluded.explanation, difficulty=excluded.difficulty, type=excluded.type,
            image_id=excluded.image_id, image_alt=excluded.image_alt WHERE questions.revision=0''',
            [question_values(q) for q in catalogue])
        if conn.execute('PRAGMA user_version').fetchone()[0] < 5:
            conn.execute("""UPDATE questions SET category_id='PCTO',category='PCTO'
                            WHERE category_id LIKE 'CAT-%' AND lower(trim(category))='pcto'""")
            conn.execute('PRAGMA user_version=5')
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


install_catalogue()


def selected_question(game):
    if game is None or game['current_index'] < 0:
        return None
    ids = json.loads(game['selected_json'])
    if game['current_index'] >= len(ids):
        return None
    item = row('SELECT payload FROM game_questions WHERE game_id=? AND question_id=?',
               (game['id'], ids[game['current_index']]))
    return json.loads(item['payload']) if item else None


def admin_session(value: str | None):
    # Accept earlier timestamp-only signatures until the end of their original lifetime.
    match = re.fullmatch(r'([0-9]{1,12})(?:\.[0-9a-f]{32})?\.[0-9a-f]{64}', value or '')
    if not match:
        return None
    issued = int(match[1])
    expires = issued + ADMIN_SESSION_SECONDS
    if not issued <= time.time() < expires:
        return None
    payload, signature = value.rsplit('.', 1)
    expected = hmac.new(SESSION_SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    session_id = hashlib.sha256(value.encode()).hexdigest()
    if row('SELECT 1 FROM revoked_admin_sessions WHERE session_id=?', (session_id,)):
        return None
    return session_id, expires


def request_is_admin(request: Request):
    return admin_session(request.cookies.get('esc_admin')) is not None


def require_admin(request: Request):
    if not request_is_admin(request):
        raise HTTPException(status_code=401,detail='Accesso docente richiesto.')


def websocket_origin_ok(ws: WebSocket):
    """A browser must originate on the same host as this WebSocket endpoint."""
    origin = ws.headers.get('origin')
    if not origin:
        return True  # Non-browser clients need their own valid bearer credential.
    parsed = urlparse(origin)
    return parsed.scheme in ('http', 'https') and parsed.netloc.lower() == ws.headers.get('host','').lower()


def get_player(pid, token):
    if not isinstance(pid,str) or not isinstance(token,str) or len(token)>256:
        return None
    player = row('SELECT * FROM players WHERE id=?', (pid,))
    if not player: return None
    if hmac.compare_digest(player['token_hash'],hashlib.sha256(token.encode()).hexdigest()):
        return player
    return None


def connected_players(game_id):
    return sum(1 for group in player_clients.values() if group.game_id == game_id and group.sockets)


def settings(game):
    saved = row('SELECT config FROM quiz_settings WHERE game_id=?',(game['id'],))
    return json.loads(saved['config']) if saved else {'title':'','areas':[], 'bets':False,'multipliers':{}}


def save_settings(game_id, body, chosen):
    old = settings({'id':game_id})
    config = quiz_options(body, chosen, old)
    config['areas'] = game_categories(conn, game_id, chosen)
    conn.execute('INSERT OR REPLACE INTO quiz_settings VALUES (?,?)',(game_id,json.dumps(config,sort_keys=True)))


def lesson_report(game):
    ids = json.loads(game['selected_json'])[:game['current_index']+1]
    frozen = {r[0]:json.loads(r[1]) for r in conn.execute('SELECT question_id,payload FROM game_questions WHERE game_id=?',(game['id'],))}
    counts = {r[0]:(r[1],r[2]) for r in conn.execute('SELECT question_index,COUNT(*),SUM(correct) FROM answers WHERE game_id=? GROUP BY question_index',(game['id'],))}
    areas, rounds = {}, []
    for index,qid in enumerate(ids):
        q = frozen[qid]
        answered, correct = counts.get(index,(0,0))
        area = areas.setdefault(q['category'],[0,0])
        area[0] += correct
        area[1] += answered
        if answered:
            rounds.append(dict(text=q['text'],solution=q['options'][q['correct']],why=q['explanation'],correct=correct,answered=answered))
    rounds.sort(key=lambda r:r['correct']/r['answered'])
    return dict(areas=areas,hardest=rounds[:3])


def deck_revision(game):
    values = [json.loads(game['selected_json']), game['duration'], bool(game['reveal_on_complete']),settings(game)]
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def public_base_url():
    override = os.getenv('PUBLIC_URL', '').strip().rstrip('/')
    if override:
        return override
    domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip().rstrip('/')
    return f'https://{domain}' if domain else None


def game_info(game, include_pin=True):
    if not game: return None
    total = len(json.loads(game['selected_json']))
    n = row('SELECT COUNT(*) AS n FROM players WHERE game_id=?',(game['id'],))['n']
    config=settings(game)
    return dict(title=config['title'],areas=config['areas'],bets=config['bets'],id=game['id'], pin=game['pin'] if include_pin else None,
                status=game['status'],duration=game['duration'],total=total,
                reveal_on_complete=bool(game['reveal_on_complete']),
                current=game['current_index']+1,players=n,connected=connected_players(game['id']),max_players=MAX_PLAYERS,
                public_url=public_base_url(),deadline=game['deadline_at'],created=game['created_at'],server_now=time.time())


def ranked_players(game, limit=MAX_PLAYERS):
    return conn.execute('''SELECT id,nickname,score,RANK() OVER (ORDER BY score DESC) AS rank,COUNT(*) OVER (PARTITION BY score) AS tied
        FROM players WHERE game_id=? ORDER BY score DESC,joined_at,id LIMIT ?''', (game['id'],limit)).fetchall()


def leaderboard(game, limit=10):
    return [dict(r) for r in ranked_players(game, limit)] if game else []


def final_totals(game, player_id=None):
    """Fetch final counts in a single indexed query for either a reconnect or the whole room."""
    sql = '''SELECT a.player_id, COUNT(*) AS answered, SUM(a.correct) AS correct,
        SUM(COALESCE(d.base,a.points)) AS base,SUM(COALESCE(d.bonus,0)) AS bonus,SUM(COALESCE(d.stake_delta,0)) AS stake
        FROM answers a LEFT JOIN score_details d USING(game_id,player_id,question_index) WHERE game_id=? AND question_index BETWEEN 0 AND ?'''
    params = [game['id'], game['current_index']]
    if player_id is not None:
        sql += ' AND player_id=?'
        params.append(player_id)
    return {r['player_id']: r for r in conn.execute(sql + ' GROUP BY player_id', params)}


def personal_summary(played, totals):
    correct = totals['correct'] if totals else 0
    answered = totals['answered'] if totals else 0
    return {'base':totals['base'] if totals else 0,'bonus':totals['bonus'] if totals else 0,'stake':totals['stake'] if totals else 0,'played': played, 'correct': correct, 'wrong': answered - correct,
            'missed': played - answered}


def question_stats(game):
    if not game or game['current_index']<0: return None
    r=row('SELECT COUNT(*) AS n FROM answers WHERE game_id=? AND question_index=?',
          (game['id'],game['current_index']))
    q=selected_question(game)
    breakdown=[0]*len(q['options']) if q else []
    for ch in conn.execute('''SELECT choice,COUNT(*) AS n FROM answers
        WHERE game_id=? AND question_index=? GROUP BY choice''',
        (game['id'],game['current_index'])):
        if 0 <= ch['choice'] < len(breakdown):breakdown[ch['choice']]=ch['n']
    return {'answered':r['n'],'breakdown':breakdown}


def visible_question(game, question, host=False):
    visible = {k:question[k] for k in ('id','category_id','category','text','options','type','difficulty')}
    if question.get('image'):
        visible.update(image=question['image'], imageAlt=question.get('imageAlt',''))
    visible['multiplier'] = settings(game)['multipliers'].get(question['id'],1)
    visible['number'] = game['current_index'] + 1
    if host or game['status'] in ('results','finished'):
        visible.update(correct=question['correct'], explanation=question['explanation'])
    return visible


def public_snapshot(game, role, player_id=None):
    if not game:
        return {'type':'snapshot','game':None}
    info=game_info(game)
    question=selected_question(game)
    result={'type':'snapshot','game':info}
    if question:
        result['question']=visible_question(game, question, host=role=='host')
        stats=question_stats(game)
        result['answered']=stats['answered']
        if role in ('host','screen') and (game['status'] in ('results','finished') or role=='host'):
            result['breakdown']=stats['breakdown']
    if role in ('host','screen') and game['status'] in ('results', 'finished'):
        result['leaderboard']=leaderboard(game, MAX_PLAYERS if role=='host' else 10)
    if role=='host' and game['status']=='finished':
        result['lesson']=lesson_report(game)
    if role == 'player' and player_id:
        p=row('SELECT * FROM players WHERE id=? AND game_id=?',(player_id,game['id']))
        if not p:return {'type':'error','message':'Partecipante non trovato nella partita.'}
        spent=row('SELECT COUNT(*) FROM score_details WHERE game_id=? AND player_id=? AND wager=1',(game['id'],player_id))[0]
        result['me']={'remainingBets':max(0,2-spent),'nickname':p['nickname'],'score':p['score']}
        if question:
            ans=row('''SELECT a.choice,a.correct,a.points,COALESCE(d.wager,0) AS wager FROM answers a
                  LEFT JOIN score_details d USING(game_id,player_id,question_index)
                  WHERE a.game_id=? AND a.player_id=? AND a.question_index=?''',
                  (game['id'],player_id,game['current_index']))
            result['me']['answered']=bool(ans)
            if ans: result['me'].update(choice=ans['choice'], wager=bool(ans['wager']))
            if ans and game['status'] in ('results','finished'):
                result['me']['answer']={'choice':ans['choice'],'correct':bool(ans['correct']),
                                       'points':ans['points']}
            if game['status'] in ('results','finished'):
                ranking = next((r for r in ranked_players(game) if r['id']==player_id), None)
                if ranking:
                    result['me'].update(rank=ranking['rank'], tied=ranking['tied'])
            if game['status'] == 'finished':
                totals = final_totals(game, player_id).get(player_id)
                result['me']['summary'] = personal_summary(info['current'], totals)
    return result


async def safe_send(ws, data):
    try:
        await ws.send_json(data)
        return True
    except (RuntimeError, WebSocketDisconnect, OSError):
        return False


def batched_player_snapshots(game, wanted_ids):
    """Prepare 400 player updates with O(1) database queries, not 400 ranking scans."""
    if not game or not wanted_ids:
        return {}
    question = selected_question(game)
    info = game_info(game)
    players = ranked_players(game)
    by_id = {r['id']:r for r in players}
    totals = final_totals(game) if game['status'] == 'finished' else {}
    answers = {}
    common = {'type':'snapshot','game':info}
    if question:
        common['question'] = visible_question(game, question)
        stats=question_stats(game)
        common['answered'] = stats['answered']
        answers = {r['player_id']:r for r in conn.execute("""SELECT a.player_id,a.choice,a.correct,a.points,COALESCE(d.wager,0) AS wager
            FROM answers a LEFT JOIN score_details d USING(game_id,player_id,question_index)
            WHERE a.game_id=? AND a.question_index=?""",(game['id'],game['current_index']))}
    spent={r[0]:r[1] for r in conn.execute('SELECT player_id,SUM(wager) FROM score_details WHERE game_id=? GROUP BY player_id',(game['id'],))}
    snapshots={}
    for pid in wanted_ids:
        p=by_id.get(pid)
        if not p:
            continue
        snap=dict(common)
        me={'remainingBets':max(0,2-spent.get(pid,0)),'nickname':p['nickname'],'score':p['score']}
        if question:
            ans=answers.get(pid)
            me['answered']=bool(ans)
            if ans: me.update(choice=ans['choice'], wager=bool(ans['wager']))
            if game['status'] in ('results','finished'):
                if ans:
                    me['answer']={'choice':ans['choice'],'correct':bool(ans['correct']),'points':ans['points']}
                me['rank']=p['rank']
                me['tied']=p['tied']
        if game['status'] == 'finished':
            me['summary'] = personal_summary(info['current'], totals.get(pid))
        snap['me']=me
        snapshots[pid]=snap
    return snapshots


async def broadcast_game():
    game=latest_game()
    tasks=[]
    if host_clients:
        info=public_snapshot(game,'host')
        tasks.extend(safe_send(ws,info) for ws in tuple(host_clients))
    if screen_clients:
        info=public_snapshot(game,'screen')
        tasks.extend(safe_send(ws,info) for ws in tuple(screen_clients))
    obsolete=[]
    if game and player_clients:
        snapshots=batched_player_snapshots(game,tuple(player_clients))
        for pid,group in list(player_clients.items()):
            sockets = tuple(group.sockets)
            if pid in snapshots:
                tasks.extend(safe_send(ws,snapshots[pid]) for ws in sockets)
            else:
                for ws in sockets:
                    tasks.append(safe_send(ws,{'type':'session_invalid','message':'Questa sessione è terminata. Puoi accedere a una nuova partita.'}))
                    obsolete.append(ws)
                del player_clients[pid]
    if tasks:
        await asyncio.gather(*tasks,return_exceptions=True)
    if obsolete:
        await asyncio.gather(*(ws.close(code=1000) for ws in obsolete),return_exceptions=True)


async def broadcast_counts():
    global count_broadcast_task
    await asyncio.sleep(.40)
    count_broadcast_task = None
    async with lock:
        game = active_game()
        if not game or game['status'] not in ('lobby', 'question'):
            return
        players = row('SELECT COUNT(*) AS n FROM players WHERE game_id=?', (game['id'],))['n']
        answered = 0
        if game['status'] == 'question':
            answered = row('SELECT COUNT(*) AS n FROM answers WHERE game_id=? AND question_index=?',
                           (game['id'], game['current_index']))['n']
        complete = game['status'] == 'question' and game['reveal_on_complete'] and players > 0 and answered == players
        if complete:
            finalize_question(game)
            if timer_task and not timer_task.done():
                timer_task.cancel()
    if complete:
        await broadcast_game()
        return
    msg = {'type':'counts', 'gameId':game['id'], 'index':game['current_index'],
           'status':game['status'], 'players':players, 'connected':connected_players(game['id']), 'answered':answered}
    targets = list(host_clients) + list(screen_clients)
    if game['status'] == 'lobby':
        targets.extend(ws for group in player_clients.values() if group.game_id == game['id'] for ws in group.sockets)
    if targets:
        await asyncio.gather(*(safe_send(ws, msg) for ws in targets), return_exceptions=True)


def schedule_counts():
    global count_broadcast_task
    if count_broadcast_task is None or count_broadcast_task.done():
        count_broadcast_task=asyncio.create_task(broadcast_counts())


def finalize_question(game):
    if not game or game['status']!='question':return False
    conn.execute('BEGIN')
    try:
        conn.execute('''UPDATE players SET score=score+COALESCE((SELECT points FROM answers a
         WHERE a.game_id=players.game_id AND a.player_id=players.id AND a.question_index=?),0)
         WHERE game_id=?''',(game['current_index'],game['id']))
        conn.execute('UPDATE games SET status=? WHERE id=?',('results',game['id']))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return True


async def auto_reveal(game_id, idx, deadline):
    try:
        await asyncio.sleep(max(0,deadline-time.time()))
        async with lock:
            game=active_game()
            if game and game['id']==game_id and game['status']=='question' and game['current_index']==idx:
                finalize_question(game)
            else:return
        await broadcast_game()
    except asyncio.CancelledError:
        return


def start_timer(game):
    global timer_task
    if timer_task and not timer_task.done():timer_task.cancel()
    if game and game['status']=='question':
        timer_task=asyncio.create_task(auto_reveal(game['id'],game['current_index'],game['deadline_at']))


@asynccontextmanager
async def lifespan(app):
    game=active_game()
    if game and game['status']=='question':
        start_timer(game)
        if game['reveal_on_complete']:
            schedule_counts()
    yield
    if timer_task: timer_task.cancel()
    if count_broadcast_task: count_broadcast_task.cancel()
    conn.close()

app=FastAPI(title='Escalation Trivial',docs_url=None,redoc_url=None,lifespan=lifespan)
app.include_router(teacher_routes(conn, require_admin, lock))
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@app.middleware('http')
async def secure_headers(request: Request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    if 'Cache-Control' not in response.headers:
        path = request.url.path
        response.headers['Cache-Control'] = ('public, max-age=120' if path.startswith('/static/')
                                             else 'no-store' if path.startswith('/api/') else 'no-cache')
    response.headers['Content-Security-Policy']="default-src 'self'; connect-src 'self' ws: wss:; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response

@app.get('/health')
async def health():
    return {'status':'ok','question_count':row('SELECT COUNT(*) AS n FROM questions')['n']}

@app.get('/api/question-images/{image_id}')
async def question_image(image_id: str, request: Request):
    if not IMAGE_ID.fullmatch(image_id):
        raise HTTPException(404)
    data = row('SELECT content FROM question_images WHERE id=?', (image_id,))
    if not data:
        raise HTTPException(404)
    headers = {'ETag': f'"{image_id}"', 'Cache-Control': 'private, max-age=31536000, immutable'}
    if request.headers.get('if-none-match') == headers['ETag']:
        return Response(status_code=304, headers=headers)
    return Response(data['content'], media_type='image/webp', headers=headers)

@app.get('/')
@app.get('/docente')
@app.get('/schermo')
async def homepage():
    return FileResponse(ROOT/'static'/'index.html')

@app.post('/api/admin/login')
async def login(request:Request):
    body=await read_object(request)
    pwd=body.get('password','')
    source=request.client.host if request.client else 'unknown'
    now=time.time()
    failures=[v for v in login_failures.get(source,[]) if now-v<300]
    login_failures[source]=failures
    if len(failures)>=12:
        raise HTTPException(429,detail='Troppi tentativi di accesso. Riprova più tardi.')
    if not isinstance(pwd,str) or len(pwd)>512 or not hmac.compare_digest(
        hashlib.sha256(pwd.encode()).digest(),hashlib.sha256(ADMIN_PASSWORD.encode()).digest()):
        failures.append(now)
        raise HTTPException(401,detail='Password non corretta.')
    login_failures.pop(source,None)
    conn.execute('DELETE FROM revoked_admin_sessions WHERE expires_at<=?', (now,))
    payload=f'{int(now)}.{secrets.token_hex(16)}'
    sig=hmac.new(SESSION_SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
    response=JSONResponse({'ok':True})
    secure=request.headers.get('x-forwarded-proto','')=='https' or request.url.scheme=='https'
    response.set_cookie('esc_admin',payload+'.'+sig,httponly=True,secure=secure,
                        samesite='strict',max_age=ADMIN_SESSION_SECONDS,path='/')
    return response

@app.post('/api/admin/logout')
async def logout(request: Request):
    session=admin_session(request.cookies.get('esc_admin'))
    if session:
        session_id=session[0]
        conn.execute('INSERT OR REPLACE INTO revoked_admin_sessions VALUES (?,?)',session)
        closing=[]
        for clients in (host_clients,screen_clients):
            for ws, sid in tuple(clients.items()):
                if sid==session_id:
                    del clients[ws]
                    closing.append(sign_out_socket(ws))
        if closing:
            await asyncio.gather(*closing,return_exceptions=True)
    response=JSONResponse({'ok':True})
    response.delete_cookie('esc_admin',path='/')
    return response

@app.get('/api/admin/overview')
async def overview(request:Request):
    require_admin(request)
    qs=[dict(**decode_question(q), revision=q['revision']) for q in conn.execute('SELECT * FROM questions ORDER BY category_id,id')]
    game=latest_game()
    result={'questions':qs,'game':game_info(game),'selected':json.loads(game['selected_json']) if game else [],
            'leaderboard':leaderboard(game,20)}
    if game:
        result['snapshot']=public_snapshot(game,'host')
        if game['status']=='lobby':
            result['settings']=settings(game)
            result['configurationRevision'] = deck_revision(game)
            frozen={r['question_id']:json.loads(r['payload']) for r in conn.execute(
                'SELECT question_id,payload FROM game_questions WHERE game_id=?',(game['id'],))}
            result['questions']=[dict(frozen[q['id']], revision=q['revision'], frozen=True) if q['id'] in frozen else q for q in qs]
    return result

@app.get('/api/screen')
async def screen_state(request: Request):
    require_admin(request)
    return public_snapshot(latest_game(), 'screen')


@app.get('/api/catalogue-summary')
async def catalogue_summary():
    r = row('SELECT COUNT(*) AS questions, COUNT(DISTINCT category_id) AS categories FROM questions')
    return {**dict(r), 'capacity': MAX_PLAYERS}


@app.post('/api/admin/create')
async def create_game(request:Request):
    require_admin(request)
    body=await read_object(request)
    chosen=checked_ids(conn, body.get('ids'))
    if type(body.get('shuffle', False)) is not bool:
        raise HTTPException(400, detail='Impostazione di ordinamento non valida.')
    duration=body.get('duration',20)
    reveal_on_complete = body.get('revealOnComplete', False)
    if type(reveal_on_complete) is not bool:
        raise HTTPException(400, detail='Impostazione di chiusura del round non valida.')
    if type(duration) is not int or not 10<=duration<=120:
        raise HTTPException(400,detail='Durata consentita: da 10 a 120 secondi.')
    async with lock:
        if active_game():raise HTTPException(409,detail='Esiste già una lobby o una partita attiva.')
        if body.get('shuffle',False):secrets.SystemRandom().shuffle(chosen)
        gid=secrets.token_hex(12)
        for _ in range(20):
            pin=str(secrets.randbelow(900000)+100000)
            if not row('SELECT id FROM games WHERE pin=?',(pin,)):break
        else:raise HTTPException(503,detail='Impossibile creare un PIN univoco.')
        conn.execute('BEGIN')
        try:
            conn.execute('''INSERT INTO games(id,pin,status,selected_json,duration,created_at,reveal_on_complete)
                VALUES (?,?,?,?,?,?,?)''',(gid,pin,'lobby',json.dumps(chosen),duration,time.time(),reveal_on_complete))
            freeze_questions(gid,chosen)
            save_settings(gid,body,chosen)
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    await broadcast_game()
    return {'ok':True,'game':game_info(active_game())}

@app.patch('/api/admin/questions')
async def edit_lobby(request:Request):
    require_admin(request)
    body=await read_object(request)
    chosen=checked_ids(conn, body.get('ids'))
    if type(body.get('shuffle', False)) is not bool:
        raise HTTPException(400, detail='Impostazione di ordinamento non valida.')
    async with lock:
        game=active_game()
        if not game or game['status']!='lobby':raise HTTPException(409,detail='Le domande possono essere modificate solo in lobby.')
        duration=body.get('duration',game['duration'])
        if type(duration) is not int or not 10<=duration<=120:
            raise HTTPException(400,detail='Durata non valida.')
        reveal_on_complete = body.get('revealOnComplete', bool(game['reveal_on_complete']))
        if type(reveal_on_complete) is not bool:
            raise HTTPException(400, detail='Impostazione di chiusura del round non valida.')
        if body.get('shuffle',False):secrets.SystemRandom().shuffle(chosen)
        if body.get('gameId',game['id'])!=game['id']:
            raise HTTPException(409,detail='La lobby è cambiata. Aggiorna la pagina.')
        if 'expectedRevision' in body and body['expectedRevision'] != deck_revision(game):
            raise HTTPException(409, detail={'code':'deck_changed',
                'message':'Un’altra regia ha modificato questa selezione. Ricaricala per continuare.'})
        conn.execute('BEGIN')
        try:
            freeze_questions(game['id'],chosen)
            save_settings(game['id'],body,chosen)
            conn.execute('UPDATE games SET selected_json=?,duration=?,reveal_on_complete=? WHERE id=?',
                         (json.dumps(chosen),duration,reveal_on_complete,game['id']))
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    await broadcast_game()
    return {'ok':True}

@app.post('/api/admin/action')
async def host_action(request:Request):
    require_admin(request)
    body=await read_object(request)
    action=body.get('action')
    async with lock:
        game=active_game()
        if not game:raise HTTPException(404,detail='Nessuna partita attiva.')
        status=game['status']
        if (body.get('gameId',game['id'])!=game['id'] or body.get('index',game['current_index'])!=game['current_index']
                or body.get('status',status)!=status):
            raise HTTPException(409,detail='La partita è già passata a una nuova fase.')
        ids=json.loads(game['selected_json'])
        if action=='start' and status=='lobby' and ids:
            if not row('SELECT id FROM players WHERE game_id=? LIMIT 1',(game['id'],)):
                raise HTTPException(409,detail='Attendi il primo giocatore prima di iniziare.')
            now=time.time()
            conn.execute('UPDATE games SET status=?,current_index=0,opened_at=?,deadline_at=? WHERE id=?',
                         ('question',now,now+game['duration'],game['id']))
            start_timer(active_game())
        elif action=='reveal' and status=='question':
            finalize_question(game)
            if timer_task and not timer_task.done():timer_task.cancel()
        elif action=='next' and status=='results' and game['current_index']+1<len(ids):
            now=time.time()
            conn.execute('UPDATE games SET status=?,current_index=?,opened_at=?,deadline_at=? WHERE id=?',
                         ('question',game['current_index']+1,now,now+game['duration'],game['id']))
            start_timer(active_game())
        elif action=='finish' and status=='results':
            conn.execute('UPDATE games SET status=?,closed_at=? WHERE id=?',('finished',time.time(),game['id']))
        elif action=='cancel':
            if status=='question':
                finalize_question(game)
            conn.execute('UPDATE games SET status=?,closed_at=? WHERE id=?',('cancelled',time.time(),game['id']))
            if timer_task and not timer_task.done():timer_task.cancel()
        else:
            raise HTTPException(409,detail='Operazione non consentita nello stato corrente.')
    await broadcast_game()
    return {'ok':True,'game':game_info(latest_game())}

@app.get('/api/admin/export')
async def export_results(request:Request):
    require_admin(request)
    requested = request.query_params.get('gameId')
    game = row('SELECT * FROM games WHERE id=?', (requested,)) if requested is not None else latest_game()
    if not game:raise HTTPException(404,detail='Nessuna partita disponibile.')
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(['Posizione','Nickname','Punteggio','Risposte corrette','Risposte inviate'])
    last_published=game['current_index'] - int(game['status']=='question')
    for r in conn.execute('''WITH published AS (
        SELECT player_id,SUM(correct) AS correct_answers,COUNT(*) AS all_answers
        FROM answers WHERE game_id=? AND question_index<=? GROUP BY player_id
        ) SELECT RANK() OVER (ORDER BY p.score DESC) AS rank,p.nickname,p.score,
        COALESCE(a.correct_answers,0) AS correct_answers,COALESCE(a.all_answers,0) AS all_answers
        FROM players p LEFT JOIN published a ON a.player_id=p.id
        WHERE p.game_id=? ORDER BY p.score DESC,p.joined_at,p.id''',(game['id'],last_published,game['id'])):
        nickname=r['nickname']
        if nickname and nickname[0] in '=+-@': nickname="'"+nickname
        writer.writerow([r['rank'],nickname,r['score'],r['correct_answers'],r['all_answers']])
    stream=io.BytesIO(('\ufeff'+output.getvalue()).encode('utf-8'))
    return StreamingResponse(stream,media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="Escalation-Trivial-{game["pin"]}.csv"',
                 'Cache-Control':'private, no-store'})

@lru_cache(maxsize=8)
def qr_png(url):
    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(url)
    qr.make()
    size = qr.getModuleCount()
    image = Image.new('L', (size + 8, size + 8), 255)
    for y in range(size):
        for x in range(size):
            if qr.isDark(y, x):
                image.putpixel((x + 4, y + 4), 0)
    data = io.BytesIO()
    image.resize((image.width * 8, image.height * 8), Image.Resampling.NEAREST).save(data, format='PNG')
    return data.getvalue()


@app.get('/api/admin/qr')
async def qr_code(request:Request):
    require_admin(request)
    game=latest_game()
    if not game:raise HTTPException(404,detail='Nessuna partita.')
    requested = request.query_params.get('pin')
    if requested is not None and (requested != game['pin'] or game['status'] != 'lobby'):
        raise HTTPException(409, detail='Il QR appartiene a una lobby che non è più aperta.')
    base=public_base_url() or str(request.base_url).rstrip('/')
    return Response(qr_png(f'{base}/?pin={game["pin"]}'),media_type='image/png',
                    headers={'Cache-Control':'private, no-store'})

def join_result(game, player_id, nickname, token, reconnected):
    return {'ok':True, 'playerId':player_id, 'token':token, 'nickname':nickname,
            'game':game_info(game), 'reconnected':reconnected}


@app.post('/api/join')
async def join(request: Request):
    body = await read_object(request)
    pin = str(body.get('pin','')).strip()
    if not re.fullmatch(r'[0-9]{6}', pin):
        raise HTTPException(400, detail='Inserisci un PIN di sei cifre.')
    key = body.get('joinKey')
    if key is not None and (not isinstance(key,str) or not re.fullmatch(r'[0-9a-f]{64}',key)):
        raise HTTPException(400, detail='Tentativo di ingresso non valido. Riapri la pagina.')
    async with lock:
        game = latest_game()
        if body.get('token') is not None or body.get('playerId') is not None:
            player = get_player(body.get('playerId'), body.get('token'))
            if not player or not game or player['game_id'] != game['id'] or game['pin'] != pin:
                raise HTTPException(401, detail='Impossibile riprendere questa sessione.')
            return join_result(game, player['id'], player['nickname'], body['token'], True)
        if not game or game['pin'] != pin:
            raise HTTPException(404, detail='Nessuna partita attiva con questo PIN.')

        # Scope repeatable credentials to the original game, even if a client reuses its key.
        token = (hmac.new(bytes.fromhex(key),game['id'].encode(),hashlib.sha256).hexdigest()
                 if key else secrets.token_urlsafe(32))
        digest = hashlib.sha256(token.encode()).hexdigest()
        if key is not None:
            previous = row('SELECT id,nickname FROM players WHERE game_id=? AND token_hash=?',
                           (game['id'],digest))
            if previous:
                return join_result(game,previous['id'],previous['nickname'],token,True)
        if game['status'] in ('finished','cancelled'):
            raise HTTPException(404, detail='Questa partita è terminata.')
        if game['status'] != 'lobby':
            raise HTTPException(409, detail='La partita è già iniziata. Gli iscritti possono rientrare dallo stesso browser.')
        nickname = body.get('nickname','')
        if not isinstance(nickname,str):
            raise HTTPException(400, detail='Nickname non valido.')
        nickname = unicodedata.normalize('NFC',' '.join(nickname.split()))
        if not 2 <= len(nickname) <= 24 or any(ord(ch) < 32 for ch in nickname):
            raise HTTPException(400, detail='Il nickname deve contenere da 2 a 24 caratteri.')
        count = row('SELECT COUNT(*) AS n FROM players WHERE game_id=?',(game['id'],))['n']
        if count >= MAX_PLAYERS:
            raise HTTPException(409, detail='Lobby piena. È stato raggiunto il limite di 400 giocatori.')
        key_name = normalized(nickname)
        occupied = row('SELECT id FROM players WHERE game_id=? AND nickname_key=?',(game['id'],key_name))
        # Existing lobbies may contain decomposed accent sequences saved by older clients.
        if not occupied and not key_name.isascii():
            occupied = any(normalized(r[0])==key_name for r in conn.execute(
                'SELECT nickname_key FROM players WHERE game_id=?',(game['id'],)))
        if occupied:
            raise HTTPException(409, detail='Nickname già utilizzato. Scegline un altro.')
        pid = secrets.token_hex(12)
        conn.execute('INSERT INTO players(id,game_id,nickname,nickname_key,token_hash,joined_at) VALUES (?,?,?,?,?,?)',
                     (pid,game['id'],nickname,key_name,digest,time.time()))
        result = join_result(game,pid,nickname,token,False)
    schedule_counts()
    return result


@app.post('/api/player/review')
async def player_review(request: Request):
    body = await read_object(request)
    player = get_player(body.get('playerId'), body.get('token'))
    game = latest_game()
    if not player or not game or player['game_id'] != game['id'] or body.get('pin') != game['pin']:
        raise HTTPException(401, detail='Il ripasso di questa partita non è più disponibile.')
    if game['status'] != 'finished':
        raise HTTPException(409, detail='Il ripasso si apre al termine della partita.')

    played = json.loads(game['selected_json'])[:game['current_index'] + 1]
    frozen = {r['question_id']: r['payload'] for r in conn.execute(
        'SELECT question_id,payload FROM game_questions WHERE game_id=?', (game['id'],))}
    answers = {r['question_index']: r for r in conn.execute(
        'SELECT question_index,choice,correct FROM answers WHERE game_id=? AND player_id=?',
        (game['id'], player['id']))}
    rounds = []
    for index, qid in enumerate(played):
        q = json.loads(frozen[qid])
        answer = answers.get(index)
        rounds.append({'number':index + 1, 'category':q['category'], 'text':q['text'],
                       'options':q['options'], 'correct':q['correct'], 'explanation':q['explanation'],
                       **({k:q[k] for k in ('image','imageAlt') if k in q}),
                       'choice':answer['choice'] if answer else None,
                       'outcome':('correct' if answer['correct'] else 'wrong') if answer else 'missed'})
    return {'gameId':game['id'], 'rounds':rounds}


@app.post('/api/leave')
async def leave_lobby(request: Request):
    body = await read_object(request)
    async with lock:
        player = get_player(body.get('playerId'), body.get('token'))
        game = active_game()
        if not player or not game or player['game_id'] != game['id'] or body.get('pin') != game['pin']:
            raise HTTPException(401, detail='Sessione non valida.')
        if game['status'] != 'lobby':
            raise HTTPException(409, detail='La partita è già iniziata.')
        conn.execute('DELETE FROM players WHERE id=?', (player['id'],))
        group = player_clients.pop(player['id'], None)
        sockets = tuple(group.sockets) if group else ()
    for ws in sockets:
        await safe_send(ws, {'type':'session_invalid', 'message':'Hai lasciato la lobby.'})
        try: await ws.close(code=1000)
        except RuntimeError: pass
    schedule_counts()
    return {'ok': True}

async def sign_out_socket(ws):
    await safe_send(ws, {'type':'admin_signed_out'})
    try:
        await ws.close(code=1008)
    except (RuntimeError, WebSocketDisconnect, OSError):
        pass


async def staff_socket(ws, role, clients):
    cookie = ws.cookies.get('esc_admin')
    if not websocket_origin_ok(ws) or not admin_session(cookie):
        await ws.close(code=1008)
        return
    await ws.accept()
    # Logout can run while the connection handshake is in progress.
    session = admin_session(cookie)
    if not session:
        await sign_out_socket(ws)
        return
    session_id, expires = session
    clients[ws] = session_id
    try:
        async with asyncio.timeout(max(0, expires-time.time())):
            await safe_send(ws, public_snapshot(latest_game(), role))
            while ws in clients:
                msg = await ws.receive_json()
                if ws not in clients:
                    break
                if not isinstance(msg, dict):
                    continue
                if msg.get('type') == 'sync':
                    await safe_send(ws, public_snapshot(latest_game(), role))
                elif msg.get('type') == 'ping':
                    await safe_send(ws, {'type':'pong'})
    except TimeoutError:
        clients.pop(ws, None)
        await sign_out_socket(ws)
    except (WebSocketDisconnect,ValueError,RuntimeError):
        pass
    finally:
        clients.pop(ws, None)


@app.websocket('/ws/host')
async def ws_host(ws:WebSocket):
    await staff_socket(ws, 'host', host_clients)


@app.websocket('/ws/screen')
async def ws_screen(ws:WebSocket):
    await staff_socket(ws, 'screen', screen_clients)


def record_choice(game, question, player_id, choice, wager, received_at):
    index = game['current_index']
    keys = (game['id'], player_id, index)
    used = row('SELECT COUNT(*) FROM score_details WHERE game_id=? AND player_id=? AND wager=1', keys[:2])[0]
    previous = row('SELECT a.choice,COALESCE(d.wager,0) AS wager FROM answers a '
                   'LEFT JOIN score_details d USING(game_id,player_id,question_index) '
                   'WHERE a.game_id=? AND a.player_id=? AND a.question_index=?', keys)
    ack = dict(type='answer_ack', questionIndex=index, remainingBets=max(0,2-used))
    if previous:
        return dict(**ack, ok=False, alreadyAnswered=True, choice=previous['choice'],
                    wager=bool(previous['wager']), message='La prima scelta è già registrata.')
    config = settings(game)
    if type(wager) is not bool or (wager and (not config['bets'] or used>=2)):
        return dict(**ack, ok=False, message='Raddoppio non disponibile.')
    correct = int(choice == question['correct'])
    remaining = min(game['duration'],max(0,game['deadline_at']-received_at))
    base = round(500+500*remaining/game['duration']) if correct else 0
    bonus = base*(config['multipliers'].get(question['id'],1)-1)
    stake = 0
    if wager:
        score = row('SELECT score FROM players WHERE id=?', (player_id,))[0]
        stake = base if correct else -min(500,score)
    conn.execute('BEGIN')
    try:
        conn.execute('INSERT INTO answers VALUES (?,?,?,?,?,?,?)',
                     (*keys,choice,correct,base+bonus+stake,received_at))
        conn.execute('INSERT INTO score_details VALUES (?,?,?,?,?,?,?)', (*keys,base,bonus,int(wager),stake))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    schedule_counts()
    ack['remainingBets'] -= int(wager)
    return dict(**ack, ok=True, choice=choice, wager=wager)


@app.websocket('/ws/play')
async def ws_play(ws:WebSocket):
    if not websocket_origin_ok(ws):
        await ws.close(code=1008);return
    await ws.accept()
    pid=None
    try:
        try:hello=await asyncio.wait_for(ws.receive_json(),timeout=12)
        except asyncio.TimeoutError:await ws.close(code=1008);return
        if not isinstance(hello,dict) or hello.get('type')!='hello':await ws.close(code=1008);return
        pid=hello.get('playerId')
        p=get_player(pid,hello.get('token'))
        game=latest_game()
        if not p or not game or p['game_id']!=game['id'] or hello.get('pin')!=game['pin']:
            await safe_send(ws,{'type':'session_invalid','message':'Sessione non valida. Rientra nella lobby.'})
            await ws.close(code=1008);return
        group = player_clients.setdefault(pid, PlayerConnections(game['id']))
        if len(group.sockets) >= 2:
            await safe_send(ws,{'type':'error','code':'tab_limit',
                                'message':'Questo giocatore è già collegato in due schede. Chiudine una e premi Ricollega.'})
            await ws.close(code=1008);return
        first_connection = not group.sockets
        group.sockets.add(ws)
        if first_connection and game['status'] == 'lobby':
            schedule_counts()
        await safe_send(ws,public_snapshot(game,'player',pid))
        while True:
            payload=await ws.receive_json()
            if isinstance(payload,dict) and payload.get('type')=='ping':
                await safe_send(ws,{'type':'pong'})
                continue
            if isinstance(payload,dict) and payload.get('type')=='sync':
                current = latest_game()
                if not current or current['id'] != p['game_id'] or pid not in player_clients:
                    await safe_send(ws,{'type':'session_invalid','message':'Questa sessione è terminata.'})
                    break
                await safe_send(ws,public_snapshot(current,'player',pid))
                continue
            if not isinstance(payload,dict) or payload.get('type')!='answer':continue
            choice=payload.get('choice')
            question_id=payload.get('questionId')
            question_index=payload.get('questionIndex')
            async with lock:
                received_at=time.time()
                game=active_game()
                q=selected_question(game)
                if (not game or p['game_id']!=game['id'] or game['status']!='question'
                    or received_at>=game['deadline_at'] or type(choice) is not int
                    or not q or not 0<=choice<len(q['options'])
                    or question_id!=q['id'] or type(question_index) is not int
                    or question_index!=game['current_index']):
                    ack={'type':'answer_ack','ok':False,'questionIndex':question_index,'message':'Risposta non accettata: tempo scaduto o domanda non attiva.'}
                else:
                    ack=record_choice(game,q,pid,choice,payload.get('wager',False),received_at)
            await safe_send(ws,ack)
            if ack['ok']:
                group = player_clients.get(pid)
                for other in tuple(group.sockets) if group else ():
                    if other is not ws: await safe_send(other,ack)
    except (WebSocketDisconnect,ValueError,RuntimeError,TypeError,AttributeError):pass
    finally:
        group = player_clients.get(pid)
        if group and ws in group.sockets:
            group.sockets.remove(ws)
            if not group.sockets:
                del player_clients[pid]
                schedule_counts()
