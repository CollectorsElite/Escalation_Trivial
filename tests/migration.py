"""A v1.1 game in progress retains its original answer after a catalogue update."""
import json,os,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='et-v1-') as data:
    env=dict(os.environ,DATA_DIR=data,ADMIN_PASSWORD='test-only',SESSION_SECRET='test-'*14)
    path=Path(data)/'escalation-trivial.sqlite3'
    # Generate the shared v1 schema, then construct an old database without v2 tables.
    subprocess.run([sys.executable,'-c','import app'],cwd=ROOT,env=env,check=True)
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE game_questions');db.execute('PRAGMA user_version=0')
        db.execute("UPDATE questions SET question='Testo originale della partita',correct=3 WHERE id='PHI-001'")
        fields=('old-game','212345','question',json.dumps(['PHI-001']),30,0,time.time(),time.time()+20,time.time())
        db.execute('INSERT INTO games(id,pin,status,selected_json,duration,current_index,opened_at,deadline_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)',fields)
    for _ in range(2):subprocess.run([sys.executable,'-c','import app'],cwd=ROOT,env=env,check=True)
    with sqlite3.connect(path) as db:
        frozen=json.loads(db.execute('SELECT payload FROM game_questions').fetchone()[0]);assert frozen['correct']==3 and frozen['text']=='Testo originale della partita'
        current=db.execute("SELECT correct,question FROM questions WHERE id='PHI-001'").fetchone();assert current[0]==1 and current[1]!=frozen['text'];assert db.execute('PRAGMA user_version').fetchone()[0]==4
    print('OK: migration of a v1.1 database, frozen game, new catalogue and idempotent second start')
