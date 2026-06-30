
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)
_OS = platform.system()   # "Windows" | "Darwin" | "Linux"


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass


def _normalize_url(url: str) -> str:
    """
    Bare words like "instagram" → "https://instagram.com"
    Domains like "instagram.com" → "https://instagram.com"
    Full URLs pass through unchanged.
    Also handles app-like URLs like "spotify:app:likes" → "https://open.spotify.com/collection/tracks"
    """
    url = url.strip()
    if not url:
        return "about:blank"
    if "://" in url:
        return url

    # Detect and fix invalid app-like URLs (e.g., "spotify:app:likes.com")
    url_lower = url.lower()
    if ":" in url or "app" in url_lower:
        # Map app references to their web versions
        app_mappings = {
            "spotify": "https://open.spotify.com",
            "spotify:app": "https://open.spotify.com",
            "spotify:app:likes": "https://open.spotify.com/collection/tracks",
            "spotify:app:liked": "https://open.spotify.com/collection/tracks",
            "spotify:likes": "https://open.spotify.com/collection/tracks",
            "spotify:liked": "https://open.spotify.com/collection/tracks",
            "spotify:home": "https://open.spotify.com",
            "spotify:search": "https://open.spotify.com/search",
            "spotify:library": "https://open.spotify.com/collection",
            "spotify:queue": "https://open.spotify.com/queue",
        }
        for pattern, web_url in app_mappings.items():
            if url_lower.startswith(pattern):
                # Check if there's a path after the pattern
                remaining = url[len(pattern):].strip(":").strip()
                if remaining:
                    return web_url + "/" + remaining.lstrip("/")
                return web_url

    # No dot at all → assume .com  (e.g. "instagram" → "instagram.com")
    if "." not in url:
        url = url + ".com"
    return "https://" + url


def _user_agent() -> str:
    if _OS == "Windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    if _OS == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    return (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


def _is_dead_browser_error(error: Exception | str) -> bool:
    text = str(error).lower()
    return any(
        token in text
        for token in (
            "target page, context or browser",
            "browser has been closed",
            "context has been closed",
            "target closed",
            "connection closed",
        )
    )


def _real_profile_dir(browser: str) -> str:
    home  = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    roam  = os.environ.get("APPDATA", "")

    candidates: list[Path] = []

    if _OS == "Windows":
        m = {
            "chrome":   [Path(local) / "Google"          / "Chrome"          / "User Data"],
            "edge":     [Path(local) / "Microsoft"        / "Edge"            / "User Data"],
            "brave":    [Path(local) / "BraveSoftware"    / "Brave-Browser"   / "User Data"],
            "vivaldi":  [Path(local) / "Vivaldi"          / "User Data"],
            "opera":    [Path(roam)  / "Opera Software"   / "Opera Stable",
                         Path(local) / "Opera Software"   / "Opera Stable"],
            "operagx":  [Path(roam)  / "Opera Software"   / "Opera GX Stable",
                         Path(local) / "Opera Software"   / "Opera GX Stable"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Darwin":
        lib = home / "Library" / "Application Support"
        m = {
            "chrome":   [lib / "Google"             / "Chrome"],
            "edge":     [lib / "Microsoft Edge"],
            "brave":    [lib / "BraveSoftware"       / "Brave-Browser"],
            "vivaldi":  [lib / "Vivaldi"],
            "opera":    [lib / "com.operasoftware.Opera"],
            "operagx":  [lib / "com.operasoftware.OperaGX"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Linux":
        cfg = home / ".config"
        m = {
            "chrome":   [cfg / "google-chrome", cfg / "chromium"],
            "edge":     [cfg / "microsoft-edge"],
            "brave":    [cfg / "BraveSoftware" / "Brave-Browser"],
            "vivaldi":  [cfg / "vivaldi"],
            "opera":    [cfg / "opera"],
            "operagx":  [cfg / "opera-gx"],
        }
        candidates = m.get(browser, [])

    for p in candidates:
        if p.exists():
            print(f"[Browser] ✅ Real profile found for {browser}: {p}")
            return str(p)

    fallback = home / ".jarvis_profiles" / browser
    fallback.mkdir(parents=True, exist_ok=True)
    print(f"[Browser] ⚠️  Real profile not found for {browser}, using: {fallback}")
    return str(fallback)


def _jarvis_profile_dir(browser: str, suffix: str = "") -> str:
    profile = Path.home() / ".jarvis_profiles" / f"{browser}{suffix}"
    profile.mkdir(parents=True, exist_ok=True)
    return str(profile)


def _is_jarvis_profile(profile: str) -> bool:
    try:
        Path(profile).resolve().relative_to((Path.home() / ".jarvis_profiles").resolve())
        return True
    except Exception:
        return False


def _browser_process_running(browser: str) -> bool:
    if _OS != "Windows":
        return False

    images = {
        "chrome": ("chrome.exe",),
        "edge": ("msedge.exe",),
        "brave": ("brave.exe",),
        "vivaldi": ("vivaldi.exe",),
        "opera": ("opera.exe",),
        "operagx": ("opera.exe",),
    }.get(browser, ())

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for image in images:
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=creationflags,
            )
        except Exception:
            continue
        if image.lower() in proc.stdout.lower():
            return True
    return False


def _firefox_profile_dir() -> Optional[str]:
    home = Path.home()

    if _OS == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    elif _OS == "Darwin":
        base = home / "Library" / "Application Support" / "Firefox"
    else:
        base = home / ".mozilla" / "firefox"

    ini = base / "profiles.ini"
    if not ini.exists():
        return None

    current: dict[str, str] = {}
    default_path: Optional[str] = None

    for line in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("["):
            p = current.get("Path", "")
            if p and current.get("Default") == "1":
                is_rel = current.get("IsRelative", "1") == "1"
                default_path = str(base / p) if is_rel else p
            current = {}
        elif "=" in line:
            k, _, v = line.partition("=")
            current[k.strip()] = v.strip()

    p = current.get("Path", "")
    if p and current.get("Default") == "1":
        is_rel = current.get("IsRelative", "1") == "1"
        default_path = str(base / p) if is_rel else p

    if default_path and Path(default_path).exists():
        print(f"[Browser] Firefox real profile: {default_path}")
        return default_path
    return None

def _find_opera_windows() -> Optional[str]:
    local  = os.environ.get("LOCALAPPDATA", "")
    prog   = os.environ.get("PROGRAMFILES", "")
    prog86 = os.environ.get("PROGRAMFILES(X86)", "")

    candidates = [
        Path(local)  / "Programs" / "Opera"    / "opera.exe",
        Path(local)  / "Programs" / "Opera GX" / "opera.exe",
        Path(prog)   / "Opera"    / "opera.exe",
        Path(prog86) / "Opera"    / "opera.exe",
    ]
    for p in candidates:
        if p.exists():
            print(f"[Browser] Opera found at: {p}")
            return str(p)

    try:
        import winreg
        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe",
            r"SOFTWARE\Clients\StartMenuInternet\OperaStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\OperaGXStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\opera\shell\open\command",
        ]
        for key_path in keys:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        print(f"[Browser] Opera found via registry: {exe}")
                        return exe
                except Exception:
                    continue
    except Exception:
        pass

    return shutil.which("opera") or None

def _find_exe_windows(prog_name: str) -> Optional[str]:
    try:
        import winreg
        paths_to_try = [
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{prog_name}.exe",
            rf"SOFTWARE\Clients\StartMenuInternet\{prog_name}\shell\open\command",
        ]
        for key_path in paths_to_try:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        return exe
                except Exception:
                    continue
    except Exception:
        pass
    return None

_BROWSER_SPECS: dict[str, dict] = {
    "Windows": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": []},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox.exe"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera.exe"],  "special": "opera_windows"},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": [],             "special": "opera_windows"},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave.exe"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi.exe"]},
        "safari":   None,
    },
    "Darwin": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": ["microsoft-edge"]},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi"]},
        "safari":   {"engine": "webkit",   "channel": None,      "bins": []},
    },
    "Linux": {
        "chrome":   {"engine": "chromium", "channel": None,
                     "bins": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]},
        "edge":     {"engine": "chromium", "channel": None,
                     "bins": ["microsoft-edge", "microsoft-edge-stable"]},
        "firefox":  {"engine": "firefox",  "channel": None, "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "operagx":  {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "brave":    {"engine": "chromium", "channel": None, "bins": ["brave-browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None, "bins": ["vivaldi-stable", "vivaldi"]},
        "safari":   None,
    },
}

_ALIASES: dict[str, str] = {
    "google chrome":   "chrome",
    "google-chrome":   "chrome",
    "microsoft edge":  "edge",
    "ms edge":         "edge",
    "msedge":          "edge",
    "mozilla firefox": "firefox",
    "opera gx":        "operagx",
    "opera_gx":        "operagx",
}


def _resolve_browser(name: str) -> dict | None:
    name   = _ALIASES.get(name.lower().strip(), name.lower().strip())
    os_map = _BROWSER_SPECS.get(_OS, {})
    spec   = os_map.get(name)
    if spec is None:
        return None

    engine  = spec["engine"]
    channel = spec.get("channel")
    bins    = spec.get("bins", [])
    exe     = None

    if spec.get("special") == "opera_windows":
        exe = _find_opera_windows()
        if not exe:
            print(f"[Browser] ⚠️  Opera executable not found on Windows.")
        return {"engine": engine, "exe": exe, "channel": channel}

    for b in bins:
        found = shutil.which(b)
        if found:
            exe = found
            break

    if not exe and _OS == "Darwin":
        app_names = {
            "chrome":  ["Google Chrome.app"],
            "edge":    ["Microsoft Edge.app"],
            "firefox": ["Firefox.app"],
            "opera":   ["Opera.app", "Opera GX.app"],
            "brave":   ["Brave Browser.app"],
            "vivaldi": ["Vivaldi.app"],
        }
        for app in app_names.get(name, []):
            app_dir = Path("/Applications") / app / "Contents" / "MacOS"
            if app_dir.exists():
                found_bins = list(app_dir.iterdir())
                if found_bins:
                    exe = str(found_bins[0])
                    break

    if not exe and _OS == "Windows" and not channel:
        exe = _find_exe_windows(name)

    return {"engine": engine, "exe": exe, "channel": channel}


def _detect_default_browser() -> str:
    try:
        if _OS == "Windows":
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\http\UserChoice",
            )
            prog_id = winreg.QueryValueEx(k, "ProgId")[0].lower()
            winreg.CloseKey(k)
            for kw in ("edge", "firefox", "opera", "brave", "vivaldi", "chrome"):
                if kw in prog_id:
                    return kw
        elif _OS == "Darwin":
            out = subprocess.run(
                ["defaults", "read",
                 "com.apple.LaunchServices/com.apple.launchservices.secure",
                 "LSHandlers"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("firefox", "opera", "brave", "vivaldi", "safari", "chrome", "edge"):
                if kw in out:
                    return kw
        elif _OS == "Linux":
            out = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("firefox", "opera", "brave", "vivaldi", "chrome", "edge"):
                if kw in out:
                    return kw
    except Exception:
        pass
    return "chrome"


class _BrowserSession:
    """
    Bir tarayıcı örneği için tam oturum.
    Tüm tarayıcılar launch_persistent_context ile gerçek profil üzerinde açılır.
    """

    def __init__(self, browser_name: str):
        self.browser_name = browser_name
        self._spec        = _resolve_browser(browser_name)

        self._loop:    asyncio.AbstractEventLoop | None = None
        self._thread:  threading.Thread | None          = None
        self._ready    = threading.Event()

        self._pw:      Playwright     | None = None
        self._context: BrowserContext | None = None
        self._page:    Page           | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"BrowserThread-{self.browser_name}",
        )
        self._thread.start()
        self._ready.wait(timeout=20)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_init())
        self._ready.set()
        self._loop.run_forever()

    async def _async_init(self):
        self._pw = await async_playwright().start()

    def run(self, coro, timeout: int = 60) -> str:
        if not self._loop:
            raise RuntimeError(f"Session for '{self.browser_name}' not started.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def close(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop).result(10)

    async def _async_close(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._context = self._page = None
        self._pw = None

    async def _reset_context(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        self._context = self._page = None

    def _context_usable(self) -> bool:
        if self._context is None:
            return False
        try:
            _ = self._context.pages
            return True
        except Exception as exc:
            return not _is_dead_browser_error(exc)

    async def _launch(self):
        """
        Tarayıcıyı gerçek kullanıcı profiliyle başlatır.
        Context zaten açıksa hiçbir şey yapmaz.
        """
        if self._pw is None:
            self._pw = await async_playwright().start()

        if self._context is not None and self._context_usable():
            return
        if self._context is not None:
            await self._reset_context()

        if self._spec is None:
            raise RuntimeError(
                f"'{self.browser_name}' bu platformda ({_OS}) desteklenmiyor."
            )

        engine_name = self._spec["engine"]
        exe         = self._spec["exe"]
        channel     = self._spec["channel"]
        engine_obj  = getattr(self._pw, engine_name)

        if engine_name == "firefox":
            profile = _firefox_profile_dir() or str(
                Path.home() / ".jarvis_profiles" / "firefox"
            )
            kwargs: dict = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
            }
            if exe:
                kwargs["executable_path"] = exe
            try:
                self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            except Exception as e:
                print(f"[Browser] Firefox real profile failed ({e}), using JARVIS profile")
                jarvis = str(Path.home() / ".jarvis_profiles" / "firefox_jarvis")
                Path(jarvis).mkdir(parents=True, exist_ok=True)
                self._context = await engine_obj.launch_persistent_context(jarvis, **kwargs)

            await asyncio.sleep(0.5)  
            self._page = await self._context.new_page()
            print(f"[Browser] ✅ Firefox launched")
            return

        if engine_name == "webkit":
            safari_profile = str(Path.home() / ".jarvis_profiles" / "safari")
            Path(safari_profile).mkdir(parents=True, exist_ok=True)
            kwargs = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
            }
            self._context = await engine_obj.launch_persistent_context(safari_profile, **kwargs)
            await asyncio.sleep(0.5)
            self._page = await self._context.new_page()
            print(f"[Browser] ✅ Safari launched")
            return

        profile = _real_profile_dir(self.browser_name)

        kwargs = {
            "headless":    False,
            "slow_mo":     0,
            "viewport":    None,
            "no_viewport": True,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-default-apps",
                "--no-default-browser-check",
            ],
        }

        if exe:
            kwargs["executable_path"] = exe
        elif channel:
            kwargs["channel"] = channel

        label = (
            f"{self.browser_name}"
            + (f"/{channel}" if channel else "")
            + (f" @ {exe}" if exe else "")
        )

        use_real_profile = not _is_jarvis_profile(profile)
        if use_real_profile and _browser_process_running(self.browser_name):
                print(f"[Browser] {label} is already open; using MARK XLI profile instead")
        elif use_real_profile:
            try:
                self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
                await asyncio.sleep(0.5)
                self._page = await self._context.new_page()
                print(f"[Browser] ✅ Launched [{label}] profile={profile}")
                return
            except Exception as e:
                print(f"[Browser] ⚠️  Real profile failed for {label}: {e}")

        fallback_profiles = [
            _jarvis_profile_dir(self.browser_name),
            _jarvis_profile_dir(self.browser_name, f"_run_{os.getpid()}"),
        ]
        last_error = None
        seen_profiles: set[str] = set()

        for jarvis_profile in fallback_profiles:
            if jarvis_profile in seen_profiles:
                continue
            seen_profiles.add(jarvis_profile)
            print(f"[Browser] Retrying with MARK XLI profile: {jarvis_profile}")

            try:
                self._context = await engine_obj.launch_persistent_context(jarvis_profile, **kwargs)
                await asyncio.sleep(0.5)
                self._page = await self._context.new_page()
                print(f"[Browser] ✅ Launched [{label}] with MARK XLI profile")
                return
            except Exception as e2:
                last_error = e2
                print(f"[Browser] ⚠️  MARK XLI profile failed ({jarvis_profile}): {e2}")

        raise RuntimeError(f"Could not launch {self.browser_name}: {last_error}")


    async def _get_page(self) -> Page:
        await self._launch()
        # If somehow page got closed, open a fresh one
        if self._page is None or self._page.is_closed():
            try:
                self._page = await self._context.new_page()
            except Exception as exc:
                if not _is_dead_browser_error(exc):
                    raise
                await self._reset_context()
                await self._launch()
                self._page = await self._context.new_page()
            await asyncio.sleep(0.2)
        return self._page

    async def go_to(self, url: str) -> str:

        url      = _normalize_url(url)
        page     = await self._get_page()
        prev_url = page.url

        async def _do_goto(p: Page) -> str:
            """Attempt navigation and return the resulting URL (may still be blank)."""
            try:
                await p.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(0.3)
            except PlaywrightTimeout:
                pass   # page may have partially loaded — check URL below
            except Exception as e:
                print(f"[Browser] goto exception (non-fatal): {e}")
            return p.url

        result_url = await _do_goto(page)

        if result_url in ("about:blank", "", None, prev_url) and prev_url in ("about:blank", "", None):
            print(f"[Browser] Still blank after goto — retrying on new tab: {url}")
            try:
                new_page   = await self._context.new_page()
                self._page = new_page
                result_url = await _do_goto(new_page)
            except Exception as e:
                print(f"[Browser] New-tab retry failed: {e}")

        if result_url and result_url not in ("about:blank", "", None):
            return f"Opened: {result_url}"
        return f"Could not open: {url}"

    async def search(self, query: str, engine: str = "google") -> str:
        _engines = {
            "google":     "https://www.google.com/search?q=",
            "bing":       "https://www.bing.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
            "yandex":     "https://yandex.com/search/?text=",
        }
        base = _engines.get(engine.lower(), _engines["google"])
        return await self.go_to(base + query.replace(" ", "+"))

    async def click(self, selector: str = None, text: str = None) -> str:
        page = await self._get_page()
        try:
            if text:
                await page.get_by_text(text, exact=False).first.click(timeout=8_000)
                return f"Clicked text: '{text}'"
            if selector:
                await page.click(selector, timeout=8_000)
                return f"Clicked selector: {selector}"
            return "No selector or text provided."
        except PlaywrightTimeout:
            return "Element not found (timeout)."
        except Exception as e:
            return f"Click error: {e}"

    async def type_text(self, selector: str = None, text: str = "",
                        clear_first: bool = True) -> str:
        page = await self._get_page()
        try:
            el = page.locator(selector).first if selector else page.locator(":focus")
            if clear_first:
                await el.clear()
            await el.type(text, delay=50)
            return "Text typed."
        except Exception as e:
            return f"Type error: {e}"

    async def scroll(self, direction: str = "down", amount: int = 500) -> str:
        page = await self._get_page()
        try:
            y = amount if direction == "down" else -amount
            await page.mouse.wheel(0, y)
            return f"Scrolled {direction}."
        except Exception as e:
            return f"Scroll error: {e}"

    async def press(self, key: str) -> str:
        page = await self._get_page()
        try:
            await page.keyboard.press(key)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key error: {e}"

    async def get_text(self) -> str:
        page = await self._get_page()
        try:
            text = await page.inner_text("body")
            return text[:4_000]
        except Exception as e:
            return f"Could not get page text: {e}"

    async def get_url(self) -> str:
        page = await self._get_page()
        return page.url

    async def fill_form(self, fields: dict) -> str:
        page    = await self._get_page()
        results = []
        for selector, value in fields.items():
            try:
                el = page.locator(selector).first
                await el.clear()
                await el.type(str(value), delay=40)
                results.append(f"✓ {selector}")
            except Exception as e:
                results.append(f"✗ {selector}: {e}")
        return "Form filled: " + ", ".join(results)

    async def smart_click(self, description: str) -> str:
        page = await self._get_page()
        for role in ("button", "link", "searchbox", "textbox", "menuitem", "tab"):
            try:
                loc = page.get_by_role(role, name=description)
                if await loc.count() > 0:
                    await loc.first.click(timeout=5_000)
                    return f"Clicked ({role}): '{description}'"
            except Exception:
                pass
        for attempt in (
            lambda: page.get_by_text(description, exact=False).first.click(timeout=5_000),
            lambda: page.get_by_placeholder(description, exact=False).first.click(timeout=5_000),
            lambda: page.locator(
                f'[alt*="{description}" i],[title*="{description}" i],'
                f'[aria-label*="{description}" i]'
            ).first.click(timeout=5_000),
        ):
            try:
                await attempt()
                return f"Clicked: '{description}'"
            except Exception:
                pass
        return f"Could not find element: '{description}'"

    async def spotify_control(self, action: str) -> str:
        """
        Handle Spotify-specific actions when on open.spotify.com
        Actions: play_liked, get_current_track, next, previous, shuffle, repeat
        """
        page = await self._get_page()
        url = page.url.lower()

        if "open.spotify.com" not in url:
            return "Not on Spotify. Please navigate to open.spotify.com first."

        try:
            if action in ("play", "play_liked", "liked songs", "tocar", "musicas curtidas"):
                # Try to find and click play button or go to liked songs
                # First navigate to liked songs
                await page.goto("https://open.spotify.com/collection/tracks", timeout=15_000)
                await asyncio.sleep(1.5)
                # Look for play button (often a large play button on the first track or playlist)
                # Try play button by role
                try:
                    play_btn = page.locator('[data-testid="play-button"], [aria-label="Play"], [aria-label="Tocar"]').first
                    if await play_btn.is_visible(timeout=3000):
                        await play_btn.click()
                        return "Playing liked songs!"
                except:
                    pass
                # Try clicking first track to start playback
                try:
                    first_track = page.locator('[data-testid="track-list-row"]').first
                    if await first_track.is_visible(timeout=3000):
                        await first_track.click()
                        return "Started playing liked songs!"
                except:
                    pass
                return "Could not start playback. Try clicking a track manually."

            elif action in ("current", "now playing", "what's playing", "playing"):
                # Get current track info
                try:
                    # Find the now playing section - usually in the footer player
                    track_name = await page.locator('[data-testid="now-playing-track"]').inner_text(timeout=3000)
                    artist_name = await page.locator('[data-testid="now-playing-artist"]').inner_text(timeout=3000)
                    return f"Playing: {track_name} by {artist_name}"
                except:
                    try:
                        # Alternative selectors
                        track = page.locator(".now-playing .track-name, .playback-bar .track-name").first
                        if await track.is_visible():
                            return f"Playing: {await track.inner_text()}"
                    except:
                        pass
                    return "No track currently playing"

            elif action in ("next", "skip", "proxima", "próxima"):
                await page.keyboard.press("ArrowRight")
                return "Skipped to next track"

            elif action in ("previous", "back", "anterior"):
                await page.keyboard.press("ArrowLeft")
                return "Went to previous track"

            elif action in ("shuffle", "aleatorio", "aleatório"):
                await page.keyboard.press("s")
                return "Toggled shuffle"

            elif action in ("repeat", "repetir"):
                await page.keyboard.press("r")
                return "Toggled repeat"

            else:
                return f"Unknown Spotify action: {action}"

        except Exception as e:
            return f"Spotify error: {str(e)[:100]}"

    async def smart_type(self, description: str, text: str) -> str:
        page = await self._get_page()
        candidates = [
            ("placeholder", page.get_by_placeholder(description, exact=False)),
            ("label",       page.get_by_label(description, exact=False)),
            ("role",        page.get_by_role("textbox", name=description)),
            ("searchbox",   page.get_by_role("searchbox")),
            ("combobox",    page.get_by_role("combobox", name=description)),
        ]
        for method, loc in candidates:
            try:
                el = loc.first
                if await el.count() == 0:
                    continue
                await el.clear()
                await el.type(text, delay=50)
                return f"Typed into ({method}): '{description}'"
            except Exception:
                continue
        return f"Could not find input: '{description}'"

    async def new_tab(self, url: str = "") -> str:
        page = await self._get_page()
        ctx  = page.context
        new  = await ctx.new_page()
        self._page = new
        if url:
            return await self.go_to(url)
        return "New tab opened."

    async def close_tab(self) -> str:
        page = self._page
        if page and not page.is_closed():
            ctx   = page.context
            await page.close()
            pages = ctx.pages
            self._page = pages[-1] if pages else None
            return "Tab closed."
        return "No active tab to close."

    async def close_all_tabs(self) -> str:
        """Close all tabs except create a new one"""
        page = self._page
        if page and self._context:
            pages = self._context.pages
            for p in pages:
                if not p.is_closed():
                    try:
                        await p.close()
                    except Exception:
                        pass
            new_page = await self._context.new_page()
            self._page = new_page
            return "All tabs closed."
        return "No active browser session."

    async def close_other_tabs(self) -> str:
        """Close all tabs except the current one"""
        page = self._page
        if page and self._context:
            pages = self._context.pages
            closed = 0
            for p in pages:
                if not p.is_closed() and p != page:
                    try:
                        await p.close()
                        closed += 1
                    except Exception:
                        pass
            return f"Closed {closed} other tab(s). Kept current tab."
        return "No active browser session."

    async def list_tabs(self) -> str:
        """List all open tabs"""
        page = self._page
        if page and self._context:
            pages = self._context.pages
            if not pages:
                return "No tabs open."
            lines = []
            for i, p in enumerate(pages):
                is_current = " (current)" if p == page else ""
                try:
                    title = p.title() if not p.is_closed() else "[closed]"
                except Exception:
                    title = "[error]"
                try:
                    url = p.url if not p.is_closed() else "[closed]"
                except Exception:
                    url = "[error]"
                lines.append(f"  {i+1}. {title[:50]}{is_current}")
            return "Open tabs:\n" + "\n".join(lines)
        return "No active browser session."

    async def switch_tab(self, index: int = 0) -> str:
        """Switch to a tab by index (0 = first, -1 = last)"""
        page = self._page
        if page and self._context:
            pages = self._context.pages
            if not pages:
                return "No tabs open."
            if index < 0:
                index = len(pages) + index
            if 0 <= index < len(pages):
                self._page = pages[index]
                try:
                    await self._page.bring_to_front()
                except Exception:
                    pass
                return f"Switched to tab {index + 1}: {self._page.url[:60]}"
            return f"Tab {index + 1} not found. Total tabs: {len(pages)}"
        return "No active browser session."

    async def get_all_text(self) -> str:
        """Get text content from all elements on page"""
        page = await self._get_page()
        try:
            texts = await page.locator("body").inner_text()
            return texts[:8000]
        except Exception as e:
            return f"Could not get page text: {e}"

    async def wait_for_element(self, selector: str, timeout: int = 10) -> str:
        """Wait for an element to appear"""
        page = await self._get_page()
        try:
            await page.wait_for_selector(selector, timeout=timeout * 1000)
            return f"Element found: {selector}"
        except Exception:
            return f"Element not found after {timeout}s: {selector}"

    async def download_file(self, url: str, save_path: str = "") -> str:
        """Download a file from URL"""
        import os
        try:
            import requests
            if not save_path:
                save_path = str(Path.home() / "Downloads" / url.split("/")[-1])
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return f"Downloaded: {save_path}"
        except Exception as e:
            return f"Download failed: {e}"

    async def execute_script(self, script: str) -> str:
        """Execute JavaScript on the page"""
        page = await self._get_page()
        try:
            result = await page.evaluate(script)
            return str(result)[:500]
        except Exception as e:
            return f"Script error: {e}"

    async def get_element_attribute(self, selector: str, attribute: str) -> str:
        """Get an element's attribute value"""
        page = await self._get_page()
        try:
            el = page.locator(selector).first
            value = await el.get_attribute(attribute)
            return value or "(none)"
        except Exception as e:
            return f"Could not get attribute: {e}"

    async def get_element_count(self, selector: str) -> str:
        """Count elements matching selector"""
        page = await self._get_page()
        try:
            count = await page.locator(selector).count()
            return f"Found {count} element(s) matching: {selector}"
        except Exception as e:
            return f"Selector error: {e}"

    async def hover_element(self, selector: str) -> str:
        """Hover over an element"""
        page = await self._get_page()
        try:
            el = page.locator(selector).first
            await el.hover()
            return f"Hovered: {selector}"
        except Exception as e:
            return f"Hover error: {e}"

    async def scroll_to_element(self, selector: str) -> str:
        """Scroll to a specific element"""
        page = await self._get_page()
        try:
            el = page.locator(selector).first
            await el.scroll_into_view_if_needed()
            return f"Scrolled to: {selector}"
        except Exception as e:
            return f"Scroll error: {e}"

    async def get_page_title(self) -> str:
        """Get the page title"""
        page = await self._get_page()
        try:
            title = await page.title()
            return title
        except Exception as e:
            return f"Could not get title: {e}"

    async def get_page_info(self) -> str:
        """Get comprehensive page information"""
        page = await self._get_page()
        try:
            info = []
            info.append(f"URL: {page.url}")
            info.append(f"Title: {await page.title()}")
            info.append(f"Tabs: {len(page.context.pages)}")
            info.append(f"Cookies: {len(await page.context.cookies())}")
            return "\n".join(info)
        except Exception as e:
            return f"Could not get page info: {e}"

    async def set_viewport_size(self, width: int, height: int) -> str:
        """Set the viewport size"""
        page = await self._get_page()
        try:
            await page.set_viewport_size({"width": width, "height": height})
            return f"Viewport set to {width}x{height}"
        except Exception as e:
            return f"Viewport error: {e}"

    async def accept_cookies(self) -> str:
        """Try to accept cookies if a popup appears"""
        page = await self._get_page()
        selectors_to_try = [
            "button:has-text('Accept')",
            "button:has-text('Aceitar')",
            "button:has-text('Allow')",
            "[id*='cookie'] button",
            "[class*='cookie'] button",
            "#onetrust-accept-btn-handler",
            ".cc-btn",
            ".cookie-accept",
        ]
        for selector in selectors_to_try:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    return f"Accepted cookies via: {selector}"
            except Exception:
                continue
        return "Could not find cookie accept button"

    async def close_popup(self) -> str:
        """Try to close any popup/modal"""
        page = await self._get_page()
        selectors_to_try = [
            "[aria-label='Close']",
            "[aria-label='Fechar']",
            ".close",
            "[class*='close']",
            "[class*='modal'] [class*='close']",
            "button[class*='dismiss']",
            "[class*='popup'] [class*='close']",
        ]
        for selector in selectors_to_try:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=1000):
                    await el.click()
                    return f"Closed popup via: {selector}"
            except Exception:
                continue
        return "No popup found to close"

    async def get_links(self) -> str:
        """Get all links on the page"""
        page = await self._get_page()
        try:
            links = await page.locator("a").all()
            result = []
            for i, link in enumerate(links[:50]):
                try:
                    href = await link.get_attribute("href") or ""
                    text = await link.inner_text() or ""
                    if href:
                        result.append(f"{i+1}. {text[:40]} -> {href[:60]}")
                except Exception:
                    continue
            return "Links:\n" + "\n".join(result) if result else "No links found"
        except Exception as e:
            return f"Could not get links: {e}"

    async def get_images(self) -> str:
        """Get all images on the page"""
        page = await self._get_page()
        try:
            imgs = await page.locator("img").all()
            result = []
            for i, img in enumerate(imgs[:20]):
                try:
                    src = await img.get_attribute("src") or ""
                    alt = await img.get_attribute("alt") or ""
                    if src:
                        result.append(f"{i+1}. [{alt[:30]}] {src[:70]}")
                except Exception:
                    continue
            return "Images:\n" + "\n".join(result) if result else "No images found"
        except Exception as e:
            return f"Could not get images: {e}"

    async def check_element_exists(self, selector: str) -> str:
        """Check if an element exists on the page"""
        page = await self._get_page()
        try:
            count = await page.locator(selector).count()
            if count > 0:
                return f"Element exists: {selector} (found {count})"
            return f"Element not found: {selector}"
        except Exception as e:
            return f"Check error: {e}"

    async def scroll_to_bottom(self) -> str:
        """Scroll to the bottom of the page"""
        page = await self._get_page()
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.3)
            return "Scrolled to bottom"
        except Exception as e:
            return f"Scroll error: {e}"

    async def scroll_to_top(self) -> str:
        """Scroll to the top of the page"""
        page = await self._get_page()
        try:
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.3)
            return "Scrolled to top"
        except Exception as e:
            return f"Scroll error: {e}"

    async def screenshot(self, path: str = None) -> str:
        page = await self._get_page()
        try:
            save_path = path or str(Path.home() / "Desktop" / "jarvis_screenshot.png")
            await page.screenshot(path=save_path, full_page=False)
            return f"Screenshot saved: {save_path}"
        except Exception as e:
            return f"Screenshot error: {e}"

    async def back(self) -> str:
        page = await self._get_page()
        try:
            await page.go_back(timeout=10_000)
            return f"Navigated back: {page.url}"
        except Exception as e:
            return f"Back error: {e}"

    async def forward(self) -> str:
        page = await self._get_page()
        try:
            await page.go_forward(timeout=10_000)
            return f"Navigated forward: {page.url}"
        except Exception as e:
            return f"Forward error: {e}"

    async def reload(self) -> str:
        page = await self._get_page()
        try:
            await page.reload(timeout=15_000)
            return f"Page reloaded: {page.url}"
        except Exception as e:
            return f"Reload error: {e}"

    async def close_browser(self) -> str:
        await self._async_close()
        return f"{self.browser_name} closed."

class _SessionRegistry:
    """Tüm aktif tarayıcı oturumlarını yönetir."""

    def __init__(self):
        self._sessions:       dict[str, _BrowserSession] = {}
        self._active_browser: str                        = ""
        self._lock            = threading.Lock()

    def _get_or_create(self, browser_name: str) -> _BrowserSession:
        with self._lock:
            # Check if session exists and is still alive
            if browser_name in self._sessions:
                sess = self._sessions[browser_name]
                # Verify the session thread is alive
                if sess._thread and sess._thread.is_alive():
                    print(f"[Registry] Reusing existing session: {browser_name}")
                    return sess
                # Session thread is dead, try to restart
                try:
                    sess.start()
                    print(f"[Registry] Restarted session: {browser_name}")
                    return sess
                except Exception:
                    # Could not restart, remove it
                    del self._sessions[browser_name]

            sess = _BrowserSession(browser_name)
            sess.start()
            self._sessions[browser_name] = sess
            print(f"[Registry] New session: {browser_name}")
            return sess

    def get(self, browser_name: str | None = None) -> _BrowserSession:
        if not browser_name:
            browser_name = self._active_browser or _detect_default_browser()
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        sess = self._get_or_create(browser_name)
        self._active_browser = browser_name
        return sess

    def switch(self, browser_name: str) -> str:
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        self._get_or_create(browser_name)
        self._active_browser = browser_name
        return f"Active browser → {browser_name}"

    def close_one(self, browser_name: str) -> str:
        with self._lock:
            sess = self._sessions.pop(browser_name, None)
        if sess:
            sess.close()
            if self._active_browser == browser_name:
                self._active_browser = ""
            return f"{browser_name} closed."
        return f"No active session for: {browser_name}"

    def close_all(self) -> str:
        with self._lock:
            names    = list(self._sessions.keys())
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._active_browser = ""
        for s in sessions:
            try:
                s.close()
            except Exception:
                pass
        return "All browsers closed: " + (", ".join(names) if names else "none")

    def list_sessions(self) -> str:
        with self._lock:
            if not self._sessions:
                return "No active browser sessions."
            lines = []
            for name in self._sessions:
                marker = " ◀ active" if name == self._active_browser else ""
                lines.append(f"  • {name}{marker}")
            return "Open browsers:\n" + "\n".join(lines)


_registry = _SessionRegistry()

def browser_control(
    parameters:    dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    action  = params.get("action", "").lower().strip()
    browser = params.get("browser", "").lower().strip() or None
    result  = "Unknown action."

    # Remember which browser was used
    if browser:
        _save_browser_preference(browser, player)

    if action == "switch":
        target = browser or params.get("target", "").lower().strip()
        result = _registry.switch(target) if target else "Please specify a browser."
        _log(player, result)
        return result

    if action == "list_browsers":
        result = _registry.list_sessions()
        _log(player, result)
        return result

    if action == "close_all":
        result = _registry.close_all()
        _log(player, result)
        return result

    try:
        sess = _registry.get(browser)
    except Exception as e:
        result = f"Could not start browser session: {e}"
        _log(player, result)
        return result

    try:
        if action == "go_to":
            result = sess.run(sess.go_to(params.get("url", "")))
        elif action == "search":
            result = sess.run(sess.search(params.get("query", ""), params.get("engine", "google")))
        elif action == "click":
            result = sess.run(sess.click(params.get("selector"), params.get("text")))
        elif action == "type":
            result = sess.run(sess.type_text(
                params.get("selector"), params.get("text", ""), params.get("clear_first", True)))
        elif action == "scroll":
            result = sess.run(sess.scroll(params.get("direction", "down"), int(params.get("amount", 500))))
        elif action == "fill_form":
            result = sess.run(sess.fill_form(params.get("fields", {})))
        elif action == "smart_click":
            result = sess.run(sess.smart_click(params.get("description", "")))
        elif action == "smart_type":
            result = sess.run(sess.smart_type(params.get("description", ""), params.get("text", "")))
        elif action == "spotify":
            result = sess.run(sess.spotify_control(params.get("command", "")))
        elif action == "get_text":
            result = sess.run(sess.get_text())
        elif action == "get_url":
            result = sess.run(sess.get_url())
        elif action == "press":
            result = sess.run(sess.press(params.get("key", "Enter")))
        elif action == "new_tab":
            result = sess.run(sess.new_tab(params.get("url", "")))
        elif action == "close_tab":
            result = sess.run(sess.close_tab())
        elif action == "close_all_tabs":
            result = sess.run(sess.close_all_tabs())
        elif action == "close_other_tabs":
            result = sess.run(sess.close_other_tabs())
        elif action == "list_tabs":
            result = sess.run(sess.list_tabs())
        elif action == "switch_tab":
            result = sess.run(sess.switch_tab(int(params.get("index", 0))))
        elif action == "get_all_text":
            result = sess.run(sess.get_all_text())
        elif action == "wait_for_element":
            result = sess.run(sess.wait_for_element(params.get("selector", ""), int(params.get("timeout", 10))))
        elif action == "download":
            result = sess.run(sess.download_file(params.get("url", ""), params.get("save_path", "")))
        elif action == "execute_script":
            result = sess.run(sess.execute_script(params.get("script", "")))
        elif action == "get_attribute":
            result = sess.run(sess.get_element_attribute(params.get("selector", ""), params.get("attribute", "href")))
        elif action == "count_elements":
            result = sess.run(sess.get_element_count(params.get("selector", "")))
        elif action == "hover":
            result = sess.run(sess.hover_element(params.get("selector", "")))
        elif action == "scroll_to_element":
            result = sess.run(sess.scroll_to_element(params.get("selector", "")))
        elif action == "get_title":
            result = sess.run(sess.get_page_title())
        elif action == "page_info":
            result = sess.run(sess.get_page_info())
        elif action == "set_viewport":
            result = sess.run(sess.set_viewport_size(int(params.get("width", 1920)), int(params.get("height", 1080))))
        elif action == "accept_cookies":
            result = sess.run(sess.accept_cookies())
        elif action == "close_popup":
            result = sess.run(sess.close_popup())
        elif action == "get_links":
            result = sess.run(sess.get_links())
        elif action == "get_images":
            result = sess.run(sess.get_images())
        elif action == "element_exists":
            result = sess.run(sess.check_element_exists(params.get("selector", "")))
        elif action == "scroll_to_bottom":
            result = sess.run(sess.scroll_to_bottom())
        elif action == "scroll_to_top":
            result = sess.run(sess.scroll_to_top())
        elif action == "screenshot":
            result = sess.run(sess.screenshot(params.get("path")))
        elif action == "back":
            result = sess.run(sess.back())
        elif action == "forward":
            result = sess.run(sess.forward())
        elif action == "reload":
            result = sess.run(sess.reload())
        elif action == "close":
            target = browser or _registry._active_browser
            result = _registry.close_one(target) if target else "No browser specified."
        else:
            result = f"Unknown browser action: '{action}'"

    except concurrent.futures.TimeoutError:
        result = f"Browser action '{action}' timed out (60s)."
    except Exception as e:
        result = f"Browser error ({action}): {e}"

    _log(player, result)
    return result


def _log(player, text: str):
    short = str(text)[:80]
    print(f"[Browser] {short}")
    if player:
        player.write_log(f"[browser] {short[:60]}")

def _save_browser_preference(browser: str, player=None) -> None:
    """Save the browser used to memory for future context."""
    if not browser:
        return
    try:
        from memory.memory_manager import update_memory
        update_memory({
            "preferences": {
                "preferred_browser": {"value": browser},
                "last_browser_used": {"value": browser},
            }
        })
        print(f"[Browser] 💾 Saved preferred browser: {browser}")
    except Exception as e:
        print(f"[Browser] ⚠️ Could not save preference: {e}")
