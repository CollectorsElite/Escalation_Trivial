"""Verify server scoring through real HTTP/WebSocket handlers on a disposable database."""
import os
import tempfile

from fastapi.testclient import TestClient

def run():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    with tempfile.TemporaryDirectory() as data:
        os.environ.update(DATA_DIR=data,ADMIN_PASSWORD='fixture-only',SESSION_SECRET='local-fixture')
        import app
        with TestClient(app.app) as client:
            client.post('/api/admin/login',json={'password':'fixture-only'}).raise_for_status()
            questions=client.get('/api/admin/overview').json()['questions'][:4]
            ids=[q['id'] for q in questions]
            config=dict(ids=ids,bets=True,title='Aula',multipliers={ids[1]:3,ids[3]:2},duration=120)
            pin=client.post('/api/admin/create',json=config).json()['game']['pin']
            player=client.post('/api/join',json=dict(pin=pin,nickname='Demo')).json()
            def action(name):
                client.post('/api/admin/action',json=dict(action=name)).raise_for_status()
            with client.websocket_connect('/ws/play') as ws:
                ws.send_json(dict(type='hello',pin=pin,playerId=player['playerId'],token=player['token']))
                def receive(kind,status=None):
                    while True:
                        m=ws.receive_json()
                        if m['type']==kind and (status is None or m['game']['status']==status):return m
                receive('snapshot','lobby')
                for i,q in enumerate(questions):
                    action('start' if i==0 else 'next')
                    snap=receive('snapshot','question')
                    assert snap['question']['multiplier']==config['multipliers'].get(ids[i],1)
                    wager=i in (1,2,3)
                    right=i!=2
                    msg=dict(type='answer',questionId=q['id'],questionIndex=i,choice=q['correct'] if right else (q['correct']+1)%len(q['options']),wager=wager)
                    ws.send_json(msg)
                    ack=receive('answer_ack')
                    if i==3:
                        assert not ack['ok']
                        msg['wager']=False
                        ws.send_json(msg)
                        ack=receive('answer_ack')
                    assert ack['ok']
                    ws.send_json(msg)
                    assert receive('answer_ack')['alreadyAnswered']
                    action('reveal')
                    result=receive('snapshot','results')['me']
                    pts=result['answer']['points']
                    if i==2:assert pts==-500
                    elif i==1:assert 2000<=pts<=4000 and pts%4==0
                    elif i==3:assert 1000<=pts<=2000 and pts%2==0
                action('finish')
                final=receive('snapshot','finished')['me']
                detail=final['summary']
                assert final['score']==detail['base']+detail['bonus']+detail['stake']
                report=client.get('/api/admin/overview').json()['snapshot']['lesson']
                assert len(report['hardest'])==3 and report['hardest'][0]['correct']==0
    print('OK: bonus ×2/×3, wager stacking, loss, duplicate, limits and final recap')

if __name__=='__main__':run()
