"""Small local activity bridge; never publishes note content or filesystem paths."""
from contextlib import contextmanager
from pathlib import Path
import json
import re
import threading
import time
import unicodedata
import uuid

ACTIVITY_PATH = Path(__file__).resolve().parent.parent / 'memory' / 'brain_activity.js'
_lock = threading.Lock()
_active = {}
_revision = 0


def is_note_count_request(text: str) -> bool:
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').lower()) if not unicodedata.combining(c))
    value = re.sub(r'[^a-z0-9 ]+', ' ', value)
    value = ' '.join(value.split())
    value = re.sub(r'^jarvis ', '', value)
    value = re.sub(r'^(?:por favor |pfv )', '', value)
    value = re.sub(r' (?:por favor|pfv)$', '', value)
    value = re.sub(r'^(?:leia|le|veja|ve|me diga|diga|me fala|fala) ', '', value)
    place = r'(?:no|do|em|na|da) (?:meu |seu |nosso )?(?:obsidian|obisidian|cerebro|vault|cofre)'
    return bool(re.fullmatch(
        rf'(?:quantas notas(?: (?:tem|ha|existem|tenho|voce tem|temos))? {place}'
        rf'|(?:conte|conta|contar) (?:todas )?(?:as )?notas {place}'
        rf'|qual (?:e )?(?:o )?(?:total|numero|quantidade) de notas {place})', value))


def _publish(player, token, starting, failed=False):
    global _revision
    now = time.time() * 1000
    with _lock:
        if starting:
            _active[token] = now
        started = _active.get(token, now)
        if not starting:
            _active.pop(token, None)
        _revision = max(_revision + 1, time.time_ns())
        payload = {'revision': str(_revision), 'updated_at': now,
                   'started_at': min(_active.values()) if _active else started,
                   'active': bool(_active), 'operation': 'count_notes',
                   'phase': 'reading' if _active else ('error' if failed else 'complete')}
        # Atomic replacement means a browser never evaluates a half-written script.
        temp = ACTIVITY_PATH.with_suffix('.tmp')
        try:
            ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text('window.JARVIS_BRAIN_ACTIVITY=' + json.dumps(payload, separators=(',', ':')) + ';\n', encoding='utf-8')
            temp.replace(ACTIVITY_PATH)
        except OSError:
            pass  # Visual feedback must never prevent a real vault query.
        try:
            callback = getattr(player, 'update_brain_activity', None)
            if callable(callback):
                callback(payload)
        except Exception:
            pass
        return payload


@contextmanager
def reading_notes(player=None):
    token = uuid.uuid4().hex
    _publish(player, token, True)
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        _publish(player, token, False, failed)
