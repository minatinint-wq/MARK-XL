"""Build a key-free source distribution from the Git-tracked Jarvis files.

This intentionally omits all 3D/media assets, Python runtime, local state,
private config and the personal prompt. It never copies a live install.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "packaging" / "external"
NEEDED_ROOT = {"main.py", "ui.py", "requirements.txt"}
NEEDED_CONFIG = {
    "config/__init__.py", "config/api_keys.example.json",
    "config/spotify_credentials.example.json", "config/local_llm.example.json",
}
NEEDED_TOOLS = {"tools/api_key_manager.py"}
FORBIDDEN_NAMES = {
    "api_keys.json", "spotify_credentials.json", "gmail_oauth_client.json",
    ".remote_ai_access.key", ".gmail_token.dpapi", ".env",
}
SECRET_MARKERS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|client[_-]?secret)\s*[:=]\s*['\"](?!PASTE_|SEU_|YOUR_)[A-Za-z0-9_-]{32,}['\"]"),
)


def include(path: str) -> bool:
    if path in NEEDED_ROOT | NEEDED_CONFIG | NEEDED_TOOLS | {"core/protocol.json"}:
        return True
    if path.startswith(("actions/", "agent/", "memory/")) and path.endswith(".py"):
        return True
    return False


def sanitize_source(text: str) -> str:
    # Only references in source text, not secret values. The personal prompt
    # is replaced in full from the external template below.
    return (text.replace("Sabrina", "usuário")
                .replace("Lucas", "usuário")
                .replace("LRM TECNO", "assistente local")
                .replace("Tony Stark's AI assistant", "a helpful local assistant")
                .replace("Iron-Man-style interface", "holographic interface")
                .replace("JARVIS_LEADIO_AI_KEY", "JARVIS_REMOTE_AI_KEY"))


def build(target: Path) -> Path:
    target = target.resolve()
    archive = target.with_suffix(".zip")
    if target.exists() or archive.exists():
        raise FileExistsError("Destino ou ZIP já existe; escolha um novo nome para preservar arquivos.")
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    tracked = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    selected = [item for item in tracked if include(item)]
    if len(selected) < 90:
        raise RuntimeError("Conjunto de fontes inesperadamente pequeno; build interrompido.")
    target.mkdir(parents=True)
    try:
        for rel in selected:
            source = ROOT / rel
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == ".py":
                dest.write_text(sanitize_source(source.read_text(encoding="utf-8-sig")), encoding="utf-8")
            else:
                shutil.copy2(source, dest)
        (target / "core" / "prompt.txt").write_text(
            (TEMPLATE / "core_prompt.txt").read_text(encoding="utf-8"), encoding="utf-8"
        )
        shutil.copy2(TEMPLATE / "core_protocol.json", target / "core" / "protocol.json")
        shutil.copy2(TEMPLATE / "remote_ai_gateway_stub.py", target / "actions" / "remote_ai_gateway.py")
        shutil.copy2(TEMPLATE / "relay_connector_stub.py", target / "actions" / "jarvis_relay_connector.py")
        shutil.copy2(TEMPLATE / "lrm_navigation_stub.py", target / "actions" / "lrm_navigation.py")
        for name in ("LICENSE", "CONTENT_LICENSE.md", "README.md", "INSTALAR.bat", "INICIAR.bat", ".gitignore"):
            shutil.copy2(TEMPLATE / name, target / name)
        for item in target.rglob("*"):
            if not item.is_file():
                continue
            if item.name.lower() in FORBIDDEN_NAMES:
                raise RuntimeError(f"Arquivo privado detectado: {item.relative_to(target)}")
            if item.suffix.lower() in {".py", ".txt", ".json", ".md", ".bat"}:
                contents = item.read_text(encoding="utf-8-sig")
                if "Sabrina" in contents or "Tony Stark" in contents or any(p.search(contents) for p in SECRET_MARKERS):
                    raise RuntimeError(f"Referência privada ou segredo detectado: {item.relative_to(target)}")
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for item in sorted(target.rglob("*")):
                if item.is_file():
                    zf.write(item, arcname=f"{target.name}/{item.relative_to(target).as_posix()}")
        with zipfile.ZipFile(archive) as zf:
            if zf.testzip() is not None:
                raise RuntimeError("Falha na verificação CRC do ZIP.")
    except Exception:
        # Keep the staged output for inspection; never overwrite or delete it.
        raise
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Nova pasta de release")
    args = parser.parse_args()
    try:
        result = build(args.output)
    except Exception as exc:
        print(f"Release externa não criada: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Release externa: {result}")
