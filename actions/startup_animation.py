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

_BOOT_SCREEN_VISIBLE = threading.Event()
_BOOT_VOICE_STARTED = threading.Event()
_BOOT_NARRATION_FINISHED = threading.Event()


def wait_for_boot_screen(timeout: float = 12.0) -> bool:
    """Allow native audio to wait until the visual boot is visible."""
    return _BOOT_SCREEN_VISIBLE.wait(timeout=max(0.0, timeout))


def signal_native_boot_voice() -> None:
    """Start visual module progress with the native Jarvis voice prompt."""
    _BOOT_VOICE_STARTED.set()


def signal_native_boot_voice_finished() -> None:
    """Release the final boot screen only after the spoken boot has ended."""
    _BOOT_NARRATION_FINISHED.set()
def _activate_pyautogui() -> bool:
    """Prepare desktop automation without sending any input to the user."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return True
    except Exception as exc:
        print(f"[JARVIS] Desktop automation unavailable: {exc}")
        return False


def _play_boot_sound(kind: str = "pulse") -> None:
    """Play small local synth cues without relying on external audio files."""
    if os.name != "nt" or not _env_enabled("MARK_XL_BOOT_SFX", "1"):
        return

    tones = {
        "wake": ((440, 35), (660, 45), (990, 70)),
        "pulse": ((780, 24), (1120, 32)),
        "ready": ((660, 45), (880, 55), (1320, 90)),
    }.get(kind, ())

    def play() -> None:
        try:
            import winsound
            for frequency, duration in tones:
                winsound.Beep(frequency, duration)
        except Exception:
            pass

    threading.Thread(target=play, daemon=True, name="JarvisBootSFX").start()


class _ParticleBed:
    """Loop the composed electronic boot texture without competing with speech."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._asset = Path(__file__).resolve().parent.parent / "assets" / "audio" / "jarvis_boot_electronic_mix.wav"

    def start(self) -> None:
        if not self._asset.exists():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="JarvisElectronicBed")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.8)

    def _load_texture(self):
        import wave
        import numpy as np

        with wave.open(str(self._asset), "rb") as source:
            sample_rate = source.getframerate()
            channels = source.getnchannels()
            width = source.getsampwidth()
            frames = source.readframes(source.getnframes())
        if width != 2:
            raise ValueError("Formato de textura de boot não suportado")
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        return audio, sample_rate

    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd

            audio, sample_rate = self._load_texture()
        except Exception:
            return
        if not len(audio):
            return

        volume = max(0.0, min(1.0, float(os.environ.get("MARK_XL_BOOT_PARTICLE_VOLUME", "0.32"))))
        block_size = 1024
        # Each boot starts at another point of the non-linear composition.
        position = random.randrange(len(audio))

        try:
            with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size) as stream:
                while not self._stop.is_set():
                    end = position + block_size
                    if end <= len(audio):
                        frame = audio[position:end]
                    else:
                        frame = np.concatenate((audio[position:], audio[:end % len(audio)]))
                    position = end % len(audio)
                    stream.write(np.clip(frame * volume, -0.42, 0.42).astype(np.float32).reshape(-1, 1))
        except Exception:
            return
def _run_futuristic_loading_screen_legacy(pyautogui_ready: bool) -> bool:
    """Show the visual boot sequence and announce each module in order."""
    try:
        from PyQt6.QtCore import QEventLoop, Qt, QTimer
        from PyQt6.QtGui import QColor, QFont
        from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget
    except Exception:
        return False

    modules = [
        ("VOICE", "CANAL DE VOZ NATIVO", "Ativando canal de voz nativo."),
        ("BACKEND", "BACKEND NEURAL", "Conectando backend neural."),
        ("BLUETOOTH", "LINK BLUETOOTH", "Verificando enlace Bluetooth."),
        ("CORTEX", "CÓRTEX NEURAL", "Sincronizando córtex neural."),
        ("VISION", "VISÃO COMPUTACIONAL", "Carregando visão computacional."),
        ("AUTOMATION", "AUTOMAÇÃO DESKTOP", "Automação desktop online." if pyautogui_ready else "Automação desktop em modo manual."),
        ("BRIDGE", "PONTE IPHONE", "Sincronizando ponte móvel."),
        ("NEXUS", "NEXUS OPERACIONAL", "Sistemas avançados online. Jarvis pronto."),
    ]

    _BOOT_SCREEN_VISIBLE.clear()
    _BOOT_VOICE_STARTED.clear()
    app = QApplication.instance() or QApplication(sys.argv)
    screen = QWidget()
    screen.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
    screen.setWindowTitle("JARVIS // NEURAL BOOT")
    screen.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    screen.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    screen.setFixedSize(820, 680)
    screen.setStyleSheet("background:#02070e; color:#d8f8ff;")

    root = QVBoxLayout(screen)
    root.setContentsMargins(28, 26, 28, 24)
    root.setSpacing(14)

    eyebrow = QLabel("JARVIS // NEURAL SYSTEM BOOT")
    eyebrow.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
    eyebrow.setStyleSheet("color:#00d4ff; letter-spacing:3px;")
    root.addWidget(eyebrow)

    title = QLabel("INICIALIZANDO\nSISTEMAS")
    title.setFont(QFont("Segoe UI", 31, QFont.Weight.Bold))
    title.setStyleSheet("color:#e9fbff; line-height:1.0;")
    root.addWidget(title)

    state = QLabel("AGUARDANDO CANAL NATIVO")
    state.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
    state.setStyleSheet("color:#ffb000; padding:8px 10px; border:1px solid #694c00; background:#120e02;")
    root.addWidget(state)

    progress = QProgressBar()
    progress.setRange(0, len(modules))
    progress.setValue(0)
    progress.setTextVisible(False)
    progress.setFixedHeight(8)
    progress.setStyleSheet("QProgressBar{background:#061522;border:1px solid #164967;border-radius:4px;}QProgressBar::chunk{background:#00d4ff;border-radius:3px;}")
    root.addWidget(progress)

    rows = []
    rows_box = QVBoxLayout()
    rows_box.setSpacing(5)
    for tag, label, _speech in modules:
        row = QFrame()
        row.setFixedHeight(34)
        row.setStyleSheet("QFrame{background:#04101a;border:1px solid #102d40;border-radius:4px;}")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 3, 10, 3)
        tag_label = QLabel(tag)
        tag_label.setFixedWidth(120)
        tag_label.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        tag_label.setStyleSheet("color:#39748d;")
        text_label = QLabel(label)
        text_label.setFont(QFont("Consolas", 9))
        text_label.setStyleSheet("color:#6da0b4;")
        status_label = QLabel("AGUARDANDO")
        status_label.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_label.setStyleSheet("color:#365061;")
        row_layout.addWidget(tag_label)
        row_layout.addWidget(text_label, 1)
        row_layout.addWidget(status_label)
        rows.append((row, tag_label, text_label, status_label))
        rows_box.addWidget(row)
    root.addLayout(rows_box)

    telemetry = QLabel("NEURAL BUS  //  00:00:00  //  SYNAPSE LINK STANDBY")
    telemetry.setFont(QFont("Consolas", 8))
    telemetry.setStyleSheet("color:#35728a; padding-top:6px;")
    root.addWidget(telemetry)

    available = QApplication.primaryScreen().availableGeometry()
    screen.move(available.center() - screen.rect().center())
    screen.show()
    particle_bed = _ParticleBed()
    particle_bed.start()
    _BOOT_SCREEN_VISIBLE.set()
    if not _env_enabled("MARK_XL_BOOT_VOICE", "1"):
        _BOOT_VOICE_STARTED.set()

    loop = QEventLoop()
    index = 0
    started_at = time.time()

    def update_telemetry() -> None:
        elapsed = int(time.time() - started_at)
        telemetry.setText(f"NEURAL BUS  //  00:00:{elapsed:02d}  //  SYNAPSE LINK ACTIVE")

    pulse = QTimer(screen)
    pulse.timeout.connect(update_telemetry)
    pulse.start(250)

    def begin_next_module() -> None:
        nonlocal index
        tag, label, speech = modules[index]
        active = rows[index]
        active[0].setStyleSheet("QFrame{background:#071c2a;border:1px solid #00d4ff;border-radius:4px;}")
        active[1].setStyleSheet("color:#00d4ff;")
        active[2].setStyleSheet("color:#d8f8ff;")
        active[3].setText("CARREGANDO")
        active[3].setStyleSheet("color:#ffb000;")
        state.setText(f"CARREGANDO // {label}")
        progress.setValue(index)
        index += 1
        QTimer.singleShot(1800, advance)

    def advance() -> None:
        # The first module starts immediately. Later modules get a visible pause
        # after the prior one is confirmed online and its pulse has played.
        if index == 0:
            begin_next_module()
            return

        previous = rows[index - 1]
        previous[0].setStyleSheet("QFrame{background:#02170f;border:1px solid #0d6d48;border-radius:4px;}")
        previous[1].setStyleSheet("color:#00ff88;")
        previous[2].setStyleSheet("color:#b7f9dd;")
        previous[3].setText("ONLINE")
        previous[3].setStyleSheet("color:#00ff88;")

        if index >= len(modules):
            state.setText("NÚCLEO OPERACIONAL ONLINE")
            state.setStyleSheet("color:#00ff88; padding:8px 10px; border:1px solid #0d6d48; background:#02170f;")
            progress.setValue(len(modules))
            particle_bed.stop()
            _play_boot_sound("ready")
            final_wait_started = time.monotonic()

            def finish_after_narration() -> None:
                voice_expected = _env_enabled("MARK_XL_BOOT_VOICE", "1")
                timed_out = time.monotonic() - final_wait_started >= 22.0
                if not voice_expected or _BOOT_NARRATION_FINISHED.is_set() or timed_out:
                    # Keep the green ONLINE screen visible briefly before the main UI opens.
                    QTimer.singleShot(850, finish)
                    return
                QTimer.singleShot(100, finish_after_narration)

            finish_after_narration()
            return

        _play_boot_sound("pulse")
        QTimer.singleShot(300, begin_next_module)
    def finish() -> None:
        pulse.stop()
        particle_bed.stop()
        screen.close()
        loop.quit()

    voice_wait_started = time.monotonic()

    def wait_for_native_voice() -> None:
        if _BOOT_VOICE_STARTED.is_set():
            advance()
            return
        if time.monotonic() - voice_wait_started >= 12.0:
            # A delayed/missing voice handshake must never hide the main UI forever.
            print("[JARVIS BOOT] Voz ainda indisponível; abrindo a interface.", flush=True)
            finish()
            return
        QTimer.singleShot(80, wait_for_native_voice)

    QTimer.singleShot(80, wait_for_native_voice)
    loop.exec()
    return True


def _run_futuristic_loading_screen(pyautogui_ready: bool) -> bool:
    """Show a short HUD core loader with no spoken module roll-call."""
    try:
        import math
        from PyQt6.QtCore import QEventLoop, QPointF, QRectF, Qt, QTimer
        from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
        from PyQt6.QtWidgets import QApplication, QWidget
    except Exception:
        return False

    class _TechBootCanvas(QWidget):
        def __init__(self):
            super().__init__()
            self.progress = 0.0
            self.angle = 0.0
            self.setWindowTitle("JARVIS // CORE LINK")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
            self.setFixedSize(680, 440)

        def paintEvent(self, _event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), QColor(0, 4, 9))
            w, h = self.width(), self.height()
            cx, cy = w * 0.5, h * 0.47
            radius = min(w, h) * 0.31

            # Blueprint grid.
            p.setPen(QPen(QColor(20, 92, 128, 34), 1))
            for x in range(20, w, 28):
                p.drawLine(x, 0, x, h)
            for y in range(20, h, 28):
                p.drawLine(0, y, w, y)

            glow = QRadialGradient(QPointF(cx, cy), radius * 1.35)
            glow.setColorAt(0.0, QColor(80, 220, 255, 105))
            glow.setColorAt(0.42, QColor(20, 150, 235, 38))
            glow.setColorAt(1.0, QColor(0, 30, 65, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(cx, cy), radius * 1.35, radius * 1.35)
            p.setBrush(Qt.BrushStyle.NoBrush)

            specs = ((1.02, 48, 4.4, 1.0), (0.86, 32, 7.1, -1.4), (0.69, 24, 9.8, 2.1), (0.50, 16, 15.0, -2.8))
            for ring, (scale, count, span, speed) in enumerate(specs):
                rr = radius * scale
                rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
                for index in range(count):
                    if (index + ring) % 8 == 0:
                        continue
                    alpha = 80 + ring * 25 + int(70 * max(0.0, math.sin(self.angle * 0.04 + index)))
                    p.setPen(QPen(QColor(38, 190 if ring < 2 else 225, 255, alpha), 1.0 + ring * 0.3))
                    start = self.angle * speed + index * 360.0 / count
                    p.drawArc(rect, int(start * 16), int(span * 16))

            # Radial progress sectors light up clockwise.
            lit = int(40 * self.progress)
            for index in range(40):
                angle = math.radians(index * 9 - 90)
                inner = radius * 0.55
                outer = radius * (0.63 if index % 5 else 0.68)
                color = QColor(195, 246, 255, 235) if index < lit else QColor(22, 93, 130, 70)
                p.setPen(QPen(color, 2.2 if index < lit else 1.0))
                p.drawLine(
                    QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                    QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer),
                )

            core_r = radius * (0.16 + math.sin(self.angle * 0.08) * 0.012)
            core = QRadialGradient(QPointF(cx, cy), core_r)
            core.setColorAt(0.0, QColor(245, 255, 255, 255))
            core.setColorAt(0.25, QColor(105, 225, 255, 245))
            core.setColorAt(1.0, QColor(15, 120, 235, 0))
            p.setPen(QPen(QColor(176, 240, 255, 220), 1.0))
            p.setBrush(core)
            p.drawEllipse(QPointF(cx, cy), core_r, core_r)

            p.setPen(QColor(205, 247, 255))
            p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            p.drawText(QRectF(0, 22, w, 22), Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S  //  CORE LINK")
            p.setFont(QFont("Consolas", 25, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy - 21, w, 42), Qt.AlignmentFlag.AlignCenter, f"{int(self.progress * 100):02d}%")

            bar = QRectF(90, h - 50, w - 180, 3)
            p.fillRect(bar, QColor(13, 55, 78))
            fill = QRectF(bar.left(), bar.top(), bar.width() * self.progress, bar.height())
            gradient = QLinearGradient(fill.topLeft(), fill.topRight())
            gradient.setColorAt(0.0, QColor(20, 130, 255))
            gradient.setColorAt(1.0, QColor(180, 245, 255))
            p.fillRect(fill, gradient)
            p.setFont(QFont("Consolas", 8))
            p.setPen(QColor(61, 145, 180))
            p.drawText(QRectF(90, h - 35, w - 180, 18), Qt.AlignmentFlag.AlignCenter, "SYNCHRONIZING NEURAL INTERFACE")
            p.end()

    _BOOT_SCREEN_VISIBLE.clear()
    _BOOT_VOICE_STARTED.clear()
    _BOOT_NARRATION_FINISHED.set()
    app = QApplication.instance() or QApplication(sys.argv)
    screen = _TechBootCanvas()
    available = QApplication.primaryScreen().availableGeometry()
    screen.move(available.center() - screen.rect().center())
    screen.show()
    _BOOT_SCREEN_VISIBLE.set()
    _play_boot_sound("wake")

    loop = QEventLoop()
    started = time.perf_counter()
    duration = max(0.8, float(os.environ.get("MARK_XL_BOOT_DURATION", "2.2")))
    timer = QTimer(screen)

    def advance():
        elapsed = time.perf_counter() - started
        raw = min(1.0, elapsed / duration)
        # Smooth acceleration/deceleration still reaches a truthful 100%.
        screen.progress = raw * raw * (3.0 - 2.0 * raw)
        screen.angle = elapsed * 78.0
        screen.update()
        if raw >= 1.0:
            timer.stop()
            _play_boot_sound("ready")
            QTimer.singleShot(180, finish)

    def finish():
        screen.close()
        loop.quit()

    timer.timeout.connect(advance)
    timer.start(16)
    loop.exec()
    return True


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
    pyautogui_ready = _activate_pyautogui()
    if _env_enabled("MARK_XL_BOOT_GUI", "1") and _run_futuristic_loading_screen(pyautogui_ready):
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
