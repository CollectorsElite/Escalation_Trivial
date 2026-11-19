"""Verify that SQLite game state and deadline survive a backend process crash/restart."""
import os, sys, time, json, signal, sqlite3, subprocess, tempfile
from pathlib import Path
import httpx
BASE=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8131'

with tempfile.TemporaryDirectory(prefix='escalation-restore-') as datadir:
 env={**os.environ,'DATA_DIR':datadir,'ADMIN_PASSWORD':'SuperSicuraDiTest-2026','SESSION_SECRET':'0123456789abcdef'*4}
 def boot():
  proc=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port','8131','--workers','1'],cwd=BASE,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for _ in range(90):
   try:
    if httpx.get(URL+'/health',timeout=.3).status_code==200:return proc
   except Exception:pass
   time.sleep(.1)
  proc.kill();print(proc.stderr.read().decode()[-1000:]);raise RuntimeError('server not started')
 proc=boot()
 try:
  c=httpx.Client(base_url=URL,timeout=4)
  assert c.post('/api/admin/login',json={'password':env['ADMIN_PASSWORD']}).status_code==200
  r=c.post('/api/admin/create',json={'ids':['PHI-001'],'duration':10});assert r.status_code==200,r.text
  pin=r.json()['game']['pin']
  p=c.post('/api/join',json={'pin':pin,'nickname':'Persisted'}).json()
  assert c.post('/api/admin/action',json={'action':'start'}).status_code==200
  game_id=r.json()['game']['id']
  proc.kill();proc.wait(timeout=8)
  db=sqlite3.connect(Path(datadir)/'escalation-trivial.sqlite3')
  db.execute('UPDATE games SET deadline_at=? WHERE id=?',(time.time()-2,game_id));db.commit();db.close()
  proc=boot()
  time.sleep(.7)
  # Check timer automatically finalizes expired question on startup.
  overview=c.get('/api/admin/overview'); assert overview.status_code==200,overview.text
  game=overview.json()['game']
  assert game['status']=='results',game
  restored=c.post('/api/join',json={'pin':pin,'playerId':p['playerId'],'token':p['token']})
  assert restored.status_code==200,restored.text
  print('PASS: deadline auto-finalized, saved game recovered, player token still valid')
 finally:
  if proc.poll() is None:proc.kill();proc.wait(timeout=8)
