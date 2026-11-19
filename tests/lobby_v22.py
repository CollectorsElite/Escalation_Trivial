"""Regressions for normal classroom interactions. tests/run.py supplies a temporary server."""
import asyncio
import csv
import io
import json
import os
import secrets

import httpx
import websockets

BASE = 'http://127.0.0.1:8129'
WS = 'ws://127.0.0.1:8129/ws/'


async def frame(socket, kind, **expected):
    async with asyncio.timeout(5):
        while True:
            msg = json.loads(await socket.recv())
            if msg.get('type') == kind and all(msg.get(k) == v for k, v in expected.items()):
                return msg


async def sync(socket):
    await socket.send(json.dumps({'type':'sync'}))
    return await frame(socket, 'snapshot')


async def main():
    async with httpx.AsyncClient(base_url=BASE, trust_env=False) as client:
        (await client.post('/api/admin/login', json={'password':os.environ['ADMIN_PASSWORD']})).raise_for_status()
        ids = ['PHI-001','PHI-002']
        deck = {'ids':ids,'duration':30,'revealOnComplete':True}
        async def create():
            response = await client.post('/api/admin/create', json=deck)
            response.raise_for_status()
            return response.json()['game']
        async def command(name):
            answer = await client.post('/api/admin/action', json={'action':name,'gameId':game['id']})
            answer.raise_for_status()
        async def join(data):
            answer = await client.post('/api/join', json=data)
            answer.raise_for_status()
            return answer.json()
        async def presence(expected):
            async with asyncio.timeout(4):
                while True:
                    game = (await client.get('/api/screen')).json()['game']
                    if (game['players'],game['connected']) == expected:
                        return
                    await asyncio.sleep(.04)
        game=await create()
        pin=game['pin']
        assert (await client.post('/api/admin/action',json={'action':'start','gameId':game['id']})).status_code==409
        rev=(await client.get('/api/admin/overview')).json()['configurationRevision']
        data={**deck,'duration':45,'gameId':game['id'],'expectedRevision':rev}
        fresh=await client.patch('/api/admin/questions',json=data)
        fresh.raise_for_status()
        stale=await client.patch('/api/admin/questions',json={**data,'duration':60})
        assert stale.status_code==409 and stale.json()['detail']['code']=='deck_changed'
        latest=(await client.get('/api/admin/overview')).json()
        assert latest['game']['duration']==45
        assert latest['configurationRevision']!=rev
        (await client.patch('/api/admin/questions',json={**data,'expectedRevision':latest['configurationRevision'],'duration':60})).raise_for_status()

        first={'pin':pin,'nickname':'Nova','joinKey':secrets.token_hex(32)}
        nova=await join(first)
        repeat=await join(first)
        assert repeat['playerId']==nova['playerId'] and repeat['token']==nova['token'] and repeat['reconnected']
        assert (await client.post('/api/join',json={**first,'joinKey':secrets.token_hex(32)})).status_code==409
        vega=await join({'pin':pin,'nickname':'Vega'})
        await presence((2,0))
        def cred(person):
            return {'pin':pin,'playerId':person['playerId'],'token':person['token']}
        async def hello(socket,person):
            await socket.send(json.dumps({'type':'hello',**cred(person)}))
        cookies={'Cookie':'esc_admin='+client.cookies.get('esc_admin')}
        async with (websockets.connect(WS+'host',additional_headers=cookies) as host,
                    websockets.connect(WS+'screen',additional_headers=cookies) as screen,
                    websockets.connect(WS+'play') as one):
            for desk in (host,screen):
                assert (await frame(desk,'snapshot'))['game']['status']=='lobby'
                assert (await sync(desk))['game']['duration']==60
            await hello(one,nova)
            assert (await frame(one,'snapshot'))['game']['connected']==1
            async with websockets.connect(WS+'play') as clone:
                await hello(clone,nova)
                assert (await frame(clone,'snapshot'))['game']['connected']==1
                async with websockets.connect(WS+'play') as extra:
                    await hello(extra,nova)
                    assert (await frame(extra,'error'))['code']=='tab_limit'
                for display in (host,screen,one):
                    counts=await frame(display,'counts',connected=1,players=2)
                    assert counts['status']=='lobby'
            await presence((2,1))
            async with websockets.connect(WS+'play') as clone, websockets.connect(WS+'play') as other:
                await hello(clone,nova); await frame(clone,'snapshot')
                await hello(other,vega); await frame(other,'snapshot')
                await presence((2,2))
                await other.close()
                await presence((2,1))
                await command('start')
                assert (await frame(one,'snapshot'))['game']['status']=='question'
                await frame(clone,'snapshot')
                h=await frame(host,'snapshot')
                correct=h['question']['correct']
                assert 'correct' not in (await frame(screen,'snapshot'))['question']
                assert 'correct' not in (await sync(one))['question']
                resumed=await join(first)
                assert resumed['playerId']==nova['playerId'] and resumed['game']['status']=='question'
                assert (await client.post('/api/join',json={'pin':pin,'nickname':'Nuovo'})).status_code==409
                answer={'type':'answer','questionId':ids[0],'questionIndex':0,'choice':correct}
                await one.send(json.dumps(answer))
                assert (await frame(one,'answer_ack',ok=True))['choice']==correct
                await frame(clone,'answer_ack',ok=True)
                await clone.send(json.dumps({**answer,'choice':(correct+1)%len(h['question']['options'])}))
                duplicate=await frame(clone,'answer_ack',ok=False)
                assert duplicate['alreadyAnswered'] and duplicate['choice']==correct
                assert 'points' not in duplicate and 'correct' not in duplicate
                assert (await sync(clone))['me']['choice']==correct
                async with websockets.connect(WS+'play') as again:
                    await hello(again,vega)
                    assert (await frame(again,'snapshot'))['game']['status']=='question'
                    await again.send(json.dumps(answer))
                    assert (await frame(again,'answer_ack'))['ok']
                    results=await frame(one,'snapshot')
                    assert results['game']['status']=='results' and 500<=results['me']['score']<=1000
                    assert results['me']['score']==results['me']['answer']['points']
                await command('next')
                assert (await frame(one,'snapshot'))['question']['id']==ids[1]
                await command('reveal'); await frame(one,'snapshot')
                await command('finish')
                assert (await frame(one,'snapshot'))['game']['status']=='finished'
                review=(await client.post('/api/player/review',json=cred(nova))).json()
                assert [r['outcome'] for r in review['rounds']]==['correct','missed']
        before=game
        game=await create()
        newcomer=await join({**first,'pin':game['pin'],'nickname':'AltraClasse'})
        assert newcomer['token']!=nova['token']
        old=await client.get('/api/admin/export',params={'gameId':before['id']})
        assert 'no-store' in old.headers['cache-control']
        names={r['Nickname'] for r in csv.DictReader(io.StringIO(old.content.decode('utf-8-sig')))}
        assert names=={'Nova','Vega'}
        assert (await client.get('/api/admin/qr',params={'pin':before['pin']})).status_code==409
        current_qr=await client.get('/api/admin/qr',params={'pin':game['pin']})
        assert current_qr.headers['content-type']=='image/png' and current_qr.content.startswith(bytes.fromhex('89504e470d0a1a0a'))
        await command('cancel')
        print('OK: lobby, presence in all roles, retry, two tabs, resync, protected deck, original CSV/QR and review')

if __name__=='__main__':
    asyncio.run(main())
