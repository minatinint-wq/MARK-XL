from __future__ import annotations

from typing import Any


def jarvis_lab(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").lower().strip()

    if player is None:
        return "Nexus Lab indisponivel: UI do Jarvis nao foi encontrada."

    if action in {"status", "info", "modules", "modulos"}:
        return (
            "Nexus Lab pronto: LAB, 05 memoria auditiva, 07 automacao, "
            "08 visao/camera, 09 cerebro neural e 11 busca/assets."
        )

    if action in {"close", "fechar", "stop", "hide"}:
        close = getattr(player, "close_lab_screen", None)
        if callable(close):
            close()
            return "Nexus Lab fechado."
        return "A UI atual nao expoe fechamento do Nexus Lab."

    if action in {"toggle", "alternar"}:
        toggle = getattr(player, "toggle_lab_screen", None)
        if callable(toggle):
            toggle()
            return "Nexus Lab alternado."
        return "A UI atual nao expoe alternancia do Nexus Lab."

    open_lab = getattr(player, "open_lab_screen", None)
    if callable(open_lab):
        open_lab()
        return "Nexus Lab aberto como tela complementar."

    return "A UI atual nao expoe abertura do Nexus Lab."
