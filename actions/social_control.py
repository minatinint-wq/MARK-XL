from __future__ import annotations

import os
import re
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from actions.operation_memory import record_operation


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def _write_log(player, text: str) -> None:
    try:
        if player:
            player.write_log(text)
    except Exception:
        pass


def _open_url(url: str, wait: float = 1.2) -> str:
    webbrowser.open(url)
    time.sleep(max(0.0, min(float(wait), 8.0)))
    return f"Aberto: {url}"


def _digits(text: str) -> str:
    return re.sub(r"\D+", "", str(text or ""))


def _slug_user(text: str) -> str:
    text = str(text or "").strip()
    text = text.strip("@").strip("/")
    text = re.sub(r"[^A-Za-z0-9._]", "", text)
    return text


def _copy(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def _send_enter(delay: float = 2.5) -> bool:
    try:
        import pyautogui
        time.sleep(max(0.0, min(float(delay), 8.0)))
        pyautogui.press("enter")
        return True
    except Exception:
        return False


def _whatsapp_url(receiver: str = "", message: str = "") -> str:
    digits = _digits(receiver)
    encoded = urllib.parse.quote(message or "")
    if digits:
        base = f"https://wa.me/{digits}"
        return f"{base}?text={encoded}" if encoded else base
    return "https://web.whatsapp.com/"


def _instagram_profile_url(username: str) -> str:
    user = _slug_user(username)
    return f"https://www.instagram.com/{user}/" if user else "https://www.instagram.com/"


def _instagram_post_url(post: str) -> str:
    post = str(post or "").strip()
    if post.startswith("http://") or post.startswith("https://"):
        return post
    code = post.strip("/").split("/")[-1]
    return f"https://www.instagram.com/p/{code}/" if code else "https://www.instagram.com/explore/"


def _platform(params: dict[str, Any]) -> str:
    return str(params.get("platform") or params.get("app") or params.get("service") or "whatsapp").lower().strip()


def _send_via_existing_action(platform: str, receiver: str, message: str, player=None) -> str:
    from actions.send_message import send_message
    return send_message(
        parameters={
            "platform": platform,
            "receiver": receiver,
            "message_text": message,
        },
        response=None,
        player=player,
        session_memory=None,
    )


def social_control(parameters: dict[str, Any] | None = None, player=None, speak=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").lower().strip()
    platform = _platform(params)
    receiver = str(params.get("receiver") or params.get("contact") or params.get("to") or "").strip()
    message = str(params.get("message") or params.get("message_text") or params.get("text") or "").strip()
    username = str(params.get("username") or params.get("profile") or receiver or "").strip()
    post = str(params.get("post") or params.get("url") or params.get("shortcode") or "").strip()
    send_now = bool(params.get("send") or action in {"send", "send_message", "mandar", "enviar"})
    record_operation(
        "social",
        action,
        {
            "platform": platform,
            "receiver": receiver,
            "username": username,
            "post": post,
            "message": message,
        },
        sensitive=True,
    )

    _write_log(player, f"[Social] {platform}:{action}")

    if action in {"status", "help", "ajuda"}:
        return (
            "Social Control pronto para WhatsApp e Instagram: open, open_chat, send_message, "
            "open_profile, open_post, view_posts, view_conversations/direct, copy_message. "
            "Usa contas ja logadas no navegador/app e nao burla login ou restricoes da plataforma."
        )

    if platform in {"whatsapp", "wp", "wpp", "zap", "zapzap"}:
        if os.environ.get("MARK_XL_GLOW_ONLY") == "1":
            if action in {"open", "web", "home", "open_chat", "chat", "conversation", "view_conversation", "conversa"}:
                if player and hasattr(player, "open_bird_local"):
                    player.open_bird_local()
                    return "Painel WhatsApp Bird local aberto no Jarvis."
                return "Painel WhatsApp Bird local indisponível."
            if action in {"send", "send_message", "mandar", "enviar"}:
                from actions.send_message import send_message
                return send_message({"platform": "whatsapp", "receiver": receiver, "message_text": message}, player=player)
            return "Na edição leve, WhatsApp usa apenas a Bird local para abrir e enviar."
        if action in {"open", "web", "home"}:
            return _open_url("https://web.whatsapp.com/")

        if action in {"open_chat", "chat", "conversation", "view_conversation", "conversa"}:
            if receiver and _digits(receiver):
                return _open_url(_whatsapp_url(receiver))
            _open_url("https://web.whatsapp.com/")
            if receiver:
                copied = _copy(receiver)
                return f"WhatsApp Web aberto. Contato copiado para busca: {'sim' if copied else 'nao'}."
            return "WhatsApp Web aberto."

        if action in {"send", "send_message", "mandar", "enviar"}:
            if not receiver or not message:
                return "Informe receiver e message para enviar pelo WhatsApp."
            if _digits(receiver):
                _open_url(_whatsapp_url(receiver, message), wait=4.0)
                if send_now:
                    pressed = _send_enter()
                    return f"WhatsApp preparado para {receiver}. Envio por Enter: {'executado' if pressed else 'nao disponivel'}."
                return "WhatsApp aberto com mensagem preenchida; revise e pressione enviar."
            return _send_via_existing_action("whatsapp", receiver, message, player=player)

        if action in {"copy_message", "copy", "copiar"}:
            if not message:
                return "Informe message/text para copiar."
            return "Mensagem copiada." if _copy(message) else "Nao consegui copiar a mensagem."

        return "Acao WhatsApp desconhecida. Use open, open_chat ou send_message."

    if platform in {"instagram", "ig", "insta"}:
        if action in {"open", "home"}:
            return _open_url("https://www.instagram.com/")

        if action in {"direct", "dm", "inbox", "view_conversations", "conversations", "mensagens"}:
            return _open_url("https://www.instagram.com/direct/inbox/")

        if action in {"open_chat", "chat", "conversation", "view_conversation", "conversa"}:
            _open_url("https://www.instagram.com/direct/inbox/")
            if receiver:
                copied = _copy(receiver)
                return f"Instagram Direct aberto. Usuario/contato copiado para busca: {'sim' if copied else 'nao'}."
            return "Instagram Direct aberto."

        if action in {"open_profile", "profile", "perfil", "view_posts", "posts"}:
            return _open_url(_instagram_profile_url(username))

        if action in {"open_post", "post", "reel", "ver_post"}:
            return _open_url(_instagram_post_url(post))

        if action in {"explore", "search", "buscar"}:
            query = urllib.parse.quote(str(params.get("query") or username or ""))
            if query:
                return _open_url(f"https://www.instagram.com/explore/search/keyword/?q={query}")
            return _open_url("https://www.instagram.com/explore/")

        if action in {"send", "send_message", "mandar", "enviar"}:
            if not receiver or not message:
                return "Informe receiver e message para enviar pelo Instagram."
            return _send_via_existing_action("instagram", receiver, message, player=player)

        if action in {"copy_message", "copy", "copiar"}:
            if not message:
                return "Informe message/text para copiar."
            return "Mensagem copiada." if _copy(message) else "Nao consegui copiar a mensagem."

        return "Acao Instagram desconhecida. Use direct, open_profile, open_post ou send_message."

    return "Plataforma social suportada agora: WhatsApp e Instagram."
