"""Explicit Spotify account check/reauthorization; never embeds credentials."""
from __future__ import annotations

import threading
import webbrowser


def check_and_reconnect() -> str:
    from actions.smart_home import _get_spotipy, _spotify_generate_auth_url

    client = _get_spotipy()
    if client is not None:
        try:
            profile = client.current_user() or {}
            product = str(profile.get("product") or "não informado")
            name = str(profile.get("display_name") or profile.get("id") or "conta atual")
            return f"API conectada como {name}. Plano informado pela API: {product}. Abra o Spotify no aparelho para aparecer em Dispositivos."
        except Exception as exc:
            status = getattr(exc, "http_status", getattr(exc, "status_code", None))
            if status == 403:
                return (
                    "A API Spotify respondeu 403: o Premium do dono do app ainda não foi reconhecido. "
                    "Após renovar o plano, aguarde a atualização do Spotify e teste novamente; "
                    "novo login não corrige essa restrição."
                )
            if status == 429:
                return "Spotify limitou as consultas. Aguarde antes de testar novamente."
            if status != 401:
                return "A API Spotify não respondeu à verificação. Confira a conexão e teste novamente."

    _auth, url = _spotify_generate_auth_url()
    if _auth is None:
        return "Credenciais Spotify ausentes. Configure client_id e client_secret no próprio PC; nenhuma chave vem no patch."

    from actions.spotify_callback_server import receive_callback

    ready = threading.Event()
    outcome: dict[str, str] = {}

    def serve() -> None:
        try:
            outcome["message"] = receive_callback(180, ready)
        except OSError:
            outcome["message"] = "Porta 8888 ocupada. Feche o outro callback Spotify e tente novamente."
            ready.set()

    thread = threading.Thread(target=serve, name="JarvisSpotifyOAuth", daemon=True)
    thread.start()
    if not ready.wait(3):
        return "O receptor local do Spotify não iniciou na porta 8888."
    if "message" in outcome:
        return outcome["message"]
    if not webbrowser.open(url):
        return "Abra o navegador e use o comando Spotify setup para autorizar a conta."
    thread.join(timeout=185)
    return outcome.get("message", "Autorização pendente. Confira a página aberta no navegador.")
