import time
import sys
import os
import random
import threading
import shutil
import platform
from pathlib import Path

try:
    import colorama
    colorama.init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# ── ANSI helpers ─────────────────────────────────────────────
if HAS_COLORAMA:
    R = colorama.Fore.RED
    G = colorama.Fore.GREEN
    Y = colorama.Fore.YELLOW
    B = colorama.Fore.CYAN
    M = colorama.Fore.MAGENTA
    W = colorama.Fore.WHITE
    RES = colorama.Style.RESET_ALL
    BR = colorama.Style.BRIGHT
    DIM = colorama.Style.DIM
else:
    R = G = Y = B = M = W = RES = BR = DIM = ""

def _cls():
    os.system("cls" if os.name == "nt" else "clear")

def _set_cursor(visible: bool):
    os.system("echo \x1b[?25l" if not visible else "echo \x1b[?25h")

def _env_enabled(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).lower().strip() in {"1", "true", "yes", "on"}

def _progress_bar(pct: float, width: int = 40, char: str = "█", empty: str = "░", color: str = "") -> str:
    filled = int(pct * width)
    bar = color + char * filled + DIM + empty * (width - filled) + RES
    return f"|{bar}| {int(pct * 100):>3}%"

def _type_out(text: str, delay: float = 0.015, end: str = "\n"):
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print(end, end="", flush=True)

def _center(text: str) -> str:
    w = shutil.get_terminal_size().columns
    return text.center(w)

# ── JARVIS ASCII art ─────────────────────────────────────────
JARVIS_ART = [
    "⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣴⣶⣾⣿⣿⣿⣿⣷⣶⣦⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⣠⣴⣿⠿⢛⣩⣥⣶⠶⠶⠶⠶⣶⣬⣍⡛⠿⣿⣦⣄⠀⠀⠀⠀⠀",
    "⠀⠀⠀⣠⣾⡿⢋⣥⠞⠋⠈⣿⣿⠀⠀⠀⠀⣿⣿⠉⠙⠳⣬⡛⢿⣷⣄⠀⠀⠀",
    "⠀⠀⣴⣿⠏⣴⠋⠀⠀⠀⠀⣿⣿⡆⠀⠀⢸⣿⣿⠀⠀⠀⠀⢹⣦⠻⣿⣦⠀⠀",
    "⠀⣼⣿⢃⣾⣿⣏⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⠉⣹⣿⣷⡘⣿⣧⠀",
    "⢰⣿⠇⡾⠻⡅⠉⠛⢦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⡴⠛⠉⢨⠟⣧⢸⣿⡆",
    "⣾⣿⢸⡇⠀⠹⣄⠀⠀⠈⢻⣿⡿⢿⣿⣿⡿⢿⣿⡟⠁⠀⠀⣰⠋⠀⢸⡆⣿⣷",
    "⣿⣿⢸⡇⠀⠀⣘⣆⠀⠀⠀⠻⣷⣦⠀⠀⣴⣾⠏⠀⠀⠀⣰⣃⠀⠀⢸⡇⣿⣿",
    "⢿⣿⢸⣷⣾⣿⡿⠟⢦⠀⠀⠀⠹⣿⣇⣸⣿⠏⠀⠀⠀⡼⠻⢿⣿⣷⣾⠇⣿⡟",
    "⠸⣿⡆⢿⡉⠁⠀⠀⠈⢧⠀⠀⠀⠙⣿⣿⠃⠀⠀⢀⡜⠁⠀⠀⠈⢙⡟⣸⣿⠇",
    "⠀⢻⣿⡌⢷⡀⠀⣠⣴⣿⣷⡀⠀⠀⢸⡇⠀⠀⢀⣾⣿⣦⣄⠀⢀⡾⣡⣿⡟⠀",
    "⠀⠀⠻⣿⣦⠻⣿⣿⠿⠋⠀⠳⡄⠀⢸⡇⠀⢠⠎⠀⠙⢿⣿⣿⢟⣴⣿⠟⠀⠀",
    "⠀⠀⠀⠙⢿⣷⣬⡛⢦⣄⡀⠀⠹⣄⣸⣇⣠⠏⠀⢀⣠⡴⢛⣵⣾⡿⠃⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠉⠻⣿⣶⣬⣉⣛⠲⠿⠿⠿⠿⠖⣛⣩⣥⣾⣿⠟⠉⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⣿⣿⣿⣿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀",
]

# ── Scanning line ────────────────────────────────────────────
def _scan_line(w: int, y: int, h: int, color: str = B):
    chars = "══════════════════════"
    line = chars * (w // len(chars) + 1)
    return color + BR + line[:w] + RES
# ── Particle Matrix Rain RGB ─────────────────────────────────
def _matrix_rain(duration: float = 4.0, speed: float = 0.02):
    w = shutil.get_terminal_size().columns
    h = shutil.get_terminal_size().lines - 2

    chars = (
        "01"
        "アイウエオ"
        "カキクケコ"
        "サシスセソ"
        "タチツテト"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )

    colors = [G, B, M, Y]

    try:
        print("\033[2J", end="", flush=True)

        # ═══════════════════════════════════════════════
        # FASE 1 - DESCENDO
        # ═══════════════════════════════════════════════

        drops_down = [random.randint(-h, 0) for _ in range(w)]

        start = time.time()

        while time.time() - start < duration:

            for i in range(w):

                y = drops_down[i]
                color = random.choice(colors)

                # Cabeça
                if 0 <= y < h:
                    print(
                        f"\033[{y};{i+1}H"
                        f"{BR}{W}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Corpo
                if 0 <= y - 1 < h:
                    print(
                        f"\033[{y-1};{i+1}H"
                        f"{color}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Cauda
                if 0 <= y - 2 < h:
                    print(
                        f"\033[{y-2};{i+1}H"
                        f"{DIM}{color}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Limpeza
                if 0 <= y - 4 < h:
                    print(
                        f"\033[{y-4};{i+1}H ",
                        end="",
                        flush=True
                    )

                drops_down[i] += 1

                if drops_down[i] > h + 15:
                    drops_down[i] = random.randint(-25, 0)

            time.sleep(speed)

        # ═══════════════════════════════════════════════
        # FASE 2 - SUBINDO
        # ═══════════════════════════════════════════════

        drops_up = [random.randint(h, h + 15) for _ in range(w)]

        start = time.time()

        while time.time() - start < duration:

            for i in range(w):

                y = drops_up[i]
                color = random.choice(colors)

                # Cabeça
                if 0 <= y < h:
                    print(
                        f"\033[{y};{i+1}H"
                        f"{BR}{W}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Corpo
                if 0 <= y + 1 < h:
                    print(
                        f"\033[{y+1};{i+1}H"
                        f"{color}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Cauda
                if 0 <= y + 2 < h:
                    print(
                        f"\033[{y+2};{i+1}H"
                        f"{DIM}{color}{random.choice(chars)}{RES}",
                        end="",
                        flush=True
                    )

                # Limpeza
                if 0 <= y + 4 < h:
                    print(
                        f"\033[{y+4};{i+1}H ",
                        end="",
                        flush=True
                    )

                drops_up[i] -= 1

                if drops_up[i] < -15:
                    drops_up[i] = random.randint(h, h + 20)

            time.sleep(speed)

        # ═══════════════════════════════════════════════
        # FASE 3 - FADE OUT
        # ═══════════════════════════════════════════════

        for _ in range(5):
            print("\033[2J", end="", flush=True)
            time.sleep(0.05)

        print("\033[H", end="", flush=True)

    except:
        pass



# ── Boot modules ─────────────────────────────────────────────
BOOT_MODULES = [
    ("CORE",           "Initializing neural matrices...",      18, M),
    ("MEM",            "Mapping synaptic pathways...",          22, B),
    ("VAULT",          "Indexing Obsidian knowledge base...",   35, G),
    ("AUDIO",          "Calibrating acoustic interface...",     12, M),
    ("FACE",           "Loading facial recognition engine...",  15, B),
    ("SPOTIFY",        "Bridging Spotify Web API...",           8, G),
    ("NEURAL",         "Syncing advanced learner cortex...",    25, M),
    ("SMART_HOME",     "Discovering IoT devices...",            10, B),
    ("MOTOR",          "Arming response systems...",            20, G),
    ("NEXUS",          "Finalizing integration layer...",       30, M),
]

def _start_background_boot_sequence(duration: float = 2.8):
    modules = BOOT_MODULES[:]
    random.shuffle(modules)
    total_steps = sum(max(1, steps) for _, _, steps, _ in modules)
    lock = threading.Lock()
    state = {
        "completed": [],
        "running": True,
    }

    def worker():
        try:
            for tag, desc, steps, color in modules:
                time.sleep(duration * (max(1, steps) / total_steps))
                with lock:
                    state["completed"].append((tag, desc, color))
        finally:
            with lock:
                state["running"] = False

    thread = threading.Thread(target=worker, daemon=True, name="JarvisBootChecks")
    thread.start()
    return state, lock, thread

def _boot_sequence(duration: float = 0.45, state=None, lock=None, thread=None):
    modules = BOOT_MODULES[:]

    if state is not None and lock is not None:
        if thread is not None:
            thread.join(timeout=max(0.0, duration))
        with lock:
            completed = {tag for tag, _desc, _color in state.get("completed", [])}
            still_running = bool(state.get("running"))

        for tag, desc, _steps, color in modules:
            if tag in completed:
                status = BR + G + " OK " + RES
            else:
                status = Y + " BG " + RES
            print(f"  [{status}] {color}{tag:8}{RES}  {desc}")

        if still_running:
            print(DIM + "  Background boot checks still running..." + RES)
        return

    random.shuffle(modules)
    completed = []
    per_module = duration / len(modules)

    for tag, desc, steps, color in modules:
        print(f"  [{Y}...{RES}] {color}{tag:8}{RES}  {desc}", end="", flush=True)
        for s in range(steps):
            if s % (steps // 4) == 0:
                dots = "." * ((s // (steps // 4)) % 3 + 1)
                print(f"\r  [{Y}...{RES}] {color}{tag:8}{RES}  {desc}{dots}", end="", flush=True)
            time.sleep(per_module / steps)
        print(f"\r  [{BR + G} OK {RES}] {color}{tag:8}{RES}  {desc}")
        completed.append((tag, desc, color))

    for tag, desc, color in completed:
        pass

# ── Cinematic system info ────────────────────────────────────
def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def _system_specs() -> list[tuple[str, str]]:
    specs = [
        ("OS", platform.platform()),
        ("CPU", platform.processor() or platform.machine() or "Unknown"),
        ("PYTHON", platform.python_version()),
    ]
    try:
        import psutil
        specs.append(("RAM", _format_bytes(psutil.virtual_memory().total)))
        disk = shutil.disk_usage(str(Path.home()))
        specs.append(("DISK", f"{_format_bytes(disk.free)} free / {_format_bytes(disk.total)} total"))
    except Exception:
        pass
    return specs

def _show_system_specs(main_color: str = M, accent_color: str = B):
    """Display hardware specs with neon styling."""
    specs = _system_specs()

    w = shutil.get_terminal_size().columns
    box_w = min(70, w - 4)
    pad = (w - box_w) // 2

    print("\n" + " " * pad + accent_color + "┌" + "─" * (box_w - 2) + "┐" + RES)
    print(" " * pad + "│" + " " * (box_w - 2) + "│")
    title = " SYSTEM SPECIFICATIONS "
    tl = len(title)
    left = (box_w - 2 - tl) // 2
    right = box_w - 2 - tl - left
    print(" " * pad + "│" + " " * left + BR + main_color + title + RES + " " * right + "│")
    print(" " * pad + "│" + " " * (box_w - 2) + "│")

    for label, value in specs:
        inner = f"  {main_color}{label:8}{RES}  {BR}{value}{RES}"
        print(" " * pad + "│" + " " * max(1, (box_w - 2 - len(inner)) // 2) + inner + " " * max(1, (box_w - 2 - len(inner) - (box_w - 2 - len(inner)) // 2)) + "│")

    print(" " * pad + "│" + " " * (box_w - 2) + "│")
    print(" " * pad + accent_color + "└" + "─" * (box_w - 2) + "┘" + RES)
    print()

# ── The main animation ───────────────────────────────────────
def enable_clap_detection(on_clap: callable = None) -> bool:
    """Stub: clap detection was removed — face recognition replaced it."""
    return False

def run_startup_animation(
    silent: bool = False,
    theme_color: str = "magenta",
    detailed: bool | None = None,
    clear_after: bool | None = None,
) -> None:
    """Epic cinematic startup animation for JARVIS system.

    Parameters
    ----------
    silent : bool
        If True, skip animation entirely.
    theme_color : str
        One of 'magenta', 'cyan', 'green', 'red' — maps to pink/neon preference.
    """
    if silent:
        return
    if detailed is None:
        detailed = _env_enabled("MARK_XL_BOOT_DETAIL", "0")
    if clear_after is None:
        clear_after = not _env_enabled("MARK_XL_BOOT_KEEP_SCREEN", "0")

    color_map = {
        "magenta": M, "pink": M, "rosa": M, "neon": M,
        "cyan": B, "blue": B, "azul": B,
        "green": G, "verde": G,
        "red": R, "vermelho": R,
    }
    main_color = color_map.get(theme_color, M)
    accent_color = B if main_color == M else M

    _cls()
    _set_cursor(False)
    boot_state, boot_lock, boot_thread = _start_background_boot_sequence(2.8)

    try:
        # ── Phase 1: Matrix rain ──
        _matrix_rain(1.8)
        _cls()

        # ── Phase 1.5: JARVIS typing reveal ──
        for line in JARVIS_ART:
            padded = _center(line)
            for ch in padded:
                print(BR + main_color + ch + RES, end="", flush=True)
                time.sleep(0.003)
            print()
            time.sleep(0.04)
        print()
        jarvis_sub = "  Sistema de IA personalizada J.A.R.V.I.S!  "
        for ch in _center("╔" + "═" * (len(jarvis_sub) + 2) + "╗"):
            print(BR + accent_color + ch + RES, end="", flush=True)
            time.sleep(0.002)
        print()
        for ch in _center("║ " + jarvis_sub + " ║"):
            print(BR + accent_color + ch + RES, end="", flush=True)
            time.sleep(0.002)
        print()
        for ch in _center("╚" + "═" * (len(jarvis_sub) + 2) + "╝"):
            print(BR + accent_color + ch + RES, end="", flush=True)
            time.sleep(0.002)
        print()
        time.sleep(0.45)
        _cls()

        if detailed:
            # Optional verbose boot diagnostics. Disabled by default for faster startup.
            print()
            print(accent_color + _center("🔧 INITIALIZING SYSTEMS") + RES)
            print(accent_color + _center("────────────────────") + RES)
            print()
            _boot_sequence(0.45, state=boot_state, lock=boot_lock, thread=boot_thread)

            print()
            _type_out(accent_color + _center("› Scanning hardware configuration...") + RES, 0.002, "\n\n")
            _show_system_specs(main_color, accent_color)
            time.sleep(0.25)
        else:
            boot_thread.join(timeout=0.05)

    except:
        pass
    finally:
        if clear_after:
            _cls()
        _set_cursor(True)

if __name__ == "__main__":
    run_startup_animation(theme_color="magenta")
