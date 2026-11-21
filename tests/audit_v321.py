"""Exercise the entire catalogue, both wager receipts, CSV consistency and staff session lifecycle."""
import csv
import io
import os
from pathlib import Path
import secrets
import sys
import tempfile
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def take(ws, kind, status=None):
    while True:
        event = ws.receive_json()
        if event['type'] == kind and (status is None or event['game']['status'] == status):
            return event


def payload(response):
    response.raise_for_status()
    return response.json()


def export(browser, game):
    result = browser.get('/api/admin/export', params={'gameId': game['id']})
    result.raise_for_status()
    records = csv.DictReader(io.StringIO(result.content.decode('utf-8-sig')))
    return {r['Nickname']: r for r in records}


def play_catalogue(browser, app):
    questions = payload(browser.get('/api/admin/overview'))['questions']
    ids = [q['id'] for q in questions]
    assert len(set(ids)) == len(ids) == 210
    bonus = {qid: 1 + index % 3 for index, qid in enumerate(ids)}
    game = payload(browser.post('/api/admin/create', json={
        'ids':ids, 'duration':60, 'multipliers':bonus, 'bets':True, 'revealOnComplete':False
    }))['game']
    with patch.object(app.secrets.SystemRandom,'shuffle',lambda rng, chosen:chosen.reverse()):
        payload(browser.patch('/api/admin/questions',json={'ids':ids,'shuffle':True,'gameId':game['id']}))
    changed = payload(browser.get('/api/admin/overview'))
    assert changed['selected'] == ids[::-1] and changed['game']['duration']==60
    payload(browser.patch('/api/admin/questions',json={'ids':ids, 'gameId':game['id']}))
    def action(name):
        return payload(browser.post('/api/admin/action', json={'action':name, 'gameId':game['id']}))
    def join(name):
        return browser.post('/api/join', json={'pin':game['pin'], 'nickname':name})
    def identity(player):
        return {'pin':game['pin'], 'playerId':player['playerId'], 'token':player['token']}
    first = payload(join('Nicolò'))
    assert join('Nicolo\u0300').status_code == 409
    second = payload(join('Orione'))
    total_a = 0
    total_b = 0
    with browser.websocket_connect('/ws/play') as primary, browser.websocket_connect('/ws/play') as peer:
        for ws, player in ((primary, first), (peer, second)):
            ws.send_json(dict(type='hello', **identity(player)))
            take(ws, 'snapshot', 'lobby')
        for index, question in enumerate(questions):
            action('next' if index else 'start')
            opened = take(primary,'snapshot','question')
            take(peer,'snapshot','question')
            assert opened['question']['id'] == ids[index] and opened['question']['multiplier']==bonus[ids[index]]
            assert 'correct' not in opened['question'] and 'explanation' not in opened['question']
            message = dict(type='answer', questionId=ids[index], questionIndex=index, choice=question['correct'])
            outcome = index % 3
            # At the first three rounds the simulated arrival is at the start, halfway, and 0.12 s from expiry.
            points_at = [1000,750,501]
            remaining = [60,30,.12]
            freeze = nullcontext()
            if index < 3:
                at = opened['game']['deadline'] - remaining[index]
                freeze = patch.object(app, 'time', SimpleNamespace(time=lambda:at))
            with freeze:
                peer.send_json(message)
                assert take(peer, 'answer_ack')['ok']
                if outcome != 2:
                    choice = question['correct'] if outcome == 0 else (question['correct'] + 1) % len(question['options'])
                    primary.send_json(dict(message, choice=choice, wager=index < 2))
                    ack = take(primary,'answer_ack')
                    assert ack['ok'] and ack['wager'] == (index < 2)
                    if index == 0:
                        with browser.websocket_connect('/ws/play') as resumed:
                            resumed.send_json(dict(type='hello', **identity(first)))
                            me = take(resumed, 'snapshot', 'question')['me']
                            assert me['wager'] and me['remainingBets'] == 1
                            resumed.send_json(dict(message, wager=False))
                            repeat = take(resumed,'answer_ack')
                            assert repeat['alreadyAnswered'] and repeat['wager'] and repeat['remainingBets'] == 1
            if index == 0:
                before = export(browser, game)['Nicolò']
                assert [before[k] for k in ('Punteggio','Risposte corrette','Risposte inviate')] == ['0','0','0']
            action('reveal')
            a = take(primary,'snapshot','results')
            b = take(peer,'snapshot','results')
            assert a['question']['correct'] == question['correct']
            assert a['question']['explanation'] == question['explanation']
            assert b['me']['answer']['correct'] and b['me']['answer']['choice'] == question['correct']
            if index < 3:
                assert b['me']['answer']['points'] == points_at[index] * bonus[ids[index]]
            delta = a['me'].get('answer',{}).get('points',0)
            if outcome == 0:
                assert a['me']['answer']['correct'] and delta > 0
            elif outcome == 1:
                assert not a['me']['answer']['correct'] and delta == (-500 if index == 1 else 0)
            else:
                assert 'answer' not in a['me']
            if index == 0:
                assert delta == 2000
            total_a += delta
            total_b += b['me']['answer']['points']
            assert a['me']['score'] == total_a and b['me']['score'] == total_b
        action('finish')
        end_a = take(primary, 'snapshot', 'finished')['me']
        end_b = take(peer, 'snapshot', 'finished')['me']
    assert end_b['rank'] == 1 and end_a['rank'] == 2
    recap = end_a['summary']
    assert (recap['correct'],recap['wrong'],recap['missed']) == (70,70,70)
    assert recap['base'] + recap['bonus'] + recap['stake'] == total_a
    published = export(browser, game)
    assert (int(published['Nicolò']['Punteggio']), int(published['Nicolò']['Risposte inviate'])) == (total_a, 140)
    assert (int(published['Orione']['Punteggio']), int(published['Orione']['Risposte corrette'])) == (total_b, 210)
    reviews = payload(browser.post('/api/player/review',json=identity(first)))['rounds']
    assert len(reviews)==210 and [r['outcome'] for r in reviews] == ['correct','wrong','missed']*70
    teacher=payload(browser.get('/api/admin/overview'))['snapshot']
    projection=payload(browser.get('/api/screen'))
    assert projection['leaderboard']==teacher['leaderboard']
    assert len(teacher['lesson']['areas'])==9
    assert sum(a[1] for a in teacher['lesson']['areas'].values())==350
    print('OK 210 round, 350 risposte, 9 categorie, velocità 1000/750/501, bonus e Raddoppi, classifica, CSV e ripasso')


def staff_sessions(browser, app, password):
    separate=TestClient(app.app)
    try:
        payload(separate.post('/api/admin/login',json={'password':password}))
        with browser.websocket_connect('/ws/host') as host, browser.websocket_connect('/ws/screen') as screen:
            take(host, 'snapshot')
            take(screen, 'snapshot')
            payload(browser.post('/api/admin/logout'))
            for ws in (host,screen):
                take(ws, 'admin_signed_out')
                assert ws.receive()['type']=='websocket.close'
        assert browser.get('/api/screen').status_code==401
        separate.get('/api/screen').raise_for_status()
        with patch.object(app, 'ADMIN_SESSION_SECONDS', 2):
            payload(browser.post('/api/admin/login',json={'password':password}))
            with browser.websocket_connect('/ws/screen') as screen:
                take(screen, 'snapshot')
                take(screen, 'admin_signed_out')
                assert screen.receive()['type']=='websocket.close'
            assert browser.get('/api/admin/overview').status_code==401
    finally:
        separate.close()
    print('OK uscita e scadenza anche a proiettore inattivo, seconda sessione indipendente')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='trivial-audit-') as data:
        password=secrets.token_urlsafe(24)
        os.environ.update(DATA_DIR=data,ADMIN_PASSWORD=password,SESSION_SECRET=secrets.token_hex(32))
        import app
        with TestClient(app.app) as browser:
            payload(browser.post('/api/admin/login',json={'password':password}))
            play_catalogue(browser,app)
            staff_sessions(browser,app,password)
