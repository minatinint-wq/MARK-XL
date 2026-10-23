"""Google Home web control using the existing Jarvis browser session."""
import asyncio
import re
import unicodedata
from urllib.parse import urlparse

HOME = "Grow jarvis"
DEFAULT_DEVICE = "grow control"

DEVICES = (
    {
        "name": "smart plug",
        "room": "Depósito",
        "aliases": {
            "smart plug", "tomada", "tomada do deposito", "luz do deposito",
            "deposito",
        },
    },
    {
        "name": "grow control",
        "room": "Depósito",
        "aliases": {
            "grow control", "grow", "luz do grow", "luzes do grow",
            "lampada do grow", "iluminacao do grow", "luz da estufa",
            "lampada da estufa",
        },
    },
    {
        "name": "rega",
        "room": "Depósito",
        "aliases": {
            "rega", "sistema de rega", "sistema da rega", "irrigacao",
            "sistema de irrigacao", "bomba de rega", "bomba da rega",
            "agua do grow",
        },
    },
    {
        "name": "Cafeteira switch_1",
        "room": "Depósito",
        "aliases": {
            "cafeteira switch_1", "cafeteira switch 1", "cafeteira switch one",
            "cafeteira sweet", "cafeteira suite", "switch da cafeteira",
            "cafeteira do deposito", "cafeteira deposito",
        },
    },
    {
        "name": "Cafeteira",
        "room": "Quarto",
        "aliases": {
            "cafeteira", "cafeteira do quarto", "cafeteira quarto",
        },
    },
)

def normalize(text):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(text).lower()) if unicodedata.category(c) != "Mn").split())

def read_state(text):
    words = set(re.findall(r"[a-z]+", normalize(text)))
    on = bool(words & {"ativado", "ativada", "ligado", "ligada", "on"})
    off = bool(words & {"desativado", "desativada", "desligado", "desligada", "off"})
    return on if on != off else None


def resolve_device(value):
    requested = normalize(value or DEFAULT_DEVICE)
    for device in DEVICES:
        names = {normalize(device["name"]), *(normalize(alias) for alias in device["aliases"])}
        if requested in names:
            return device
    return None

async def control(session, params):
    action = normalize(params.get("command", params.get("action", "status")))
    aliases = {
        "ligar": "on", "liga": "on", "ligue": "on",
        "acender": "on", "acenda": "on", "ativar": "on", "ativa": "on", "ative": "on",
        "desligar": "off", "desliga": "off", "desligue": "off",
        "apagar": "off", "apaga": "off", "apague": "off",
        "desativar": "off", "desativa": "off", "desative": "off",
        "abrir": "setup",
    }
    action = aliases.get(action, action)
    if action not in {"setup", "status", "on", "off"}:
        return "Google Home: use setup, status, on ou off."
    target = resolve_device(params.get("device"))
    if target is None:
        return (
            "Dispositivo não reconhecido. Configurados: smart plug, grow control e rega no Depósito, "
            "Cafeteira switch_1 no Depósito e Cafeteira no Quarto."
        )
    device_name = target["name"]
    room_name = target["room"]
    page = await session._get_page()
    pages = [p for p in session._context.pages if not p.is_closed() and urlparse(p.url).hostname == "home.google.com"]
    if len(pages) > 1:
        return "Há várias abas Google Home. Deixe apenas a aba da casa Grow jarvis aberta no navegador do Jarvis."
    if pages:
        page = pages[0]
        session._page = page
    else:
        page = await session._context.new_page()
        session._page = page
        await page.goto("https://home.google.com/", wait_until="domcontentloaded", timeout=25000)
    await page.bring_to_front()
    if action == "setup":
        return "Google Home aberto no navegador do Jarvis. Entre na conta e abra Grow jarvis > Dispositivos."
    if urlparse(page.url).hostname != "home.google.com":
        return "Faça login no Google Home no navegador do Jarvis e tente novamente."
    body = normalize(await page.locator("body").inner_text())
    if normalize(HOME) not in body or normalize(room_name) not in body:
        return f"Abra Grow jarvis > Dispositivos > {room_name} no navegador do Jarvis. Nenhum comando enviado."
    # Require a single visible interactive tile with an explicit, readable state.
    exact_name = page.get_by_text(device_name, exact=True)
    tiles = page.locator('button, [role="button"], [role="switch"]').filter(has=exact_name)
    visible = []
    for i in range(await tiles.count()):
        tile = tiles.nth(i)
        if await tile.is_visible(): visible.append(tile)
    names = exact_name
    visible_names = sum([await names.nth(i).is_visible() for i in range(await names.count())])
    if len(visible) != 1 or visible_names != 1:
        return f"Não identifiquei um cartão único e seguro de {device_name}. Abra o cartão no Google Home. Nenhum comando enviado."
    tile = visible[0]
    before = read_state(await tile.inner_text())
    if before is None:
        return "O cartão não informa ligado/desligado de forma reconhecível. Nenhum comando enviado."
    if action == "status":
        return f"{device_name} ({room_name}): " + ("ligada." if before else "desligada.")
    desired = action == "on"
    if before == desired:
        return f"{device_name} ({room_name}) já está " + ("ligada." if desired else "desligada.")
    await tile.click(timeout=5000)
    for _ in range(12):
        await asyncio.sleep(0.5)
        if read_state(await tile.inner_text()) == desired:
            return f"Google Home confirmou: {device_name} ({room_name}) " + ("ligada." if desired else "desligada.")
    return "Clique enviado, mas o Google Home não confirmou o estado solicitado. Não repeti o clique."
