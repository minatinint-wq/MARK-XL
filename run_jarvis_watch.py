"""Inicia o JARVIS e reinicia somente quando o código for alterado.

Use este arquivo para manter a instalação em modo de desenvolvimento. Ele não
vigia memória, vídeos, imagens nem logs, portanto uma ação normal do JARVIS não
causa reinicialização.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WATCHED_FILES = (ROOT / "main.py", ROOT / "ui.py")
WATCHED_DIRECTORIES = (ROOT / "actions", ROOT / "agent", ROOT / "core")
CHECK_INTERVAL_SECONDS = 1.0


def source_fingerprint() -> tuple[tuple[str, int], ...]:
    """Return a stable snapshot of executable Python sources only."""
    files = [path for path in WATCHED_FILES if path.is_file()]
    for directory in WATCHED_DIRECTORIES:
        if directory.is_dir():
            files.extend(directory.rglob("*.py"))
    return tuple(sorted((str(path.relative_to(ROOT)), path.stat().st_mtime_ns) for path in files))


def spawn_jarvis() -> subprocess.Popen:
    print("[JARVIS WATCH] Iniciando JARVIS.", flush=True)
    return subprocess.Popen([sys.executable, "main.py"], cwd=ROOT)


def stop_jarvis(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    print("[JARVIS WATCH] Atualização detectada. Reiniciando JARVIS...", flush=True)
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    snapshot = source_fingerprint()
    child = spawn_jarvis()
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            current = source_fingerprint()
            if current != snapshot:
                snapshot = current
                stop_jarvis(child)
                child = spawn_jarvis()
            elif child.poll() is not None:
                # Preserva o comportamento normal de relançar após uma queda.
                print(f"[JARVIS WATCH] Processo encerrou ({child.returncode}); relançando em 2 s.", flush=True)
                time.sleep(2)
                snapshot = source_fingerprint()
                child = spawn_jarvis()
    except KeyboardInterrupt:
        print("\n[JARVIS WATCH] Encerrando.", flush=True)
    finally:
        stop_jarvis(child)


if __name__ == "__main__":
    main()
