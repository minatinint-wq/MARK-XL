from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from actions.runtime_identity import APP_ROOT

def _studio_path() -> Path:
    configured = os.environ.get("JARVIS_NVIDIA_STUDIO", "").strip()
    candidates = ([Path(configured)] if configured else []) + [
        APP_ROOT / "NVIDIA_AI_ART_STUDIO" / "art_studio.py",
        APP_ROOT.parent / "NVIDIA_AI_ART_STUDIO" / "art_studio.py",
        APP_ROOT.parent.parent / "NVIDIA_AI_ART_STUDIO" / "art_studio.py",
        Path.home() / "Desktop" / "NVIDIA_AI_ART_STUDIO" / "art_studio.py",
    ]
    for candidate in candidates:
        script = candidate / "art_studio.py" if candidate.is_dir() else candidate
        if script.is_file():
            return script
    return candidates[0]


def nvidia_camera_lab(parameters=None, response=None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").strip().casefold()
    studio = _studio_path()
    if action == "status":
        return "NVIDIA Camera Lab pronto para abrir." if studio.is_file() else "NVIDIA Camera Lab não instalado neste PC; o Studio é separado do Jarvis."
    if action not in {"open", "abrir", "start", "iniciar", "toggle"}:
        return "Use action=open para abrir o NVIDIA Camera Lab."
    if not studio.is_file():
        return "NVIDIA Camera Lab não instalado neste PC. Instale o NVIDIA_AI_ART_STUDIO ou configure JARVIS_NVIDIA_STUDIO com o caminho de art_studio.py."
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(Path(sys.executable)), str(studio), "--tab", "camera"],
        cwd=str(studio.parent),
        creationflags=flags,
    )
    return "NVIDIA Camera Lab aberto na aba de reconhecimento de objetos, pessoas e gestos."
