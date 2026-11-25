"""Integration checks for question illustrations and for all 27 imported PCTO exercises."""
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CATALOG = '/api/admin/catalogue'
MEDIA = '/api/question-images/'
KEY = 'b' * 32
QID = 'DOC-' + KEY


def encoded_image(kind, color, size=(160,90), **kwargs):
    output = BytesIO()
    Image.new('RGB', size, color).save(output,format=kind,**kwargs)
    return base64.b64encode(output.getvalue()).decode('ascii')


def ok(response):
    response.raise_for_status()
    return response.json()


def check_media_response(client, image_id):
    response=client.get(MEDIA + image_id)
    response.raise_for_status()
    assert response.headers['content-type']=='image/webp'
    assert 'immutable' in response.headers['cache-control'] and response.headers['x-content-type-options']=='nosniff'
    assert hashlib.sha256(response.content).hexdigest()==image_id
    conditional=client.get(MEDIA+image_id,headers={'If-None-Match':response.headers['etag']})
    assert conditional.status_code==304 and conditional.content==b''
    with Image.open(BytesIO(response.content)) as img:
        assert img.format=='WEBP' and not img.getexif()
        img.load()
        return img.size


def question_fields(q):
    return {**{k:q[k] for k in ('text','options','correct','explanation','difficulty')}, 'categoryId':q['category_id']}


def write(client, db):
    assert client.post(CATALOG,json={}).status_code==401
    assert client.get(MEDIA+'missing').status_code==404
    assert client.get(MEDIA+'0'*64).status_code==404
    ok(client.post('/api/admin/login',json={'password':os.environ['ADMIN_PASSWORD']}))
    questions=ok(client.get('/api/admin/overview'))['questions']
    pcto=[q for q in questions if q['category_id']=='PCTO']
    assert [q['id'] for q in pcto]==[f'PCTO-{n:03}' for n in range(1,28)]
    assert ''.join('ABCD'[q['correct']] for q in pcto)=='BBCCCAABBDCDDBDCBDABBBBADAA'
    assert [q['id'] for q in pcto if q['type']=='AB']==['PCTO-008','PCTO-014','PCTO-027']
    assert len({q['image'] for q in pcto})==27 and all(q['imageAlt'] for q in pcto)
    assert all('image' not in q for q in questions if q['category_id']!='PCTO')
    for q in pcto:
        check_media_response(client,q['image'])
    assert [q['correct'] for q in pcto[2:6]]==[2,2,2,0]
    assert check_media_response(client,pcto[22]['image'])==(670,137)
    media_count=lambda:db.execute('SELECT count(*) FROM question_images').fetchone()[0]
    assert media_count()==27
    fields=dict(text='Quale traccia vedi nella figura?',options=['Un cerchio','Una linea'],correct=1,
                explanation='La figura di prova mostra una linea.',difficulty='Base',categoryId='PCTO',creationKey=KEY)
    exif=Image.Exif();exif[274]=6;exif[315]='Autore del test'
    jpeg=encoded_image('JPEG','red',(300,100),exif=exif)
    png=encoded_image('PNG','blue',(2801,100))
    webp=encoded_image('WEBP','yellow')
    for change,status in [
        ({'imageUpload':'not a file'},400),
        ({'imageUpload':base64.b64encode(b'<svg></svg>').decode()},400),
        ({'image':'0'*64},400),({'image':3},400),
        ({'imageUpload':png,'correct':8},400),({'imageUpload':png,'imageAlt':'x'*601},400),
        ({'imageUpload':'A'*6_991_000},413),({'imageUpload':'A'*7_100_000},413),
        ({'imageUpload':encoded_image('PNG','white',(6000,4001))},400)]:
        assert client.post(CATALOG,json=fields|change).status_code==status
        assert media_count()==27
    frames=BytesIO()
    Image.new('RGB',(16,16),'red').save(frames,format='PNG',save_all=True,
        append_images=[Image.new('RGB',(16,16),'green')],duration=100,loop=0)
    assert client.post(CATALOG,json=fields|{'imageUpload':base64.b64encode(frames.getvalue()).decode()}).status_code==400
    assert media_count()==27
    initial=fields|{'imageUpload':jpeg,'imageAlt':'Una traccia rossa.'}
    first=ok(client.post(CATALOG,json=initial))
    assert first['id']==QID and first['revision']==1 and first['imageAlt']==initial['imageAlt']
    assert ok(client.post(CATALOG,json=initial))==first and media_count()==28
    assert check_media_response(client,first['image'])==(100,300)
    # A legacy editor can still save a text-only request without losing the attachment.
    path=CATALOG+'/'+QID
    assert ok(client.put(path,json=fields|{'expectedRevision':1}))==first
    copy=ok(client.post(CATALOG,json=fields|{'creationKey':'c'*32,'text':'Dove vedi la traccia rossa?',
                                             'image':first['image'],'imageAlt':'Traccia rossa.'}))
    assert media_count()==28 and copy['image']==first['image']
    changed=ok(client.put(path,json=fields|{'expectedRevision':1,'imageUpload':png,'imageAlt':'Linea blu.'}))
    assert changed['revision']==2 and changed['image']!=first['image']
    assert check_media_response(client,changed['image'])==(2400,86)
    assert check_media_response(client,first['image'])==(100,300)
    assert client.put(path,json=fields|{'expectedRevision':1,'imageUpload':webp}).status_code==409
    assert media_count()==29
    # In a visual exercise the same wording and alternatives can apply to two different pictures.
    other=ok(client.post(CATALOG,json=fields|{'creationKey':'d'*32,'imageUpload':webp,'imageAlt':'Linea gialla.'}))
    check_media_response(client,other['image'])
    removed=ok(client.put(CATALOG+'/'+other['id'],json=fields|{'expectedRevision':1,'image':None}))
    assert 'image' not in removed and 'imageAlt' not in removed
    assert client.get(MEDIA+other['image']).status_code==404
    assert media_count()==29
    game=ok(client.post('/api/admin/create',json={'ids':[QID,'PCTO-006'],'duration':120,'revealOnComplete':False}))['game']
    p=ok(client.post('/api/join',json={'pin':game['pin'],'nickname':'Verifica immagini'}))
    ident={k:p[k] for k in ('playerId','token')}|{'pin':game['pin']}
    def action(name):
        return ok(client.post('/api/admin/action',json={'action':name,'gameId':game['id']}))
    def take(ws,status):
        while True:
            event=ws.receive_json()
            if event['type']=='snapshot' and event['game']['status']==status:
                return event
    with client.websocket_connect('/ws/play') as ws:
        ws.send_json(dict(type='hello',**ident))
        take(ws,'lobby')
        action('start')
        student=take(ws,'question')['question']
        projection=ok(client.get('/api/screen'))['question']
        teacher=ok(client.get('/api/admin/overview'))['snapshot']['question']
        for view in (student,projection,teacher):
            assert (view['image'],view['imageAlt'])==(changed['image'],'Linea blu.')
        assert 'correct' not in student and 'correct' not in projection and 'explanation' not in projection
        assert teacher['correct']==1
        # The frozen lesson retains its illustration after later changes to the question.
        saved=ok(client.put(path,json=fields|{'expectedRevision':2,'imageUpload':jpeg,'imageAlt':'Linea rossa.'}))
        assert saved['revision']==3 and saved['image']==first['image']
        assert check_media_response(client,changed['image'])==(2400,86)
        action('reveal');take(ws,'results')
        action('next')
        assert take(ws,'question')['question']['image']==pcto[5]['image']
        action('reveal');take(ws,'results')
        action('finish');take(ws,'finished')
    rounds=ok(client.post('/api/player/review',json=ident))['rounds']
    assert [r['image'] for r in rounds]==[changed['image'],pcto[5]['image']]
    # When a bundled illustration is removed it stays removed after restarting.
    q=pcto[8]
    no_picture=ok(client.put(CATALOG+'/'+q['id'],json=question_fields(q)|{'expectedRevision':0,'image':None}))
    assert no_picture['revision']==1 and 'image' not in no_picture


def restart(client, db):
    ok(client.post('/api/admin/login',json={'password':os.environ['ADMIN_PASSWORD']}))
    q=ok(client.get(CATALOG+'/'+QID))
    assert q['imageAlt']=='Linea rossa.' and q['revision']==3
    assert check_media_response(client,q['image'])==(100,300)
    assert 'image' not in ok(client.get(CATALOG+'/PCTO-009'))
    lesson=json.loads(db.execute('SELECT payload FROM game_questions WHERE question_id=?',(QID,)).fetchone()[0])
    assert lesson['imageAlt']=='Linea blu.' and check_media_response(client,lesson['image'])==(2400,86)


if __name__=='__main__':
    if len(sys.argv)==1:
        with tempfile.TemporaryDirectory(prefix='pcto-media-') as volume:
            env=dict(os.environ,DATA_DIR=volume,ADMIN_PASSWORD='local-media-test',SESSION_SECRET='local-media-secret')
            for phase in ('write','restart'):
                subprocess.run([sys.executable,__file__,phase],env=env,check=True)
        print('OK 27 immagini e chiavi PCTO, upload e sostituzione JPG/PNG/WebP, copia delle domande, rimozione, tre viste, ripasso e riavvio')
    else:
        import app
        with TestClient(app.app) as session:
            (write if sys.argv[1]=='write' else restart)(session,app.conn)
