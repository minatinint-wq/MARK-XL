from __future__ import annotations
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

TOKEN_FILE = Path(__file__).resolve().parent / ".hf-token.dpapi"
DEFAULT_KEYS = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def stored_token() -> str:
    if not TOKEN_FILE.exists():
        return ""
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(TOKEN_FILE.read_bytes(), None, None, None, 0)[1].decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Nao foi possivel abrir o token protegido. Configure novamente a conta Hugging Face.") from exc


def huggingface_token() -> str:
    # The account explicitly saved in this Studio takes precedence.
    saved = stored_token()
    if saved:
        return saved
    for name in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_API_KEY"):
        token = os.environ.get(name, "").strip()
        if token:
            return token
    try:
        config = json.loads(Path(os.environ.get("JARVIS_API_KEYS", str(DEFAULT_KEYS))).read_text(encoding="utf-8"))
        for name in ("huggingface_api_key", "huggingface_token", "hf_token"):
            token = str(config.get(name) or "").strip()
            if token:
                return token
    except (OSError, ValueError, AttributeError):
        pass
    from huggingface_hub import get_token
    return get_token() or ""


def validate_token(token: str) -> dict:
    token = token.strip()
    if not re.fullmatch(r"hf_[A-Za-z0-9]{8,}", token):
        raise ValueError("Cole o token completo, com inicio hf_.")
    request = urllib.request.Request(
        "https://huggingface.co/api/whoami-v2",
        headers={"Authorization": "Bearer " + token, "User-Agent": "Jarvis-Studio"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError("Token invalido ou sem acesso. Confira o token de leitura na sua conta.") from None
        raise RuntimeError(f"Hugging Face respondeu HTTP {exc.code}. Tente novamente depois.") from None
    except (OSError, ValueError):
        raise RuntimeError("Nao foi possivel validar a conta. Confira a conexao e tente novamente.") from None
    username = result.get("name")
    if not isinstance(username, str) or not username:
        raise RuntimeError("Hugging Face nao retornou uma conta pessoal valida.")
    # Never return the raw API response (it can contain credential metadata).
    return {"username": username, "email_verified": result.get("emailVerified"),
            "is_pro": bool(result.get("isPro", False))}


def save_token(token: str) -> None:
    import win32crypt
    encrypted = win32crypt.CryptProtectData(token.strip().encode("utf-8"), "Jarvis Hugging Face", None, None, None, 0)
    temp = TOKEN_FILE.with_name(TOKEN_FILE.name + ".tmp")
    try:
        with temp.open("wb") as output:
            output.write(encrypted)
        temp.replace(TOKEN_FILE)
    finally:
        temp.unlink(missing_ok=True)


def safe_error(error: Exception) -> str:
    # Do not allow server errors to echo a credential into the GUI/log.
    message = str(error).strip() or type(error).__name__
    return re.sub(r"hf_[A-Za-z0-9]+", "[token oculto]", message)
