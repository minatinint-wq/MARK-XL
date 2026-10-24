"""Build a private 8 GB transfer folder, without committing credentials."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _fish_key(source: Path) -> str:
    module_path = source / "actions" / "fish_voice.py"
    spec = importlib.util.spec_from_file_location("jarvis_source_fish_voice", module_path)
    if spec is None or spec.loader is None:
        return ""
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_key().strip()


def build(source: Path, output: Path) -> None:
    source = source.resolve()
    output = output.resolve()
    if not (source / "config" / "api_keys.json").is_file():
        raise RuntimeError("A origem não contém config/api_keys.json.")
    if output.exists():
        raise RuntimeError("O destino já existe; escolha uma pasta privada nova.")
    if _inside(output, ROOT) or _inside(output, source) or _inside(source, output):
        raise RuntimeError("O destino precisa ficar fora das pastas do código e da origem.")

    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    tracked = [Path(raw.decode("utf-8")) for raw in paths if raw]
    output.mkdir(parents=True)
    for relative in tracked:
        src = ROOT / relative
        if not src.is_file():
            continue
        dest = output / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    private = output / "config"
    private.mkdir(exist_ok=True)
    shutil.copy2(source / "config" / "api_keys.json", private / "api_keys.json")
    spotify = source / "config" / "spotify_credentials.json"
    if spotify.is_file():
        shutil.copy2(spotify, private / "spotify_credentials.json")
    fish_settings = source / "config" / "fish_voice.json"
    if fish_settings.is_file():
        shutil.copy2(fish_settings, private / "fish_voice.json")

    local_config = json.loads((ROOT / "config" / "local_llm.example.json").read_text(encoding="utf-8"))
    local_config.update({"mode": "normal", "model": local_config["normal_model"],
                         "parameters_b": 1, "num_ctx": 2048, "num_predict": 128,
                         "keep_alive": "0"})
    (private / "local_llm.json").write_text(
        json.dumps(local_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fish_key = _fish_key(source)
    if fish_key:
        (private / ".fish-key-transfer.txt").write_text(fish_key + "\n", encoding="utf-8")
    cache = Path.home() / ".spotify_cache"
    if cache.is_file():
        shutil.copy2(cache, private / ".spotify-cache-transfer.json")

    print(f"Pacote privado criado em: {output}")
    print(f"Chave Fish para migração: {'sim' if fish_key else 'não'}")
    print(f"Sessão Spotify para migração: {'sim' if cache.is_file() else 'não'}")
    print("ATENÇÃO: contém credenciais legíveis; não envie para GitHub ou link público.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="instalação atual com as chaves")
    parser.add_argument("--output", type=Path, required=True, help="nova pasta privada para transferência")
    args = parser.parse_args()
    build(args.source, args.output)
