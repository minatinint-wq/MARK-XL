"""Small localhost-only client for the independent APIBird /v1 WhatsApp API.

No browser automation, inbound listener, cloud fallback, or automatic sends live here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config" / "bird_local.json"
KEY_FILE = ROOT / "config" / ".bird_local_key.dpapi"
PENDING = ROOT / "config" / ".bird_local_idempotency.json"
PHONE_RE = re.compile(r"^\d{10,15}$")
_pending_lock = threading.Lock()


class BirdLocalError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise BirdLocalError("API Bird local tentou redirecionar a requisição; operação bloqueada.")


def _open(request, timeout):
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect).open(request, timeout=timeout)


def _loopback_url(value: str) -> str:
    url = urllib.parse.urlsplit(str(value or "").strip().rstrip("/"))
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"}
            or url.username or url.password or url.path or url.query or url.fragment):
        raise BirdLocalError("Use apenas a API local: http://127.0.0.1:8787")
    if not url.port:
        raise BirdLocalError("Informe a porta da API Bird local.")
    return f"http://{url.hostname}:{url.port}"


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(base_url: str, instance_id: str) -> None:
    base_url = _loopback_url(base_url)
    instance_id = str(instance_id or "").strip()
    if not re.fullmatch(r"wa_[A-Za-z0-9_-]+", instance_id):
        raise BirdLocalError("Informe o ID da instância Bird (wa_...).")
    data = load_settings()
    data.update(base_url=base_url, instance_id=instance_id)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS)


def save_key(key: str) -> None:
    key = str(key or "").strip()
    if not key.startswith("bird_live_"):
        raise BirdLocalError("Chave de integração Bird inválida (esperado bird_live_...).")
    try:
        import win32crypt
        protected = win32crypt.CryptProtectData(key.encode("utf-8"), "Jarvis Bird local", None, None, None, 0)
    except ImportError as exc:
        raise BirdLocalError("Proteção DPAPI indisponível; instale pywin32 no Python do Jarvis.") from exc
    except Exception as exc:
        raise BirdLocalError("Não foi possível proteger a chave Bird neste usuário do Windows.") from exc
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(base64.b64encode(protected))


def _load_key() -> str:
    env_key = os.environ.get("JARVIS_BIRD_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(base64.b64decode(KEY_FILE.read_bytes()), None, None, None, 0)[1].decode("utf-8")
    except Exception as exc:
        raise BirdLocalError("Configure a chave Bird neste PC pelo botão WhatsApp do Jarvis.") from exc


def save_contact(name: str, phone: str, *, consent: bool) -> None:
    name = " ".join(str(name or "").split())
    phone = re.sub(r"[\s()+-]", "", str(phone or ""))
    if not name or len(name) > 80 or not PHONE_RE.fullmatch(phone):
        raise BirdLocalError("Informe nome e telefone com DDI/DDD (10 a 15 dígitos).")
    if not consent:
        raise BirdLocalError("Confirme que este contato autorizou mensagens por este canal.")
    data = load_settings()
    contacts = data.get("contacts")
    if not isinstance(contacts, dict):
        contacts = {}
    contacts[name] = {"phone": phone, "consent": True}
    data["contacts"] = contacts
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS)


def _contact(receiver: str) -> tuple[str, str]:
    receiver = str(receiver or "").strip()
    contacts = load_settings().get("contacts") or {}
    if not isinstance(contacts, dict):
        contacts = {}
    matches = [(name, entry) for name, entry in contacts.items() if isinstance(entry, dict)
               if name.casefold() == receiver.casefold()
               or str(entry.get("phone", "")) == receiver.lstrip("+")]
    if len(matches) != 1:
        raise BirdLocalError("Contato não cadastrado ou ambíguo na Bird local. Cadastre-o pelo botão WhatsApp.")
    name, entry = matches[0]
    phone = str(entry.get("phone", ""))
    if not PHONE_RE.fullmatch(phone) or entry.get("consent") is not True:
        raise BirdLocalError("Contato sem número válido ou sem autorização registrada.")
    return name, phone


def resolve_contact(receiver: str) -> tuple[str, str]:
    """Resolve only a saved, consented local contact for a voice draft."""
    return _contact(receiver)


def _idempotency_key(instance_id: str, phone: str, message: str) -> str:
    """Keep a retry after a lost HTTP response from creating a second message."""
    digest = hashlib.sha256(f"{instance_id}\0{phone}\0{message}".encode("utf-8")).hexdigest()
    with _pending_lock:
        try:
            entries = json.loads(PENDING.read_text(encoding="utf-8"))
            if not isinstance(entries, dict):
                entries = {}
        except (OSError, ValueError):
            entries = {}
        now = time.time()
        entries = {item: value for item, value in entries.items()
                   if isinstance(value, dict) and now - float(value.get("created", 0)) < 86400}
        if digest not in entries:
            entries[digest] = {"key": f"jarvis-{uuid.uuid4().hex}", "created": now}
        PENDING.parent.mkdir(parents=True, exist_ok=True)
        temp = PENDING.with_suffix(".tmp")
        temp.write_text(json.dumps(entries), encoding="utf-8")
        temp.replace(PENDING)
        return entries[digest]["key"]


def instance_status() -> str:
    settings = load_settings()
    base_url = _loopback_url(settings.get("base_url", "http://127.0.0.1:8787"))
    instance_id = str(settings.get("instance_id") or "")
    if not re.fullmatch(r"wa_[A-Za-z0-9_-]+", instance_id):
        raise BirdLocalError("Configure o ID da instância Bird pelo botão WhatsApp.")
    request = urllib.request.Request(
        f"{base_url}/v1/instances/{instance_id}",
        headers={"Authorization": f"Bearer {_load_key()}"},
    )
    try:
        with _open(request, timeout=5) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise BirdLocalError(f"Bird local recusou a consulta (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise BirdLocalError("API Bird local não respondeu em 127.0.0.1; inicie o serviço neste PC.") from exc
    return f"Instância {instance_id}: {data.get('status', 'estado desconhecido')}"


def send_text(receiver: str, message: str, *, confirmed: bool = False) -> str:
    if not confirmed:
        raise BirdLocalError("Confirme destinatário e texto na janela do Jarvis antes de enviar.")
    name, phone = _contact(receiver)
    message = str(message or "").strip()
    if not message or len(message) > 4096:
        raise BirdLocalError("Mensagem vazia ou maior que 4.096 caracteres.")
    settings = load_settings()
    base_url = _loopback_url(settings.get("base_url", "http://127.0.0.1:8787"))
    instance_id = str(settings.get("instance_id") or "")
    if not re.fullmatch(r"wa_[A-Za-z0-9_-]+", instance_id):
        raise BirdLocalError("Configure o ID da instância Bird pelo botão WhatsApp.")
    key = _load_key()
    if not key.startswith("bird_live_"):
        raise BirdLocalError("Chave Bird local inválida.")
    idempotency_key = _idempotency_key(instance_id, phone, message)
    request = urllib.request.Request(
        f"{base_url}/v1/instances/{instance_id}/messages",
        data=json.dumps({"to": phone, "text": message, "consent": True}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Idempotency-Key": idempotency_key},
        method="POST",
    )
    try:
        with _open(request, timeout=8) as response:
            if response.status != 202:
                raise BirdLocalError(f"Bird retornou HTTP {response.status}; envio não confirmado.")
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise BirdLocalError(f"Bird recusou o pedido (HTTP {exc.code}); nenhuma entrega foi confirmada.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise BirdLocalError("Sem confirmação da API Bird. Não repita o envio antes de verificar os trabalhos da instância.") from exc
    job = data.get("job") if isinstance(data, dict) else None
    job_id = (job or {}).get("id") if isinstance(job, dict) else (data.get("id") or data.get("jobId")) if isinstance(data, dict) else None
    return f"Mensagem para {name} enfileirada na Bird local" + (f" (trabalho {job_id})." if job_id else ". Aguarde o recibo de entrega.")
