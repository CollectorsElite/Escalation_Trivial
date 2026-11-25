"""Optional quiz illustrations. Canonical WebP bytes live on the same volume as the questions."""
import base64
import binascii
import hashlib
from io import BytesIO
import re

from fastapi import HTTPException
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024
MAX_B64 = ((MAX_BYTES + 2) // 3) * 4
MAX_QUESTION_BODY = MAX_B64 + 64 * 1024
IMAGE_ID = re.compile(r'[0-9a-f]{64}')


def install_media(db, catalogue, directory):
    db.execute('CREATE TABLE IF NOT EXISTS question_images (id TEXT PRIMARY KEY, content BLOB NOT NULL)')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(questions)')}
    if 'image_id' not in columns:
        db.execute('ALTER TABLE questions ADD COLUMN image_id TEXT REFERENCES question_images(id)')
    if 'image_alt' not in columns:
        db.execute("ALTER TABLE questions ADD COLUMN image_alt TEXT NOT NULL DEFAULT ''")
    for image_id in {q['image'] for q in catalogue if q.get('image')}:
        if not IMAGE_ID.fullmatch(image_id):
            raise ValueError('Identificativo immagine non valido nel catalogo.')
        if db.execute('SELECT 1 FROM question_images WHERE id=?', (image_id,)).fetchone():
            continue
        data = (directory / (image_id + '.webp')).read_bytes()
        if hashlib.sha256(data).hexdigest() != image_id:
            raise ValueError('Illustrazione del catalogo danneggiata.')
        db.execute('INSERT INTO question_images VALUES (?,?)', (image_id, data))


def normalize_upload(encoded):
    if not isinstance(encoded, str) or not encoded:
        raise HTTPException(400, detail='Scegli un file immagine.')
    if len(encoded) > MAX_B64:
        raise HTTPException(413, detail='L’immagine supera il limite di 5 MB.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, detail='Il file ricevuto è incompleto o illeggibile.')
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, detail='L’immagine supera il limite di 5 MB.')
    try:
        with Image.open(BytesIO(raw), formats=('JPEG','PNG','WEBP')) as source:
            if source.width * source.height > 24_000_000:
                raise HTTPException(400, detail='L’immagine supera il limite di 24 megapixel.')
            if getattr(source, 'n_frames', 1) != 1:
                raise HTTPException(400, detail='Scegli un’immagine fissa, senza animazione.')
            source.load()
            oriented = ImageOps.exif_transpose(source)
            has_alpha = 'A' in oriented.getbands() or 'transparency' in oriented.info
            pixels = oriented.convert('RGBA' if has_alpha else 'RGB')
            pixels.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
            pixels.info.clear()
            output = BytesIO()
            pixels.save(output, format='WEBP', lossless=source.format=='PNG', quality=89, method=4)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(400, detail='Il file non è un’immagine JPG, PNG o WebP valida.')
    data = output.getvalue()
    return hashlib.sha256(data).hexdigest(), data


def apply_media(db, body, current, upload):
    """Resolve a saved reference or an optional new upload inside the question transaction."""
    image_id = body.get('image', current.get('image'))
    if upload is not None:
        image_id, data = upload
        db.execute('INSERT OR IGNORE INTO question_images VALUES (?,?)', (image_id, data))
    elif image_id is not None:
        if (not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id) or
                not db.execute('SELECT 1 FROM question_images WHERE id=?', (image_id,)).fetchone()):
            raise HTTPException(400, detail='Immagine non disponibile. Seleziona nuovamente il file.')
    if image_id is None:
        return None, ''
    alt = body.get('imageAlt', current.get('imageAlt', ''))
    if not isinstance(alt, str) or len(alt.strip()) > 600:
        raise HTTPException(400, detail='La descrizione dell’immagine può contenere fino a 600 caratteri.')
    return image_id, alt.strip()


def release_unused(db, image_id):
    # A past round or another question can still display a replaced picture.
    db.execute("""DELETE FROM question_images WHERE id=?
        AND NOT EXISTS (SELECT 1 FROM questions WHERE image_id=?)
        AND NOT EXISTS (SELECT 1 FROM game_questions WHERE json_extract(payload,'$.image')=?)""",
        (image_id, image_id, image_id))
