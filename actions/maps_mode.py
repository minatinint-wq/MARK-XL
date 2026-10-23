from __future__ import annotations

import json
import re
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "maps_mode.json"
USER_AGENT = "MARK-XLIV-JARVIS/1.0 (local personal assistant; maps_mode)"


def _default_config() -> dict[str, Any]:
    return {
        "country": "Brasil",
        "country_code": "br",
        "default_city": "",
        "default_state": "",
        "default_origin": "",
        "map_provider": "google",
        "open_after_search": False,
        "limit": 5,
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


def _http_json(url: str, timeout: int = 12) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _google_travel_mode(mode: str) -> str:
    normalized = _clean(mode).lower()
    if normalized in {"walk", "walking", "foot", "a_pe", "ape", "pedestre"}:
        return "walking"
    if normalized in {"bike", "bicycle", "cycling", "bicycling", "bicicleta"}:
        return "bicycling"
    if normalized in {"bus", "metro", "transit", "public", "publico", "transporte"}:
        return "transit"
    return "driving"


def _osrm_profile(mode: str) -> str:
    normalized = _clean(mode).lower()
    if normalized in {"walk", "walking", "foot", "a_pe", "ape", "pedestre"}:
        return "foot"
    if normalized in {"bike", "bicycle", "cycling", "bicycling", "bicicleta"}:
        return "bike"
    return "driving"


def _google_maps_url(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)


def _google_directions_url(origin: str, destination: str, mode: str = "driving") -> str:
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": _google_travel_mode(mode),
    }
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def _format_cep(cep: str) -> str:
    digits = _digits(cep)
    if len(digits) != 8:
        return cep
    return f"{digits[:5]}-{digits[5:]}"


def _format_duration(seconds: Any) -> str:
    try:
        total_minutes = max(0, round(float(seconds) / 60))
    except Exception:
        return "tempo indisponivel"
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h{minutes:02d}min"
    if hours:
        return f"{hours}h"
    return f"{minutes} min"


def _format_distance(meters: Any) -> str:
    try:
        distance = float(meters)
    except Exception:
        return "distancia indisponivel"
    if distance >= 1000:
        return f"{distance / 1000:.1f} km".replace(".", ",")
    return f"{round(distance)} m"


def _address_from_cep(data: dict[str, Any]) -> str:
    parts = [
        data.get("logradouro") or data.get("street"),
        data.get("bairro") or data.get("neighborhood"),
        data.get("localidade") or data.get("city"),
        data.get("uf") or data.get("state"),
        "Brasil",
    ]
    return ", ".join(_clean(part) for part in parts if _clean(part))


def _lookup_cep(cep: str) -> dict[str, Any]:
    digits = _digits(cep)
    if len(digits) != 8:
        raise ValueError("CEP precisa ter 8 numeros.")

    errors: list[str] = []
    try:
        data = _http_json(f"https://viacep.com.br/ws/{digits}/json/")
        if isinstance(data, dict) and not data.get("erro"):
            data["cep"] = data.get("cep") or _format_cep(digits)
            data["source"] = "ViaCEP"
            return data
        errors.append("ViaCEP sem resultado")
    except Exception as exc:
        errors.append(f"ViaCEP: {exc}")

    try:
        data = _http_json(f"https://brasilapi.com.br/api/cep/v2/{digits}")
        if isinstance(data, dict) and data.get("cep"):
            return {
                "cep": _format_cep(data.get("cep") or digits),
                "logradouro": data.get("street") or "",
                "bairro": data.get("neighborhood") or "",
                "localidade": data.get("city") or "",
                "uf": data.get("state") or "",
                "source": "BrasilAPI",
                "location": data.get("location") or {},
            }
        errors.append("BrasilAPI sem resultado")
    except Exception as exc:
        errors.append(f"BrasilAPI: {exc}")

    raise RuntimeError("; ".join(errors) or "CEP nao encontrado.")


def _build_query(params: dict[str, Any], cfg: dict[str, Any]) -> str:
    raw = _clean(
        params.get("query")
        or params.get("address")
        or params.get("endereco")
        or params.get("street")
        or params.get("rua")
        or params.get("value")
    )
    number = _clean(params.get("number") or params.get("numero"))
    city = _clean(params.get("city") or params.get("cidade") or cfg.get("default_city"))
    state = _clean(params.get("state") or params.get("uf") or params.get("estado") or cfg.get("default_state"))
    country = _clean(params.get("country") or params.get("pais") or cfg.get("country") or "Brasil")
    cep = _digits(params.get("cep") or params.get("zipcode") or params.get("postal_code"))

    if cep and not raw:
        return _address_from_cep(_lookup_cep(cep))

    bits = [raw]
    if number and number not in raw:
        bits.append(number)
    if cep:
        bits.append(_format_cep(cep))
    if city and city.lower() not in raw.lower():
        bits.append(city)
    if state and state.lower() not in raw.lower():
        bits.append(state)
    if country and country.lower() not in raw.lower():
        bits.append(country)
    return ", ".join(bit for bit in bits if bit)


def _search_address(query: str, cfg: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    if not query:
        return []
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": str(max(1, min(limit, 10))),
    }
    country_code = _clean(cfg.get("country_code")).lower()
    if country_code:
        params["countrycodes"] = country_code
    url = "https://nominatim.openstreetmap.org/search?" + urlencode(params)
    data = _http_json(url)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _geocode_one(place: str, cfg: dict[str, Any]) -> dict[str, Any]:
    query = _clean(place)
    if not query:
        raise ValueError("Endereco vazio.")
    results = _search_address(query, cfg, 1)
    if not results:
        raise RuntimeError(f"Nao encontrei '{place}'.")
    item = results[0]
    if not item.get("lat") or not item.get("lon"):
        raise RuntimeError(f"'{place}' nao retornou coordenadas.")
    return item


def _route_osrm(origin: dict[str, Any], destination: dict[str, Any], mode: str) -> dict[str, Any]:
    profile = _osrm_profile(mode)
    coords = f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    url = f"https://router.project-osrm.org/route/v1/{profile}/{coords}?overview=false&alternatives=false&steps=false"
    data = _http_json(url, timeout=15)
    if not isinstance(data, dict) or data.get("code") != "Ok":
        raise RuntimeError(str(data.get("message") or data.get("code") or "rota indisponivel"))
    routes = data.get("routes") or []
    if not routes:
        raise RuntimeError("rota sem resultado.")
    route = routes[0]
    route["profile"] = profile
    return route


def _reverse_geocode(lat: Any, lon: Any) -> dict[str, Any]:
    lat_text = _clean(lat)
    lon_text = _clean(lon)
    if not lat_text or not lon_text:
        raise ValueError("Informe lat e lon.")
    params = {"lat": lat_text, "lon": lon_text, "format": "jsonv2", "addressdetails": "1"}
    data = _http_json("https://nominatim.openstreetmap.org/reverse?" + urlencode(params))
    if not isinstance(data, dict):
        raise RuntimeError("Coordenada sem resultado.")
    return data


def _format_search(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return f"Nao encontrei endereco para: {query}"
    lines = [f"Enderecos encontrados para '{query}':"]
    for index, item in enumerate(results, 1):
        display = _clean(item.get("display_name") or item.get("name") or "Endereco")
        lat = _clean(item.get("lat"))
        lon = _clean(item.get("lon"))
        maps_url = _google_maps_url(f"{lat},{lon}" if lat and lon else display)
        lines.append(f"{index}. {display}")
        if lat and lon:
            lines.append(f"   Coordenadas: {lat}, {lon}")
        lines.append(f"   Maps: {maps_url}")
    return "\n".join(lines)


def _format_cep_result(data: dict[str, Any]) -> str:
    address = _address_from_cep(data)
    lines = [
        f"CEP {_format_cep(data.get('cep') or '')}:",
        f"Logradouro: {_clean(data.get('logradouro') or data.get('street')) or '-'}",
        f"Bairro: {_clean(data.get('bairro') or data.get('neighborhood')) or '-'}",
        f"Cidade/UF: {_clean(data.get('localidade') or data.get('city')) or '-'} / {_clean(data.get('uf') or data.get('state')) or '-'}",
        f"Fonte: {_clean(data.get('source')) or 'CEP'}",
    ]
    if address:
        lines.append(f"Maps: {_google_maps_url(address)}")
    return "\n".join(lines)


def _split_route_query(text: str) -> tuple[str, str] | None:
    phrase = _clean(text)
    if not phrase:
        return None
    patterns = [
        r"^(?:quantos?\s+minutos?|quanto\s+tempo|tempo|rota)\s+de\s+(.+?)\s+(?:ate|até|para|pra|pro)\s+(.+)$",
        r"^de\s+(.+?)\s+(?:ate|até|a|para|pra|pro)\s+(.+)$",
        r"^(.+?)\s+(?:ate|até|para|pra|pro)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, phrase, flags=re.IGNORECASE)
        if match:
            origin = _clean(match.group(1))
            destination = _clean(match.group(2))
            if origin and destination:
                return origin, destination
    return None

def _trigger_route_animation(origin: str, destination: str, mode: str, status: str) -> None:
    """Avisa o HUD 3D (Blender/Three.js) para tocar a animação RouteConsult.

    Grava memory/route_anim_trigger.json — nunca quebra a consulta se falhar.
    """
    try:
        from datetime import datetime, timezone

        trigger_path = BASE_DIR / "memory" / "route_anim_trigger.json"
        payload = {
            "event": "route_consult",
            "origin": _clean(origin),
            "destination": _clean(destination),
            "mode": _clean(mode) or "driving",
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_3d": "RouteConsult",
        }
        trigger_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _route_response(origin: str, destination: str, mode: str, cfg: dict[str, Any], open_maps: bool = False) -> str:
    if not origin:
        return "Me passa a origem da rota. Exemplo: de Avenida Paulista ate Shopping Eldorado."
    if not destination:
        return "Me passa o destino da rota."

    url = _google_directions_url(origin, destination, mode)
    _trigger_route_animation(origin, destination, mode, "started")
    try:
        origin_geo = _geocode_one(origin, cfg)
        destination_geo = _geocode_one(destination, cfg)
        route = _route_osrm(origin_geo, destination_geo, mode)
        if open_maps:
            webbrowser.open(url)
        _trigger_route_animation(origin, destination, mode, "done")
        return (
            f"De {origin} ate {destination}: cerca de {_format_duration(route.get('duration'))}, "
            f"{_format_distance(route.get('distance'))} ({_google_travel_mode(mode)}, sem transito em tempo real).\n"
            f"Maps: {url}"
        )
    except Exception as exc:
        if open_maps:
            webbrowser.open(url)
        _trigger_route_animation(origin, destination, mode, "fallback")
        return f"Nao consegui calcular o tempo exato ({exc}). Link da rota: {url}"


def maps_mode(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = _clean(params.get("action") or "search").lower()
    cfg = _load_config()

    if player:
        player.write_log(f"[Maps] {action}")

    if action in {"status", "config", "help", "ajuda"}:
        return (
            "Modo Maps ativo.\n"
            f"Pais padrao: {cfg.get('country')} ({cfg.get('country_code')})\n"
            f"Cidade/UF padrao: {cfg.get('default_city') or '-'} / {cfg.get('default_state') or '-'}\n"
            f"Origem padrao: {cfg.get('default_origin') or '-'}\n"
            "Acoes: tempo/minutos, rota, cep, endereco/search, abrir, reverse, set_default."
        )

    if action in {"set_default", "default", "configurar", "preferencia", "cidade_padrao"}:
        for src, dst in (
            ("country", "country"),
            ("pais", "country"),
            ("country_code", "country_code"),
            ("city", "default_city"),
            ("cidade", "default_city"),
            ("state", "default_state"),
            ("uf", "default_state"),
            ("estado", "default_state"),
            ("origin", "default_origin"),
            ("origem", "default_origin"),
            ("home", "default_origin"),
            ("casa", "default_origin"),
        ):
            if params.get(src) is not None:
                cfg[dst] = _clean(params.get(src))
        if params.get("open_after_search") is not None:
            cfg["open_after_search"] = bool(params.get("open_after_search"))
        if params.get("limit") is not None:
            cfg["limit"] = _safe_int(params.get("limit"), int(cfg.get("limit", 5)), 1, 10)
        _save_config(cfg)
        return "Preferencias do modo Maps salvas."

    if action in {"cep", "zipcode", "postal_code", "buscar_cep"} or params.get("cep"):
        cep = params.get("cep") or params.get("zipcode") or params.get("postal_code") or params.get("query")
        try:
            data = _lookup_cep(str(cep or ""))
            return _format_cep_result(data)
        except Exception as exc:
            return f"Nao consegui consultar esse CEP: {exc}"

    if action in {"reverse", "coordenadas", "latlon"}:
        try:
            data = _reverse_geocode(params.get("lat") or params.get("latitude"), params.get("lon") or params.get("lng") or params.get("longitude"))
            display = _clean(data.get("display_name") or "Endereco")
            return f"Endereco das coordenadas: {display}\nMaps: {_google_maps_url(display)}"
        except Exception as exc:
            return f"Nao consegui converter essas coordenadas: {exc}"

    if action in {"time", "tempo", "minutes", "minutos", "eta", "duration", "duracao", "route", "rota", "directions"}:
        origin = _clean(params.get("origin") or params.get("origem") or params.get("from") or params.get("de") or cfg.get("default_origin"))
        destination = _clean(params.get("destination") or params.get("destino") or params.get("to") or params.get("ate") or params.get("para") or params.get("query") or params.get("address"))
        raw_route = _clean(params.get("query") or params.get("text") or params.get("value"))
        parsed = _split_route_query(raw_route)
        if parsed and (not origin or not destination or raw_route == destination):
            origin, destination = parsed
        mode = _clean(params.get("mode") or params.get("travelmode") or "driving").lower()
        return _route_response(origin, destination, mode, cfg, bool(params.get("open")))

    if action in {"navegar", "navigation", "navigate", "route_open", "abrir_rota"}:
        origin = _clean(params.get("origin") or params.get("origem") or params.get("from") or params.get("de") or cfg.get("default_origin") or "Minha localizacao")
        destination = _clean(params.get("destination") or params.get("destino") or params.get("to") or params.get("ate") or params.get("para") or params.get("query") or params.get("address"))
        raw_route = _clean(params.get("query") or params.get("text") or params.get("value"))
        parsed = _split_route_query(raw_route)
        if parsed and (not destination or raw_route == destination):
            origin, destination = parsed
        mode = _clean(params.get("mode") or params.get("travelmode") or "driving").lower()
        return _route_response(origin, destination, mode, cfg, open_maps=True)

    if action in {"route_link", "link_rota"}:
        origin = _clean(params.get("origin") or params.get("origem") or params.get("from") or params.get("de") or cfg.get("default_origin"))
        destination = _clean(params.get("destination") or params.get("destino") or params.get("to") or params.get("ate") or params.get("query"))
        if not origin or not destination:
            return "Me passa origem e destino para gerar o link da rota."
        return _google_directions_url(origin, destination, _clean(params.get("mode") or "driving").lower())

    raw_phrase = _clean(params.get("query") or params.get("text") or params.get("value"))
    parsed_route = _split_route_query(raw_phrase)
    if parsed_route and any(word in raw_phrase.lower() for word in ("minuto", "tempo", "rota", "ate", "até", " para ", " pra ", " pro ")):
        return _route_response(parsed_route[0], parsed_route[1], _clean(params.get("mode") or "driving").lower(), cfg, bool(params.get("open")))

    query = _build_query(params, cfg)
    if not query:
        return "Me passa uma rua, endereco, cidade ou CEP para procurar."

    if action in {"open", "abrir", "maps", "google_maps", "open_maps"}:
        url = _google_maps_url(query)
        webbrowser.open(url)
        return f"Abri no Google Maps: {query}\n{url}"

    try:
        limit = _safe_int(params.get("limit") or params.get("count") or cfg.get("limit"), 5, 1, 10)
        results = _search_address(query, cfg, limit)
        if params.get("open") or cfg.get("open_after_search"):
            target = results[0].get("display_name") if results else query
            webbrowser.open(_google_maps_url(_clean(target)))
        return _format_search(query, results)
    except Exception as exc:
        fallback = _google_maps_url(query)
        return f"Busca de mapa falhou ({exc}). Link direto no Maps: {fallback}"


if __name__ == "__main__":
    print(maps_mode({"action": "status"}))