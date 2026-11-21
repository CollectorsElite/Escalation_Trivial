"""Test funzionale + carico reale con massimo 400 client WebSocket simulati.
Avviare separatamente il server e lanciare: python tests/integration.py --players 400
"""
import argparse
import asyncio
import csv
import io
import json
import time
import httpx
import websockets

async def receive(ws, typ, status=None, timeout=25):
    async with asyncio.timeout(timeout):
        while True:
            msg=json.loads(await ws.recv())
            if msg.get('type')==typ and (status is None or msg.get('game',{}).get('status')==status):
                return msg

async def main(n=10,url='http://127.0.0.1:8128'):
    print('Test su',url,'con',n,'giocatori')
    async with httpx.AsyncClient(base_url=url,timeout=30,limits=httpx.Limits(max_connections=150,max_keepalive_connections=50)) as c:
        health=(await c.get('/health')).json()
        assert health['question_count']==210,health
        assert (await c.get('/api/admin/overview')).status_code==401
        r=await c.post('/api/admin/login',json={'password':'SuperSicuraDiTest-2026'})
        assert r.status_code==200,r.text
        info=(await c.get('/api/admin/overview')).json()
        qs=info['questions']
        assert len(qs)==210
        assert len({q['id'] for q in qs})==210
        assert len({q['category_id'] for q in qs})==9
        assert sum(q['type']=='AB' for q in qs)>0
        selected=[next(q for q in qs if q['type']=='MULTI'),next(q for q in qs if q['type']=='AB')]
        active=info['game']
        if active and active['status'] in ('lobby','question','results'):
            print('Annullamento precedente',active['pin'])
            r=await c.post('/api/admin/action',json={'action':'cancel'});assert r.status_code==200,r.text
        r=await c.post('/api/admin/create',json={'ids':[q['id'] for q in selected],'duration':10})
        assert r.status_code==200,r.text
        game=r.json()['game'];pin=game['pin'];assert game['status']=='lobby'
        # Modifica lobby e conserva la selezione
        r=await c.patch('/api/admin/questions',json={'ids':[q['id'] for q in selected],'duration':10})
        assert r.status_code==200,r.text
        async def join(i):
            data={'pin':pin,'nickname':f'CyberPlayer-{i:03d}'}
            for attempt in range(4):
                try:
                    r=await c.post('/api/join',json=data)
                    assert r.status_code==200,(r.status_code,r.text)
                    return r.json()
                except (httpx.ConnectError,httpx.PoolTimeout,httpx.ReadTimeout):
                    if attempt==3:raise
                    await asyncio.sleep(.2*(attempt+1))
        t=time.monotonic()
        players=await asyncio.gather(*(join(i) for i in range(n)))
        print(f'Iscrizione completata: {len(players)} in {time.monotonic()-t:.2f}s')
        for p in players:assert p['game']['pin']==pin
        if n==400:
            over=await c.post('/api/join',json={'pin':pin,'nickname':'TooMany'})
            assert over.status_code==409,over.text
        wsurl=url.replace('http://','ws://').replace('https://','wss://')+'/ws/play'
        async def connect(p):
            for attempt in range(3):
                try:
                    ws=await websockets.connect(wsurl,open_timeout=25,close_timeout=2,max_size=1024*1024,ping_interval=None)
                    await ws.send(json.dumps({'type':'hello','pin':pin,'playerId':p['playerId'],'token':p['token']}))
                    first=json.loads(await asyncio.wait_for(ws.recv(),12))
                    assert first['type']=='snapshot',first
                    assert first['game']['status']=='lobby',first
                    return ws
                except (OSError,TimeoutError) as e:
                    if attempt==2:raise
                    await asyncio.sleep(.3*(attempt+1))
        t=time.monotonic()
        sockets=await asyncio.gather(*(connect(p) for p in players))
        print(f'WebSocket connessi: {len(sockets)} in {time.monotonic()-t:.2f}s')
        occupancy=(await c.get('/api/screen')).json()['game']
        assert (occupancy['players'],occupancy['connected'])==(n,n),occupancy
        r=await c.post('/api/admin/action',json={'action':'start'})
        assert r.status_code==200,r.text
        start_msgs=await asyncio.gather(*(receive(s,'snapshot','question') for s in sockets))
        assert all(m['type']=='snapshot' and m['game']['status']=='question' for m in start_msgs)
        # Risposta corretta per tutti, invio in parallelo
        # L'ordine delle domande è quello selezionato, senza shuffle
        first_id=selected[0]['id']
        chosen=next(q['correct'] for q in qs if q['id']==first_id)
        t=time.monotonic()
        await asyncio.gather(*(s.send(json.dumps({'type':'answer','choice':chosen,'questionId':first_id,'questionIndex':0})) for s in sockets))
        messages=await asyncio.gather(*(receive(s,'answer_ack') for s in sockets))
        assert all(m['type']=='answer_ack' and m['ok'] for m in messages),[m for m in messages if m['type']!='answer_ack' or not m.get('ok')][:5]
        print(f'Risposte accettate: {len(messages)} in {time.monotonic()-t:.2f}s')
        dup=await sockets[0].send(json.dumps({'type':'answer','choice':chosen,'questionId':first_id,'questionIndex':0}))
        reject=json.loads(await asyncio.wait_for(sockets[0].recv(),10))
        assert reject['type']=='answer_ack' and not reject['ok'],reject
        r=await c.post('/api/admin/action',json={'action':'reveal'})
        assert r.status_code==200,r.text
        results=await asyncio.gather(*(receive(s,'snapshot','results') for s in sockets))
        assert all(m['type']=='snapshot' and m['game']['status']=='results' for m in results),results[0]
        assert all(m['me']['answer']['correct'] and m['me']['score']>0 for m in results)
        report=await c.get('/api/admin/export')
        assert report.status_code==200,report.text[:500]
        lines=list(csv.reader(io.StringIO(report.content.decode('utf-8-sig'))))
        assert len(lines)==n+1,(len(lines),n)
        # seconda domanda
        r=await c.post('/api/admin/action',json={'action':'next'})
        assert r.status_code==200,r.text
        m=await asyncio.wait_for(sockets[0].recv(),12)
        assert json.loads(m)['game']['current']==2
        # consenti chiusura anticipata con una domanda a zero risposte
        r=await c.post('/api/admin/action',json={'action':'reveal'});assert r.status_code==200
        r=await c.post('/api/admin/action',json={'action':'finish'});assert r.status_code==200
        finals=await asyncio.gather(*(receive(s,'snapshot','finished') for s in sockets))
        assert all(m['me']['rank']>=1 for m in finals)
        final_board=(await c.get('/api/admin/overview')).json()['snapshot']['leaderboard']
        projected=(await c.get('/api/screen')).json()['leaderboard']
        assert len(final_board)==n and projected==final_board[:10]
        export_rows=list(csv.DictReader(io.StringIO((await c.get('/api/admin/export')).content.decode('utf-8-sig'))))
        assert len(export_rows)==n
        by_player={m['me']['nickname']:m['me'] for m in finals}
        for participant, record in zip(final_board, export_rows):
            me=by_player[participant['nickname']]
            assert record['Nickname']==participant['nickname']
            assert int(record['Punteggio'])==participant['score']==me['score']
            assert int(record['Posizione'])==participant['rank']==me['rank']
            assert me['tied']==participant['tied']
        print(f'Classifica completa, prime {min(10,n)} in proiezione e {len(export_rows)} righe CSV coerenti.')
        await asyncio.gather(*(s.close() for s in sockets))
        print('TUTTI I TEST SUPERATI:',n,'giocatori; 210 domande; 9 categorie; risposte; punteggi; export; finale.')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--players',type=int,default=10)
    ap.add_argument('--url',default='http://127.0.0.1:8128')
    args=ap.parse_args()
    asyncio.run(main(args.players,args.url))
