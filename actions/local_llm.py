from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "local_llm.json"
BRAIN_ROOT = Path(r"D:\xxxx_memory")
MODEL_NOTE = BRAIN_ROOT / "00_Cerebro" / "_jarvis-local-model.md"

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "mode": "fast",
    "model": "llama3.2:1b",
    "parameters_b": 1,
    "fast_model": "llama3.2:1b",
    "fast_parameters_b": 1,
    "deep_model": "llama3.1:8b",
    "deep_parameters_b": 8,
    "role": "local_text_reasoning",
    "enabled": True,
    "use_for": ["offline_text", "private_reasoning", "brain_answer"],
    "fallback": "gemini",
    "timeout_seconds": 90,
    "temperature": 0.25,
    "num_ctx": 1024,
    "num_predict": 96,
    "keep_alive": "30m",
}

MODEL_PARAMETER_HINTS = {
    "llama3.1:8b": 8,
    "llama3.2:3b": 3,
    "llama3.2:1b": 1,
    "mistral:7b": 7,
    "qwen2.5:7b": 7,
    "qwen2.5:14b": 14,
    "gemma2:9b": 9,
    "phi3:mini": 3.8,
}


def _load_config() -> dict[str, Any]:
    data = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass
    return data


def _save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def _ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    common = Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
    if common.exists():
        return str(common)
    return None



def _is_deep_request(params: dict[str, Any], config: dict[str, Any]) -> bool:
    mode = str(params.get("mode") or params.get("modo") or params.get("profile") or config.get("mode") or "fast").lower().strip()
    if str(params.get("model") or params.get("modelo") or "").strip():
        return False
    if str(params.get("deep") or "").lower() in {"1", "true", "sim", "yes", "8b", "profundo"}:
        return True
    return mode in {"deep", "profundo", "8b", "analysis", "analise", "análise"}


def _resolve_runtime(params: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    deep = _is_deep_request(params, config)
    model = str(params.get("model") or params.get("modelo") or (config.get("deep_model") if deep else config.get("fast_model")) or config.get("model") or DEFAULT_CONFIG["model"])
    params_b = _parameter_billions(model) or (config.get("deep_parameters_b") if deep else config.get("fast_parameters_b")) or config.get("parameters_b")
    if deep:
        num_ctx = int(params.get("num_ctx") or config.get("deep_num_ctx") or 4096)
        num_predict = int(params.get("num_predict") or config.get("deep_num_predict") or 256)
        timeout = int(params.get("timeout_seconds") or config.get("deep_timeout_seconds") or 300)
        context_chars = int(params.get("context_chars") or config.get("deep_context_chars") or 3000)
    else:
        num_ctx = int(params.get("num_ctx") or config.get("num_ctx") or 1024)
        num_predict = int(params.get("num_predict") or config.get("num_predict") or 96)
        timeout = int(params.get("timeout_seconds") or config.get("timeout_seconds") or 90)
        context_chars = int(params.get("context_chars") or config.get("context_chars") or 1200)
    return {
        "deep": deep,
        "model": model,
        "parameters_b": params_b,
        "num_ctx": max(256, min(num_ctx, 32768)),
        "num_predict": max(8, min(num_predict, 2048)),
        "timeout_seconds": max(10, min(timeout, 1200)),
        "context_chars": max(300, min(context_chars, 32000)),
        "keep_alive": str(params.get("keep_alive") or config.get("keep_alive") or "30m"),
    }
def _request_json(path: str, payload: dict[str, Any] | None = None, timeout: float = 8.0) -> dict[str, Any]:
    config = _load_config()
    base = str(config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _is_server_online() -> bool:
    try:
        _request_json("/api/tags", timeout=2.5)
        return True
    except Exception:
        return False


def _start_server() -> str:
    exe = _ollama_exe()
    if not exe:
        return "Ollama nao encontrado. Instale o Ollama para ativar modelo local real."
    if _is_server_online():
        return "Ollama ja esta online em 127.0.0.1:11434."

    flags = 0
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception as exc:
        return f"Falha ao iniciar Ollama: {exc}"

    for _ in range(20):
        time.sleep(0.5)
        if _is_server_online():
            return "Ollama iniciado em segundo plano."
    return "Ollama foi chamado, mas a API local ainda nao respondeu."



def _stop_model(model: str | None) -> None:
    model = str(model or "").strip()
    exe = _ollama_exe()
    if not exe or not model:
        return
    try:
        subprocess.run([exe, "stop", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    except Exception:
        pass
def _list_models() -> list[str]:
    data = _request_json("/api/tags", timeout=5)
    models = data.get("models") or []
    names = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _parameter_billions(model: str) -> float | int | None:
    lower = str(model or "").lower()
    for name, value in MODEL_PARAMETER_HINTS.items():
        if lower == name.lower():
            return value
    match = re.search(r"(\d+(?:\.\d+)?)\s*b", lower)
    if match:
        value = float(match.group(1))
        return int(value) if value.is_integer() else value
    return None


def _write_model_note(config: dict[str, Any], online: bool, installed: list[str]) -> Path:
    MODEL_NOTE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runtime = _resolve_runtime({}, config)
    model = str(runtime["model"])
    params_b = runtime.get("parameters_b") or "desconhecido"
    lines = [
        "---",
        f"updated: {now}",
        "tags: [cerebro, jarvis, local-llm, ollama]",
        "type: local-model",
        "folder: 00_Cerebro",
        "---",
        "",
        "# Jarvis Local Model",
        "",
        "Este arquivo registra o motor de linguagem local do Jarvis.",
        "",
        "## Modelo local",
        "",
        f"- Provider: {config.get('provider')}",
        f"- Base URL: {config.get('base_url')}",
        f"- Modo ativo: {config.get('mode', 'fast')}",
        f"- Modelo alvo: {model}",
        f"- Parametros aproximados: {params_b}B",
        f"- Modelo rapido: {config.get('fast_model')}",
        f"- Modelo profundo: {config.get('deep_model')}",
        f"- Num ctx: {config.get('num_ctx')}",
        f"- Num predict: {config.get('num_predict')}",
        f"- Timeout: {config.get('timeout_seconds')}s",
        f"- Online agora: {'sim' if online else 'nao'}",
        f"- Instalado no Ollama: {'sim' if model in installed else 'nao'}",
        f"- Modelos instalados: {', '.join(installed) if installed else 'nenhum listado'}",
        "",
        "## Papel no Jarvis",
        "",
        "- Texto local/offline e raciocinio privado quando solicitado.",
        "- Respostas com contexto do Obsidian via action=brain_answer.",
        "- Gemini continua como ponte de audio, visao e fallback quando o modelo local nao estiver disponivel.",
        "- O vault nao e carregado inteiro; o Jarvis pesquisa o cerebro e envia apenas os trechos relevantes ao modelo local.",
    ]
    MODEL_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return MODEL_NOTE


def _status() -> str:
    config = _load_config()
    exe = _ollama_exe()
    online = _is_server_online()
    installed: list[str] = []
    if online:
        try:
            installed = _list_models()
        except Exception:
            installed = []
    note = _write_model_note(config, online, installed)
    runtime = _resolve_runtime({}, config)
    model = str(runtime["model"])
    params_b = runtime.get("parameters_b") or "desconhecido"
    return (
        "Local LLM status.\n"
        f"Ollama exe: {exe or 'nao encontrado'}\n"
        f"Ollama API: {'online' if online else 'offline'}\n"
        f"Modo ativo: {config.get('mode', 'fast')}\n"
        f"Modelo alvo: {model}\n"
        f"Parametros aproximados: {params_b}B\n"
        f"Modelo rapido: {config.get('fast_model')} (~{config.get('fast_parameters_b')}B)\n"
        f"Modelo profundo: {config.get('deep_model')} (~{config.get('deep_parameters_b')}B)\n"
        f"Runtime: ctx={runtime['num_ctx']}, predict={runtime['num_predict']}, timeout={runtime['timeout_seconds']}s\n"
        f"Modelo instalado: {'sim' if model in installed else 'nao'}\n"
        f"Modelos instalados: {', '.join(installed) if installed else 'nenhum listado'}\n"
        f"Config: {CONFIG_PATH}\n"
        f"Nota: {note}"
    )

def _setup(params: dict[str, Any]) -> str:
    config = _load_config()
    model = str(params.get("model") or params.get("modelo") or config.get("model") or DEFAULT_CONFIG["model"]).strip()
    if model:
        config["model"] = model
        config["parameters_b"] = params.get("parameters_b") or params.get("parametros_b") or _parameter_billions(model) or config.get("parameters_b")
    if params.get("mode") or params.get("modo"):
        mode = str(params.get("mode") or params.get("modo")).lower().strip()
        config["mode"] = "deep" if mode in {"deep", "profundo", "8b"} else "fast"
    if params.get("fast_model"):
        config["fast_model"] = str(params["fast_model"])
        config["fast_parameters_b"] = _parameter_billions(config["fast_model"]) or config.get("fast_parameters_b")
    if params.get("deep_model"):
        config["deep_model"] = str(params["deep_model"])
        config["deep_parameters_b"] = _parameter_billions(config["deep_model"]) or config.get("deep_parameters_b")
    if params.get("base_url"):
        config["base_url"] = str(params["base_url"]).rstrip("/")
    if params.get("num_ctx") is not None:
        config["num_ctx"] = max(1024, min(int(params["num_ctx"]), 32768))
    if params.get("temperature") is not None:
        config["temperature"] = max(0.0, min(float(params["temperature"]), 2.0))
    if params.get("timeout_seconds") is not None:
        config["timeout_seconds"] = max(30, min(int(params["timeout_seconds"]), 1200))
    if params.get("num_predict") is not None:
        config["num_predict"] = max(32, min(int(params["num_predict"]), 2048))
    config["enabled"] = True
    _save_config(config)
    online = _is_server_online()
    installed = _list_models() if online else []
    note = _write_model_note(config, online, installed)
    return (
        "Modelo local configurado.\n"
        f"Modo: {config.get('mode', 'fast')}\n"
        f"Modelo: {config['model']}\n"
        f"Parametros aproximados: {config.get('parameters_b')}B\n"
        f"Ollama API: {'online' if online else 'offline'}\n"
        f"Nota: {note}"
    )


def _pull(params: dict[str, Any]) -> str:
    exe = _ollama_exe()
    if not exe:
        return "Ollama nao encontrado. Instale o Ollama antes de baixar o modelo."
    config = _load_config()
    model = str(params.get("model") or params.get("modelo") or config.get("model") or DEFAULT_CONFIG["model"]).strip()
    wait = str(params.get("wait") or params.get("sync") or "").lower() in {"1", "true", "sim", "yes"}
    if wait:
        proc = subprocess.run([exe, "pull", model], capture_output=True, text=True, timeout=60 * 60)
        output = (proc.stdout or proc.stderr or "").strip()
        return f"Pull concluido para {model}.\n{output[-2000:]}"

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    subprocess.Popen([exe, "pull", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
    return f"Download do modelo local iniciado em segundo plano: {model}. Use local_llm status para verificar depois."


def _generate(params: dict[str, Any]) -> str:
    config = _load_config()
    if not _is_server_online():
        start_msg = _start_server()
        if not _is_server_online():
            return start_msg + "\nModelo local indisponivel."

    runtime = _resolve_runtime(params, config)
    model = str(runtime["model"])
    prompt = str(params.get("prompt") or params.get("query") or params.get("text") or "").strip()
    if not prompt:
        return "Me passa o prompt para o modelo local."

    system = str(params.get("system") or "Voce e o motor local do Jarvis. Responda em portugues brasileiro, direto e com base no contexto fornecido.")
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "keep_alive": runtime["keep_alive"],
        "options": {
            "temperature": float(params.get("temperature") or config.get("temperature") or 0.25),
            "num_ctx": int(runtime["num_ctx"]),
            "num_predict": int(runtime["num_predict"]),
        },
    }
    try:
        data = _request_json("/api/generate", payload=payload, timeout=float(runtime["timeout_seconds"]))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        return f"Ollama HTTP {exc.code}: {body[:1000]}"
    except Exception as exc:
        return f"Erro no modelo local: {exc}"
    return str(data.get("response") or "").strip() or "Modelo local respondeu vazio."


def _brain_answer(params: dict[str, Any], player=None, speak=None) -> str:
    from actions.brain_mode import brain_mode

    query = str(params.get("query") or params.get("text") or params.get("prompt") or "").strip()
    if not query:
        return "Me passa a pergunta para responder com o cerebro local."
    context = brain_mode(
        {
            "action": "pesquisa",
            "query": query,
            "deep": True,
            "max_chars": int(_resolve_runtime(params, _load_config())["context_chars"]),
        },
        player=player,
        speak=speak,
    )
    prompt = (
        "Use o contexto do cerebro Obsidian abaixo para responder. "
        "Se o contexto for fraco, diga isso claramente.\n\n"
        f"PERGUNTA:\n{query}\n\n"
        f"CONTEXTO DO CEREBRO:\n{context}\n\n"
        "RESPOSTA:"
    )
    payload = dict(params)
    payload["prompt"] = prompt
    payload.setdefault("num_predict", 96 if not _is_deep_request(params, _load_config()) else 256)
    return _generate(payload)


def local_llm(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    if player:
        try:
            player.write_log(f"[LocalLLM] {action}")
        except Exception:
            pass

    if action in {"status", "estado", "info"}:
        return _status()
    if action in {"fast", "rapido", "rápido", "modo_rapido"}:
        config = _load_config()
        payload = dict(params)
        payload.update({"mode": "fast", "model": config.get("fast_model") or "llama3.2:1b"})
        result = _setup(payload)
        _stop_model(config.get("deep_model"))
        _stop_model("qwen2.5-coder:3b")
        return result + "\nModelos pesados descarregados para priorizar velocidade."
    if action in {"deep", "profundo", "8b", "modo_profundo"}:
        payload = dict(params)
        payload.update({"mode": "deep", "model": _load_config().get("deep_model") or "llama3.1:8b"})
        return _setup(payload)
    if action in {"setup", "config", "configure", "set_model", "modelo"}:
        return _setup(params)
    if action in {"start", "serve", "iniciar"}:
        return _start_server() + "\n" + _status()
    if action in {"list", "listar", "models", "modelos"}:
        if not _is_server_online():
            msg = _start_server()
            if not _is_server_online():
                return msg
        return "Modelos Ollama instalados:\n" + ("\n".join(f"- {m}" for m in _list_models()) or "- nenhum")
    if action in {"pull", "baixar", "download"}:
        return _pull(params)
    if action in {"ask", "generate", "gerar", "perguntar"}:
        return _generate(params)
    if action in {"brain_answer", "cerebro", "responder_cerebro"}:
        return _brain_answer(params, player=player, speak=speak)
    return "Acao local_llm desconhecida. Use status, fast, deep, setup, start, list, pull, ask ou brain_answer."
