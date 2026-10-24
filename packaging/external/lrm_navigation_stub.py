"""Safe browser fallback for installations without the creator's LRM engine."""
from __future__ import annotations

import webbrowser


def navigate(parameters):
    if str(parameters.get("action") or "") == "go_to":
        url = str(parameters.get("url") or "").strip()
        if url.startswith(("https://", "http://")):
            return "Navegação encaminhada" if webbrowser.open(url) else "Não foi possível abrir o navegador."
    return "LRM privado indisponível nesta edição."


def install_web_routing():
    return None
