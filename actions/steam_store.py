from __future__ import annotations

import json
import os
import re
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "steam_store.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

TASKBAR_HERO_APPID = "3678970"
TASKBAR_HERO_QUERY = "TBH Task Bar Hero"
KNOWN_APPS = {
    "tbh": (TASKBAR_HERO_APPID, "TBH: Task Bar Hero"),
    "taskbar hero": (TASKBAR_HERO_APPID, "TBH: Task Bar Hero"),
    "task bar hero": (TASKBAR_HERO_APPID, "TBH: Task Bar Hero"),
    "taskbarheroes": (TASKBAR_HERO_APPID, "TBH: Task Bar Hero"),
    "taskbar heroes": (TASKBAR_HERO_APPID, "TBH: Task Bar Hero"),
}


def _default_config() -> dict[str, Any]:
    return {
        "country": "BR",
        "language": "brazilian",
        "market_currency": 7,
        "default_appid": TASKBAR_HERO_APPID,
        "default_game": "TBH: Task Bar Hero",
        "brain_category": "games",
        "brain_note_name": "steam-tbh-task-bar-hero-precos",
    }


def _load_config() -> dict[str, Any]:
    cfg = _default_config()
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if v is not None})
    except Exception:
        pass
    return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _http_json(url: str, params: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    import requests

    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Resposta Steam invalida.")
    return data


def _resolve_app(params: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str]:
    appid = str(params.get("appid") or params.get("app_id") or "").strip()
    if appid:
        return appid, str(params.get("game") or params.get("game_name") or f"Steam App {appid}")

    raw = str(params.get("game") or params.get("game_name") or params.get("query") or cfg.get("default_game") or "").lower().strip()
    if raw in KNOWN_APPS:
        return KNOWN_APPS[raw]
    for key, value in KNOWN_APPS.items():
        if key in raw or raw in key:
            return value
    return str(cfg.get("default_appid") or TASKBAR_HERO_APPID), str(cfg.get("default_game") or "TBH: Task Bar Hero")


def _price_from_store_price(price: dict[str, Any] | None, is_free: bool = False) -> str:
    if is_free:
        return "Gratis"
    if not price:
        return "Preco indisponivel"
    if price.get("final_formatted"):
        return str(price["final_formatted"])
    currency = str(price.get("currency") or "").strip()
    final = price.get("final")
    if isinstance(final, int):
        return f"{currency} {final / 100:.2f}".strip()
    return "Preco indisponivel"


def _store_search(query: str, cfg: dict[str, Any], count: int = 10) -> list[dict[str, Any]]:
    data = _http_json(
        "https://store.steampowered.com/api/storesearch/",
        {
            "term": query,
            "cc": cfg.get("country", "BR"),
            "l": cfg.get("language", "brazilian"),
            "count": max(1, min(int(count or 10), 50)),
        },
    )
    return list(data.get("items") or [])


def _app_details(appid: str, cfg: dict[str, Any]) -> dict[str, Any]:
    data = _http_json(
        "https://store.steampowered.com/api/appdetails",
        {
            "appids": appid,
            "cc": cfg.get("country", "BR"),
            "l": cfg.get("language", "brazilian"),
        },
    )
    payload = data.get(str(appid)) or {}
    if not payload.get("success"):
        raise ValueError(f"AppID Steam nao encontrado: {appid}")
    details = payload.get("data") or {}
    if not isinstance(details, dict):
        raise ValueError(f"Detalhes Steam invalidos para {appid}")
    return details


def _market_search(appid: str, query: str, cfg: dict[str, Any], count: int = 10) -> dict[str, Any]:
    return _http_json(
        "https://steamcommunity.com/market/search/render/",
        {
            "appid": appid,
            "query": query or "",
            "norender": 1,
            "count": max(1, min(int(count or 10), 100)),
            "start": 0,
            "currency": int(cfg.get("market_currency") or 7),
        },
    )


def _market_priceoverview(appid: str, item_name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return _http_json(
        "https://steamcommunity.com/market/priceoverview/",
        {
            "appid": appid,
            "market_hash_name": item_name,
            "currency": int(cfg.get("market_currency") or 7),
        },
    )


def _format_store_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Nenhum resultado de loja encontrado."
    lines = ["Steam Store:"]
    for item in items:
        price = _price_from_store_price(item.get("price") or item.get("price_overview"), is_free=bool(item.get("is_free")))
        appid = item.get("id") or item.get("steam_appid") or ""
        extra = f" | erro: {item.get('error')}" if item.get("error") else ""
        lines.append(f"- {item.get('name', 'sem nome')} | AppID {appid} | {price}{extra}")
    return "\n".join(lines)


def _dlc_items_from_details(details: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for dlc_appid in list(details.get("dlc") or [])[:25]:
        try:
            dlc = _app_details(str(dlc_appid), cfg)
            dlc["id"] = dlc.get("steam_appid") or dlc_appid
            items.append(dlc)
        except Exception as exc:
            items.append({"id": dlc_appid, "name": f"DLC {dlc_appid}", "error": str(exc)})
    return items


def _format_app_details(details: dict[str, Any]) -> str:
    name = details.get("name") or "Steam app"
    appid = details.get("steam_appid") or ""
    price = _price_from_store_price(details.get("price_overview"), is_free=bool(details.get("is_free")))
    devs = ", ".join(details.get("developers") or [])
    pubs = ", ".join(details.get("publishers") or [])
    release = (details.get("release_date") or {}).get("date") or ""
    genres = ", ".join(item.get("description", "") for item in details.get("genres") or [] if item.get("description"))
    categories = ", ".join(item.get("description", "") for item in details.get("categories") or [] if item.get("description"))
    return (
        f"{name} | AppID {appid}\n"
        f"Preco base: {price}\n"
        f"Desenvolvedor: {devs or 'indisponivel'}\n"
        f"Publicador: {pubs or 'indisponivel'}\n"
        f"Lancamento: {release or 'indisponivel'}\n"
        f"Generos: {genres or 'indisponivel'}\n"
        f"Categorias: {categories or 'indisponivel'}"
    )


def _format_market_results(data: dict[str, Any], count: int = 10) -> str:
    if data.get("error"):
        return f"Steam Market: indisponivel agora ({data.get('error')})."
    results = list(data.get("results") or [])
    total = data.get("total_count", len(results))
    if not results:
        return f"Steam Market: nenhum item encontrado. Total reportado: {total}."
    lines = [f"Steam Market: {total} item(ns) encontrado(s), exibindo {min(count, len(results))}:"]
    for item in results[:count]:
        name = item.get("name") or item.get("hash_name") or "item"
        price = item.get("sell_price_text") or item.get("sale_price_text") or "preco indisponivel"
        listings = item.get("sell_listings")
        item_type = ((item.get("asset_description") or {}).get("type") or "").strip()
        suffix = f" | {item_type}" if item_type else ""
        listings_text = f" | {listings} listagem(ns)" if listings is not None else ""
        lines.append(f"- {name}: {price}{listings_text}{suffix}")
    return "\n".join(lines)


def _taskbar_snapshot(cfg: dict[str, Any], market_query: str = "", count: int = 10) -> dict[str, Any]:
    details = _app_details(TASKBAR_HERO_APPID, cfg)
    store_items = _store_search(TASKBAR_HERO_QUERY, cfg, count=10)
    if not store_items:
        store_items = _dlc_items_from_details(details, cfg)
    try:
        market = _market_search(TASKBAR_HERO_APPID, market_query, cfg, count=count)
    except Exception as exc:
        market = {"success": False, "error": str(exc), "results": [], "total_count": 0}
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": details,
        "store_items": store_items,
        "market": market,
    }


def _snapshot_markdown(snapshot: dict[str, Any], cfg: dict[str, Any], market_query: str = "") -> str:
    details = snapshot["details"]
    store_items = snapshot["store_items"]
    market = snapshot["market"]
    timestamp = snapshot["timestamp"]
    store_url = f"https://store.steampowered.com/app/{TASKBAR_HERO_APPID}/"
    market_url = f"https://steamcommunity.com/market/search?appid={TASKBAR_HERO_APPID}&q={quote(market_query or '')}"
    return (
        f"Atualizado em: {timestamp}\n\n"
        "## Resumo rapido\n\n"
        "- Jogo principal: TBH: Task Bar Hero.\n"
        f"- AppID principal: {TASKBAR_HERO_APPID}.\n"
        f"- Preco base atual: {_price_from_store_price(details.get('price_overview'), bool(details.get('is_free')))}.\n"
        "- Modelo de custo: jogo base free-to-play; custos aparecem em DLCs/packs e itens do Steam Market.\n"
        "- Risco: os precos do Market sao volateis e podem ser inflados por baixa liquidez, bots ou hype.\n"
        f"- Loja: {store_url}\n"
        f"- Market: {market_url}\n\n"
        "## Store / DLCs / Packs\n\n"
        f"{_format_store_items(store_items)}\n\n"
        "## Marketplace snapshot\n\n"
        f"{_format_market_results(market, count=10)}\n\n"
        "## Como o Jarvis deve usar\n\n"
        "- Para preco base: chamar steam_store com action='price' ou action='taskbar_hero'.\n"
        "- Para itens: chamar steam_store com action='market', appid='3678970' e query opcional.\n"
        "- Para atualizar esta nota: chamar steam_store com action='save_taskbar_hero'.\n"
    )


def _save_snapshot_to_brain(snapshot: dict[str, Any], cfg: dict[str, Any], market_query: str = "") -> str:
    from actions.obsidian_controller import obsidian_control

    content = _snapshot_markdown(snapshot, cfg, market_query=market_query)
    return obsidian_control(
        {
            "action": "create",
            "category": cfg.get("brain_category") or "games",
            "title": "Steam - TBH: Task Bar Hero - preços e custos",
            "name": cfg.get("brain_note_name") or "steam-tbh-task-bar-hero-precos",
            "content": content,
            "tags": ["games", "steam", "taskbar-hero", "precos", "market"],
            "overwrite": True,
            "sync": False,
        }
    )


def steam_store(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "taskbar_hero").lower().strip().replace("-", "_")
    cfg = _load_config()

    if player:
        try:
            player.write_log(f"[SteamStore] {action}")
        except Exception:
            pass

    if action in {"status", "config"}:
        return (
            "Steam Store pronto.\n"
            f"Pais: {cfg.get('country')}\n"
            f"Idioma: {cfg.get('language')}\n"
            f"Market currency: {cfg.get('market_currency')}\n"
            f"TBH AppID: {TASKBAR_HERO_APPID}"
        )

    if action in {"set_config", "configurar"}:
        for key in ("country", "language", "market_currency", "brain_category", "brain_note_name"):
            if params.get(key) is not None:
                cfg[key] = params[key]
        _save_config(cfg)
        return "Config Steam Store salva."

    if action in {"search", "buscar"}:
        query = str(params.get("query") or params.get("game") or TASKBAR_HERO_QUERY).strip()
        count = int(params.get("count") or 10)
        items = _store_search(query, cfg, count=count)
        appid, _ = _resolve_app({"query": query}, cfg)
        if not items and appid == TASKBAR_HERO_APPID:
            details = _app_details(TASKBAR_HERO_APPID, cfg)
            items = [details, *_dlc_items_from_details(details, cfg)]
        return _format_store_items(items)

    if action in {"details", "detail", "price", "preco", "preços", "custos"}:
        appid, _ = _resolve_app(params, cfg)
        return _format_app_details(_app_details(appid, cfg))

    if action in {"market", "market_search", "marketplace", "itens"}:
        appid, _ = _resolve_app(params, cfg)
        query = str(params.get("query") or params.get("item") or "").strip()
        count = int(params.get("count") or 10)
        try:
            market = _market_search(appid, query, cfg, count=count)
        except Exception as exc:
            return _format_market_results({"error": str(exc), "results": [], "total_count": 0}, count=count)
        return _format_market_results(market, count=count)

    if action in {"item", "priceoverview", "item_price"}:
        appid, _ = _resolve_app(params, cfg)
        item = str(params.get("item") or params.get("market_hash_name") or params.get("query") or "").strip()
        if not item:
            return "Informe item/market_hash_name para consultar preco de item."
        data = _market_priceoverview(appid, item, cfg)
        if not data.get("success"):
            return f"Preco indisponivel para item: {item}"
        return (
            f"{item}\n"
            f"Menor preco: {data.get('lowest_price', 'indisponivel')}\n"
            f"Mediana: {data.get('median_price', 'indisponivel')}\n"
            f"Volume: {data.get('volume', 'indisponivel')}"
        )

    if action in {"taskbar_hero", "tbh", "snapshot"}:
        market_query = str(params.get("market_query") or params.get("query") or "").strip()
        count = int(params.get("count") or 10)
        snapshot = _taskbar_snapshot(cfg, market_query=market_query, count=count)
        return (
            f"{_format_app_details(snapshot['details'])}\n\n"
            f"{_format_store_items(snapshot['store_items'])}\n\n"
            f"{_format_market_results(snapshot['market'], count=count)}"
        )

    if action in {"save_taskbar_hero", "save_snapshot", "salvar_cerebro", "salvar_no_cerebro"}:
        market_query = str(params.get("market_query") or params.get("query") or "").strip()
        snapshot = _taskbar_snapshot(cfg, market_query=market_query, count=10)
        saved = _save_snapshot_to_brain(snapshot, cfg, market_query=market_query)
        return f"{saved}\nSnapshot Steam salvo/atualizado para TBH."

    if action in {"open_store", "abrir_loja"}:
        appid, _ = _resolve_app(params, cfg)
        webbrowser.open(f"https://store.steampowered.com/app/{appid}/")
        return f"Abrindo loja Steam AppID {appid}."

    if action in {"open_market", "abrir_market"}:
        appid, _ = _resolve_app(params, cfg)
        query = str(params.get("query") or "").strip()
        webbrowser.open(f"https://steamcommunity.com/market/search?appid={appid}&q={quote(query)}")
        return f"Abrindo Steam Market AppID {appid}."

    return "Acao Steam Store desconhecida. Use status, search, price, market, item, taskbar_hero, save_taskbar_hero, open_store ou open_market."


if __name__ == "__main__":
    print(steam_store({"action": "taskbar_hero", "count": 5}))





