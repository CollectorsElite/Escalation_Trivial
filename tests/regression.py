"""Edge-case regression tests for Escalation Trivial. Run only against the isolated test server."""
import asyncio
import json
import time
import httpx
import websockets
from websockets.exceptions import InvalidStatus

URL='http://127.0.0.1:8129'
WS='ws://127.0.0.1:8129/ws/play'

async def recv_type(ws, typ, max_messages=4):
    for _ in range(max_messages):
        m=json.loads(await asyncio.wait_for(ws.recv(),5))
        if m['type']==typ: return m
    raise AssertionError(f'no message of type {typ}')

async def main():
    async with httpx.AsyncClient(base_url=URL,timeout=15) as c:
        assert (await c.get('/api/admin/overview')).status_code==401
        assert (await c.post('/api/admin/create',json={'ids':['PHI-001']})).status_code==401
        assert (await c.post('/api/admin/login',json={'password':'SuperSicuraDiTest-2026'})).status_code==200
        q=(await c.get('/api/admin/overview')).json()['questions']
        assert len(q)==210 and len(set(x['id'] for x in q))==210
        assert sum(x['type']=='AB' for x in q)==138
        assert all(len(x['options']) in (2,4) and 0<=x['correct']<len(x['options']) for x in q)
        print('OK: auth and catalogue integrity')
        # Reject invalid inputs
        assert (await c.post('/api/admin/create',json={'ids':['PHI-001','PHI-001']})).status_code==400
        assert (await c.post('/api/admin/create',json={'ids':['PHI-001'],'duration':True})).status_code==400
        x=(await c.post('/api/admin/create',json={'ids':['PHI-001','PHI-002'],'duration':20})); assert x.status_code==200,x.text
        pin=x.json()['game']['pin']
        assert (await c.patch('/api/admin/questions',json={'ids':['PHI-001','PHI-002'],'duration':15})).status_code==200
        assert (await c.post('/api/join',json={'pin':pin,'nickname':'A'})).status_code==400
        p=(await c.post('/api/join',json={'pin':pin,'nickname':'Verifica01'})).json()
        assert (await c.post('/api/join',json={'pin':pin,'nickname':'verifica01'})).status_code==409
        assert (await c.post('/api/join',json={'pin':pin,'playerId':p['playerId'],'token':'incorrect'})).status_code==401
        print('OK: input validation and duplicate nicknames')
        try:
            async with websockets.connect(WS,origin='https://malicious.example'):
                raise AssertionError('Cross-origin WebSocket was permitted')
        except InvalidStatus:
            pass
        print('OK: cross-origin WebSocket rejected')
        async with websockets.connect(WS,ping_interval=None) as ws:
            await ws.send(json.dumps({'type':'hello','pin':pin,'playerId':p['playerId'],'token':p['token']}))
            lobby=await recv_type(ws,'snapshot');assert lobby['game']['status']=='lobby'
            assert (await c.post('/api/admin/action',json={'action':'start'})).status_code==200
            q1=await recv_type(ws,'snapshot'); assert q1['question']['id']=='PHI-001'
            # Disallow answers without a question identity.
            await ws.send(json.dumps({'type':'answer','choice':0}))
            invalid=await recv_type(ws,'answer_ack');assert invalid['ok']==False,invalid
            await ws.send(json.dumps({'type':'answer','choice':1,'questionId':'PHI-001','questionIndex':0}))
            ack=await recv_type(ws,'answer_ack');assert ack['ok'],ack
            await ws.send(json.dumps({'type':'answer','choice':1,'questionId':'PHI-001','questionIndex':0}))
            invalid=await recv_type(ws,'answer_ack');assert invalid['ok']==False,invalid
            assert (await c.post('/api/admin/action',json={'action':'reveal'})).status_code==200
            results=await recv_type(ws,'snapshot');assert results['me']['score']>=500 and results['me']['answer']['correct']
            assert (await c.post('/api/admin/action',json={'action':'next'})).status_code==200
            q2=await recv_type(ws,'snapshot');assert q2['question']['id']=='PHI-002',q2
            await ws.send(json.dumps({'type':'answer','choice':0,'questionId':'PHI-001','questionIndex':0}))
            stale=await recv_type(ws,'answer_ack');assert stale['ok']==False,stale
            await ws.send(json.dumps({'type':'answer','choice':0,'questionId':'PHI-002','questionIndex':1}))
            ack=await recv_type(ws,'answer_ack');assert ack['ok'],ack
            assert (await c.post('/api/admin/action',json={'action':'reveal'})).status_code==200
            await recv_type(ws,'snapshot')
            assert (await c.post('/api/admin/action',json={'action':'finish'})).status_code==200
            final=await recv_type(ws,'snapshot');assert final['game']['status']=='finished',final
            print('OK: question-bound answers, duplicates, scores, and finishing')
            restored=(await c.post('/api/join',json={'pin':pin,'playerId':p['playerId'],'token':p['token']}))
            assert restored.status_code==200,restored.text
            assert restored.json()['reconnected']
            async with websockets.connect(WS,ping_interval=None) as second:
                await second.send(json.dumps({'type':'hello','pin':pin,'playerId':p['playerId'],'token':p['token']}))
                restored_final=await recv_type(second,'snapshot')
                assert restored_final['game']['status']=='finished'
                print('OK: reconnect after game finished')
                r=await c.post('/api/admin/create',json={'ids':['PHI-002'],'duration':20});assert r.status_code==200,r.text
                invalidated=await recv_type(ws,'session_invalid')
                invalidated2=await recv_type(second,'session_invalid')
                assert invalidated['type']=='session_invalid' and invalidated2['type']=='session_invalid'
                print('OK: previous game WebSockets invalidated on new lobby')
        assert (await c.post('/api/admin/action',json={'action':'cancel'})).status_code==200
        print('ALL REGRESSION TESTS PASSED')

if __name__=='__main__':asyncio.run(main())
