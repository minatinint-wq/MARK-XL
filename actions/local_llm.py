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
    "mode": "normal",
    "model": "llama3.2:1b",
    "parameters_b": 1,
    "normal_model": "llama3.2:1b",
    "normal_parameters_b": 1,
    "fast_model": "qwen3.5:4b",
    "fast_parameters_b": 4.66,
    "ultra_model": "gemma4:latest",
    "ultra_parameters_b": 8,
    "deep_model": "gemma4:latest",
    "deep_parameters_b": 8,
    "role": "local_text_reasoning",
    "enabled": True,
    "use_for": ["offline_text", "private_reasoning", "brain_answer"],
    "fallback": "gemini",
    "timeout_seconds": 90,
    "temperature": 0.25,
    "normal_num_ctx": 2048,
    "normal_num_predict": 128,
    "normal_context_chars": 3000,
    "normal_timeout_seconds": 90,
    "normal_effort": "low",
    "normal_think": False,
    "fast_num_ctx": 4096,
    "fast_num_predict": 384,
    "fast_context_chars": 9000,
    "fast_timeout_seconds": 180,
    "fast_effort": "medium",
    "fast_think": True,
    "ultra_num_ctx": 8192,
    "ultra_num_predict": 1024,
    "ultra_context_chars": 18000,
    "ultra_timeout_seconds": 360,
    "ultra_effort": "high",
    "ultra_think": True,
    "num_ctx": 2048,
    "num_predict": 128,
    "keep_alive": "0",
}

MODEL_PARAMETER_HINTS = {
    "llama3.1:8b": 8,
    "llama3.2:3b": 3,
    "llama3.2:1b": 1,
    "mistral:7b": 7,
    "qwen2.5:7b": 7,
    "qwen2.5:14b": 14,
    "gemma2:9b": 9,
    "gemma4": 8,
    "gemma4:latest": 8,
    "phi3:mini": 3.8,
    "qwen3.5:4b": 4.66,
    "qwen3.5:4b-q4_k_m": 4.66,
    "qwen3.5:9b": 9.65,
    "qwen3.5:9b-q4_k_m": 9.65,
}

MODE_ALIASES = {
    "normal": "normal", "padrao": "normal", "padrão": "normal", "leve": "normal", "low": "normal", "1b": "normal",
    "fast": "fast", "rapido": "fast", "rápido": "fast", "medio": "fast", "médio": "fast", "medium": "fast", "4b": "fast", "6b": "fast",
    "ultra": "ultra", "deep": "ultra", "profundo": "ultra", "alto": "ultra", "high": "ultra", "max": "ultra", "8b": "ultra", "9b": "ultra",
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



def _normalize_mode(value: Any) -> str:
    mode = str(value or "normal").lower().strip().replace("-", "_").replace(" ", "_")
    return MODE_ALIASES.get(mode, "normal")


def _resolve_mode(params: dict[str, Any], config: dict[str, Any]) -> str:
    explicit = params.get("mode") or params.get("modo") or params.get("profile")
    if explicit:
        return _normalize_mode(explicit)
    if str(params.get("deep") or "").lower() in {"1", "true", "sim", "yes", "8b", "9b", "profundo", "ultra"}:
        return "ultra"
    return _normalize_mode(config.get("mode") or "normal")


def _is_deep_request(params: dict[str, Any], config: dict[str, Any]) -> bool:
    return _resolve_mode(params, config) == "ultra"


def _resolve_runtime(params: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    mode = _resolve_mode(params, config)
    model_key = f"{mode}_model"
    params_key = f"{mode}_parameters_b"
    if mode == "ultra" and not config.get("ultra_model"):
        model_key = "deep_model"
        params_key = "deep_parameters_b"
    if mode == "normal" and not config.get("normal_model"):
        model_key = "fast_model"
        params_key = "fast_parameters_b"
    model = str(params.get("model") or params.get("modelo") or config.get(model_key) or DEFAULT_CONFIG[model_key])
    params_b = _parameter_billions(model) or config.get(params_key) or config.get("parameters_b")
    num_ctx = int(params.get("num_ctx") or config.get(f"{mode}_num_ctx") or DEFAULT_CONFIG[f"{mode}_num_ctx"])
    num_predict = int(params.get("num_predict") or config.get(f"{mode}_num_predict") or DEFAULT_CONFIG[f"{mode}_num_predict"])
    timeout = int(params.get("timeout_seconds") or config.get(f"{mode}_timeout_seconds") or DEFAULT_CONFIG[f"{mode}_timeout_seconds"])
    context_chars = int(params.get("context_chars") or config.get(f"{mode}_context_chars") or DEFAULT_CONFIG[f"{mode}_context_chars"])
    effort = str(params.get("effort") or params.get("esforco") or config.get(f"{mode}_effort") or DEFAULT_CONFIG[f"{mode}_effort"]).lower().strip()
    if effort not in {"none", "low", "medium", "high"}:
        effort = DEFAULT_CONFIG[f"{mode}_effort"]
    requested_think = params.get("think")
    if requested_think is None:
        requested_think = config.get(f"{mode}_think", DEFAULT_CONFIG[f"{mode}_think"])
    think = requested_think if isinstance(requested_think, bool) else str(requested_think).lower().strip() in {"1", "true", "sim", "yes", "on"}
    if effort in {"none", "low"}:
        think = False
    return {
        "mode": mode,
        "deep": mode == "ultra",
        "model": model,
        "parameters_b": params_b,
        "num_ctx": max(256, min(num_ctx, 32768)),
        "num_predict": max(8, min(num_predict, 2048)),
        "timeout_seconds": max(10, min(timeout, 1200)),
        "context_chars": max(300, min(context_chars, 32000)),
        "effort": effort,
        "think": think,
        "keep_alive": str(params.get("keep_alive") if params.get("keep_alive") is not None else config.get("keep_alive") or "0"),
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


def _request_json_stream(path: str, payload: dict[str, Any], timeout: float):
    """Yield newline-delimited Ollama events for the visual model monitor."""
    config = _load_config()
    base = str(config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError(str(event["error"]))
            yield event


def _emit_model_status(player, runtime: dict[str, Any], phase: str, **extra: Any) -> None:
    callback = getattr(player, "update_model_status", None) if player is not None else None
    if not callable(callback):
        return
    payload = {
        "tier": runtime.get("mode") or "normal",
        "model": runtime.get("model") or "",
        "effort": runtime.get("effort") or "low",
        "think": bool(runtime.get("think")),
        "phase": phase,
    }
    payload.update(extra)
    try:
        callback(payload)
    except Exception:
        pass


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
        f"- Modo ativo: {config.get('mode', 'normal')}",
        f"- Modelo alvo: {model}",
        f"- Parametros aproximados: {params_b}B",
        f"- Normal: {config.get('normal_model')} (~{config.get('normal_parameters_b')}B), effort=low",
        f"- Rapido: {config.get('fast_model')} (~{config.get('fast_parameters_b')}B), effort=medium",
        f"- Ultra: {config.get('ultra_model') or config.get('deep_model')} (~{config.get('ultra_parameters_b') or config.get('deep_parameters_b')}B), effort=high",
        f"- Runtime ativo: ctx={runtime['num_ctx']}, predict={runtime['num_predict']}, timeout={runtime['timeout_seconds']}s",
        f"- Thinking ativo: {'sim' if runtime['think'] else 'nao'}",
        f"- Keep alive: {runtime['keep_alive']}",
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
        f"Modo ativo: {runtime['mode']}\n"
        f"Modelo alvo: {model}\n"
        f"Parametros aproximados: {params_b}B\n"
        f"Normal: {config.get('normal_model')} (~{config.get('normal_parameters_b')}B), effort=low\n"
        f"Rapido: {config.get('fast_model')} (~{config.get('fast_parameters_b')}B), effort=medium\n"
        f"Ultra: {config.get('ultra_model') or config.get('deep_model')} (~{config.get('ultra_parameters_b') or config.get('deep_parameters_b')}B), effort=high\n"
        f"Runtime: ctx={runtime['num_ctx']}, predict={runtime['num_predict']}, timeout={runtime['timeout_seconds']}s, think={runtime['think']}, keep_alive={runtime['keep_alive']}\n"
        f"Modelo instalado: {'sim' if model in installed else 'nao'}\n"
        f"Modelos instalados: {', '.join(installed) if installed else 'nenhum listado'}\n"
        f"Config: {CONFIG_PATH}\n"
        f"Nota: {note}"
    )

def _setup(params: dict[str, Any]) -> str:
    config = _load_config()
    requested_mode = params.get("mode") or params.get("modo")
    mode = _normalize_mode(requested_mode or config.get("mode") or "normal")
    model = str(params.get("model") or params.get("modelo") or config.get("model") or DEFAULT_CONFIG["model"]).strip()
    if model:
        config["model"] = model
        config["parameters_b"] = params.get("parameters_b") or params.get("parametros_b") or _parameter_billions(model) or config.get("parameters_b")
        if requested_mode:
            config[f"{mode}_model"] = model
            config[f"{mode}_parameters_b"] = config["parameters_b"]
            if mode == "ultra":
                config["deep_model"] = model
                config["deep_parameters_b"] = config["parameters_b"]
    if requested_mode:
        config["mode"] = mode
    if params.get("normal_model"):
        config["normal_model"] = str(params["normal_model"])
        config["normal_parameters_b"] = _parameter_billions(config["normal_model"]) or config.get("normal_parameters_b")
    if params.get("fast_model"):
        config["fast_model"] = str(params["fast_model"])
        config["fast_parameters_b"] = _parameter_billions(config["fast_model"]) or config.get("fast_parameters_b")
    if params.get("ultra_model"):
        config["ultra_model"] = str(params["ultra_model"])
        config["ultra_parameters_b"] = _parameter_billions(config["ultra_model"]) or config.get("ultra_parameters_b")
        config["deep_model"] = config["ultra_model"]
        config["deep_parameters_b"] = config["ultra_parameters_b"]
    if params.get("deep_model"):
        config["deep_model"] = str(params["deep_model"])
        config["deep_parameters_b"] = _parameter_billions(config["deep_model"]) or config.get("deep_parameters_b")
        config["ultra_model"] = config["deep_model"]
        config["ultra_parameters_b"] = config["deep_parameters_b"]
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
    if params.get("keep_alive") is not None:
        config["keep_alive"] = str(params["keep_alive"])
    for tier in ("normal", "fast", "ultra"):
        for key in ("num_ctx", "num_predict", "context_chars", "timeout_seconds", "effort", "think"):
            full_key = f"{tier}_{key}"
            if params.get(full_key) is not None:
                config[full_key] = params[full_key]
    config["enabled"] = True
    _save_config(config)
    online = _is_server_online()
    installed = _list_models() if online else []
    note = _write_model_note(config, online, installed)
    return (
        "Modelo local configurado.\n"
        f"Modo: {config.get('mode', 'normal')}\n"
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


def _generate(params: dict[str, Any], player=None) -> str:
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

    _emit_model_status(player, runtime, "loading", resident=False)

    system = str(params.get("system") or "Voce e o motor local do Jarvis. Responda em portugues brasileiro, direto e com base no contexto fornecido.")
    effort_instruction = {
        "low": "Responda diretamente, sem raciocinio longo.",
        "medium": "Analise os pontos principais antes de responder e verifique contradicoes.",
        "high": "Raciocine profundamente, cruze as evidencias e so entao produza uma resposta objetiva.",
        "none": "Responda apenas com o resultado.",
    }[runtime["effort"]]
    payload = {
        "model": model,
        "prompt": prompt,
        "system": f"{system}\nNivel de esforco: {runtime['effort']}. {effort_instruction}",
        "stream": False,
        "think": runtime["think"],
        "keep_alive": runtime["keep_alive"],
        "options": {
            "temperature": float(params.get("temperature") or config.get("temperature") or 0.25),
            "num_ctx": int(runtime["num_ctx"]),
            "num_predict": int(runtime["num_predict"]),
        },
    }
    visual_stream = callable(getattr(player, "update_model_status", None))
    answer = ""
    thinking = ""
    try:
        if visual_stream:
            payload["stream"] = True
            answer_parts: list[str] = []
            thinking_parts: list[str] = []
            last_event_at = 0.0
            for event in _request_json_stream(
                "/api/generate",
                payload=payload,
                timeout=float(runtime["timeout_seconds"]),
            ):
                thought_delta = str(event.get("thinking") or "")
                response_delta = str(event.get("response") or "")
                if thought_delta:
                    thinking_parts.append(thought_delta)
                if response_delta:
                    answer_parts.append(response_delta)
                now = time.monotonic()
                if now - last_event_at >= 0.09 or event.get("done"):
                    thinking = "".join(thinking_parts)
                    answer = "".join(answer_parts)
                    if response_delta or answer:
                        _emit_model_status(
                            player,
                            runtime,
                            "responding",
                            resident=True,
                            thinking_chars=len(thinking),
                            thinking_preview=thinking[-520:],
                            response_preview=answer[-320:],
                        )
                    elif thought_delta or thinking:
                        _emit_model_status(
                            player,
                            runtime,
                            "thinking",
                            resident=True,
                            thinking_chars=len(thinking),
                            thinking_preview=thinking[-520:],
                        )
                    last_event_at = now
            answer = "".join(answer_parts).strip()
            thinking = "".join(thinking_parts).strip()
        else:
            data = _request_json("/api/generate", payload=payload, timeout=float(runtime["timeout_seconds"]))
            answer = str(data.get("response") or "").strip()
            thinking = str(data.get("thinking") or "").strip()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        _emit_model_status(player, runtime, "error", resident=False, error=f"HTTP {exc.code}: {body[:240]}")
        return f"Ollama HTTP {exc.code}: {body[:1000]}"
    except Exception as exc:
        _emit_model_status(player, runtime, "error", resident=False, error=str(exc)[:240])
        return f"Erro no modelo local: {exc}"
    if answer:
        _emit_model_status(
            player,
            runtime,
            "done",
            resident=False,
            thinking_chars=len(thinking),
            thinking_preview=thinking[-520:],
            response_preview=answer[-320:],
        )
        return answer
    if thinking:
        _emit_model_status(
            player,
            runtime,
            "error",
            resident=False,
            thinking_chars=len(thinking),
            thinking_preview=thinking[-520:],
            error="limite consumido antes da resposta final",
        )
        return "Modelo local consumiu o limite no raciocinio e nao concluiu a resposta."
    _emit_model_status(player, runtime, "error", resident=False, error="resposta vazia")
    return "Modelo local respondeu vazio."


def _research_answer(params: dict[str, Any], player=None) -> str:
    query = str(params.get("query") or params.get("text") or "").strip()
    context = str(params.get("context") or "").strip()
    if not query or not context:
        return "Contexto de pesquisa insuficiente."
    runtime = _resolve_runtime(params, _load_config())
    if runtime["mode"] == "normal":
        return context
    output_limits = {"normal": 3500, "fast": 6000, "ultra": 9000}
    prompt = (
        "Organize o resultado de pesquisa abaixo para o Gemini Live responder ao usuario. "
        "Preserve fatos, fontes e alertas relevantes. Nao invente informacao. "
        "Entregue uma sintese clara em portugues brasileiro, sem expor o raciocinio interno.\n\n"
        f"PERGUNTA:\n{query}\n\n"
        f"RESULTADO DA PESQUISA:\n{context}\n\n"
        "SINTESE:"
    )
    payload = dict(params)
    payload["prompt"] = prompt
    payload["system"] = "Voce e a camada local de pesquisa do Jarvis. Sintetize apenas as evidencias fornecidas."
    payload.setdefault("num_predict", {"normal": 192, "fast": 384, "ultra": 768}[runtime["mode"]])
    answer = _generate(payload, player=player)
    if answer.startswith(("Erro no modelo local:", "Ollama HTTP ", "Modelo local indisponivel", "Ollama nao encontrado")):
        return answer
    limit = output_limits[runtime["mode"]]
    return answer if len(answer) <= limit else answer[: limit - 20].rstrip() + "\n[resumo truncado]"


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
    return _generate(payload, player=player)


def local_llm(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    if player:
        try:
            player.write_log(f"[LocalLLM] {action}")
        except Exception:
            pass

    if action in {"status", "estado", "info"}:
        config = _load_config()
        _emit_model_status(player, _resolve_runtime({}, config), "ready", resident=False)
        return _status()
    if action in {"normal", "padrao", "padrão", "leve", "modo_normal"}:
        config = _load_config()
        payload = dict(params)
        payload.update({"mode": "normal", "model": config.get("normal_model") or "llama3.2:1b"})
        result = _setup(payload)
        _emit_model_status(player, _resolve_runtime({"mode": "normal"}, _load_config()), "selected", resident=False)
        _stop_model(config.get("fast_model"))
        _stop_model(config.get("ultra_model") or config.get("deep_model"))
        return result + "\nModelos maiores descarregados."
    if action in {"fast", "rapido", "rápido", "modo_rapido"}:
        config = _load_config()
        payload = dict(params)
        payload.update({"mode": "fast", "model": config.get("fast_model") or "qwen3.5:4b"})
        result = _setup(payload)
        _emit_model_status(player, _resolve_runtime({"mode": "fast"}, _load_config()), "selected", resident=False)
        _stop_model(config.get("ultra_model") or config.get("deep_model"))
        return result + "\nModelos pesados descarregados para priorizar velocidade."
    if action in {"ultra", "deep", "profundo", "8b", "9b", "modo_profundo", "modo_ultra"}:
        payload = dict(params)
        config = _load_config()
        payload.update({"mode": "ultra", "model": config.get("ultra_model") or config.get("deep_model") or "gemma4:latest"})
        result = _setup(payload)
        _emit_model_status(player, _resolve_runtime({"mode": "ultra"}, _load_config()), "selected", resident=False)
        return result
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
        return _generate(params, player=player)
    if action in {"brain_answer", "cerebro", "responder_cerebro"}:
        return _brain_answer(params, player=player, speak=speak)
    if action in {"research_answer", "responder_pesquisa", "summarize_research"}:
        return _research_answer(params, player=player)
    return "Acao local_llm desconhecida. Use status, normal, fast, ultra, setup, start, list, pull, ask, research_answer ou brain_answer."
