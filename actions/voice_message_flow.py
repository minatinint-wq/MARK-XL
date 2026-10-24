"""Deterministic, review-before-send WhatsApp voice workflow."""
from __future__ import annotations

import re
import unicodedata


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).casefold().split())


class VoiceMessageFlow:
    def __init__(self):
        self.receiver = ""
        self.message = ""
        self.stage = "idle"

    def reset(self):
        self.receiver = self.message = ""
        self.stage = "idle"

    def accept(self, text: str) -> tuple[str, str, str] | None:
        """Return (event, receiver, message); never sends anything."""
        raw = " ".join(str(text or "").strip().split())
        raw = re.sub(r"^jarvis[\s,.:;-]+", "", raw, flags=re.I)
        plain = _plain(raw)
        if not plain:
            return None
        if self.stage != "idle":
            if plain in {"cancelar", "cancela", "cancelar mensagem", "esquece mensagem", "nao enviar"}:
                self.reset()
                return ("cancel", "", "")
            if self.stage == "awaiting_text":
                message = re.sub(r"^(?:mensagem|texto|dizer|ditar)(?:\s*(?::|e|eh)\s*)?", "", raw, flags=re.I).strip() or raw
                if _plain(message) in {"enviar", "confirmar", "confirmar envio"}:
                    return ("need_text", self.receiver, "")
                self.message = message
                self.stage = "draft"
                return ("draft", self.receiver, self.message)
            if plain in {"ler mensagem", "repetir mensagem", "qual e a mensagem"}:
                return ("read", self.receiver, self.message)
            if plain in {"confirmar", "confirmar envio", "pode enviar", "enviar agora", "envia agora"}:
                return ("send", self.receiver, self.message)
            correction = re.match(r"^(?:corrigir|trocar|alterar|mudar)\s+(?:a\s+)?mensagem(?:\s+para|\s*:)\s*(.+)$", raw, flags=re.I)
            if correction:
                self.message = correction.group(1).strip()
                return ("draft", self.receiver, self.message)
            return None
        start = re.match(r"^(?:enviar|envia|mandar|manda)\s+(?:uma\s+)?mensagem\s+(?:para|pra|pro|a|ao)\s+(.+)$", raw, flags=re.I)
        if not start:
            return None
        receiver = start.group(1).strip(" .,!?")
        if not receiver or len(receiver) > 80:
            return ("invalid", "", "")
        self.receiver = receiver
        self.stage = "awaiting_text"
        return ("open", receiver, "")
