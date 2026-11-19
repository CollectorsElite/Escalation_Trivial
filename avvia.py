"""Avvio locale portabile con configurazione privata e dipendenze isolate."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.version_info < (3, 12):
    sys.exit('Installa Python 3.12 o successivo, poi riapri questo file.')
parser = argparse.ArgumentParser(description='Avvia Escalation Trivial sul computer o nella rete dell’aula.')
parser.add_argument('--rete', action='store_true', help='Consenti il collegamento dei dispositivi nella stessa rete.')
parser.add_argument('--porta', type=int, default=8000, choices=range(1, 65536), metavar='PORTA')
parser.add_argument('--senza-browser', action='store_true', help='Stampa gli indirizzi senza aprire una finestra.')
args = parser.parse_args()

# Use an already provisioned Python (also useful for managed installations).
def dependencies_available():
    from importlib.metadata import PackageNotFoundError, version
    bounds = {'fastapi':((0,115),(1,)), 'uvicorn':((0,30),(1,)), 'websockets':((13,),(17,)),
              'reportlab':((4,2),(5,)), 'Pillow':((11,),(14,))}
    for package, (low, high) in bounds.items():
        try: parts = tuple(int(x) for x in version(package).split('.')[:2])
        except (PackageNotFoundError, ValueError): return False
        if not low <= parts < high: return False
    return True

if not dependencies_available():
    envdir = ROOT / '.venv'
    py = envdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not py.exists():
        print('Preparazione dell’ambiente Python locale…', flush=True)
        venv.EnvBuilder(with_pip=True).create(envdir)
    try:
        subprocess.run([str(py), '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], check=True)
    except subprocess.CalledProcessError:
        sys.exit('Installazione non completata. Verifica la connessione a PyPI e riprova.')
    if Path(sys.prefix).resolve() != envdir.resolve():
        sys.exit(subprocess.call([str(py), str(Path(__file__).resolve()), *sys.argv[1:]]))

from threading import Timer
import uvicorn

data = Path(os.environ.get('DATA_DIR', str(ROOT/'data'))).resolve()
data.mkdir(parents=True, exist_ok=True)
os.environ['DATA_DIR'] = str(data)
private = data/'accesso-locale.env'
if not private.exists() and not (os.environ.get('ADMIN_PASSWORD') and os.environ.get('SESSION_SECRET')):
    try:
        fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(f'ADMIN_PASSWORD={secrets.token_urlsafe(13)}\nSESSION_SECRET={secrets.token_hex(32)}\n')
    except FileExistsError:
        pass
if private.exists():
    for line in private.read_text(encoding='utf-8').splitlines():
        key, _, value = line.partition('=')
        if key in ('ADMIN_PASSWORD','SESSION_SECRET') and value:
            os.environ.setdefault(key, value)
if not os.environ.get('ADMIN_PASSWORD') or not os.environ.get('SESSION_SECRET'):
    sys.exit('Credenziali locali incomplete. Controlla il file accesso-locale.env nella cartella dati.')

def local_ipv4():
    # UDP connect selects the local interface without sending packets.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('192.0.2.1', 9))
            return sock.getsockname()[0]
        except OSError:
            try: return socket.gethostbyname(socket.gethostname())
            except OSError: return '127.0.0.1'

base=f'http://127.0.0.1:{args.porta}'
if args.rete and not os.environ.get('PUBLIC_URL'):
    ip=local_ipv4()
    if ip.startswith('127.'):
        sys.exit('Impossibile individuare l’indirizzo della rete. Imposta PUBLIC_URL con l’indirizzo LAN del computer e riprova.')
    os.environ['PUBLIC_URL']=f'http://{ip}:{args.porta}'
print('\nEscalation Trivial\n', flush=True)
print(f'Regia docente   {base}/docente\nProiettore      {base}/schermo\nGiocatori       {os.environ.get("PUBLIC_URL",base)}/',flush=True)
if private.exists(): print(f'Password docente e chiave di sessione nel file privato {private}',flush=True)
print('Per terminare, premi Ctrl+C nella finestra del server.\n',flush=True)
if not args.senza_browser:
    timer=Timer(1.2, webbrowser.open, args=(base+'/docente',));timer.daemon=True;timer.start()
uvicorn.run('app:app', host='0.0.0.0' if args.rete else '127.0.0.1', port=args.porta, workers=1)
