from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
MEMORY_PATH = BASE_DIR / "memory" / "operation_memory.json"
MAX_EVENTS = 500


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    try:
        if MEMORY_PATH.exists():
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {
        "version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "counts": {},
        "contacts": {},
        "events": [],
        "preferences": {
            "silent_by_default": True,
            "require_confirmation_for_send": True,
            "learn_contacts": True,
            "learn_event_types": True,
        },
    }


def _save(data: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    data["events"] = data.get("events", [])[-MAX_EVENTS:]
    MEMORY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _inc(mapping: dict[str, Any], key: str, amount: int = 1) -> None:
    if not key:
        return
    current = mapping.get(key)
    if not isinstance(current, dict):
        current = {"count": 0, "last_seen": None}
    current["count"] = int(current.get("count") or 0) + amount
    current["last_seen"] = _now()
    mapping[key] = current


def _safe_text(value: Any, limit: int = 160) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ")
    return text[:limit]


def record_operation(source: str, action: str, metadata: dict[str, Any] | None = None, sensitive: bool = False) -> None:
    data = _load()
    metadata = metadata or {}
    source = _safe_text(source, 48).lower() or "unknown"
    action = _safe_text(action, 64).lower() or "unknown"

    counts = data.setdefault("counts", {})
    _inc(counts, source)
    _inc(counts, f"{source}:{action}")

    prefs = data.setdefault("preferences", {})
    if prefs.get("learn_contacts", True):
        contact = _safe_text(metadata.get("receiver") or metadata.get("contact") or metadata.get("username"), 80)
        platform = _safe_text(metadata.get("platform") or source, 40).lower()
        if contact:
            contacts = data.setdefault("contacts", {})
            _inc(contacts, f"{platform}:{contact}")

    clean_meta: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in {"message", "message_text", "text", "base64", "file_base64", "data_base64"}:
            if sensitive:
                clean_meta[key] = "[redacted]"
            else:
                clean_meta[key] = _safe_text(value, 100)
        else:
            clean_meta[key] = _safe_text(value, 140) if isinstance(value, str) else value

    event = {
        "time": _now(),
        "source": source,
        "action": action,
        "metadata": clean_meta,
    }
    data.setdefault("events", []).append(event)
    _save(data)


def set_preference(key: str, value: Any) -> str:
    data = _load()
    data.setdefault("preferences", {})[str(key)] = value
    _save(data)
    return f"Preferencia operacional salva: {key}={value}"


def _top(mapping: dict[str, Any], limit: int = 8) -> list[tuple[str, int]]:
    items = []
    for key, value in mapping.items():
        if isinstance(value, dict):
            items.append((key, int(value.get("count") or 0)))
    return sorted(items, key=lambda item: item[1], reverse=True)[:limit]


def summary(limit: int = 8) -> str:
    data = _load()
    lines = [
        "Memoria operacional:",
        f"- eventos: {len(data.get('events', []))}",
        f"- atualizado: {data.get('updated_at')}",
        "- operacoes frequentes:",
    ]
    for key, count in _top(data.get("counts", {}), limit):
        lines.append(f"  - {key}: {count}")
    lines.append("- contatos frequentes:")
    contacts = _top(data.get("contacts", {}), limit)
    if contacts:
        for key, count in contacts:
            lines.append(f"  - {key}: {count}")
    else:
        lines.append("  - nenhum ainda")
    return "\n".join(lines)


def operation_memory(parameters: dict[str, Any] | None = None, player=None, speak=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()
    if action in {"status", "summary", "resumo"}:
        return summary(int(params.get("limit") or 8))
    if action in {"list", "events", "listar"}:
        data = _load()
        events = data.get("events", [])[-int(params.get("limit") or 20):][::-1]
        if not events:
            return "Nenhuma operacao aprendida ainda."
        return json.dumps(events, indent=2, ensure_ascii=False)
    if action in {"clear", "limpar"}:
        _save({
            "version": 1,
            "created_at": _now(),
            "updated_at": _now(),
            "counts": {},
            "contacts": {},
            "events": [],
            "preferences": _load().get("preferences", {}),
        })
        return "Memoria operacional limpa."
    if action in {"set_preference", "preferencia"}:
        key = params.get("key")
        if not key:
            return "Informe key para salvar preferencia operacional."
        return set_preference(str(key), params.get("value"))
    if action in {"record", "learn", "aprender"}:
        record_operation(
            str(params.get("source") or "manual"),
            str(params.get("operation") or params.get("name") or "manual"),
            params.get("metadata") if isinstance(params.get("metadata"), dict) else params,
        )
        return "Operacao aprendida."
    return "Acao desconhecida. Use status, list, clear, set_preference ou record."

