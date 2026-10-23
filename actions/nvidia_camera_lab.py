from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from actions.runtime_identity import APP_ROOT

STUDIO = Path.home() / "Desktop" / "NVIDIA_AI_ART_STUDIO" / "art_studio.py"
BUNDLED_PYTHON = APP_ROOT / "Python" / "bin" / "python.exe"


def nvidia_camera_lab(parameters=None, response=None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").strip().casefold()
    if action == "status":
        return "O NVIDIA Camera Lab esta instalado e pronto para abrir."
    if action not in {"open", "abrir", "start", "iniciar", "toggle"}:
        return "Use action=open para abrir o NVIDIA Camera Lab."
    if not STUDIO.exists():
        return f"NVIDIA Camera Lab nao encontrado em {STUDIO}"
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(BUNDLED_PYTHON if BUNDLED_PYTHON.exists() else Path(sys.executable)), str(STUDIO), "--tab", "camera"],
        cwd=str(STUDIO.parent),
        creationflags=flags,
    )
    return "NVIDIA Camera Lab aberto na aba de reconhecimento de objetos, pessoas e gestos."
