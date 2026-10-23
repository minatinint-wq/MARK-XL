"""AI image generator with automatic NVIDIA -> Cloudflare failover."""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
KEYS_PATH = BASE_DIR / "config" / "api_keys.json"
DEFAULT_OUTPUT = BASE_DIR / "generated_images"
CF_MODEL = "@cf/black-forest-labs/flux-1-schnell"
GEMINI_MODEL = "gemini-2.5-flash-image"
NVIDIA_DEFAULT_MODEL = "black-forest-labs/flux.2-klein-4b"
NVIDIA_ENDPOINTS = {
    "black-forest-labs/flux.2-klein-4b": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
    "black-forest-labs/flux.1-schnell": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
}


def _load_keys() -> dict[str, Any]:
    try:
        return json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 90) -> tuple[bytes, str]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        body = exc.read(1200).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())[:48].strip("-")
    return value or "jarvis-image"


def _save(raw: bytes, folder: str | None, filename: str | None) -> Path:
    destination = Path(folder).expanduser() if folder else DEFAULT_OUTPUT
    destination.mkdir(parents=True, exist_ok=True)
    extension = "jpg" if raw[:3] == b"\xff\xd8\xff" else "png"
    path = destination / f"{_filename(filename or 'jarvis-image')}-{time.strftime('%Y%m%d-%H%M%S')}.{extension}"
    path.write_bytes(raw)
    return path



def _clip_prompt(text: str, limit: int) -> str:
    """Normalize and safely shorten a provider prompt without breaking words."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    head = value[:limit]
    cut = max(head.rfind("."), head.rfind(","), head.rfind(" "))
    if cut >= int(limit * 0.80):
        head = head[:cut]
    shortened = head.rstrip(" ,.;:")
    return shortened + "." if len(shortened) < limit else shortened[:limit]


PORTRAIT_TERMS = (
    "portrait", "face", "headshot", "close-up", "close up", "person", "people",
    "woman", "man", "girl", "boy", "rosto", "retrato", "pessoa", "mulher", "homem",
)
PORTRAIT_DETAIL = (
    "high-fidelity anatomically coherent face, balanced natural facial proportions, "
    "symmetrical eyes with detailed irises and natural eyelids, realistic skin pores "
    "and subtle imperfections, accurate nose and mouth, individual hair strands, "
    "sharp focus on the eyes, soft cinematic key light, 85mm portrait lens, shallow depth of field. "
    "Avoid waxy skin, crossed eyes, malformed pupils, distorted mouth, duplicate facial features, "
    "over-smoothed skin and artificial plastic texture"
)


def _prepare_nvidia_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", str(prompt or "")).strip()
    if any(term in normalized.casefold() for term in PORTRAIT_TERMS):
        base = _clip_prompt(normalized, 500).rstrip(".")
        return _clip_prompt(f"{base}. {PORTRAIT_DETAIL}.", 800)
    return _clip_prompt(normalized, 800)


def _nvidia_key(keys: dict[str, Any]) -> str:
    return str(os.environ.get("NVIDIA_API_KEY") or keys.get("nvidia_api_key") or "").strip()


def _nvidia(prompt: str, keys: dict[str, Any]) -> bytes:
    prompt = _prepare_nvidia_prompt(prompt)
    api_key = _nvidia_key(keys)
    if not api_key:
        raise RuntimeError("NVIDIA nao configurada")
    model = str(os.environ.get("NVIDIA_IMAGE_MODEL") or keys.get("nvidia_image_model") or NVIDIA_DEFAULT_MODEL).strip()
    url = NVIDIA_ENDPOINTS.get(model)
    if not url:
        available = ", ".join(NVIDIA_ENDPOINTS)
        raise RuntimeError(f"Modelo NVIDIA invalido. Use: {available}")
    raw, content_type = _post_json(
        url,
        {"prompt": prompt, "seed": 0, "steps": 4},
        {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=180,
    )
    if content_type.startswith("image/"):
        return raw
    try:
        data = json.loads(raw.decode("utf-8"))
        artifacts = data.get("artifacts") or []
        encoded = artifacts[0].get("base64") if artifacts else None
        if not encoded:
            images = data.get("data") or []
            encoded = images[0].get("b64_json") if images else None
        if encoded:
            if encoded.startswith("data:") and "," in encoded:
                encoded = encoded.split(",", 1)[1]
            return base64.b64decode(encoded)
    except (ValueError, TypeError, KeyError, IndexError):
        pass
    raise RuntimeError(raw.decode("utf-8", errors="replace")[:1000])

def _cloudflare(prompt: str, keys: dict[str, Any]) -> bytes:
    prompt = _clip_prompt(prompt, 2048)
    account_id = str(keys.get("cloudflare_account_id") or "").strip()
    token = str(keys.get("cloudflare_api_token") or "").strip()
    if not account_id or not token:
        raise RuntimeError("Cloudflare não configurado")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{CF_MODEL}"
    raw, content_type = _post_json(url, {"prompt": prompt, "steps": 4}, {"Authorization": f"Bearer {token}"})
    if content_type.startswith("image/"):
        return raw
    try:
        encoded = json.loads(raw.decode("utf-8")).get("result", {}).get("image")
        if encoded:
            return base64.b64decode(encoded)
    except (ValueError, TypeError):
        pass
    raise RuntimeError(raw.decode("utf-8", errors="replace")[:1000])


def _gemini(prompt: str, keys: dict[str, Any]) -> bytes:
    api_key = str(keys.get("gemini_api_key") or "").strip()
    if not api_key:
        raise RuntimeError("Gemini não configurado")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    raw, _ = _post_json(url, {"contents": [{"parts": [{"text": f"Generate one image only. {prompt}"}]}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}, {})
    data = json.loads(raw.decode("utf-8"))
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini não retornou imagem")



def _director_prompt(prompt: str, context: str, keys: dict[str, Any]) -> str:
    """Turn a short request into a render-ready prompt; raw prompt remains safe fallback."""
    api_key = str(keys.get("gemini_api_key") or "").strip()
    if not api_key:
        return prompt
    brief = f"Pedido: {prompt}\nContexto adicional: {context or 'nenhum'}"
    instruction = ("You are JARVIS Visual Director. Convert the user's request into one precise, rich image-generation prompt in English. " "Preserve the requested subject, facts, style and constraints. Add only useful details for composition, environment, camera/framing, lighting, color, materials and atmosphere. " "Do not add text, logos, watermarks, extra characters or brands unless explicitly requested. Return only the final image prompt, no title or commentary.")
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + urllib.parse.quote(api_key, safe="")
    try:
        raw, _ = _post_json(url, {"system_instruction": {"parts": [{"text": instruction}]}, "contents": [{"parts": [{"text": brief}]}], "generationConfig": {"temperature": 0.45}}, {})
        data = json.loads(raw.decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        result = " ".join(str(part.get("text") or "") for part in parts).strip()
        return result if len(result) >= 20 else prompt
    except Exception:
        return prompt

def _open_reference_studio(params):
    import subprocess
    import sys
    from actions.video_generation import STUDIO, BUNDLED_PYTHON, LOG_DIR, STUDIO_LOG
    if not STUDIO.exists():
        return "NVIDIA Studio nao encontrado."
    references = params.get("reference_images") or []
    if isinstance(references, str):
        references = [references]
    if not isinstance(references, list) or len(references) > 3:
        return "Use uma lista com ate 3 caminhos de imagens."
    if str(STUDIO.parent) not in sys.path:
        sys.path.insert(0, str(STUDIO.parent))
    from media_inputs import validate_image
    try:
        for path in references:
            if not isinstance(path, str):
                raise ValueError("Cada referencia precisa ser um caminho local.")
            validate_image(path)
    except (ValueError, OSError) as exc:
        return "Anexo invalido: " + str(exc)
    prompt = str(params.get("prompt") or params.get("query") or "").strip()
    args = [str(BUNDLED_PYTHON if BUNDLED_PYTHON.exists() else Path(sys.executable)), str(STUDIO),
            "--tab", "image", "--image-model", "hf"]
    editing = bool(references) or str(params.get("action") or "").casefold() == "edit"
    if editing:
        args.append("--image-edit")
    if prompt:
        args += ["--image-prompt", prompt]
    for path in references:
        args += ["--image-reference", path]
    if prompt and (references or not editing):
        args.append("--generate-image")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with STUDIO_LOG.open("a", encoding="utf-8") as log:
        subprocess.Popen(args, cwd=str(STUDIO.parent), stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "Abri a geracao de imagens no Studio com ZeroGPU. " + (
        "Os anexos e o pedido foram encaminhados." if references else
        "Anexe sua imagem e clique em Gerar." if editing else "O Studio acompanha a geracao."
    )


def image_generation(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "generate").strip().lower()
    if action not in {"status", "config", "providers"} and (
        params.get("reference_images") or action == "edit" or
        str(params.get("provider") or "").casefold() in {"huggingface", "hf", "zerogpu"}
    ):
        return _open_reference_studio(params)
    keys = _load_keys()
    if action in {"status", "config", "providers"}:
        return "Gerador de imagens: NVIDIA {} | Cloudflare {} | ordem automatica: NVIDIA, Cloudflare.".format(
            "pronta" if _nvidia_key(keys) else "pendente",
            "pronto" if keys.get("cloudflare_account_id") and keys.get("cloudflare_api_token") else "pendente",
        )
    prompt = str(params.get("prompt") or params.get("query") or "").strip()
    if not prompt:
        return "Qual imagem você quer que eu gere?"
    requested = str(params.get("provider") or "auto").strip().lower()
    requested = "nvidia" if requested in {"nim", "nvidia-nim", "nvidia_nim"} else requested
    enhance = params.get("enhance", True) is not False
    render_prompt = _director_prompt(prompt, str(params.get("context") or ""), keys) if enhance else prompt
    providers = [requested] if requested in {"nvidia", "cloudflare"} else ["nvidia", "cloudflare"]
    errors: list[str] = []
    for provider in providers:
        try:
            if player:
                player.write_log(f"[ImageGen] {provider}")
            if provider == "nvidia":
                raw = _nvidia(render_prompt, keys)
            else:
                raw = _cloudflare(render_prompt, keys)
            path = _save(raw, params.get("folder") or params.get("path"), params.get("filename") or prompt)
            return f"Imagem criada por {provider.capitalize()} e salva em: {path}"
        except Exception as exc:
            errors.append(f"{provider}: {str(exc)[:180]}")
    return "Não consegui gerar a imagem. " + " | ".join(errors)