from __future__ import annotations

import json
import re
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_PATH = BASE_DIR / "memory" / "affective_memory.json"
_LOCK = threading.RLock()
_WHISPER = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _kind(value: str) -> str:
    raw = (value or "memory").lower().strip()
    aliases = {
        "pessoa": "person", "people": "person", "face": "person", "rosto": "person",
        "objeto": "object", "thing": "object", "coisa": "object",
        "animal": "animal", "pet": "animal", "bicho": "animal",
        "voz": "voice", "speaker": "voice", "falante": "voice",
        "som": "sound", "audio": "sound", "barulho": "sound",
    }
    return aliases.get(raw, raw if raw in {"person", "object", "animal", "voice", "sound", "memory"} else "memory")


def _slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", plain).strip("-").lower()[:80] or "memoria"


def _safe(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _obsidian_folder() -> Path:
    candidates = [
        Path(r"D:\xxxx_memory\30_Sistema\obsidian_data\xxxx-vault\YYYY\learned"),
        Path(r"D:\xxxx_memory\obsidian_data\xxxx-vault\YYYY\learned"),
        Path(r"D:\xxxx_memory"),
        BASE_DIR / "memory" / "learned",
    ]
    for root in candidates:
        try:
            if root.exists():
                return (root if root.name == "learned" else root / "learned") / "memoria_afetiva"
        except OSError:
            pass
    return BASE_DIR / "memory" / "learned" / "memoria_afetiva"


class AffectiveStore:
    def __init__(self, path: str | Path | None = None, obsidian_folder: str | Path | None = None):
        self.path = Path(path) if path else MEMORY_PATH
        self.obsidian_folder = Path(obsidian_folder) if obsidian_folder else _obsidian_folder()

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("entities", {})
                data.setdefault("events", [])
                return data
        except Exception:
            pass
        return {"version": 1, "entities": {}, "events": [], "updated_at": _now()}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _now()
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def remember(
        self,
        kind: str,
        label: str,
        emotion: str = "",
        relationship: str = "",
        details: str = "",
        importance: float = 0.5,
        source: str = "manual",
    ) -> dict[str, Any]:
        label = _safe(label, 120)
        if not label:
            raise ValueError("Informe o nome da pessoa, objeto, animal ou voz.")
        kind = _kind(kind)
        key = f"{kind}:{_slug(label)}"
        with _LOCK:
            data = self.load()
            entity = data["entities"].setdefault(key, {
                "id": key,
                "kind": kind,
                "label": label,
                "created_at": _now(),
                "observations": 0,
                "recent_events": [],
            })
            entity["label"] = label
            entity["kind"] = kind
            if emotion:
                entity["emotion"] = _safe(emotion, 240)
            if relationship:
                entity["relationship"] = _safe(relationship, 300)
            if details:
                entity["details"] = _safe(details)
            entity["importance"] = max(0.0, min(1.0, float(importance)))
            entity["source"] = _safe(source, 80)
            entity["updated_at"] = _now()
            self.save(data)
            note = self._write_note(entity)
            return {**entity, "note_path": str(note)}

    def observe(
        self,
        kind: str,
        label: str,
        event: str = "recognized",
        details: str = "",
        confidence: float | None = None,
        transcript: str = "",
        source: str = "sensor",
    ) -> dict[str, Any]:
        entity = self.remember(kind, label, source=source)
        key = entity["id"]
        with _LOCK:
            data = self.load()
            stored = data["entities"][key]
            row = {
                "timestamp": _now(),
                "event": _safe(event, 160),
                "details": _safe(details),
                "source": _safe(source, 80),
            }
            if confidence is not None:
                row["confidence"] = round(max(0.0, min(1.0, float(confidence))), 3)
            if transcript:
                row["transcript"] = _safe(transcript, 1500)
                stored["last_transcript"] = row["transcript"]
            stored["observations"] = int(stored.get("observations", 0)) + 1
            stored["last_seen"] = row["timestamp"]
            stored.setdefault("recent_events", []).append(row)
            del stored["recent_events"][:-30]
            data.setdefault("events", []).append({"entity_id": key, **row})
            del data["events"][:-500]
            self.save(data)
            note = self._write_note(stored)
            return {**stored, "note_path": str(note)}

    def list(self, kind: str = "") -> list[dict[str, Any]]:
        wanted = _kind(kind) if kind else ""
        rows = list(self.load().get("entities", {}).values())
        if wanted:
            rows = [row for row in rows if row.get("kind") == wanted]
        return sorted(rows, key=lambda row: (row.get("kind", ""), row.get("label", "").casefold()))

    def get(self, kind: str, label: str) -> dict[str, Any] | None:
        key = f"{_kind(kind)}:{_slug(label)}"
        return self.load().get("entities", {}).get(key)

    def forget(self, kind: str, label: str) -> bool:
        key = f"{_kind(kind)}:{_slug(label)}"
        with _LOCK:
            data = self.load()
            entity = data.get("entities", {}).pop(key, None)
            if entity is None:
                return False
            data["events"] = [row for row in data.get("events", []) if row.get("entity_id") != key]
            self.save(data)
            note = self.obsidian_folder / f"{_slug(entity.get('kind', 'memory'))}-{_slug(entity.get('label', label))}.md"
            note.unlink(missing_ok=True)
            return True

    def _write_note(self, entity: dict[str, Any]) -> Path:
        self.obsidian_folder.mkdir(parents=True, exist_ok=True)
        label = entity.get("label", "Memoria")
        kind = entity.get("kind", "memory")
        path = self.obsidian_folder / f"{_slug(kind)}-{_slug(label)}.md"
        lines = [
            "---",
            "type: affective-memory",
            f"entity_kind: {kind}",
            f"label: {_safe(label, 120)}",
            "tags: [jarvis, memoria-afetiva, reconhecimento, aprendizado]",
            f"updated: {entity.get('updated_at') or entity.get('last_seen') or _now()}",
            "---",
            "",
            f"# {label}",
            "",
            f"- Tipo: {kind}",
            f"- Relacao: {entity.get('relationship', 'nao informada')}",
            f"- Afeto/contexto: {entity.get('emotion', 'nao informado')}",
            f"- Importancia: {entity.get('importance', 0.5)}",
            f"- Observacoes registradas: {entity.get('observations', 0)}",
            f"- Primeiro registro: {entity.get('created_at', '')}",
            f"- Ultimo encontro: {entity.get('last_seen', '')}",
            f"- Origem: {entity.get('source', '')}",
            "",
            "## O que Jarvis deve lembrar",
            "",
            entity.get("details") or "Nenhum detalhe afetivo adicional foi informado.",
        ]
        if entity.get("last_transcript"):
            lines.extend(["", "## Ultima fala transcrita", "", entity["last_transcript"]])
        lines.extend(["", "## Encontros recentes", ""])
        events = entity.get("recent_events", [])[-12:]
        if not events:
            lines.append("Nenhum encontro confirmado ainda.")
        for row in reversed(events):
            confidence = f" ({float(row['confidence']):.0%})" if "confidence" in row else ""
            detail = f" - {row.get('details')}" if row.get("details") else ""
            lines.append(f"- {row.get('timestamp', '')}: {row.get('event', 'observado')}{confidence}{detail}")
        lines.extend(["", "## Politica", "", "A nota guarda contexto e eventos confirmados. Midia bruta nao e copiada para o Obsidian.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def transcribe_audio(path: str | Path, model: str = "base") -> dict[str, str]:
    global _WHISPER
    from faster_whisper import WhisperModel

    if _WHISPER is None:
        _WHISPER = WhisperModel(model, device="cpu", compute_type="int8", local_files_only=True)
    segments, info = _WHISPER.transcribe(str(path), beam_size=3, vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    return {"text": text, "language": str(getattr(info, "language", "") or "")}


def remember_entity(**kwargs) -> dict[str, Any]:
    return AffectiveStore().remember(**kwargs)


def observe_entity(**kwargs) -> dict[str, Any]:
    return AffectiveStore().observe(**kwargs)


def affective_memory(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()
    kind = str(params.get("kind") or params.get("type") or "")
    label = _safe(params.get("label") or params.get("name"), 120)
    store = AffectiveStore()
    if player:
        player.write_log(f"[AffectiveMemory] {action}")
    if action in {"remember", "learn", "save", "lembrar", "aprender"}:
        row = store.remember(
            kind=kind,
            label=label,
            emotion=str(params.get("emotion") or params.get("affection") or ""),
            relationship=str(params.get("relationship") or ""),
            details=str(params.get("details") or params.get("note") or ""),
            importance=float(params.get("importance") or 0.5),
            source=str(params.get("source") or "conversation"),
        )
        return f"Memoria afetiva salva: {row['label']} ({row['kind']}). Nota: {row['note_path']}"
    if action in {"observe", "seen", "recognize", "observar", "reconhecer"}:
        row = store.observe(kind=kind, label=label, event=str(params.get("event") or "recognized"), details=str(params.get("details") or ""), confidence=params.get("confidence"), transcript=str(params.get("transcript") or ""), source=str(params.get("source") or "conversation"))
        return f"Encontro registrado na memoria afetiva de {row['label']}."
    if action in {"show", "get", "ver", "consultar"}:
        row = store.get(kind, label)
        return json.dumps(row, ensure_ascii=False, indent=2) if row else f"Memoria nao encontrada: {label}"
    if action in {"list", "listar"}:
        rows = store.list(kind)
        if not rows:
            return "Nenhuma memoria afetiva registrada."
        return "Memorias afetivas:\n" + "\n".join(f"- {r['label']} ({r['kind']}): {r.get('observations', 0)} encontro(s)" for r in rows)
    if action in {"forget", "delete", "remove", "esquecer", "apagar"}:
        return f"Memoria removida: {label}" if store.forget(kind, label) else f"Memoria nao encontrada: {label}"
    rows = store.list()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("kind", "memory")] = counts.get(row.get("kind", "memory"), 0) + 1
    return f"Memoria afetiva pronta. {len(rows)} entidade(s). Tipos: {counts}. Obsidian: {store.obsidian_folder}"
