"""AI image generator with silent Cloudflare -> Gemini failover."""
from __future__ import annotations

import base64
import json
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


def _cloudflare(prompt: str, keys: dict[str, Any]) -> bytes:
    account_id = str(keys.get("cloudflare_account_id") or "").strip()
    token = str(keys.get("cloudflare_api_token") or "").strip()
    if not account_id or not token:
        raise RuntimeError("Cloudflare não configurado")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{CF_MODEL}"
    raw, content_type = _post_json(url, {"prompt": prompt, "num_steps": 4}, {"Authorization": f"Bearer {token}"})
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

def image_generation(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "generate").strip().lower()
    keys = _load_keys()
    if action in {"status", "config", "providers"}:
        return "Gerador de imagens: Cloudflare {} | Gemini {} | failover silencioso.".format("pronto" if keys.get("cloudflare_account_id") and keys.get("cloudflare_api_token") else "pendente", "pronto" if keys.get("gemini_api_key") else "pendente")
    prompt = str(params.get("prompt") or params.get("query") or "").strip()
    if not prompt:
        return "Qual imagem você quer que eu gere?"
    requested = str(params.get("provider") or "auto").strip().lower()
    enhance = params.get("enhance", True) is not False
    render_prompt = _director_prompt(prompt, str(params.get("context") or ""), keys) if enhance else prompt
    providers = [requested] if requested in {"cloudflare", "gemini"} else ["cloudflare", "gemini"]
    errors: list[str] = []
    for provider in providers:
        try:
            if player:
                player.write_log(f"[ImageGen] {provider}")
            raw = _cloudflare(render_prompt, keys) if provider == "cloudflare" else _gemini(render_prompt, keys)
            path = _save(raw, params.get("folder") or params.get("path"), params.get("filename") or prompt)
            return f"Imagem criada por {provider.capitalize()} e salva em: {path}"
        except Exception as exc:
            errors.append(f"{provider}: {str(exc)[:180]}")
    return "Não consegui gerar a imagem. " + " | ".join(errors)