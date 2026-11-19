"""Check the actual lobby and QR routes with public-host settings. No network is used."""
import os
from pathlib import Path
import secrets
import sys
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix='trivial-public-url-') as data:
        password = secrets.token_urlsafe(24)
        config = {'DATA_DIR':data, 'ADMIN_PASSWORD':password, 'SESSION_SECRET':secrets.token_hex(32)}
        with patch.dict(os.environ, config):
            from app import app, qr_png
            origin = 'https://ingresso.example.test'
            cases = [
                ('', '', None, origin),
                ('', 'quiz.example.test', 'https://quiz.example.test', 'https://quiz.example.test'),
                ('https://formazione.example.test/', 'quiz.example.test',
                 'https://formazione.example.test', 'https://formazione.example.test'),
            ]
            with TestClient(app, base_url=origin) as browser:
                login = browser.post('/api/admin/login', json={'password':password})
                login.raise_for_status()
                lobby = browser.post('/api/admin/create', json={'ids':['PHI-001'],'duration':30})
                lobby.raise_for_status()
                pin = lobby.json()['game']['pin']
                for override, supplied, public, target in cases:
                    with patch.dict(os.environ, {'PUBLIC_URL':override,'RAILWAY_PUBLIC_DOMAIN':supplied}):
                        snapshot = browser.get('/api/screen')
                        snapshot.raise_for_status()
                        assert snapshot.json()['game']['public_url'] == public
                        response = browser.get('/api/admin/qr', params={'pin':pin})
                        response.raise_for_status()
                        assert response.headers['content-type'] == 'image/png'
                        assert response.content == qr_png(f'{target}/?pin={pin}')
                assert browser.get('/health').json() == {'status':'ok','question_count':100}
    print('OK: Railway public domain, custom domain, request-origin fallback, QR, PIN and health')


if __name__ == '__main__':
    main()
