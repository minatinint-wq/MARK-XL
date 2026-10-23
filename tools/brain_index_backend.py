"""
JARVIS MARK-XLIV — Backend de indexação do cérebro (intermediário).

PIPELINE:
    Obsidian (D:\\xxxx_memory)
      → este backend vigia o cofre
      → regenera memory/neural_map_data.js (índice)
      → memory_map.html + memory_brain_3d.html passam a mostrar o novo dado
        (ambos leem o mesmo neural_map_data.js — nada muda neles)

USO:
    python tools\\brain_index_backend.py --status     # mostra estado atual
    python tools\\brain_index_backend.py --once       # checa e reindexa se mudou
    python tools\\brain_index_backend.py --force      # reindexa agora
    python tools\\brain_index_backend.py --loop 120  # vigia a cada 120s (padrão)

Pode rodar como tarefa agendada do Windows ou junto do INICIAR_JARVIS.
Nunca quebra o Jarvis: qualquer falha vira log, nunca exceção fatal.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
MEMORY_DIR = BASE_DIR / "memory"
NEURAL_JS = MEMORY_DIR / "neural_map_data.js"
STATUS_PATH = MEMORY_DIR / "brain_index_status.json"
LOG_PATH = MEMORY_DIR / "brain_index_backend.log"

sys.path.insert(0, str(BASE_DIR))


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def read_status() -> dict:
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_status(data: dict) -> None:
    try:
        STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log(f"WARN status não gravado: {exc}")


def vault_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        data = json.loads((MEMORY_DIR / "vault_index.json").read_text(encoding="utf-8"))
        for entry in data.get("vault_roots", []) or []:
            p = (entry.get("path") or "").strip() if isinstance(entry, dict) else ""
            if p:
                roots.append(Path(p))
    except Exception:
        pass
    if not roots:
        fallback = Path("D:/xxxx_memory")
        if fallback.exists():
            roots.append(fallback)
    return [r for r in roots if r.exists()]


def fingerprint() -> dict:
    """Foto rápida do cofre: qtd de .md, bytes totais e mtime máximo por raiz."""
    fps = []
    for root in vault_roots():
        count, size, max_mtime = 0, 0, 0.0
        try:
            for dirpath, _dirnames, filenames in __import__("os").walk(root):
                for fn in filenames:
                    if not fn.lower().endswith(".md"):
                        continue
                    try:
                        st = (Path(dirpath) / fn).stat()
                    except OSError:
                        continue
                    count += 1
                    size += st.st_size
                    if st.st_mtime > max_mtime:
                        max_mtime = st.st_mtime
        except Exception as exc:
            log(f"WARN walk {root}: {exc}")
        fps.append({"root": str(root), "md_count": count, "bytes": size, "max_mtime": max_mtime})
    return {"roots": fps}


def changed_since(last: dict, now: dict) -> bool:
    a = {r["root"]: (r["md_count"], r["bytes"], r["max_mtime"]) for r in last.get("fingerprint", {}).get("roots", [])}
    b = {r["root"]: (r["md_count"], r["bytes"], r["max_mtime"]) for r in now.get("roots", [])}
    return a != b


def rebuild_index() -> bool:
    """Regenera neural_map_data.js via o memory_manager oficial. Retorna True se ok."""
    try:
        from memory.memory_manager import generate_vault_groups, generate_vault_index

        generate_vault_index()
        generate_vault_groups()
        try:
            from memory_visualizer import create_memory_map_html

            # reescreve o JS embutido? não — só garante que o índice existe;
            # o HTML lê memory/neural_map_data.js direto.
            _ = create_memory_map_html
        except Exception:
            pass
        return NEURAL_JS.exists()
    except Exception:
        log("ERR rebuild:\n" + traceback.format_exc())
        return False


def cmd_status() -> int:
    st = read_status()
    fp = fingerprint()
    print(json.dumps({
        "updated": st.get("updated"),
        "last_rebuild": st.get("last_rebuild"),
        "last_result": st.get("last_result"),
        "vault": fp,
        "neural_js_exists": NEURAL_JS.exists(),
        "changed_since_last": changed_since(st, fp),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_run(force: bool) -> int:
    st = read_status()
    fp = fingerprint()
    if not force and not changed_since(st, fp) and NEURAL_JS.exists():
        log(f"OK sem mudanças ({sum(r['md_count'] for r in fp['roots'])} notas). Nada a fazer.")
        st.update({"updated": datetime.now(timezone.utc).isoformat(), "fingerprint": fp})
        write_status(st)
        return 0
    log("Indexando cofre → neural_map_data.js ...")
    ok = rebuild_index()
    st.update({
        "updated": datetime.now(timezone.utc).isoformat(),
        "last_rebuild": datetime.now(timezone.utc).isoformat(),
        "last_result": "ok" if ok else "fail",
        "fingerprint": fingerprint(),
    })
    write_status(st)
    log("OK índice atualizado — Obsidian → HTMLs (mapa + cérebro 3D)." if ok else "FALHA na reindexação (ver log).")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Backend de indexação do cérebro JARVIS")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--loop", type=int, default=0, metavar="SEG")
    args = ap.parse_args()

    if args.status:
        return cmd_status()
    if args.force:
        return cmd_run(force=True)
    if args.loop and args.loop > 0:
        log(f"Backend vigiando o cofre a cada {args.loop}s. Ctrl+C para parar.")
        try:
            while True:
                cmd_run(force=False)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            log("Backend parado.")
        return 0
    return cmd_run(force=False)


if __name__ == "__main__":
    raise SystemExit(main())
