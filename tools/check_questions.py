from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalogue import load_catalogue

questions = load_catalogue(ROOT / 'questions.json')
print(f'{len(questions)} domande valide. ID, testi, alternative e indici di risposta verificati.')
for label, key in [('Categorie','category'), ('Difficoltà','difficulty'), ('Formati','type')]:
    print(label, dict(Counter(q[key] for q in questions)))
for kind in ('AB','MULTI'):
    positions=Counter('ABCD'[q['correct']] for q in questions if q['type']==kind)
    print(kind, 'posizioni corrette', dict(sorted(positions.items())))
