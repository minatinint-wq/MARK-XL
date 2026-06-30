from __future__ import annotations

import json
import re
import webbrowser
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


USER_AGENT = "MARK-XL-JARVIS/1.0 (local personal assistant; weather_report)"

WEATHER_CODES = {
    0: "ceu limpo",
    1: "principalmente limpo",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina com geada",
    51: "garoa fraca",
    53: "garoa moderada",
    55: "garoa forte",
    56: "garoa congelante fraca",
    57: "garoa congelante forte",
    61: "chuva fraca",
    63: "chuva moderada",
    65: "chuva forte",
    66: "chuva congelante fraca",
    67: "chuva congelante forte",
    71: "neve fraca",
    73: "neve moderada",
    75: "neve forte",
    77: "graos de neve",
    80: "pancadas fracas",
    81: "pancadas moderadas",
    82: "pancadas fortes",
    85: "pancadas de neve fracas",
    86: "pancadas de neve fortes",
    95: "trovoadas",
    96: "trovoadas com granizo fraco",
    99: "trovoadas com granizo forte",
}


def _http_json(url: str, timeout: int = 15) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _fmt_number(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value)
    except Exception:
        return "-"
    if decimals <= 0:
        return str(round(number))
    return f"{number:.{decimals}f}".replace(".", ",")


def _weather_label(code: Any) -> str:
    try:
        return WEATHER_CODES.get(int(code), "condicao desconhecida")
    except Exception:
        return "condicao desconhecida"


def _rain_hint(probability: Any, amount: Any = None) -> str:
    try:
        prob = float(probability)
    except Exception:
        prob = 0.0
    try:
        rain = float(amount or 0)
    except Exception:
        rain = 0.0
    if prob >= 70 or rain >= 10:
        return "alta chance de chuva"
    if prob >= 40 or rain >= 2:
        return "chance moderada de chuva"
    if prob >= 20 or rain > 0:
        return "baixa chance de chuva"
    return "sem sinal forte de chuva"


def _extract_location(params: dict[str, Any]) -> str:
    return _clean(
        params.get("city")
        or params.get("cidade")
        or params.get("location")
        or params.get("local")
        or params.get("query")
        or params.get("address")
        or params.get("endereco")
        or params.get("value")
    )


def _geocode_open_meteo(location: str) -> dict[str, Any] | None:
    params = {
        "name": location,
        "count": "1",
        "language": "pt",
        "format": "json",
    }
    data = _http_json("https://geocoding-api.open-meteo.com/v1/search?" + urlencode(params))
    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        return None
    item = results[0]
    return {
        "lat": item.get("latitude"),
        "lon": item.get("longitude"),
        "name": item.get("name") or location,
        "admin1": item.get("admin1") or "",
        "country": item.get("country") or "",
        "source": "Open-Meteo Geocoding",
    }


def _geocode_location(params: dict[str, Any]) -> dict[str, Any]:
    lat = _clean(params.get("lat") or params.get("latitude"))
    lon = _clean(params.get("lon") or params.get("lng") or params.get("longitude"))
    if lat and lon:
        return {"lat": lat, "lon": lon, "name": _extract_location(params) or f"{lat},{lon}", "source": "coordenadas"}

    cep = _clean(params.get("cep") or params.get("zipcode") or params.get("postal_code"))
    if cep:
        try:
            from actions.maps_mode import _address_from_cep, _lookup_cep

            cep_data = _lookup_cep(cep)
            location = _address_from_cep(cep_data)
            if location:
                params = dict(params)
                params["location"] = location
        except Exception:
            pass

    location = _extract_location(params)
    if not location:
        raise ValueError("Me passa a cidade, endereco, CEP ou coordenadas para ver a previsao.")

    try:
        found = _geocode_open_meteo(location)
        if found:
            return found
    except Exception:
        pass

    try:
        from actions.maps_mode import _geocode_one, _load_config

        item = _geocode_one(location, _load_config())
        return {
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "name": item.get("display_name") or location,
            "source": "OpenStreetMap",
        }
    except Exception as exc:
        raise RuntimeError(f"Nao encontrei a localizacao '{location}': {exc}") from exc


def _fetch_forecast(place: dict[str, Any], days: int) -> dict[str, Any]:
    params = {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": str(days),
    }
    return _http_json("https://api.open-meteo.com/v1/forecast?" + urlencode(params))


def _day_index(when: str, max_days: int) -> int:
    text = _clean(when).lower()
    if any(word in text for word in ("amanha", "amanhã", "tomorrow")):
        return min(1, max_days - 1)
    match = re.search(r"\b(?:dia|day)\s*(\d+)\b", text)
    if match:
        return max(0, min(max_days - 1, int(match.group(1)) - 1))
    return 0


def _format_current(place: dict[str, Any], data: dict[str, Any]) -> str:
    current = data.get("current") or {}
    name = _clean(place.get("name"))
    return (
        f"Agora em {name}: {_fmt_number(current.get('temperature_2m'))}°C, "
        f"sensacao de {_fmt_number(current.get('apparent_temperature'))}°C, "
        f"{_weather_label(current.get('weather_code'))}. "
        f"Umidade {_fmt_number(current.get('relative_humidity_2m'))}%, "
        f"vento {_fmt_number(current.get('wind_speed_10m'))} km/h."
    )


def _format_daily(place: dict[str, Any], data: dict[str, Any], when: str, days: int) -> str:
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return "Previsao indisponivel para esse local."
    idx = _day_index(when, len(times))
    date = times[idx]
    name = _clean(place.get("name"))
    max_temp = (daily.get("temperature_2m_max") or [None])[idx]
    min_temp = (daily.get("temperature_2m_min") or [None])[idx]
    rain_prob = (daily.get("precipitation_probability_max") or [None])[idx]
    rain_sum = (daily.get("precipitation_sum") or [None])[idx]
    wind = (daily.get("wind_speed_10m_max") or [None])[idx]
    code = (daily.get("weather_code") or [None])[idx]
    label_day = "hoje" if idx == 0 else "amanha" if idx == 1 else date
    return (
        f"Previsao para {name} {label_day} ({date}): {_weather_label(code)}, "
        f"min {_fmt_number(min_temp)}°C e max {_fmt_number(max_temp)}°C. "
        f"Chuva: {_fmt_number(rain_prob)}% / {_fmt_number(rain_sum, 1)} mm, {_rain_hint(rain_prob, rain_sum)}. "
        f"Vento maximo {_fmt_number(wind)} km/h."
    )


def _format_forecast(place: dict[str, Any], data: dict[str, Any], days: int) -> str:
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return "Previsao indisponivel para esse local."
    name = _clean(place.get("name"))
    lines = [_format_current(place, data), f"Proximos {min(days, len(times))} dias em {name}:"]
    max_t = daily.get("temperature_2m_max") or []
    min_t = daily.get("temperature_2m_min") or []
    rain_p = daily.get("precipitation_probability_max") or []
    rain_s = daily.get("precipitation_sum") or []
    wind = daily.get("wind_speed_10m_max") or []
    codes = daily.get("weather_code") or []
    for idx, date in enumerate(times[:days]):
        label = "hoje" if idx == 0 else "amanha" if idx == 1 else date
        lines.append(
            f"- {label}: {_weather_label(codes[idx])}, {_fmt_number(min_t[idx])}°C a {_fmt_number(max_t[idx])}°C, "
            f"chuva {_fmt_number(rain_p[idx])}%/{_fmt_number(rain_s[idx], 1)} mm, vento {_fmt_number(wind[idx])} km/h."
        )
    return "\n".join(lines)


def _google_weather_url(location: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(f"previsao do tempo {location}")


def weather_action(parameters: dict | None = None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = _clean(params.get("action") or "forecast").lower()
    when = _clean(params.get("when") or params.get("time") or params.get("dia") or "today")
    days = _safe_int(params.get("days") or params.get("dias"), 3, 1, 7)

    try:
        place = _geocode_location(params)
        data = _fetch_forecast(place, days)
        location_name = _extract_location(params) or _clean(place.get("name"))

        if action in {"current", "agora", "clima", "weather_now"}:
            msg = _format_current(place, data)
        elif action in {"today", "hoje", "tomorrow", "amanha", "amanhã", "rain", "chuva", "vai_chover"}:
            msg = _format_daily(place, data, when if action not in {"tomorrow", "amanha", "amanhã"} else "amanha", days)
        elif action in {"open", "abrir", "google"}:
            url = _google_weather_url(location_name)
            webbrowser.open(url)
            msg = f"Abri a previsao do tempo para {location_name}: {url}"
        else:
            msg = _format_forecast(place, data, days)

        if params.get("open"):
            webbrowser.open(_google_weather_url(location_name))
        if session_memory:
            try:
                session_memory.set_last_search(query=f"weather {location_name}", response=msg)
            except Exception:
                pass
        _log(msg, player)
        return msg
    except Exception as exc:
        fallback_location = _extract_location(params) or _clean(params.get("cep")) or "local informado"
        fallback = _google_weather_url(fallback_location)
        if params.get("open", True):
            try:
                webbrowser.open(fallback)
            except Exception:
                pass
        msg = f"Nao consegui calcular a previsao agora ({exc}). Link de consulta: {fallback}"
        _log(msg, player)
        return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass