"""On-demand Gmail header mirror using metadata-only OAuth scope.

No message body, attachments, send, delete, or background polling.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.header import decode_header, make_header
from pathlib import Path


ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
CLIENT = ROOT / "config" / "gmail_oauth_client.json"
TOKEN = ROOT / "config" / ".gmail_token.dpapi"
SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailMirrorError(ValueError):
    pass


def _protect(data: str) -> None:
    try:
        import win32crypt
        encrypted = win32crypt.CryptProtectData(data.encode("utf-8"), "Jarvis Gmail metadata", None, None, None, 0)
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_bytes(base64.b64encode(encrypted))
    except Exception as exc:
        raise GmailMirrorError("Não foi possível proteger a sessão Gmail no Windows.") from exc


def _unprotect() -> str:
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(base64.b64decode(TOKEN.read_bytes()), None, None, None, 0)[1].decode("utf-8")
    except Exception as exc:
        raise GmailMirrorError("Sessão Gmail ausente ou vinculada a outro usuário do Windows. Conecte novamente.") from exc


def _credentials(*, connect: bool = False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise GmailMirrorError("Dependências Google ausentes no Python do Jarvis.") from exc
    creds = None
    if TOKEN.is_file():
        try:
            creds = Credentials.from_authorized_user_info(json.loads(_unprotect()), [SCOPE])
            if SCOPE not in (creds.scopes or []):
                creds = None
        except (ValueError, KeyError):
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _protect(creds.to_json())
        except Exception as exc:
            raise GmailMirrorError("Sessão Gmail expirou; conecte novamente no botão E-mail.") from exc
    if creds and creds.valid:
        return creds
    if not connect:
        raise GmailMirrorError("Gmail não conectado. Clique em Conectar Gmail.")
    if not CLIENT.is_file():
        raise GmailMirrorError("Falta config/gmail_oauth_client.json (OAuth Client ID de aplicativo desktop).")
    try:
        data = json.loads(CLIENT.read_text(encoding="utf-8"))
        if not isinstance(data.get("installed"), dict):
            raise ValueError("not desktop")
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), [SCOPE])
        creds = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True, timeout_seconds=120)
        if not creds.valid or SCOPE not in (creds.scopes or []):
            raise GmailMirrorError("A autorização não concedeu o escopo mínimo de metadados.")
        _protect(creds.to_json())
        return creds
    except ImportError as exc:
        raise GmailMirrorError("Instale google-auth-oauthlib no Python do Jarvis.") from exc
    except (ValueError, KeyError) as exc:
        raise GmailMirrorError("O arquivo OAuth do Gmail não é um cliente Desktop válido.") from exc


def connect() -> str:
    _credentials(connect=True)
    return "Gmail conectado para metadados, somente leitura."


def _get(path: str, token: str) -> dict:
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise GmailMirrorError(f"Gmail recusou a leitura (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GmailMirrorError("Gmail não respondeu; verifique a conexão.") from exc


def _header(value: str) -> str:
    try:
        value = str(make_header(decode_header(value)))
    except (ValueError, UnicodeError):
        value = str(value)
    return re.sub(r"[\r\n\t\x00-\x1f]", " ", value).strip()[:220]


def inbox(limit: int = 12) -> list[dict]:
    creds = _credentials()
    limit = max(1, min(int(limit), 20))
    listed = _get(f"/messages?labelIds=INBOX&maxResults={limit}", creds.token)
    rows = []
    for item in listed.get("messages", []):
        message_id = str(item.get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", message_id):
            continue
        query = urllib.parse.urlencode({"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]}, doseq=True)
        data = _get(f"/messages/{message_id}?{query}", creds.token)
        headers = {str(h.get("name", "")).lower(): _header(h.get("value", ""))
                   for h in data.get("payload", {}).get("headers", []) if isinstance(h, dict)}
        thread_id = str(data.get("threadId") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", thread_id):
            thread_id = message_id
        try:
            when = datetime.fromtimestamp(int(data.get("internalDate", "0")) / 1000).strftime("%d/%m %H:%M")
        except (ValueError, OverflowError, OSError):
            when = headers.get("date", "")[:40]
        rows.append({"from": headers.get("from", "(sem remetente)"),
                     "subject": headers.get("subject", "(sem assunto)"),
                     "when": when, "thread_id": thread_id})
    return rows


def gmail_url(thread_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", str(thread_id or "")):
        raise GmailMirrorError("ID de conversa inválido.")
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"
