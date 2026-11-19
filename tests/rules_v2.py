"""Functional checks in a private test game (started by run.py)."""
import asyncio, csv, io, json, os
import httpx, websockets
from regression import recv_type

BASE = 'http://127.0.0.1:8129'

async def main():
    async with httpx.AsyncClient(base_url=BASE) as client:
        (await client.post('/api/admin/login',json={'password':'SuperSicuraDiTest-2026'})).raise_for_status()
        async def action(name, **extra):
            return await client.post('/api/admin/action',json={'action':name,**extra})
        g=(await client.post('/api/admin/create',json={'ids':['PHI-001','PHI-002'],'duration':10})).json()['game']
        pin=g['pin'];assert (await action('start')).status_code==409
        assert (await client.patch('/api/admin/questions',json={'ids':[['bad']]})).status_code==400
        assert (await client.get('/api/admin/qr')).content.startswith(b'\x89PNG\r\n\x1a\n')
        async def join(n):return (await client.post('/api/join',json={'pin':pin,'nickname':n})).json()
        p=await join('Tastiera'); temporary=await join('Temporaneo');cred=lambda user:{'pin':pin,'playerId':user['playerId'],'token':user['token']}
        assert (await client.post('/api/leave',json=cred(temporary))).status_code==200
        assert (await client.post('/api/join',json=cred(temporary))).status_code==401
        await join('Temporaneo');await join('Monitor')
        cookie=client.cookies.get('esc_admin');endpoint=BASE.replace('http:','ws:')+'/ws/'
        async with (websockets.connect(endpoint+'screen',additional_headers={'Cookie':'esc_admin='+cookie}) as screen,
                    websockets.connect(endpoint+'host',additional_headers={'Cookie':'esc_admin='+cookie}) as host,
                    websockets.connect(endpoint+'play') as ws):
            await ws.send(json.dumps({'type':'hello',**cred(p)}));await recv_type(ws,'snapshot');await recv_type(host,'snapshot');await recv_type(screen,'snapshot')
            assert (await action('start')).status_code==200;await recv_type(ws,'snapshot');hs=await recv_type(host,'snapshot');ss=await recv_type(screen,'snapshot');http_screen=(await client.get('/api/screen')).json();
            assert 'correct' in hs['question']
            for s in (ss,http_screen):
                assert all(k not in s['question'] for k in ('correct','explanation')) and 'breakdown' not in s and 'leaderboard' not in s
            assert (await action('reveal',gameId='old',index=0,status='question')).status_code==409
            correct=hs['question']['correct'];await ws.send(json.dumps({'type':'answer','choice':correct,'questionId':'PHI-001','questionIndex':0}));assert (await recv_type(ws,'answer_ack'))['ok']
            async with websockets.connect(endpoint+'play') as clone:
                await clone.send(json.dumps({'type':'hello',**cred(p)}));restored=await recv_type(clone,'snapshot');assert restored['me']['choice']==correct and 'answer' not in restored['me']
                assert (await client.post('/api/leave',json=cred(p))).status_code==409
            assert (await action('reveal')).is_success
            proof=await recv_type(ws,'snapshot');assert 500<=proof['me']['score']<=1000
            frame=await recv_type(screen,'snapshot');assert sum(frame['breakdown'])==1 and frame['breakdown'][correct]==1 and frame['question']['correct']==correct
            assert (await action('next')).is_success;assert (await action('reveal',gameId=g['id'],index=0,status='question')).status_code==409
            await recv_type(ws,'snapshot');finalround=json.loads(await asyncio.wait_for(ws.recv(),14));assert finalround['game']['status']=='results' and not finalround['me']['answered'];assert finalround['me']['score']==proof['me']['score']
            await ws.send(json.dumps({'type':'answer','choice':0,'questionId':'PHI-002','questionIndex':1}));assert not (await recv_type(ws,'answer_ack'))['ok']
            assert (await action('finish')).is_success;board=(await client.get('/api/screen')).json()['leaderboard'];assert [r['rank'] for r in board]==[1,2,2]
            csvrows=list(csv.DictReader(io.StringIO((await client.get('/api/admin/export')).content.decode('utf-8-sig'))));assert [int(r['Posizione']) for r in csvrows]==[1,2,2]
            print('OK: three live roles, private solution, released seat, stale action, reconnect including choice, timer, ties and CSV')

if __name__=='__main__':asyncio.run(main())
