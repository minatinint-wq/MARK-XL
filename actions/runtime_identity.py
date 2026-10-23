"""Single source of truth for the installed Jarvis protocol and app paths."""
from pathlib import Path
import json
APP_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((APP_ROOT / 'core' / 'protocol.json').read_text(encoding='utf-8-sig'))
PROTOCOL_NUMBER = int(PROTOCOL['number'])
MARK_NAME = 'MARK ' + PROTOCOL['roman']
WINDOW_TITLE = 'J.A.R.V.I.S — ' + MARK_NAME

def protocol_context():
    features = '; '.join(feature for stage in PROTOCOL['stages'] for feature in stage['features'])
    return (f'[INSTALLED JARVIS PROTOCOL]\nYou are JARVIS {MARK_NAME}, protocolo {PROTOCOL_NUMBER}. '
            f'Current installation: {APP_ROOT}. This is authoritative runtime identity; older versions in memory are historical. '
            f'When asked your version or protocol, answer {MARK_NAME}, protocolo {PROTOCOL_NUMBER}, in Portuguese. '
            f'Installed features: {features}. Do not claim a camera, cloud API or microphone is connected without checking its actual state.\n')
