"""Run tests against temporary local SQLite databases, never against a live class."""
import argparse,os,subprocess,sys,tempfile,time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--players',type=int,default=20,choices=range(1,401),metavar='1–400')
args=parser.parse_args()

with tempfile.TemporaryDirectory(prefix='trivial-suite-') as data:
    env=dict(os.environ, ADMIN_PASSWORD='SuperSicuraDiTest-2026',SESSION_SECRET='training-test-key-'*4,DATA_DIR=data)
    env={k:v for k,v in env.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy','ws_proxy','wss_proxy')}
    env['NO_PROXY']='127.0.0.1,localhost'
    base='http://127.0.0.1:8129'
    # Refuse to touch an unrelated process already listening on the test port.
    import socket
    for port in (8129,8131):
        with socket.socket() as probe: probe.bind(('127.0.0.1',port))
    args_server=[sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port','8129','--workers','1','--log-level','warning','--no-access-log']
    proc=subprocess.Popen(args_server,cwd=ROOT,env=env)
    def run(path,*extra):subprocess.run([sys.executable,path,*extra],cwd=ROOT,env=env,check=True)
    try:
        with httpx.Client(base_url=base,timeout=1,trust_env=False) as client:
            for _ in range(100):
                if proc.poll() is not None: raise RuntimeError('Avvio del server di prova fallito.')
                try:
                    if client.get('/health').is_success:break
                except httpx.TransportError:pass
                time.sleep(.1)
            else:raise RuntimeError('Il server di prova non risponde.')
        run('tests/railway_inviti.py');run('tests/bonus_v3.py')
        run('tools/check_questions.py');run('tests/regression.py');run('tests/rules_v2.py');run('tests/integration.py','--players',str(args.players),'--url',base);run('tests/lobby_v22.py');run('tests/restart_recovery.py');run('tests/migration.py')
    finally:
        proc.terminate();proc.wait(timeout=15)
