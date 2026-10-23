"""Keep native exception stacks locally, including launches from a console."""
from __future__ import annotations

import faulthandler
import os
from datetime import datetime
from pathlib import Path

_stream = None


def enable_native_diagnostics(base):
    global _stream
    if _stream is not None:
        return
    try:
        path = Path(base) / 'logs' / 'native_crash.log'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 2_000_000:
            path.replace(path.with_suffix('.previous.log'))
        _stream = path.open('a', encoding='utf-8', buffering=1)
        _stream.write(f'\n=== START {datetime.now().isoformat(timespec="seconds")} pid={os.getpid()} ===\n')
        # faulthandler writes native failures even when Python cannot catch them.
        # Do not log arguments, environment variables, camera frames, or credentials.
        faulthandler.enable(file=_stream, all_threads=True)
    except (OSError, RuntimeError):
        pass
