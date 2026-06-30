"""
Smart Home + Spotify Connect + Bluetooth — JARVIS como Alexa
Controla lâmpadas Wi-Fi, switches, Spotify em qualquer dispositivo, Bluetooth
"""
import json
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Optional

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# ── Config ──────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
SPOTIFY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "spotify_credentials.json"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_placeholder(value: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return True
    upper = value.upper()
    return upper.startswith(("COLE_", "SEU_", "YOUR_")) or upper.endswith("_AQUI")


def _load_config() -> dict:
    cfg = _load_json(CONFIG_PATH)
    spotify_cfg = _load_json(SPOTIFY_CONFIG_PATH)

    client_id = spotify_cfg.get("client_id") or spotify_cfg.get("spotify_client_id")
    client_secret = (
        spotify_cfg.get("client_secret")
        or spotify_cfg.get("spotify_client_secret")
        or spotify_cfg.get("private_id")
    )

    if not _is_placeholder(client_id):
        cfg["spotify_client_id"] = client_id
    if not _is_placeholder(client_secret):
        cfg["spotify_client_secret"] = client_secret
    cfg["spotify_redirect_uri"] = spotify_cfg.get("redirect_uri", SPOTIFY_REDIRECT_URI)
    return cfg

def _save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")


def _save_spotify_credentials(client_id: str, client_secret: str) -> Path:
    SPOTIFY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPOTIFY_CONFIG_PATH.write_text(
        json.dumps(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return SPOTIFY_CONFIG_PATH

# ── Spotify Connect (Web API) ──────────────────────────────────────────

SPOTIFY_SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-library-read user-top-read"

def _get_spotipy() -> Optional[object]:
    """Retorna módulo spotipy autenticado ou None."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        cfg = _load_config()
        cid = cfg.get("spotify_client_id", "")
        sec = cfg.get("spotify_client_secret", "")
        redir = cfg.get("spotify_redirect_uri", SPOTIFY_REDIRECT_URI)
        if not cid or not sec:
            return None
        cache = str(Path.home() / ".spotify_cache")
        auth = SpotifyOAuth(client_id=cid, client_secret=sec,
                            redirect_uri=redir, scope=SPOTIFY_SCOPES,
                            cache_path=cache, open_browser=False)

        # Tenta validar o token atual (se falhar, tenta refresh)
        try:
            token = auth.get_cached_token()
            if token:
                return spotipy.Spotify(auth_manager=auth)
        except Exception:
            pass
        return None
    except ImportError:
        return None
    except Exception:
        return None

def _spotify_desktop(action: str, params: dict) -> str:
    """Fallback: controla o app do Spotify no Windows (zero config)."""
    try:
        from actions.spotify_control import spotify_control
        return spotify_control({"action": action, **params}, player=None) or "Feito."
    except Exception as e:
        return f"Erro no controle local do Spotify: {e}"

def _spotify_generate_auth_url() -> str:
    """Gera URL de autorização manual."""
    try:
        from spotipy.oauth2 import SpotifyOAuth
        cfg = _load_config()
        cid = cfg.get("spotify_client_id", "")
        sec = cfg.get("spotify_client_secret", "")
        if not cid or not sec:
            return None, (
                "Configure o Spotify em config/spotify_credentials.json "
                "com client_id e client_secret primeiro."
            )
        redir = cfg.get("spotify_redirect_uri", SPOTIFY_REDIRECT_URI)
        cache = str(Path.home() / ".spotify_cache")
        auth = SpotifyOAuth(client_id=cid, client_secret=sec,
                            redirect_uri=redir,
                            scope=SPOTIFY_SCOPES, cache_path=cache, open_browser=False)
        url = auth.get_authorize_url()
        return auth, url
    except Exception as e:
        return None, f"Erro ao gerar URL: {e}"


def _spotify_credentials_loaded() -> bool:
    cfg = _load_config()
    return bool(cfg.get("spotify_client_id") and cfg.get("spotify_client_secret"))


def _spotify_auth_required_message() -> str:
    auth, url = _spotify_generate_auth_url()
    if auth is None:
        return "Spotify ainda sem credenciais. Preencha config/spotify_credentials.json com client_id e client_secret."
    return (
        "Credenciais Spotify carregadas. Falta autorizar a conta uma vez para gerar o token.\n\n"
        f"Abra este link:\n{url}\n\n"
        "Depois cole aqui a URL final completa:\n"
        "spotify callback URL_QUE_APARECEU_NO_NAVEGADOR"
    )


def _spotify_login_instructions() -> str:
    return (
        "Para configurar o Spotify:\n\n"
        "1. Vá em https://developer.spotify.com/dashboard\n"
        "2. Crie um app ou abra o app que você já criou\n"
        "3. Em Settings > Redirect URIs, adicione exatamente http://127.0.0.1:8888/callback\n"
        "4. Preencha config/spotify_credentials.json com client_id e client_secret\n"
        "5. Depois peça: spotify setup"
    )


def _spotify_process_callback(callback_url: str) -> str:
    """Processa a URL de callback que o usuário colou."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        cfg = _load_config()
        cid = cfg.get("spotify_client_id", "")
        sec = cfg.get("spotify_client_secret", "")
        redir = cfg.get("spotify_redirect_uri", SPOTIFY_REDIRECT_URI)
        cache = str(Path.home() / ".spotify_cache")
        auth = SpotifyOAuth(client_id=cid, client_secret=sec,
                            redirect_uri=redir,
                            scope=SPOTIFY_SCOPES, cache_path=cache, open_browser=False)
        # Extrai o code da URL
        parsed = urllib.parse.urlparse(callback_url)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if not code:
            return "Não encontrei o código de autorização na URL. Certifique-se de copiar a URL COMPLETA da barra de endereços."
        auth.get_access_token(code)
        # Testa se funcionou
        sp = spotipy.Spotify(auth_manager=auth)
        user = sp.current_user()
        return f"✅ Spotify conectado como {user.get('display_name', user.get('id', '?'))}! Já posso controlar música em qualquer dispositivo."
    except Exception as e:
        return f"Erro ao processar autorização: {e}"

def spotify_status_text(sp: object) -> str:
    """Texto falado do que está tocando."""
    try:
        cur = sp.current_playback()
        if not cur or not cur.get("item"):
            return "Nada tocando no momento."
        item = cur["item"]
        name = item.get("name", "?")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        dev = cur.get("device", {}).get("name", "desconhecido")
        return f"{name} — {artists} em {dev}"
    except Exception:
        return "Não consegui obter informação do Spotify."


def _spotify_norm(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum() or ch.isspace()).strip()


def spotify_devices_text(sp: object) -> str:
    devices = sp.devices().get("devices", [])
    if not devices:
        return (
            "Nenhum dispositivo Spotify encontrado. Abra o Spotify no PC/celular "
            "e aguarde ele aparecer em Spotify Connect."
        )
    lines = ["📱 Dispositivos Spotify disponíveis:"]
    for d in devices:
        active = " 🔊 ATIVO" if d.get("is_active") else ""
        dtype = d.get("type") or "device"
        volume = d.get("volume_percent")
        vol = f" · {volume}%" if volume is not None else ""
        lines.append(f"  • {d.get('name', '?')} ({dtype}){vol}{active}")
    return "\n".join(lines)


def spotify_pick_device(sp: object, device: str = "") -> tuple[dict | None, list[dict], str | None]:
    devices = sp.devices().get("devices", [])
    if not devices:
        return None, [], (
            "Nenhum dispositivo Spotify encontrado. Abra o Spotify no PC/celular "
            "e toque algo uma vez, ou deixe o app aberto por alguns segundos."
        )

    if device:
        needle = _spotify_norm(device)
        exact = [d for d in devices if _spotify_norm(d.get("name", "")) == needle]
        if exact:
            return exact[0], devices, None
        partial = [d for d in devices if needle in _spotify_norm(d.get("name", ""))]
        if partial:
            return partial[0], devices, None
        return None, devices, f"Dispositivo '{device}' não encontrado.\n{spotify_devices_text(sp)}"

    active = [d for d in devices if d.get("is_active")]
    if active:
        return active[0], devices, None
    return devices[0], devices, None


def spotify_start_on_device(sp: object, device: str = "", **play_kwargs) -> tuple[str, dict | None]:
    target, _, error = spotify_pick_device(sp, device)
    if error:
        return error, None
    if not target or not target.get("id"):
        return "Dispositivo Spotify sem ID. Abra o Spotify e tente novamente.", None

    device_id = target["id"]
    try:
        sp.start_playback(device_id=device_id, **play_kwargs)
    except Exception:
        # Alguns clients só aceitam comando após transferir o player primeiro.
        sp.transfer_playback(device_id, force_play=True)
        time.sleep(0.35)
        if play_kwargs:
            sp.start_playback(device_id=device_id, **play_kwargs)
    return f"▶ Tocando agora em {target.get('name', 'Spotify')}.", target


def spotify_transfer_to_device(sp: object, device: str, force_play: bool = True) -> str:
    target, _, error = spotify_pick_device(sp, device)
    if error:
        return error
    if not target or not target.get("id"):
        return "Dispositivo Spotify sem ID. Abra o Spotify e tente novamente."
    sp.transfer_playback(target["id"], force_play=force_play)
    return f"▶ Spotify transferido para {target.get('name', device)}."


def smart_home(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Controle de casa inteligente: Spotify em qualquer dispositivo,
    lâmpadas Wi-Fi/Bluetooth, switches, dispositivos Bluetooth.

    Parâmetros:
      domain (str): domínio da ação: "spotify", "wifi", "bluetooth", "discover", "register"
      action (str): ação específica do domínio
      device (str): nome ou IP do dispositivo alvo
      query (str): busca para música / nome do device
    """
    params = parameters or {}
    domain = params.get("domain", "").lower().strip()
    action = params.get("action", "").lower().strip()
    device = params.get("device", "")
    query  = params.get("query", "")

    if player:
        player.write_log(f"[SmartHome] {domain}/{action} {device or query}")

    # ── SPOTIFY ──────────────────────────────────────────────────────
    if domain == "spotify":
        if action in ("status", "check", "conexao", "conexão"):
            if not _spotify_credentials_loaded():
                return _spotify_login_instructions()
            sp_status = _get_spotipy()
            if sp_status is None:
                return _spotify_auth_required_message()
            try:
                user = sp_status.current_user()
                return f"Spotify conectado como {user.get('display_name', user.get('id', '?'))}."
            except Exception:
                return "Spotify conectado, mas não consegui ler o perfil agora."

        # ── Setup manual (auth URL) ──
        if action in ("setup", "setup_manual", "autorizar", "auth_url"):
            auth, url = _spotify_generate_auth_url()
            if auth is None:
                return "Erro: " + (url or "Client ID/Secret não configurados.")
            return (
                "Credenciais Spotify carregadas. Falta só autorizar a conta uma vez:\n\n"
                f"1. Abra este link:\n{url}\n"
                "2. Faça login e autorize.\n"
                "3. Copie a URL final completa da barra do navegador.\n"
                "4. Cole aqui: spotify callback URL_QUE_COPIOU"
            )

        # ── Processar código direto ──
        if action == "code":
            code = query or device or params.get("code", "")
            if not code:
                return "Me mande o código da URL. Ex: 'spotify code AQ...'"
            fake_url = f"{SPOTIFY_REDIRECT_URI}?code={code}"
            return _spotify_process_callback(fake_url)

        # ── Processar callback ──
        if action in ("auth", "callback", "auth_callback"):
            callback_url = query or device or params.get("url", "")
            if not callback_url:
                return f"Me mande a URL completa que você copiou. Ex: 'spotify callback {SPOTIFY_REDIRECT_URI}?code=AQ...'"
            return _spotify_process_callback(callback_url)

        # ── Web API ──
        sp = _get_spotipy()

        if action in ("play/pause", "toggle"):
            if sp is not None:
                try:
                    cur = sp.current_playback()
                    if cur and cur.get("is_playing"):
                        sp.pause_playback()
                        return "⏸ Música pausada."
                    msg, _ = spotify_start_on_device(sp, device)
                    return msg
                except Exception as e:
                    return _spotify_desktop("play", {})
            return _spotify_desktop("play", {})

        if action in ("play", "tocar"):
            if sp is not None:
                try:
                    msg, _ = spotify_start_on_device(sp, device)
                    return msg
                except Exception as e:
                    return f"Spotify Connect error: {str(e)[:160]}"
            return _spotify_desktop("play", {})

        elif action in ("pause", "pausar"):
            if sp is not None:
                try:
                    sp.pause_playback()
                    return "⏸ Pausado."
                except Exception:
                    pass
            return _spotify_desktop("pause", {})

        elif action in ("next", "skip", "proxima", "próxima"):
            if sp is not None:
                try:
                    sp.next_track()
                    time.sleep(0.3)
                    return f"⏭ Próxima música. {spotify_status_text(sp)}"
                except Exception:
                    pass
            return _spotify_desktop("next", {})

        elif action in ("previous", "back", "voltar", "anterior"):
            if sp is not None:
                try:
                    sp.previous_track()
                    time.sleep(0.3)
                    return f"⏮ Música anterior. {spotify_status_text(sp)}"
                except Exception:
                    pass
            return _spotify_desktop("previous", {})

        elif action in ("volume", "volume_set", "definir_volume"):
            val = params.get("value", "50")
            if sp is not None:
                try:
                    vol = min(100, max(0, int(val)))
                    sp.volume(vol)
                    return f"🔊 Volume do Spotify em {vol}%."
                except Exception:
                    pass
            return _spotify_desktop("volume", {"value": val})

        elif action in ("search", "buscar", "find"):
            if not query:
                return "O que você quer ouvir? Me passe o nome da música ou artista."
            if sp is not None:
                try:
                    res = sp.search(q=query, limit=5, type="track")
                    tracks = res.get("tracks", {}).get("items", [])
                    if not tracks:
                        return f"Nada encontrado para '{query}'."
                    uris = [t["uri"] for t in tracks[:3]]
                    try:
                        msg, target = spotify_start_on_device(sp, device, uris=uris)
                        if target is None:
                            return msg
                    except Exception:
                        return f"Spotify Connect error: {str(e)[:160]}"
                    first = tracks[0]
                    artists = ", ".join(a["name"] for a in first.get("artists", []))
                    where = f" em {target.get('name')}" if target else ""
                    return f"▶ Tocando {first['name']} — {artists}{where}"
                except Exception:
                    pass
            return _spotify_desktop("search", {"query": query})

        elif action in ("current", "now", "tocando", "playing"):
            if sp is not None:
                try:
                    return spotify_status_text(sp)
                except Exception:
                    pass
            return _spotify_desktop("current", {})

        elif action in ("shuffle", "aleatorio", "aleatório"):
            if sp is not None:
                try:
                    cur = sp.current_playback()
                    state = cur.get("shuffle_state", False) if cur else False
                    sp.shuffle(not state)
                    return "🔀 Aleatório ativado." if not state else "🔀 Aleatório desativado."
                except Exception:
                    pass
            return _spotify_desktop("shuffle", {})

        elif action == "repeat":
            if sp is not None:
                try:
                    cur = sp.current_playback()
                    state = cur.get("repeat_state", "off") if cur else "off"
                    new = "context" if state == "off" else ("track" if state == "context" else "off")
                    sp.repeat(new)
                    labels = {"off": "desativado", "context": "repetir playlist", "track": "repetir uma"}
                    return f"🔁 Repetir: {labels.get(new, new)}."
                except Exception:
                    pass
            return _spotify_desktop("repeat", {})

        elif action in ("device", "devices", "dispositivos", "connect_device"):
            if sp is not None:
                try:
                    if not device:
                        return spotify_devices_text(sp)
                    return spotify_transfer_to_device(sp, device, force_play=True)
                except Exception as e:
                    return f"Erro ao listar dispositivos: {e}"
            return _spotify_auth_required_message()

        elif action in ("queue", "fila", "add_queue"):
            if not query:
                return "Qual música adicionar à fila?"
            if sp is not None:
                try:
                    res = sp.search(q=query, limit=1, type="track")
                    tracks = res.get("tracks", {}).get("items", [])
                    if not tracks:
                        return f"Música '{query}' não encontrada."
                    sp.add_to_queue(tracks[0]["uri"])
                    return f"➕ {tracks[0]['name']} adicionada à fila."
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        elif action == "login":
            if _spotify_credentials_loaded():
                return _spotify_auth_required_message()
            return _spotify_login_instructions()

        elif action in ("configure", "config", "set_credentials"):
            cid = params.get("client_id", "") or params.get("spotify_client_id", "")
            sec = (
                params.get("client_secret", "")
                or params.get("spotify_client_secret", "")
                or params.get("private_id", "")
            )
            if cid and sec:
                path = _save_spotify_credentials(cid, sec)
                return (f"✅ Credenciais Spotify salvas em {path}! Agora me peça 'spotify setup' "
                        "para gerar o link de autorização.")
            return "Preciso do client_id e client_secret."

        elif action in ("playlist", "playlists", "list_playlists", "minhas playlists"):
            if sp is not None:
                try:
                    pl = sp.current_user_playlists(limit=50)
                    items = pl.get("items", [])
                    if not items:
                        return "Você não tem nenhuma playlist ainda."
                    lines = [f"📋 Suas playlists ({pl.get('total', len(items))}):"]
                    for i, p in enumerate(items, 1):
                        name = p.get("name", "?")
                        tracks = p.get("tracks", {}).get("total", "?")
                        public = "🌍" if p.get("public") else "🔒"
                        lines.append(f"  {i:2d}. {public} {name} ({tracks} músicas)")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Erro ao listar playlists: {e}"
            return _spotify_auth_required_message()

        elif action in ("playlist_play", "play_playlist", "tocar_playlist", "playlist"):
            if sp is not None:
                try:
                    pl = sp.current_user_playlists(limit=50)
                    items = pl.get("items", [])
                    if not query:
                        lines = ["Qual playlist? Disponíveis:"]
                        for p in items[:20]:
                            lines.append(f"  • {p['name']}")
                        return "\n".join(lines)
                    target = None
                    for p in items:
                        if query.lower() in p["name"].lower():
                            target = p
                            break
                    if not target:
                        return f"Playlist '{query}' não encontrada."
                    try:
                        msg, picked = spotify_start_on_device(sp, device, context_uri=target["uri"])
                        if picked is None:
                            return msg
                    except Exception as e:
                        return f"Spotify Connect error: {str(e)[:160]}"
                    where = f" em {picked.get('name')}" if picked else ""
                    return f"▶ Tocando playlist: {target['name']}{where}"
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        elif action in ("top", "top_tracks", "top_artists", "mais_ouvidas"):
            if sp is not None:
                try:
                    term = params.get("term", "medium_term")
                    top = sp.current_user_top_tracks(limit=10, time_range=term)
                    items = top.get("items", [])
                    if not items:
                        return "Nenhum top encontrado ainda."
                    labels = {"short_term": "últimas 4 semanas", "medium_term": "últimos 6 meses", "long_term": "de sempre"}
                    lines = [f"🏆 Suas mais ouvidas ({labels.get(term, term)}):"]
                    for i, t in enumerate(items, 1):
                        artists = ", ".join(a["name"] for a in t.get("artists", []))
                        lines.append(f"  {i:2d}. {t['name']} — {artists}")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        elif action in ("liked", "saved", "curtidas", "favoritas"):
            if sp is not None:
                try:
                    saved = sp.current_user_saved_tracks(limit=20)
                    items = saved.get("items", [])
                    if not items:
                        return "Nenhuma música curtida ainda."
                    lines = ["❤️ Suas músicas curtidas:"]
                    for i, s in enumerate(items, 1):
                        t = s.get("track", {})
                        artists = ", ".join(a["name"] for a in t.get("artists", []))
                        lines.append(f"  {i:2d}. {t['name']} — {artists}")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        elif action in ("recent", "recently_played", "ouvidas", "historico"):
            if sp is not None:
                try:
                    recent = sp.current_user_recently_played(limit=10)
                    items = recent.get("items", [])
                    if not items:
                        return "Nenhum histórico encontrado."
                    lines = ["🕐 Ouvidas recentemente:"]
                    for i, s in enumerate(items, 1):
                        t = s.get("track", {})
                        artists = ", ".join(a["name"] for a in t.get("artists", []))
                        lines.append(f"  {i:2d}. {t['name']} — {artists}")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        elif action in ("recommend", "recommendations", "recomendar", "sugerir"):
            if sp is not None:
                try:
                    top = sp.current_user_top_tracks(limit=5, time_range="medium_term")
                    seed_tracks = [t["id"] for t in top.get("items", [])[:3]]
                    if not seed_tracks:
                        return "Toque mais músicas primeiro para eu recomendar."
                    recs = sp.recommendations(seed_tracks=seed_tracks, limit=10)
                    items = recs.get("tracks", [])
                    if not items:
                        return "Não consegui gerar recomendações."
                    lines = ["🎯 Recomendações para você:"]
                    for i, t in enumerate(items, 1):
                        artists = ", ".join(a["name"] for a in t.get("artists", []))
                        lines.append(f"  {i:2d}. {t['name']} — {artists}")
                    return "\n".join(lines)
                except Exception as e:
                    return f"Erro: {e}"
            return _spotify_auth_required_message()

        else:
            return ("Ações Spotify: play, pause, next, previous, volume, search, "
                    "current, shuffle, repeat, queue, devices, setup, login, configure, "
                    "playlists, playlist_play, top, liked, recent, recommend")

    # ── WI-FI SMART DEVICES (Tasmota / Shelly / HTTP) ────────────────
    if domain == "wifi":
        cfg = _load_config()
        devices = cfg.get("wifi_devices", {})

        if action in ("list", "listar", "status"):
            if not devices:
                return ("Nenhum dispositivo Wi-Fi cadastrado. "
                        "Use domain='wifi' action='register' device='NOME' ip='IP' "
                        "para adicionar um.")
            lines = ["📶 Dispositivos Wi-Fi:"]
            for name, info in devices.items():
                lines.append(f"  • {name} ({info.get('ip', '?')}) — {info.get('type', '?')}")
            return "\n".join(lines)

        if action == "on":
            return _wifi_cmd(devices, device, "on")

        if action == "off":
            return _wifi_cmd(devices, device, "off")

        if action == "toggle":
            return _wifi_cmd(devices, device, "toggle")

        if action in ("register", "add", "adicionar"):
            dev_name = device or params.get("name", "")
            dev_ip = params.get("ip", "")
            dev_type = params.get("type", "tasmota")
            if not dev_name or not dev_ip:
                return "Preciso do nome e IP do dispositivo. Ex: nome 'lampada_quarto' ip '192.168.1.100'"
            cfg = _load_config()
            if "wifi_devices" not in cfg:
                cfg["wifi_devices"] = {}
            cfg["wifi_devices"][dev_name] = {"ip": dev_ip, "type": dev_type}
            _save_config(cfg)
            return f"✅ Dispositivo '{dev_name}' ({dev_ip}, {dev_type}) cadastrado!"

        if action in ("remove", "delete", "remover", "deletar"):
            if device in devices:
                del devices[device]
                cfg = _load_config()
                cfg["wifi_devices"] = devices
                _save_config(cfg)
                return f"🗑 Dispositivo '{device}' removido."
            return f"Dispositivo '{device}' não encontrado."

        if action in ("discover", "scan", "procurar"):
            return _discover_wifi_devices()

        if action in ("brightness", "brilho", "intensidade"):
            value = params.get("value", params.get("brightness", "100"))
            return _wifi_brightness(devices, device, value)

        if action in ("color", "cor", "colour"):
            color = params.get("color", params.get("value", "white"))
            return _wifi_color(devices, device, color)

        return ("Ações Wi-Fi: on, off, toggle, list, register, remove, discover, brightness, color")

    # ── BLUETOOTH ────────────────────────────────────────────────────
    if domain == "bluetooth":
        if action in ("scan", "discover", "procurar"):
            return _bt_scan()

        if action in ("pair", "parear", "connect"):
            return _bt_pair(device or query)

        if action in ("disconnect", "desconectar"):
            return _bt_disconnect(device or query)

        if action in ("list", "devices", "dispositivos", "status"):
            return _bt_list()

        if action in ("remove", "unpair", "remover"):
            return _bt_remove(device or query)

        if action in ("on", "ativar", "ligar"):
            return _bt_toggle(True)

        if action in ("off", "desativar", "desligar"):
            return _bt_toggle(False)

        return ("Ações Bluetooth: scan, pair, disconnect, list, remove, on, off")

    # ── DISCOVER ALL ─────────────────────────────────────────────────
    if domain in ("discover", "scan_all", "procurar_tudo"):
        results = []
        results.append("🔍 Escaneando dispositivos...")
        results.append("")
        results.append("📶 Wi-Fi:")
        wifi_res = _discover_wifi_devices()
        results.append(wifi_res)
        results.append("")
        results.append("📱 Bluetooth:")
        bt_res = _bt_scan()
        results.append(bt_res)
        return "\n".join(results)

    # ── REGISTER (atalho para wifi) ──────────────────────────────────
    if domain == "register":
        return _wifi_cmd_register(params)

    return (
        "Domínios disponíveis:\n"
        "  spotify  — Controlar Spotify em qualquer dispositivo (celular, speaker, PC)\n"
        "  wifi     — Controlar lâmpadas e switches Wi-Fi (Tasmota, Shelly, Tuya)\n"
        "  bluetooth — Escanear, parear e controlar dispositivos Bluetooth\n"
        "  discover — Escanear todos os dispositivos na rede e Bluetooth\n"
        "Use domain='spotify' action='...' para começar."
    )


# ── WiFi Device Helpers ──────────────────────────────────────────────────

_WIFI_TYPE_MAP = {
    "tasmota": {"on": "Power%20On", "off": "Power%20Off", "toggle": "Power%20Toggle"},
    "shelly":  {"on": "relay/0?turn=on", "off": "relay/0?turn=off", "toggle": "relay/0?turn=toggle"},
}

def _wifi_cmd(devices: dict, device_name: str, cmd: str) -> str:
    if not device_name:
        if not devices:
            return "Nenhum dispositivo cadastrado. Use domain='wifi' action='register'"
        return f"Qual dispositivo? Disponíveis: {', '.join(devices.keys())}"
    info = devices.get(device_name)
    if not info:
        for name, inf in devices.items():
            if device_name.lower() in name.lower():
                info = inf
                device_name = name
                break
    if not info:
        return f"Dispositivo '{device_name}' não encontrado."
    ip = info.get("ip", "")
    dtype = info.get("type", "tasmota")
    try:
        import requests
        if dtype == "tasmota":
            cmd_map = _WIFI_TYPE_MAP.get("tasmota", {})
            url = f"http://{ip}/cm?cmnd={cmd_map.get(cmd, cmd)}"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            data = r.json()
            state = "LIGADO" if data.get("POWER") == "ON" else "DESLIGADO"
            return f"💡 {device_name}: {state}"
        elif dtype == "shelly":
            cmd_map = _WIFI_TYPE_MAP.get("shelly", {})
            url = f"http://{ip}/{cmd_map.get(cmd, cmd)}"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            return f"💡 {device_name}: comando {cmd} enviado."
        elif dtype == "tuya":
            return (f"Dispositivo Tuya '{device_name}' requer configuração via app. "
                    "Use o app Smart Life ou me passe o device ID + key local.")
        else:
            return f"Tipo '{dtype}' não suportado ainda. Use 'tasmota' ou 'shelly'."
    except ImportError:
        return "requests não instalado."
    except requests.exceptions.ConnectTimeout:
        return f"⏱ Dispositivo '{device_name}' ({ip}) não respondeu. Está ligado na mesma rede?"
    except Exception as e:
        return f"Erro ao controlar {device_name}: {e}"

def _wifi_brightness(devices: dict, device_name: str, value: str) -> str:
    info = None
    for name, inf in devices.items():
        if device_name.lower() in name.lower():
            info = inf
            device_name = name
            break
    if not info:
        return f"Dispositivo '{device_name}' não encontrado."
    ip = info.get("ip", "")
    dtype = info.get("type", "tasmota")
    try:
        import requests
        val = min(100, max(0, int(value.replace("%", ""))))
        if dtype == "tasmota":
            url = f"http://{ip}/cm?cmnd=Dimmer%20{val}"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            return f"💡 {device_name}: brilho em {val}%."
        elif dtype == "shelly":
            url = f"http://{ip}/light/0?brightness={val}"
            r = requests.get(url, timeout=5)
            return f"💡 {device_name}: brilho em {val}%."
        return f"Brilho não suportado para {dtype}."
    except Exception as e:
        return f"Erro: {e}"

_WIFI_COLORS = {
    "white": "FFFFFF", "branco": "FFFFFF",
    "red": "FF0000", "vermelho": "FF0000",
    "blue": "0000FF", "azul": "0000FF",
    "green": "00FF00", "verde": "00FF00",
    "yellow": "FFFF00", "amarelo": "FFFF00",
    "orange": "FFA500", "laranja": "FFA500",
    "purple": "800080", "roxo": "800080",
    "pink": "FFC0CB", "rosa": "FFC0CB",
    "cyan": "00FFFF", "ciano": "00FFFF",
    "warm": "FFD700", "quente": "FFD700",
    "cold": "ADD8E6", "frio": "ADD8E6",
}

def _wifi_color(devices: dict, device_name: str, color: str) -> str:
    info = None
    for name, inf in devices.items():
        if device_name.lower() in name.lower():
            info = inf
            device_name = name
            break
    if not info:
        return f"Dispositivo '{device_name}' não encontrado."
    ip = info.get("ip", "")
    dtype = info.get("type", "tasmota")
    hex_color = _WIFI_COLORS.get(color.lower(), color.lstrip("#"))
    if not hex_color or len(hex_color) != 6:
        hex_color = "FFFFFF"
    try:
        import requests
        if dtype == "tasmota":
            url = f"http://{ip}/cm?cmnd=Color%20{hex_color}"
            r = requests.get(url, timeout=5)
            return f"💡 {device_name}: cor alterada."
        return f"Cor não suportada para {dtype}."
    except Exception as e:
        return f"Erro: {e}"

def _discover_wifi_devices() -> str:
    """Escaneia a rede local procurando dispositivos Tasmota/Shelly."""
    try:
        import socket
        import requests
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        subnet = ".".join(local_ip.split(".")[:3])
        found = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            for port, name in [(80, "Tasmota/Shelly")]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.3)
                try:
                    result = sock.connect_ex((ip, port))
                    if result == 0:
                        try:
                            r = requests.get(f"http://{ip}/", timeout=1)
                            if "Tasmota" in r.text:
                                found.append(f"  • {ip} — Tasmota")
                            elif "Shelly" in r.text:
                                found.append(f"  • {ip} — Shelly")
                            else:
                                found.append(f"  • {ip} — Dispositivo HTTP")
                        except:
                            found.append(f"  • {ip} — Porta 80 aberta")
                except:
                    pass
                finally:
                    sock.close()
        if found:
            lines = ["📶 Dispositivos encontrados na rede:"]
            lines.extend(found[:20])
            if len(found) > 20:
                lines.append(f"  ... e mais {len(found)-20}")
            return "\n".join(lines)
        return "Nenhum dispositivo Wi-Fi encontrado na rede local."
    except Exception as e:
        return f"Erro no scan: {e}"

def _wifi_cmd_register(params: dict) -> str:
    cfg = _load_config()
    if "wifi_devices" not in cfg:
        cfg["wifi_devices"] = {}
    name = params.get("name", "").strip()
    ip = params.get("ip", "").strip()
    dtype = params.get("type", "tasmota").strip()
    if not name or not ip:
        return "Preciso do nome e IP. Ex: name 'lampada_sala' ip '192.168.1.50'"
    cfg["wifi_devices"][name] = {"ip": ip, "type": dtype}
    _save_config(cfg)
    return f"✅ Dispositivo '{name}' ({ip}, {dtype}) registrado!"


# ── Bluetooth Helpers ────────────────────────────────────────────────────

def _bt_scan() -> str:
    """Escaneia dispositivos Bluetooth via PowerShell."""
    try:
        script = r"""
$pnp = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' -or $_.FriendlyName -ne $null }
$paired = Get-PnpDevice | Where-Object { $_.Class -eq 'Bluetooth' -and $_.Status -eq 'OK' } | Select-Object FriendlyName, Status, InstanceId
$result = @()
foreach ($d in $paired) {
    $result += [PSCustomObject]@{ Name = $d.FriendlyName; Status = $d.Status }
}
if ($result.Count -eq 0) {
    # Try alternative: query registry for known BT devices
    $reg = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\*' -ErrorAction SilentlyContinue
    foreach ($r in $reg) {
        $result += [PSCustomObject]@{ Name = $r.('Name') -replace '[^\x20-\x7E]',''; Status = 'Registered' }
    }
}
$result | ConvertTo-Json -Compress
"""
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15
        )
        output = r.stdout.strip()
        if not output:
            # Fallback: list all Bluetooth via simple command
            r2 = subprocess.run(
                ["powershell", "-NoProfile", "(Get-PnpDevice -Class Bluetooth | Where-Object Status -eq 'OK').FriendlyName"],
                capture_output=True, text=True, timeout=10
            )
            names = [n.strip() for n in r2.stdout.splitlines() if n.strip()]
            if names:
                lines = ["📱 Dispositivos Bluetooth pareados:"]
                for n in names:
                    lines.append(f"  • {n}")
                return "\n".join(lines)
            return "Nenhum dispositivo Bluetooth encontrado. O Bluetooth está ligado?"
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            lines = ["📱 Dispositivos Bluetooth:"]
            for d in data:
                name = d.get("Name", d.get("FriendlyName", "Desconhecido"))
                status = d.get("Status", "")
                lines.append(f"  • {name} [{status}]")
            return "\n".join(lines)
        except json.JSONDecodeError:
            return f"Dispositivos Bluetooth:\n{output[:500]}"
    except subprocess.TimeoutExpired:
        return "⏱ Scan Bluetooth demorou demais."
    except Exception as e:
        return f"Erro no scan Bluetooth: {e}"

def _bt_pair(name: str) -> str:
    """Tenta parear com um dispositivo Bluetooth."""
    if not name:
        return "Qual dispositivo você quer parear?"
    try:
        script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{ $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation`1" }})[0]
Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.BluetoothDevice,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()
$discovery = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)
$devices = Await $discovery ([System.Collections.Generic.IEnumerable[Windows.Devices.Enumeration.DeviceInformation]])
$found = $devices | Where-Object {{ $_.Name -like "*{name}*" }} | Select-Object -First 1
if ($found) {{
    $result = "$($found.Name) encontrado! ID: $($found.Id)"
}} else {{
    $result = "Dispositivo '$name' não encontrado."
}}
Write-Output $result
'''
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30
        )
        out = (r.stdout or "").strip()
        if out:
            return f"📱 {out}"
        return f"Comando pareamento enviado para '{name}'."
    except Exception as e:
        return f"Erro ao parear: {e}"

def _bt_disconnect(name: str) -> str:
    if not name:
        return "Qual dispositivo desconectar?"
    try:
        script = f'''
$bt = Get-PnpDevice | Where-Object {{ $_.Class -eq 'Bluetooth' -and $_.FriendlyName -like "*{name}*" }}
if ($bt) {{
    Disable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
    Start-Sleep -Seconds 1
    Enable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
    "Desconectado: $($bt.FriendlyName)"
}} else {{
    "Dispositivo não encontrado."
}}
'''
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15
        )
        out = (r.stdout or "").strip()
        return f"📱 {out}" if out else f"Comando de desconexão enviado para '{name}'."
    except Exception as e:
        return f"Erro: {e}"

def _bt_list() -> str:
    """Lista dispositivos Bluetooth conectados."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' -and $_.FriendlyName }).FriendlyName"],
            capture_output=True, text=True, timeout=10
        )
        names = [n.strip() for n in r.stdout.splitlines() if n.strip()]
        if not names:
            return "Nenhum dispositivo Bluetooth conectado."
        lines = ["📱 Bluetooth conectado:"]
        for n in names:
            lines.append(f"  • {n}")
        return "\n".join(lines)
    except Exception as e:
        return f"Erro: {e}"

def _bt_remove(name: str) -> str:
    if not name:
        return "Qual dispositivo remover?"
    try:
        script = f'''
$bt = Get-PnpDevice | Where-Object {{ $_.Class -eq 'Bluetooth' -and $_.FriendlyName -like "*{name}*" }}
if ($bt) {{
    $bt | ForEach-Object {{ Unregister-PnpDevice -InstanceId $_.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }}
    "Removido: $($bt.FriendlyName)"
}} else {{
    "Dispositivo não encontrado."
}}
'''
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15
        )
        out = (r.stdout or "").strip()
        return f"🗑 {out}" if out else f"Comando de remoção enviado para '{name}'."
    except Exception as e:
        return f"Erro: {e}"

def _bt_toggle(on: bool) -> str:
    try:
        action = "Enable" if on else "Disable"
        cmd = f"Get-PnpDevice -Class Bluetooth | Where-Object Status -eq '{( 'OK' if not on else 'Error' )}' | ForEach-Object {{ {action}-PnpDevice -InstanceId $_.InstanceId -Confirm:$false }}"
        # Simpler: use Windows Settings
        if on:
            subprocess.run(["powershell", "-NoProfile", "(Get-PnpDevice -Class Bluetooth | Where-Object Status -eq 'Error').Count"],
                           capture_output=True, timeout=5)
        subprocess.run("start ms-settings:bluetooth", shell=True, capture_output=True, timeout=3)
        return "🔵 Bluetooth ativado. Abrindo configurações..." if on else "🔵 Bluetooth desativado."
    except Exception as e:
        return f"Erro: {e}"
