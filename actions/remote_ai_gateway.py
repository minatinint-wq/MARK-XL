"""Loopback-only companion for the independent Leadio AI service.

The hosted access key stays in the local environment.  This is not a CRM
connector and never talks to leadiocrm.com.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8779
UPSTREAM = "https://leadio-ai.onrender.com"
_server: ThreadingHTTPServer | None = None
_lock = threading.Lock()
_private_key_file = Path(__file__).resolve().parents[1] / "config" / ".remote_ai_access.key"


class RemoteAIError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RemoteAIError("O serviço remoto tentou redirecionar; pedido bloqueado.")


def _key() -> str:
    key = os.environ.get("JARVIS_LEADIO_AI_KEY", "").strip()
    if not key and _private_key_file.is_file():
        key = _private_key_file.read_text(encoding="utf-8").strip()
        os.environ["JARVIS_LEADIO_AI_KEY"] = key
    if len(key) < 32 or len(key) > 512:
        raise RemoteAIError("Defina JARVIS_LEADIO_AI_KEY no ambiente local deste PC.")
    return key


def _request(path: str, payload: dict | None = None, timeout: int = 30):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        UPSTREAM + path,
        data=data,
        headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RemoteAIError("A chave local não foi aceita pelo serviço de IA.") from exc
        if exc.code == 429:
            raise RemoteAIError("Cota ou capacidade do motor remoto esgotada; aguarde.") from exc
        raise RemoteAIError(f"Motor remoto recusou o pedido (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RemoteAIError("Motor remoto indisponível; verifique a conexão ou aguarde o Render acordar.") from exc


def available_models() -> list[dict]:
    with _request("/api/models", timeout=45) as response:
        models = json.load(response).get("models", [])
    return [
        {"key": item["key"], "name": item.get("name", item["key"]), "reasoning": bool(item.get("reasoning"))}
        for item in models
        if isinstance(item, dict)
        and item.get("provider") == "openrouter"
        and item.get("free") is True
        and item.get("enabled") is True
        and isinstance(item.get("key"), str)
    ]


def ask(question: str, model: str = "") -> dict:
    question = str(question or "").strip()
    if not question or len(question) > 12000:
        raise RemoteAIError("Pergunta vazia ou longa demais (limite: 12 mil caracteres).")
    models = available_models()
    keys = {item["key"] for item in models}
    if not keys:
        raise RemoteAIError("Nenhum modelo gratuito disponível no motor remoto.")
    if model and model not in keys:
        raise RemoteAIError("Modelo não está no catálogo gratuito disponível.")
    selected = model or next((item["key"] for item in models if "dots-3-note" in item["key"]), models[0]["key"])
    payload = {
        "requestId": str(uuid.uuid4()),
        "model": selected,
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "maxTokens": 2048,
        "effort": "high",
    }
    answer: list[str] = []
    completed = False
    with _request("/api/chat", payload, timeout=180) as response:
        for raw in response:
            if not raw.startswith(b"data: "):
                continue
            try:
                event = json.loads(raw[6:])
            except (ValueError, UnicodeDecodeError):
                continue
            if event.get("type") == "delta":
                answer.append(str(event.get("text") or ""))
                if sum(map(len, answer)) > 30000:
                    raise RemoteAIError("Resposta excedeu o limite local.")
            elif event.get("type") == "error":
                raise RemoteAIError(str(event.get("error") or "Falha no motor remoto."))
            elif event.get("type") == "done":
                completed = True
    if not completed:
        raise RemoteAIError("Conexão terminou sem resposta completa; não reenviei automaticamente.")
    return {"answer": "".join(answer).strip(), "model": selected}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return  # Never log prompts or local credentials.

    def _allowed(self) -> bool:
        if self.headers.get("Host") not in {f"{HOST}:{PORT}", f"localhost:{PORT}"}:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin in {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}

    def _json(self, status: int, data: dict):
        blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):
        if not self._allowed():
            return self._json(403, {"error": "Origem local inválida."})
        if self.path == "/health":
            return self._json(200, {"service": "Jarvis remote AI gateway", "configured": bool(os.environ.get("JARVIS_LEADIO_AI_KEY"))})
        if self.path != "/models":
            return self._json(404, {"error": "Rota desconhecida."})
        try:
            self._json(200, {"models": available_models()})
        except RemoteAIError as exc:
            self._json(503, {"error": str(exc)})

    def do_POST(self):
        if not self._allowed():
            return self._json(403, {"error": "Origem local inválida."})
        if self.path != "/chat":
            return self._json(404, {"error": "Rota desconhecida."})
        try:
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise RemoteAIError("Envie JSON no serviço local.")
            size = int(self.headers.get("Content-Length", "0"))
            if size < 2 or size > 16000:
                raise RemoteAIError("Pedido local inválido ou longo demais.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise RemoteAIError("Envie um objeto JSON.")
            self._json(200, ask(body.get("question", ""), body.get("model", "")))
        except (RemoteAIError, ValueError) as exc:
            self._json(400, {"error": str(exc)})


def start_gateway() -> bool:
    global _server
    with _lock:
        if _server is not None:
            return True
        try:
            _key()
        except RemoteAIError:
            return False
        try:
            _server = ThreadingHTTPServer((HOST, PORT), _Handler)
        except OSError:
            return False
        threading.Thread(target=_server.serve_forever, name="JarvisRemoteAILocalhost", daemon=True).start()
        return True


def ask_local(question: str, model: str = "") -> dict:
    body = json.dumps({"question": question, "model": model}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"http://{HOST}:{PORT}/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=190) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc).get("error")
        except ValueError:
            error = f"HTTP {exc.code}"
        raise RemoteAIError(error) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RemoteAIError("Gateway local não respondeu em 127.0.0.1:8779.") from exc
