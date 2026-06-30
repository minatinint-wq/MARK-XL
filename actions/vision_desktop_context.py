from __future__ import annotations

import base64
import ctypes
import io
import sys
from dataclasses import dataclass
from typing import Optional

try:
    import mss
    import mss.tools
    _MSS = True
except Exception:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except Exception:
    _PIL = False


@dataclass
class WindowInfo:
    title: str
    left: int
    top: int
    width: int
    height: int


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def foreground_window_info() -> Optional[WindowInfo]:
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        title_len = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(title_len + 1)
        user32.GetWindowTextW(hwnd, title_buf, title_len + 1)

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width < 80 or height < 80:
            return None

        return WindowInfo(
            title=(title_buf.value or "janela ativa").strip(),
            left=int(rect.left),
            top=int(rect.top),
            width=width,
            height=height,
        )
    except Exception:
        return None


def _compress(img_bytes: bytes, max_w: int, max_h: int, jpeg_q: int) -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, "image/png"
    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((max_w, max_h), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return img_bytes, "image/png"


def capture_foreground_window(max_w: int = 1800, max_h: int = 1200, jpeg_q: int = 88) -> tuple[bytes, str, Optional[WindowInfo]] | None:
    info = foreground_window_info()
    if not info or not _MSS:
        return None
    try:
        with mss.mss() as sct:
            region = {
                "left": info.left,
                "top": info.top,
                "width": info.width,
                "height": info.height,
            }
            shot = sct.grab(region)
            png = mss.tools.to_png(shot.rgb, shot.size)
        img_bytes, mime_type = _compress(png, max_w=max_w, max_h=max_h, jpeg_q=jpeg_q)
        return img_bytes, mime_type, info
    except Exception:
        return None


def _looks_like_call_or_discord(text: str, title: str = "") -> bool:
    haystack = f"{text or ''} {title or ''}".lower()
    terms = (
        "discord",
        "call",
        "chamada",
        "ligacao",
        "ligação",
        "voz",
        "voice",
        "quem ta",
        "quem tá",
        "quem esta",
        "quem está",
        "participante",
        "participantes",
        "call comigo",
    )
    return any(term in haystack for term in terms)


def make_vision_turn_parts(
    image_bytes: bytes,
    mime_type: str,
    user_text: str,
    *,
    mode: str = "screen",
    log_prefix: str = "[Vision]",
) -> list[dict]:
    parts: list[dict] = [
        {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("ascii"),
            }
        }
    ]

    labels = ["Imagem 1: captura principal."]
    active_info = foreground_window_info() if mode == "screen" else None

    if mode == "screen":
        focused = capture_foreground_window()
        if focused:
            crop_bytes, crop_mime, crop_info = focused
            parts.append(
                {
                    "inline_data": {
                        "mime_type": crop_mime,
                        "data": base64.b64encode(crop_bytes).decode("ascii"),
                    }
                }
            )
            active_info = crop_info or active_info
            title = active_info.title if active_info else "janela ativa"
            labels.append(f"Imagem 2: recorte ampliado da janela ativa: {title}.")
            print(f"{log_prefix} 🔍 Added active-window crop: {title}")

    title = active_info.title if active_info else "não identificada"
    call_mode = _looks_like_call_or_discord(user_text, title)
    call_instruction = (
        "Se for Discord ou chamada/call, foque primeiro em identificar os participantes visíveis: "
        "nomes na lista lateral, cards da chamada, avatares com nomes, quem está conectado e quem está falando. "
        "Não responda apenas 'Discord está aberto'. Se algum nome estiver pequeno/ilegível, diga claramente que não consegue ler e peça para abrir/ampliar a lista de participantes. "
        "Nunca invente nomes."
        if call_mode
        else "Se houver texto pequeno importante, leia somente o que estiver legível e diga quando não conseguir ler."
    )

    prompt = (
        "Responda sempre em português brasileiro natural. "
        "Não use inglês nas respostas do modo visão. "
        "Não chame o usuário de 'sir'. "
        f"{' '.join(labels)} "
        f"Janela ativa detectada: {title}. "
        f"{call_instruction} "
        f"Pergunta do usuário: {user_text or 'Descreva o que você vê na tela.'}"
    )
    parts.append({"text": prompt})
    return parts
