"""Persistent Google Flow browser bridge for JARVIS video generation."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
FLOW_URL = "https://labs.google/fx/pt/tools/flow"
OUTPUT_DIR = Path.home() / "Desktop" / "JARVIS" / "Videos"
PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", str(BASE_DIR / "runtime"))) / "JARVIS" / "FlowChromeProfile"
GENERATED_IMAGES_DIR = BASE_DIR / "generated_images"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _chrome_path() -> str | None:
    candidates = [
        os.environ.get("JARVIS_CHROME_PATH", ""),
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _open_flow_window() -> str:
    chrome = _chrome_path()
    if not chrome:
        return "Não encontrei o Google Chrome."
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([chrome, f"--user-data-dir={PROFILE_DIR}", "--profile-directory=Default", "--new-window", "--no-first-run", FLOW_URL])
    return "Sessão persistente do Flow aberta."


def _controlled_flow():
    """Open Flow with DOM control over its existing persistent Chrome profile."""
    from playwright.sync_api import sync_playwright

    chrome = _chrome_path()
    if not chrome:
        raise RuntimeError("Google Chrome não encontrado")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    try:
        context = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            executable_path=chrome,
            headless=False,
            viewport=None,
            args=["--start-maximized", "--no-first-run", "--no-default-browser-check"],
        )
    except Exception:
        pw.stop()
        raise
    page = next((item for item in context.pages if "labs.google/fx" in item.url), None)
    if page is None:
        page = context.new_page()
    page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(3_500)
    return pw, context, page


def _inspect_flow() -> str:
    pw, context, page = _controlled_flow()
    try:
        data = page.evaluate("""() => ({
          title: document.title,
          url: location.href,
          inputs: Array.from(document.querySelectorAll('textarea,input,[contenteditable="true"]')).map((el, i) => ({
            i, tag: el.tagName, type: el.getAttribute('type'), placeholder: el.getAttribute('placeholder'),
            aria: el.getAttribute('aria-label'), contenteditable: el.getAttribute('contenteditable')
          })).slice(0, 16),
          buttons: Array.from(document.querySelectorAll('button')).map((el, i) => ({
            i, text: (el.innerText || '').trim(), aria: el.getAttribute('aria-label'), title: el.getAttribute('title'), disabled: !!el.disabled
          })).filter(x => x.text || x.aria || x.title).slice(-40)
        })""")
        buttons = " | ".join(f"{x['i']}:{x['text'] or x['aria'] or x['title']}" for x in data.get('buttons', []))
        inputs = " | ".join(f"{x['i']}:{x['tag']}:{x['placeholder'] or x['aria'] or ''}" for x in data.get('inputs', []))
        return f"Flow DOM pronto. URL={data.get('url')} Inputs=[{inputs}] Botoes=[{buttons}]"
    finally:
        context.close()
        pw.stop()


def _submit_text_video(prompt: str) -> str:
    """Create a Flow project and submit its first video prompt through the DOM.

    Flow keeps model, format and confirmation policy in the logged-in profile.
    We intentionally do not guess or bypass those settings here.
    """
    pw, context, page = _controlled_flow()
    try:
        new_project = page.get_by_role("button", name="Novo projeto")
        new_project.click(timeout=15_000)
        page.wait_for_timeout(1_500)

        composer = page.locator('[contenteditable="true"]:visible')
        composer.fill(prompt, timeout=15_000)
        page.wait_for_timeout(400)

        send = page.locator("button").filter(has_text="arrow_forward").last
        if send.is_disabled():
            raise RuntimeError("o botão Criar do Flow ficou desativado")
        project_url = page.url
        send.click(timeout=15_000)
        _approve_flow_generation(page)
        page.wait_for_timeout(1_500)
        return project_url
    finally:
        context.close()
        pw.stop()


def _approve_flow_generation(page) -> bool:
    """Wait for Flow's credit confirmation and accept its persistent setting."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        approval = page.get_by_text("Aprovar e não perguntar de novo", exact=True)
        approval.wait_for(state="visible", timeout=12_000)
        approval.click(timeout=8_000)
        page.wait_for_timeout(800)
        return True
    except PlaywrightTimeoutError:
        return False


def _reusable_image(params: dict[str, Any]) -> Path | None:
    """Resolve an explicit image path or the most recent Jarvis-generated image."""
    raw_path = str(params.get("image_path") or "").strip()
    use_latest = bool(params.get("reuse_last_image")) or raw_path.lower() in {"last", "latest", "ultima", "última"}
    if use_latest:
        if not GENERATED_IMAGES_DIR.exists():
            return None
        images = [path for path in GENERATED_IMAGES_DIR.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]
        return max(images, key=lambda path: path.stat().st_mtime) if images else None
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise RuntimeError(f"imagem não encontrada: {path}")
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise RuntimeError("use PNG, JPG ou WEBP para animar uma imagem")
    return path


def _submit_image_video(prompt: str, image_path: Path) -> str:
    """Create a Flow project, attach a local raster image and submit the motion brief."""
    pw, context, page = _controlled_flow()
    try:
        page.get_by_role("button", name="Novo projeto").click(timeout=15_000)
        page.wait_for_timeout(1_500)
        page.get_by_role("button", name="Adicionar mídia").click(timeout=15_000)
        page.wait_for_timeout(600)
        upload = page.locator('input[type="file"]').last
        upload.set_input_files(str(image_path), timeout=15_000)
        page.wait_for_timeout(2_000)

        composer = page.locator('[contenteditable="true"]:visible')
        composer.fill(prompt, timeout=15_000)
        page.wait_for_timeout(400)
        send = page.locator("button").filter(has_text="arrow_forward").last
        if send.is_disabled():
            raise RuntimeError("o botão Criar do Flow ficou desativado após anexar a imagem")
        project_url = page.url
        send.click(timeout=15_000)
        _approve_flow_generation(page)
        page.wait_for_timeout(1_500)
        return project_url
    finally:
        context.close()
        pw.stop()


def video_generation(parameters: dict[str, Any] | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "open").strip().lower()
    if action in {"open", "setup", "login", "configure"}:
        return _open_flow_window()
    if action in {"status", "config", "providers"}:
        state = "pronta" if PROFILE_DIR.exists() and any(PROFILE_DIR.iterdir()) else "ainda não iniciada"
        return f"Sessão Flow {state}. Perfil local: {PROFILE_DIR}. Saída: {OUTPUT_DIR}."
    if action in {"inspect", "calibrate"}:
        return _inspect_flow()
    if action in {"generate", "create", "criar"}:
        prompt = str(params.get("prompt") or "").strip()
        if not prompt:
            return "Qual vídeo você quer criar?"
        try:
            image_path = _reusable_image(params)
            if params.get("image_path") or params.get("reuse_last_image"):
                if image_path is None:
                    return "Não encontrei uma imagem do Jarvis para reaproveitar. Gere uma imagem primeiro ou informe image_path."
                project_url = _submit_image_video(prompt, image_path)
            else:
                project_url = _submit_text_video(prompt)
        except Exception as exc:
            message = str(exc)
            if "user data directory" in message.lower() or "process" in message.lower():
                return "Feche a janela do Google Flow do JARVIS e tente novamente; ela está usando a sessão persistente."
            return f"Não consegui enviar ao Flow: {message}"
        _open_flow_window()
        return (
            "Vídeo enviado ao Google Flow. Acompanhe a renderização na janela aberta; "
            f"quando terminar, baixe o MP4 para {OUTPUT_DIR}. Projeto: {project_url}"
        )
    return "Ação de vídeo inválida. Use open/setup, status, inspect ou generate."
