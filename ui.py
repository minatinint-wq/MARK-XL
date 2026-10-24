from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from actions.runtime_identity import MARK_NAME, WINDOW_TITLE

_qt_rules = os.environ.get("QT_LOGGING_RULES", "")
if "qt.qpa.window" not in _qt_rules:
    os.environ["QT_LOGGING_RULES"] = (_qt_rules + ";qt.qpa.window=false").strip(";")

from actions.cpu_acceleration import CPU_ACCELERATION  # Configure before importing Qt/native math libraries.
from actions.graphics_runtime import GRAPHICS_MODE  # Configure before importing Qt.

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


def _prefer_low_memory_mode() -> bool:
    """Avoid starting Chromium/WebGL automatically on machines with 8 GB RAM."""
    setting = os.environ.get("MARK_XL_LOW_MEMORY", "auto").strip().lower()
    if setting in {"1", "true", "yes", "on"}:
        return True
    if setting in {"0", "false", "no", "off"}:
        return False
    try:
        return psutil.virtual_memory().total <= 10 * 1024**3
    except Exception:
        return False


def _glow_only_mode() -> bool:
    return os.environ.get("MARK_XL_GLOW_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _OS == "Windows" else 0


def _initial_model_tier() -> str:
    """Use the brain route because search_knowledge follows this persisted preset."""
    state_path = BASE_DIR / "memory" / "brain_mode_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        operational = state.get("operational_parameters") or {}
        tier = str(operational.get("llm_mode") or "").strip().lower()
        if tier in {"normal", "fast", "ultra"}:
            return tier
        module = str(state.get("parameter_module") or operational.get("module") or "normal").strip().lower()
        return {"rapido": "fast", "rápido": "fast", "ultra": "ultra"}.get(module, "normal")
    except Exception:
        return "normal"


class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0
        self.gpu  = -1.0
        self.tmp  = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        self._cached_gpu = -1.0
        self._cached_tmp = -1.0
        self._last_gpu_check = 0.0
        self._last_tmp_check = 0.0
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(0.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        if now - self._last_gpu_check >= 1.0:
            self._cached_gpu = self._get_gpu()
            self._last_gpu_check = now
        gpu = self._cached_gpu

        if now - self._last_tmp_check >= 10.0:
            self._cached_tmp = self._get_temp()
            self._last_tmp_check = now
        tmp = self._cached_tmp

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
                creationflags=_NO_WINDOW
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3,
                    creationflags=_NO_WINDOW
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self.visual_mode = "normal"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._avatar_mode = True
        self._voice_level = 0.0
        self._voice_target = 0.0
        self._mouth_level = 0.0
        self._mouth_target = 0.0
        self._mouth_impulse = 0.0
        self._waveform = [0.0] * 48
        self._waveform_target = [0.0] * 48
        self._voice_bands = [0.0] * 14
        self._avatar_angle = 0.0
        self._energy_phase = 0.0
        self._mesh_y = 0.0
        self._mesh_x = 14.0
        self._sphere_points: list[tuple[float, float, float, float]] = []
        self._sphere_edges: list[tuple[int, int]] = []
        self._glow_only = _glow_only_mode()
        if not self._glow_only:
            self._build_consciousness_mesh()
            self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._low_memory_mode = self._glow_only or _prefer_low_memory_mode()
        self._tmr.start(80 if self._low_memory_mode else 40)
        self._reactor = None
        if self._low_memory_mode:
            print("[JARVIS] Modo leve: armadura WebGL desativada para economizar RAM.")
        else:
            try:
                from actions.reactor_view import ReactorView
                self._reactor = ReactorView(self)
                self._reactor.setGeometry(self.rect())
                self._reactor.failed.connect(self._reactor_failed)
                QApplication.instance().aboutToQuit.connect(self._reactor.shutdown)
                # The WebGL scene animates on its own requestAnimationFrame loop.
                self._tmr.start(125)
            except Exception as exc:
                print(f"[Reactor3D] Using canvas fallback: {type(exc).__name__}")

    def _reactor_failed(self, message):
        reactor, self._reactor = self._reactor, None
        if reactor is not None:
            reactor.shutdown()
            reactor.hide()
            reactor.deleteLater()
        # The painted fallback owns its animation, so restore its original frame rate.
        self._tmr.start(40)
        print(f"[Reactor3D] {message}; canvas fallback active")
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_reactor", None) is not None:
            self._reactor.setGeometry(self.rect())

    def _load_face(self, path: str):
        if self._avatar_mode:
            self._face_px = None
            return
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(Path(path)).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            if not self._avatar_mode:
                mk  = Image.new("L", (sz, sz), 0)
                ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
                img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def set_voice_metrics(self, payload: dict):
        """Drive the visual from real user/AI PCM energy."""
        if self._reactor is not None:
            self._reactor.set_voice_metrics(payload)
            return
        try:
            level = max(0.0, min(1.0, float(payload.get("level") or 0.0)))
        except (TypeError, ValueError):
            level = 0.0
        source = str(payload.get("source") or "").casefold()
        if source == "ai":
            self._voice_target = level
        elif not self.speaking:
            self._voice_target = level * 0.42

        raw_wave = payload.get("waveform") or []
        if raw_wave:
            values = []
            for index in range(len(self._waveform_target)):
                source_index = min(len(raw_wave) - 1, int(index * len(raw_wave) / len(self._waveform_target)))
                try:
                    values.append(max(-1.0, min(1.0, float(raw_wave[source_index]))))
                except (TypeError, ValueError):
                    values.append(0.0)
            self._waveform_target = values
            wave_peak = max((abs(value) for value in values), default=0.0)
            wave_rms = math.sqrt(sum(value * value for value in values) / max(1, len(values)))
            speech_energy = max(level, wave_peak * 0.92, wave_rms * 2.45)
            if source == "ai" or self.speaking:
                previous = self._mouth_target
                self._mouth_target = max(0.0, min(1.0, speech_energy * 1.75))
                self._mouth_impulse = max(self._mouth_impulse, abs(self._mouth_target - previous) * 1.8)

        raw_bands = payload.get("bands") or []
        if raw_bands:
            self._voice_bands = [
                max(0.0, min(1.0, float(value))) for value in raw_bands[:14]
            ]
            self._voice_bands.extend([0.0] * (14 - len(self._voice_bands)))

    def set_visual_mode(self, mode: str):
        aliases = {
            "devil": "evil", "maligno": "evil", "malvada": "evil", "malvado": "evil",
            "anjo": "cute", "angel": "cute", "cute": "cute", "fofo": "cute", "fofa": "cute",
            "sentinela": "sentinel", "tatico": "sentinel", "tático": "sentinel",
            "padrao": "normal", "padrão": "normal", "classico": "normal", "clássico": "normal",
        }
        mode = aliases.get(str(mode or "").strip().casefold(), str(mode or "").strip().casefold())
        if mode not in {"normal", "evil", "cute", "sentinel"}:
            mode = "normal"
        self.visual_mode = mode
        self._particles.clear()
        self.update()

    def _mode_palette(self):
        return {
            "normal": ((48, 190, 255), (190, 238, 255)),
            "evil": ((255, 32, 32), (255, 70, 70)),
            "cute": ((255, 255, 255), (235, 235, 235)),
            "sentinel": ((48, 150, 255), (0, 255, 196)),
        }.get(self.visual_mode, ((48, 190, 255), (190, 238, 255)))

    def _build_consciousness_mesh(self):
        """Create a deterministic 3D neural sphere and its local synapses."""
        count = 88
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        for index in range(count):
            y = 1.0 - (index / (count - 1)) * 2.0
            radius = math.sqrt(max(0.0, 1.0 - y * y))
            theta = golden_angle * index
            x = math.cos(theta) * radius
            z = math.sin(theta) * radius
            phase = (index * 2.399963 + y * 1.7) % (math.pi * 2)
            self._sphere_points.append((x, y, z, phase))

        edges: set[tuple[int, int]] = set()
        for index, point in enumerate(self._sphere_points):
            distances = []
            for other_index, other in enumerate(self._sphere_points):
                if index == other_index:
                    continue
                distance = sum((point[axis] - other[axis]) ** 2 for axis in range(3))
                distances.append((distance, other_index))
            for distance, other_index in sorted(distances)[:3]:
                if distance < 0.22:
                    edges.add(tuple(sorted((index, other_index))))
        self._sphere_edges = sorted(edges)

    def _project_consciousness(self, cx: float, cy: float, radius: float, y_angle: float | None = None):
        ay = math.radians(self._mesh_y if y_angle is None else y_angle)
        ax = math.radians(self._mesh_x + math.sin(self._energy_phase * 0.55) * 5.0)
        cos_y, sin_y = math.cos(ay), math.sin(ay)
        cos_x, sin_x = math.cos(ax), math.sin(ax)
        activity = max(self._voice_level, 0.18 if self.speaking else 0.0)
        projected = []
        for index, (x, y, z, phase) in enumerate(self._sphere_points):
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            y2 = y * cos_x - z1 * sin_x
            z2 = y * sin_x + z1 * cos_x
            wave = abs(self._waveform[index % len(self._waveform)])
            neural_noise = math.sin(phase + self._energy_phase * 2.1)
            deformation = 1.0 + neural_noise * 0.018 + activity * (0.025 + wave * 0.11)
            perspective = 0.91 + (z2 + 1.0) * 0.075
            projected.append((
                cx + x1 * radius * deformation * perspective,
                cy + y2 * radius * deformation * perspective,
                z2,
                phase,
            ))
        return projected

    def _draw_synthetic_face(self, p: QPainter, cx: float, cy: float, radius: float, activity: float, thinking: bool):
        """Build a humanoid expression from holographic symbols and voice energy."""
        primary, accent = self._mode_palette()
        mode = self.visual_mode
        blink_period = 92 if mode == "cute" else 137
        blink_tick = self._tick % blink_period
        if blink_tick < 2:
            eye_open = 0.08
        elif blink_tick == 2:
            eye_open = 0.42
        else:
            eye_open = 1.0

        eye_y = cy - radius * (0.17 if mode == "cute" else 0.19)
        eye_offset = radius * (0.32 if mode == "cute" else 0.34)
        eye_w = radius * (0.27 if mode == "cute" else 0.245)
        eye_height_gain = {"evil": 0.068, "cute": 0.155, "sentinel": 0.082}.get(mode, 0.105)
        eye_h = radius * (eye_height_gain + activity * 0.018) * eye_open
        focus_shift = math.sin(self._energy_phase * (2.4 if thinking else 0.72)) * eye_w * (0.14 if thinking else 0.045)
        focus_y = math.sin(self._energy_phase * 0.83) * eye_h * 0.12
        symbol_sets = (("0", "1", "/", "+", "<"), (">", "+", "\\", "1", "0"))

        for side, symbols in ((-1, symbol_sets[0]), (1, symbol_sets[1])):
            ex = cx + side * eye_offset
            eye = QPainterPath()
            eye.moveTo(ex - eye_w, eye_y)
            eye.cubicTo(
                QPointF(ex - eye_w * 0.48, eye_y - eye_h),
                QPointF(ex + eye_w * 0.48, eye_y - eye_h),
                QPointF(ex + eye_w, eye_y),
            )
            eye.cubicTo(
                QPointF(ex + eye_w * 0.48, eye_y + eye_h),
                QPointF(ex - eye_w * 0.48, eye_y + eye_h),
                QPointF(ex - eye_w, eye_y),
            )
            eye.closeSubpath()

            p.setPen(QPen(QColor(*primary, 48 + int(activity * 55)), 6.0))
            p.setBrush(QBrush(QColor(22, 12, 0, 125)))
            p.drawPath(eye)
            eye_pen = QPen(QColor(*primary, 220 + int(activity * 35)), 1.25 + activity * 1.2)
            eye_pen.setDashPattern([3.2, 1.5, 0.8, 1.5])
            p.setPen(eye_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(eye)

            pupil_x = ex + focus_shift
            pupil_y = eye_y + focus_y
            pupil_scale = 0.43 if mode == "cute" else 0.24 if mode == "evil" else 0.30
            pupil_rx = eye_w * (pupil_scale + activity * 0.06)
            pupil_ry = max(1.3, eye_h * (0.66 if eye_open > 0.3 else 0.12))
            pupil_glow = QRadialGradient(QPointF(pupil_x, pupil_y), max(pupil_rx, 2.0))
            pupil_glow.setColorAt(0.0, QColor(235, 255, 255, 255))
            pupil_glow.setColorAt(0.22, QColor(*accent, 245))
            pupil_glow.setColorAt(0.62, QColor(*accent, 120))
            pupil_glow.setColorAt(1.0, QColor(*accent, 0))
            p.setPen(QPen(QColor(*accent, 225), 1.0))
            p.setBrush(QBrush(pupil_glow))
            p.drawEllipse(QRectF(pupil_x - pupil_rx, pupil_y - pupil_ry, pupil_rx * 2, pupil_ry * 2))
            if eye_open > 0.3:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(255, 251, 214, 250)))
                p.drawEllipse(QPointF(pupil_x, pupil_y), 1.8 + activity * 1.8, 1.8 + activity * 1.8)

            # Code fragments trace the brow and make the eye itself feel assembled.
            font_size = max(6, int(radius * 0.052))
            p.setFont(QFont("Consolas", font_size, QFont.Weight.Bold))
            for index, symbol in enumerate(symbols):
                fraction = index / max(1, len(symbols) - 1)
                sx = ex - eye_w * 0.82 + fraction * eye_w * 1.64
                arch = 1.0 - abs(fraction * 2.0 - 1.0)
                sy = eye_y - eye_h - radius * (0.055 + arch * 0.035)
                alpha = 105 + int(95 * arch) + int(activity * 35)
                p.setPen(QPen(QColor(*primary, min(245, alpha)), 1))
                p.drawText(
                    QRectF(sx - font_size, sy - font_size, font_size * 2, font_size * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    symbol,
                )

            # Focused segmented eyebrow, angled toward the consciousness core.
            brow = QPainterPath()
            brow.moveTo(ex - eye_w * 0.92, eye_y - eye_h * 1.55)
            brow.cubicTo(
                QPointF(ex - eye_w * 0.25, eye_y - eye_h * (1.82 if side < 0 else 1.58)),
                QPointF(ex + eye_w * 0.38, eye_y - eye_h * (1.58 if side < 0 else 1.82)),
                QPointF(ex + eye_w * 0.92, eye_y - eye_h * 1.36),
            )
            if mode == "evil":
                brow.translate(0, side * 0.0)
            brow_pen = QPen(QColor(*primary, 155 + int(activity * 70)), 1.35)
            brow_pen.setDashPattern([5.0, 2.2])
            p.setPen(brow_pen)
            p.drawPath(brow)

        # A sparse bridge connects both eyes to the central reactor like a nose.
        bridge_top = eye_y + eye_h * 0.35
        bridge_bottom = cy + radius * 0.15
        bridge = QPainterPath(QPointF(cx, bridge_top))
        bridge.lineTo(cx - radius * 0.045, cy + radius * 0.02)
        bridge.lineTo(cx + radius * 0.035, bridge_bottom)
        bridge_pen = QPen(QColor(*primary, 105 + int(activity * 60)), 1.0)
        bridge_pen.setDashPattern([2.0, 3.0])
        p.setPen(bridge_pen)
        p.drawPath(bridge)

        # The mouth is a spectrum analyser shaped as lips. Real PCM samples
        # control its opening and every internal voice bar.
        mouth_y = cy + radius * 0.34
        mouth_w = radius * (0.36 if mode == "cute" else 0.44 if mode == "evil" else 0.42)
        idle_open = radius * (0.012 if not thinking else 0.019)
        mouth_open = idle_open + radius * activity * (0.105 if self.speaking else 0.038)
        speech_curve = math.sin(self._energy_phase * 3.2) * radius * activity * 0.012
        mouth = QPainterPath()
        mouth.moveTo(cx - mouth_w, mouth_y)
        mouth.cubicTo(
            QPointF(cx - mouth_w * 0.48, mouth_y - mouth_open - speech_curve),
            QPointF(cx + mouth_w * 0.48, mouth_y - mouth_open + speech_curve),
            QPointF(cx + mouth_w, mouth_y),
        )
        mouth.cubicTo(
            QPointF(cx + mouth_w * 0.48, mouth_y + mouth_open + speech_curve),
            QPointF(cx - mouth_w * 0.48, mouth_y + mouth_open - speech_curve),
            QPointF(cx - mouth_w, mouth_y),
        )
        mouth.closeSubpath()

        p.setPen(QPen(QColor(*primary, 58 + int(activity * 90)), 6.0))
        p.setBrush(QBrush(QColor(8, 6, 2, 195)))
        p.drawPath(mouth)
        mouth_pen = QPen(QColor(*primary, 215 + int(activity * 40)), 1.25 + activity * 1.45)
        mouth_pen.setDashPattern([4.2, 1.6, 0.8, 1.6])
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(mouth)

        p.save()
        p.setClipPath(mouth)
        bar_count = 15
        for index in range(bar_count):
            fraction = index / max(1, bar_count - 1)
            x = cx - mouth_w * 0.84 + fraction * mouth_w * 1.68
            sample = abs(self._waveform[(index * 3) % len(self._waveform)])
            band = self._voice_bands[index % len(self._voice_bands)]
            height = max(1.0, mouth_open * (0.16 + activity * 0.34 + sample * 0.66 + band * 0.28))
            color = QColor(*accent, 205) if index % 5 == 0 else QColor(*primary, 220)
            p.setPen(QPen(color, max(1.0, radius * 0.012)))
            p.drawLine(QPointF(x, mouth_y - height), QPointF(x, mouth_y + height))
        p.restore()

        mouth_symbols = ("0", "1", ":", "+", "V", "+", ":", "1", "0")
        p.setFont(QFont("Consolas", max(6, int(radius * 0.043)), QFont.Weight.Bold))
        for index, symbol in enumerate(mouth_symbols):
            fraction = index / max(1, len(mouth_symbols) - 1)
            x = cx - mouth_w * 0.82 + fraction * mouth_w * 1.64
            y = mouth_y + mouth_open + radius * 0.055
            p.setPen(QPen(QColor(*primary, 105 + int(activity * 95)), 1))
            p.drawText(QRectF(x - 8, y - 6, 16, 12), Qt.AlignmentFlag.AlignCenter, symbol)

        if mode == "evil":
            # Angular fangs made from the same voice spectrum, kept abstract.
            p.setPen(QPen(QColor(*accent, 185 + int(activity * 55)), 1.2))
            for side in (-1, 1):
                fang_x = cx + side * mouth_w * 0.48
                p.drawLine(QPointF(fang_x - side * 5, mouth_y - mouth_open * 0.65), QPointF(fang_x, mouth_y + mouth_open * 0.55))
                p.drawLine(QPointF(fang_x, mouth_y + mouth_open * 0.55), QPointF(fang_x + side * 5, mouth_y - mouth_open * 0.35))
        elif mode == "cute":
            # Two tiny cheek constellations make the expression warmer.
            for side in (-1, 1):
                cheek_x = cx + side * radius * 0.43
                cheek_y = cy + radius * 0.14
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(*primary, 72 + int(activity * 55))))
                for offset in (-5, 0, 5):
                    p.drawEllipse(QPointF(cheek_x + offset, cheek_y + abs(offset) * 0.3), 1.5, 1.5)
        elif mode == "sentinel":
            p.setPen(QPen(QColor(*accent, 190), 1.0))
            p.drawLine(QPointF(cx - mouth_w * 0.75, mouth_y), QPointF(cx + mouth_w * 0.75, mouth_y))

    def _draw_cinematic_face_legacy(self, p: QPainter, cx: float, cy: float, radius: float, activity: float, thinking: bool):
        """Suggest a humanoid presence through constellations, never a literal cartoon face."""
        primary, accent = self._mode_palette()
        mode = self.visual_mode
        blink_tick = self._tick % (103 if mode == "cute" else 151)
        lid = 0.12 if blink_tick < 2 else 0.48 if blink_tick == 2 else 1.0
        eye_y = cy - radius * 0.17
        eye_offset = radius * 0.31
        eye_width = radius * (0.25 if mode == "cute" else 0.23)
        eye_curve = radius * ({"evil": 0.012, "cute": 0.045, "sentinel": 0.006}.get(mode, 0.022)) * lid
        evil_slant = radius * 0.078 if mode == "evil" else radius * 0.018 if mode == "normal" else 0.0
        focus = math.sin(self._energy_phase * (2.3 if thinking else 0.7)) * eye_width * (0.12 if thinking else 0.035)
        rune_font = QFont("Consolas", max(6, int(radius * 0.044)), QFont.Weight.Bold)

        # Each eye is a sparse neural constellation. No enclosed eye shape is drawn.
        for side in (-1, 1):
            ex = cx + side * eye_offset
            anchors = []
            count = 9
            for index in range(count):
                local = -1.0 + 2.0 * index / (count - 1)
                arch = 1.0 - local * local
                slant = local * evil_slant * side
                y = eye_y - eye_curve * arch + slant
                if mode == "sentinel":
                    y += abs(local) * radius * 0.012
                anchors.append(QPointF(ex + local * eye_width, y))

            for index in range(count - 1):
                if index in {2, 6}:
                    continue
                a, b = anchors[index], anchors[index + 1]
                pulse = max(0.0, math.sin(self._energy_phase * 2.2 + index + side))
                alpha = 105 + int(activity * 80 + pulse * 45)
                p.setPen(QPen(QColor(*primary, min(235, alpha)), 1.0 + activity * 0.55))
                p.drawLine(a, b)

            for index, point in enumerate(anchors):
                node_size = 1.0 + (1.2 if index in {0, 4, 8} else 0.0) + activity * 0.45
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(*accent if index in {1, 7} else primary, 120 + int(activity * 90))))
                p.drawEllipse(point, node_size, node_size)

            pupil_x = ex + focus
            pupil_y = eye_y + (evil_slant * 0.08 if mode == "evil" else 0.0)
            pupil_w = eye_width * ({"evil": 0.16, "cute": 0.27, "sentinel": 0.22}.get(mode, 0.21))
            pupil_h = max(1.0, radius * ({"evil": 0.018, "cute": 0.035, "sentinel": 0.012}.get(mode, 0.025)) * lid)
            p.setPen(QPen(QColor(*accent, 62 + int(activity * 70)), 5.0))
            p.drawLine(QPointF(pupil_x - pupil_w, pupil_y), QPointF(pupil_x + pupil_w, pupil_y))
            p.setPen(QPen(QColor(225, 255, 255, 230), 1.15 + activity * 0.7))
            p.drawLine(QPointF(pupil_x - pupil_w, pupil_y), QPointF(pupil_x + pupil_w, pupil_y))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(*accent, 235)))
            p.drawEllipse(QPointF(pupil_x, pupil_y), 1.8 + activity, pupil_h)

            # Small code fragments occupy gaps in the eye constellation.
            p.setFont(rune_font)
            runes = ("01", "//", "<>" if side < 0 else "><")
            for rune_index, anchor_index in enumerate((1, 4, 7)):
                point = anchors[anchor_index]
                p.setPen(QPen(QColor(*primary, 75 + int(activity * 55)), 1))
                p.drawText(
                    QRectF(point.x() - 12, point.y() - radius * 0.09, 24, 11),
                    Qt.AlignmentFlag.AlignCenter,
                    runes[rune_index],
                )

        # Three floating nodes imply a bridge/nose while preserving the central reactor.
        nose_nodes = (
            QPointF(cx, cy - radius * 0.045),
            QPointF(cx - radius * 0.035, cy + radius * 0.095),
            QPointF(cx + radius * 0.042, cy + radius * 0.105),
        )
        nose_pen = QPen(QColor(*primary, 72 + int(activity * 55)), 0.9)
        nose_pen.setDashPattern([1.0, 3.0])
        p.setPen(nose_pen)
        p.drawLine(nose_nodes[0], nose_nodes[1])
        p.drawLine(nose_nodes[1], nose_nodes[2])
        for point in nose_nodes:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(*accent, 115 + int(activity * 60))))
            p.drawEllipse(point, 1.35, 1.35)

        # The mouth is an open spectral slit made of separated data points.
        mouth_y = cy + radius * 0.31
        mouth_width = radius * (0.34 if mode == "cute" else 0.41)
        mouth_count = 13
        mouth_open = radius * activity * (0.048 if self.speaking else 0.014)
        if mode == "evil":
            mouth_open *= 0.78
        upper = []
        lower = []
        for index in range(mouth_count):
            local = -1.0 + 2.0 * index / (mouth_count - 1)
            edge_fade = max(0.0, 1.0 - abs(local) ** 1.7)
            sample = self._waveform[(index * 4) % len(self._waveform)]
            if mode == "evil":
                expression = abs(local) * radius * 0.018 - edge_fade * radius * 0.006
                spectral = sample * radius * activity * 0.018
            elif mode == "cute":
                expression = -edge_fade * radius * 0.018
                spectral = sample * radius * activity * 0.010
            else:
                expression = -edge_fade * radius * 0.004
                spectral = sample * radius * activity * 0.012
            x = cx + local * mouth_width
            separation = mouth_open * edge_fade
            upper.append(QPointF(x, mouth_y + expression + spectral - separation))
            lower.append(QPointF(x, mouth_y + expression - spectral + separation))

        for row_index, row in enumerate((upper, lower)):
            for index in range(len(row) - 1):
                if (index + row_index) % 4 == 1:
                    continue
                band = self._voice_bands[index % len(self._voice_bands)]
                p.setPen(QPen(QColor(*primary, 105 + int(activity * 95 + band * 45)), 0.9 + band * 0.75))
                p.drawLine(row[index], row[index + 1])
            for index, point in enumerate(row):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(*accent if index in {2, 6, 10} else primary, 105 + int(activity * 100))))
                p.drawEllipse(point, 0.8 + activity * 0.65, 0.8 + activity * 0.65)

        # Momentary scan echoes make the face feel decoded from the surrounding field.
        if self._tick % 19 < 3:
            echo_y = eye_y + (self._tick % 3 - 1) * radius * 0.026
            p.setPen(QPen(QColor(*accent, 34 + int(activity * 35)), 0.7))
            p.drawLine(QPointF(cx - radius * 0.62, echo_y), QPointF(cx + radius * 0.62, echo_y))

    def _draw_cinematic_face(self, p: QPainter, cx: float, cy: float, radius: float, activity: float, thinking: bool):
        """Decode a humanoid presence from moving HUD machinery and live PCM."""
        primary, accent = self._mode_palette()
        mode = self.visual_mode
        mode_gain = {"evil": 1.18, "cute": 0.88, "sentinel": 1.08}.get(mode, 1.0)
        scan_phase = self._energy_phase * (2.4 if thinking else 1.15) * mode_gain

        # Eyes are targeting instruments assembled from separated plates and ticks.
        eye_y = cy - radius * 0.18
        eye_offset = radius * 0.30
        eye_w = radius * (0.30 if mode == "cute" else 0.285)
        lid = 0.10 if self._tick % 149 < 2 else 1.0
        focus_x = math.sin(scan_phase * 0.63) * eye_w * (0.13 if thinking else 0.035)
        focus_y = math.cos(scan_phase * 0.47) * radius * (0.018 if thinking else 0.005)

        for side in (-1, 1):
            ex = cx + side * eye_offset
            slant = (-side * radius * 0.055) if mode == "evil" else 0.0
            plate_count = 9
            points = []
            for index in range(plate_count):
                local = -1.0 + index * 2.0 / (plate_count - 1)
                arch = 1.0 - local * local
                y = eye_y - arch * radius * (0.035 if mode == "cute" else 0.020) * lid
                y += local * slant
                points.append(QPointF(ex + local * eye_w, y))

            for index in range(plate_count - 1):
                if index in {1, 5}:
                    continue
                a, b = points[index], points[index + 1]
                pulse = max(0.0, math.sin(scan_phase * 2.1 + index * 0.9 + side))
                p.setPen(QPen(QColor(*primary, 135 + int(85 * pulse + activity * 30)), 1.35 + pulse * 0.8))
                p.drawLine(a, b)
                lower_a = QPointF(a.x(), eye_y * 2 - a.y() + radius * 0.020 * lid)
                lower_b = QPointF(b.x(), eye_y * 2 - b.y() + radius * 0.020 * lid)
                p.setPen(QPen(QColor(*primary, 80 + int(65 * pulse + activity * 35)), 0.85 + pulse * 0.45))
                p.drawLine(lower_a, lower_b)
                # A short perpendicular circuit contact makes each eyelid mechanical.
                dx, dy = b.x() - a.x(), b.y() - a.y()
                length = max(1.0, math.hypot(dx, dy))
                nx, ny = -dy / length, dx / length
                contact = points[index if side < 0 else index + 1]
                p.setPen(QPen(QColor(*accent, 85 + int(activity * 75)), 0.8))
                p.drawLine(contact, QPointF(contact.x() + nx * radius * 0.025, contact.y() + ny * radius * 0.025))

            iris_x, iris_y = ex + focus_x, eye_y + focus_y
            iris_r = radius * ({"evil": 0.046, "cute": 0.062}.get(mode, 0.052)) * lid
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(*accent, 82), 5.5))
            p.drawEllipse(QPointF(iris_x, iris_y), iris_r * 1.35, iris_r * 1.35)
            p.setPen(QPen(QColor(*accent, 225), 1.15 + activity * 0.9))
            p.drawEllipse(QPointF(iris_x, iris_y), iris_r, iris_r)
            p.setPen(QPen(QColor(235, 253, 255, 240), 1.0))
            p.drawLine(QPointF(iris_x - iris_r * 1.7, iris_y), QPointF(iris_x + iris_r * 1.7, iris_y))
            p.drawLine(QPointF(iris_x, iris_y - iris_r * 1.7), QPointF(iris_x, iris_y + iris_r * 1.7))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(245, 255, 255, 245)))
            p.drawEllipse(QPointF(iris_x, iris_y), 1.6 + activity * 1.5, 1.6 + activity * 1.5)

            # Radial acquisition ticks complete the eye without enclosing it.
            p.setPen(QPen(QColor(*primary, 120 + int(activity * 70)), 0.8))
            for tick in range(8):
                ang = tick * math.pi / 4 + side * scan_phase * 0.08
                inner = iris_r * 1.65
                outer = iris_r * (2.15 if tick % 2 == 0 else 1.95)
                p.drawLine(
                    QPointF(iris_x + math.cos(ang) * inner, iris_y + math.sin(ang) * inner),
                    QPointF(iris_x + math.cos(ang) * outer, iris_y + math.sin(ang) * outer),
                )

            p.setFont(QFont("Consolas", max(5, int(radius * 0.038)), QFont.Weight.Bold))
            p.setPen(QPen(QColor(*primary, 115), 1))
            label = "TRK" if side < 0 else f"{int(activity * 99):02d}"
            p.drawText(QRectF(ex - eye_w, eye_y + radius * 0.055, eye_w * 2, 12), Qt.AlignmentFlag.AlignCenter, label)

        # Three circuit points hint at the center of a face and feed the speech array.
        bridge = [
            QPointF(cx, cy - radius * 0.035),
            QPointF(cx - radius * 0.030, cy + radius * 0.085),
            QPointF(cx + radius * 0.030, cy + radius * 0.085),
        ]
        p.setPen(QPen(QColor(*accent, 90 + int(activity * 55)), 0.8, Qt.PenStyle.DashLine))
        p.drawLine(bridge[0], bridge[1]); p.drawLine(bridge[0], bridge[2])
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(*accent, 190)))
        for node in bridge:
            p.drawEllipse(node, 1.4, 1.4)

        # The mouth is a real voice aperture. Fast envelope attack makes syllables visible.
        mouth_y = cy + radius * 0.31
        mouth_w = radius * (0.35 if mode == "cute" else 0.43)
        mouth_energy = max(self._mouth_level, 0.055 if self.speaking else 0.0)
        phoneme = mouth_energy * (0.78 + 0.22 * abs(math.sin(scan_phase * 4.7)))
        mouth_gap = min(radius * 0.12, radius * (0.007 + phoneme * 0.135 + self._mouth_impulse * 0.024))
        if mode == "evil":
            mouth_gap *= 0.92
        segment_count = 17
        upper, lower = [], []
        for index in range(segment_count):
            local = -1.0 + index * 2.0 / (segment_count - 1)
            center_gain = max(0.0, 1.0 - abs(local) ** 1.6)
            sample = self._waveform[(index * 3) % len(self._waveform)]
            band = self._voice_bands[index % len(self._voice_bands)]
            spectral = (sample * 0.22 + band * 0.18) * radius * mouth_energy
            spectral = max(-mouth_gap * 0.38, min(mouth_gap * 0.38, spectral))
            expression = 0.0
            if mode == "evil":
                expression = abs(local) * radius * 0.025 - radius * 0.012
            elif mode == "cute":
                expression = -center_gain * radius * 0.018
            x = cx + local * mouth_w
            gap = mouth_gap * center_gain
            upper.append(QPointF(x, mouth_y + expression - gap - spectral))
            lower.append(QPointF(x, mouth_y + expression + gap + spectral))

        for index in range(segment_count - 1):
            if index % 5 == 2:
                continue
            band = self._voice_bands[index % len(self._voice_bands)]
            glow_alpha = 115 + int(mouth_energy * 120 + band * 20)
            p.setPen(QPen(QColor(*primary, min(245, glow_alpha)), 1.0 + mouth_energy * 1.6))
            p.drawLine(upper[index], upper[index + 1])
            p.drawLine(lower[index], lower[index + 1])

        # Short spectrum contacts add articulation without turning the mouth into a cage.
        for index in range(1, segment_count - 1):
            if index not in {3, 6, 8, 10, 13}:
                continue
            band = self._voice_bands[index % len(self._voice_bands)]
            sample = abs(self._waveform[(index * 3) % len(self._waveform)])
            strength = max(mouth_energy, band * 0.9, sample * 0.8)
            top, bottom = upper[index], lower[index]
            mid = (top.y() + bottom.y()) * 0.5
            half = min((bottom.y() - top.y()) * 0.34, radius * 0.032 + strength * radius * 0.018)
            alpha = 70 + int(strength * 175)
            p.setPen(QPen(QColor(*accent, min(245, alpha)), 0.8 + strength * 1.5))
            p.drawLine(QPointF(top.x(), mid - half), QPointF(bottom.x(), mid + half))

        p.setPen(QPen(QColor(235, 253, 255, 130 + int(mouth_energy * 120)), 0.75))
        center_gap = mouth_gap * 0.48
        p.drawLine(QPointF(cx - mouth_w * 0.72, mouth_y), QPointF(cx - center_gap, mouth_y))
        p.drawLine(QPointF(cx + center_gap, mouth_y), QPointF(cx + mouth_w * 0.72, mouth_y))

        p.setFont(QFont("Consolas", max(5, int(radius * 0.035)), QFont.Weight.Bold))
        p.setPen(QPen(QColor(*primary, 90 + int(mouth_energy * 90)), 1))
        voice_text = f"VOICE {int(mouth_energy * 100):02d}%"
        p.drawText(QRectF(cx - mouth_w, mouth_y + mouth_gap + radius * 0.035, mouth_w * 2, 11), Qt.AlignmentFlag.AlignCenter, voice_text)

    def _draw_armored_face(self, p: QPainter, cx: float, cy: float, radius: float, activity: float, thinking: bool):
        """Render a voice-reactive holographic armored mask from independent HUD plates."""
        primary, accent = self._mode_palette()
        mode = self.visual_mode
        mouth_energy = max(self._mouth_level, 0.045 if self.speaking else 0.0)
        jaw_drop = radius * mouth_energy * 0.018
        pulse = 0.5 + 0.5 * math.sin(self._energy_phase * (3.2 if thinking else 1.6))

        # Translucent armored silhouette. The broken border keeps it holographic.
        mask = QPainterPath()
        mask.moveTo(cx, cy - radius * 0.63)
        mask.lineTo(cx - radius * 0.29, cy - radius * 0.57)
        mask.lineTo(cx - radius * 0.46, cy - radius * 0.37)
        mask.lineTo(cx - radius * 0.51, cy - radius * 0.03)
        mask.lineTo(cx - radius * 0.43, cy + radius * 0.29)
        mask.lineTo(cx - radius * 0.24, cy + radius * 0.50 + jaw_drop)
        mask.lineTo(cx, cy + radius * 0.59 + jaw_drop)
        mask.lineTo(cx + radius * 0.24, cy + radius * 0.50 + jaw_drop)
        mask.lineTo(cx + radius * 0.43, cy + radius * 0.29)
        mask.lineTo(cx + radius * 0.51, cy - radius * 0.03)
        mask.lineTo(cx + radius * 0.46, cy - radius * 0.37)
        mask.lineTo(cx + radius * 0.29, cy - radius * 0.57)
        mask.closeSubpath()

        face_glass = QLinearGradient(QPointF(cx - radius * 0.25, cy - radius * 0.62), QPointF(cx + radius * 0.22, cy + radius * 0.60))
        face_glass.setColorAt(0.0, QColor(27, 54, 66, 252))
        face_glass.setColorAt(0.22, QColor(5, 25, 36, 250))
        face_glass.setColorAt(0.55, QColor(1, 10, 18, 252))
        face_glass.setColorAt(0.82, QColor(10, 29, 39, 250))
        face_glass.setColorAt(1.0, QColor(36, 64, 72, 248))
        p.setBrush(QBrush(face_glass))
        edge_pen = QPen(QColor(*primary, 185 + int(activity * 55)), 2.0 + activity * 1.15)
        edge_pen.setDashPattern([8.0, 2.2, 1.2, 2.2])
        p.setPen(edge_pen)
        p.drawPath(mask)

        # Solid temple blades widen the helmet and create a battle-ready silhouette.
        for side in (-1, 1):
            temple = QPainterPath()
            temple.moveTo(cx + side * radius * 0.29, cy - radius * 0.55)
            temple.lineTo(cx + side * radius * 0.52, cy - radius * 0.37)
            temple.lineTo(cx + side * radius * 0.56, cy + radius * 0.08)
            temple.lineTo(cx + side * radius * 0.43, cy + radius * 0.31)
            temple.lineTo(cx + side * radius * 0.36, cy - radius * 0.16)
            temple.closeSubpath()
            temple_metal = QLinearGradient(
                QPointF(cx + side * radius * 0.56, cy - radius * 0.40),
                QPointF(cx + side * radius * 0.34, cy + radius * 0.30),
            )
            temple_metal.setColorAt(0.0, QColor(55, 88, 98, 248))
            temple_metal.setColorAt(0.42, QColor(8, 29, 40, 252))
            temple_metal.setColorAt(1.0, QColor(28, 58, 68, 248))
            p.setPen(QPen(QColor(*primary, 150 + int(activity * 75)), 1.45))
            p.setBrush(QBrush(temple_metal))
            p.drawPath(temple)

        # Crown and forehead plates form the recognizable armored brow.
        forehead = QPainterPath()
        forehead.moveTo(cx, cy - radius * 0.59)
        forehead.lineTo(cx - radius * 0.235, cy - radius * 0.51)
        forehead.lineTo(cx - radius * 0.31, cy - radius * 0.25)
        forehead.lineTo(cx - radius * 0.105, cy - radius * 0.31)
        forehead.lineTo(cx, cy - radius * 0.22)
        forehead.lineTo(cx + radius * 0.105, cy - radius * 0.31)
        forehead.lineTo(cx + radius * 0.31, cy - radius * 0.25)
        forehead.lineTo(cx + radius * 0.235, cy - radius * 0.51)
        forehead.closeSubpath()
        forehead_metal = QLinearGradient(QPointF(cx, cy - radius * 0.60), QPointF(cx, cy - radius * 0.20))
        forehead_metal.setColorAt(0.0, QColor(82, 112, 120, 245))
        forehead_metal.setColorAt(0.18, QColor(18, 45, 57, 248))
        forehead_metal.setColorAt(0.62, QColor(3, 17, 27, 252))
        forehead_metal.setColorAt(1.0, QColor(36, 66, 76, 246))
        p.setPen(QPen(QColor(*primary, 175 + int(pulse * 65)), 1.6))
        p.setBrush(QBrush(forehead_metal))
        p.drawPath(forehead)
        p.setPen(QPen(QColor(*accent, 125 + int(activity * 65)), 0.9))
        p.drawLine(QPointF(cx, cy - radius * 0.59), QPointF(cx, cy - radius * 0.24))

        # Angular glowing eye slits define the helmet expression.
        blink = 0.07 if self._tick % 151 < 2 else 1.0
        look = math.sin(self._energy_phase * (2.2 if thinking else 0.58)) * radius * (0.022 if thinking else 0.006)
        for side in (-1, 1):
            inner_x = cx + side * radius * 0.070
            outer_x = cx + side * radius * 0.430
            outer_top = cy - radius * (0.265 if mode == "evil" else 0.245)
            inner_top = cy - radius * (0.145 if mode == "evil" else 0.165)
            eye_mid = cy - radius * 0.145
            eye_h = radius * ({"cute": 0.075, "evil": 0.036}.get(mode, 0.046)) * blink
            eye = QPainterPath()
            eye.moveTo(inner_x + look, inner_top)
            eye.lineTo(outer_x + look, outer_top)
            eye.lineTo(outer_x - side * radius * 0.025 + look, eye_mid + eye_h)
            eye.lineTo(inner_x + side * radius * 0.018 + look, eye_mid + eye_h * 0.72)
            eye.closeSubpath()

            # Layered eye reactor bloom: stronger and voice-reactive while preserving the sharp armor slit.
            eye_glow_x = (inner_x + outer_x) * 0.5 + look
            eye_glow_y = (inner_top + outer_top + eye_mid * 2) * 0.25
            speech_glow = max(activity, mouth_energy) if self.speaking else activity * 0.35
            eye_aura = QRadialGradient(QPointF(eye_glow_x, eye_glow_y), radius * (0.19 + speech_glow * 0.055))
            eye_aura.setColorAt(0.0, QColor(245, 255, 255, 190 + int(speech_glow * 60)))
            eye_aura.setColorAt(0.22, QColor(*accent, 125 + int(speech_glow * 110)))
            eye_aura.setColorAt(0.58, QColor(*primary, 38 + int(speech_glow * 65)))
            eye_aura.setColorAt(1.0, QColor(*primary, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(eye_aura))
            p.drawEllipse(QPointF(eye_glow_x, eye_glow_y), radius * 0.245, radius * 0.095)

            p.setPen(QPen(QColor(*accent, 75 + int(speech_glow * 95)), 8.0 + speech_glow * 3.0))
            p.setBrush(QBrush(QColor(*accent, 65 + int(speech_glow * 90))))
            p.drawPath(eye)
            p.setPen(QPen(QColor(*accent, 125 + int(speech_glow * 100)), 4.0 + speech_glow * 2.5))
            p.drawPath(eye)
            p.setPen(QPen(QColor(225, 252, 255, 235), 1.15 + activity * 1.0))
            p.setBrush(QBrush(QColor(*accent, 155 + int(activity * 85))))
            p.drawPath(eye)

            # Targeting contacts inside each luminous aperture.
            eye_center_x = (inner_x + outer_x) * 0.5 + look
            eye_center_y = (inner_top + outer_top + eye_mid * 2) * 0.25
            p.setPen(QPen(QColor(250, 255, 255, 230), 0.8))
            p.drawLine(QPointF(eye_center_x - radius * 0.025, eye_center_y), QPointF(eye_center_x + radius * 0.025, eye_center_y))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(250, 255, 255, 245)))
            p.drawEllipse(QPointF(eye_center_x, eye_center_y), 1.45 + activity, 1.45 + activity)

        # Temple, cheek and nose armor are separate floating plates.
        for side in (-1, 1):
            cheek = QPainterPath()
            cheek.moveTo(cx + side * radius * 0.44, cy - radius * 0.15)
            cheek.lineTo(cx + side * radius * 0.36, cy + radius * 0.20)
            cheek.lineTo(cx + side * radius * 0.20, cy + radius * 0.34)
            cheek.lineTo(cx + side * radius * 0.13, cy + radius * 0.07)
            cheek.closeSubpath()
            cheek_metal = QLinearGradient(
                QPointF(cx + side * radius * 0.46, cy - radius * 0.12),
                QPointF(cx + side * radius * 0.14, cy + radius * 0.35),
            )
            cheek_metal.setColorAt(0.0, QColor(39, 73, 83, 244))
            cheek_metal.setColorAt(0.45, QColor(5, 21, 31, 250))
            cheek_metal.setColorAt(1.0, QColor(24, 51, 61, 246))
            p.setPen(QPen(QColor(*primary, 145 + int(activity * 75)), 1.35))
            p.setBrush(QBrush(cheek_metal))
            p.drawPath(cheek)

            p.setPen(QPen(QColor(*accent, 82 + int(activity * 65)), 0.8))
            for vent in range(3):
                y = cy + radius * (0.12 + vent * 0.055)
                p.drawLine(
                    QPointF(cx + side * radius * (0.27 + vent * 0.012), y),
                    QPointF(cx + side * radius * (0.36 + vent * 0.010), y - radius * 0.025),
                )

        nose = QPainterPath()
        nose.moveTo(cx, cy - radius * 0.15)
        nose.lineTo(cx - radius * 0.085, cy + radius * 0.105)
        nose.lineTo(cx, cy + radius * 0.155)
        nose.lineTo(cx + radius * 0.085, cy + radius * 0.105)
        nose.closeSubpath()
        p.setPen(QPen(QColor(*primary, 105), 0.9))
        p.setBrush(QBrush(QColor(0, 5, 11, 95)))
        p.drawPath(nose)

        # Upper mouth plate stays fixed; the lower jaw drops with the speech envelope.
        mouth_y = cy + radius * 0.285
        mouth_w = radius * 0.285
        phoneme = mouth_energy * (0.78 + 0.22 * abs(math.sin(self._energy_phase * 5.4)))
        gap = radius * (0.005 + phoneme * 0.034)
        if mode == "evil":
            gap *= 0.82
        upper = QPainterPath()
        upper.moveTo(cx - mouth_w, mouth_y)
        upper.lineTo(cx - mouth_w * 0.58, mouth_y - radius * 0.018)
        upper.lineTo(cx + mouth_w * 0.58, mouth_y - radius * 0.018)
        upper.lineTo(cx + mouth_w, mouth_y)
        lower = QPainterPath()
        lower.moveTo(cx - mouth_w, mouth_y + gap * 0.45)
        lower.lineTo(cx - mouth_w * 0.58, mouth_y + gap + jaw_drop)
        lower.lineTo(cx + mouth_w * 0.58, mouth_y + gap + jaw_drop)
        lower.lineTo(cx + mouth_w, mouth_y + gap * 0.45)

        aperture = QPainterPath()
        aperture.moveTo(cx - mouth_w, mouth_y)
        aperture.lineTo(cx - mouth_w * 0.58, mouth_y - radius * 0.018)
        aperture.lineTo(cx + mouth_w * 0.58, mouth_y - radius * 0.018)
        aperture.lineTo(cx + mouth_w, mouth_y)
        aperture.lineTo(cx + mouth_w * 0.58, mouth_y + gap + jaw_drop)
        aperture.lineTo(cx - mouth_w * 0.58, mouth_y + gap + jaw_drop)
        aperture.closeSubpath()
        # Voice reactor bloom behind the mouth aperture. It expands with the real PCM envelope.
        mouth_bloom = max(mouth_energy, 0.10 if self.speaking else 0.0)
        mouth_aura = QRadialGradient(QPointF(cx, mouth_y + (gap + jaw_drop) * 0.45), mouth_w * (1.25 + mouth_bloom * 0.35))
        mouth_aura.setColorAt(0.0, QColor(245, 255, 255, 150 + int(mouth_bloom * 95)))
        mouth_aura.setColorAt(0.24, QColor(*accent, 95 + int(mouth_bloom * 135)))
        mouth_aura.setColorAt(0.62, QColor(*primary, 22 + int(mouth_bloom * 55)))
        mouth_aura.setColorAt(1.0, QColor(*primary, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(mouth_aura))
        p.drawEllipse(
            QPointF(cx, mouth_y + (gap + jaw_drop) * 0.45),
            mouth_w * (1.15 + mouth_bloom * 0.25),
            radius * (0.035 + mouth_bloom * 0.052),
        )

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 2, 6, 225)))
        p.drawPath(aperture)
        mouth_pen = QPen(QColor(225, 253, 255, 175 + int(mouth_energy * 80)), 1.3 + mouth_energy * 2.2)
        p.setPen(mouth_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(upper); p.drawPath(lower)

        # A continuous spectral trace articulates speech without resembling teeth.
        voice_line = QPainterPath()
        sample_count = 11
        center_y = mouth_y + (gap + jaw_drop) * 0.48
        for index in range(sample_count):
            local = -1.0 + index * 2.0 / (sample_count - 1)
            sample = self._waveform[(index * 5) % len(self._waveform)]
            y = center_y - sample * min(gap * 0.34, radius * 0.018) * mouth_energy
            point = QPointF(cx + local * mouth_w * 0.68, y)
            if index == 0:
                voice_line.moveTo(point)
            else:
                voice_line.lineTo(point)
        p.setPen(QPen(QColor(235, 253, 255, 105 + int(mouth_energy * 145)), 0.8 + mouth_energy * 1.2))
        p.drawPath(voice_line)

        # Segmented jaw and chin shift down subtly as the AI speaks.
        p.setPen(QPen(QColor(*primary, 118 + int(activity * 52)), 1.0))
        p.drawLine(QPointF(cx - radius * 0.34, cy + radius * 0.30), QPointF(cx - radius * 0.21, cy + radius * 0.47 + jaw_drop))
        p.drawLine(QPointF(cx + radius * 0.34, cy + radius * 0.30), QPointF(cx + radius * 0.21, cy + radius * 0.47 + jaw_drop))
        p.drawLine(QPointF(cx - radius * 0.21, cy + radius * 0.47 + jaw_drop), QPointF(cx, cy + radius * 0.55 + jaw_drop))
        p.drawLine(QPointF(cx + radius * 0.21, cy + radius * 0.47 + jaw_drop), QPointF(cx, cy + radius * 0.55 + jaw_drop))


    def _draw_consciousness(self, p: QPainter, cx: float, cy: float, fw: float):
        """Render the voice-reactive holographic consciousness from live geometry."""
        radius = fw * 0.305 * self._scale
        activity = max(self._voice_level, 0.16 if self.speaking else 0.0)
        thinking = self.state in {"THINKING", "PROCESSING"}
        state_gain = 1.28 if thinking else 1.0
        breath = (math.sin(self._energy_phase) + 1.0) * 0.5
        primary, accent = self._mode_palette()

        # Volumetric aura follows the active identity palette.
        aura_r = radius * (1.42 + activity * 0.20 + breath * 0.05)
        aura = QRadialGradient(QPointF(cx, cy), aura_r)
        aura.setColorAt(0.0, QColor(235, 253, 255, 165 + int(activity * 70)))
        aura.setColorAt(0.16, QColor(*primary, 125 + int(activity * 80)))
        aura.setColorAt(0.48, QColor(*primary, 42 + int(activity * 55)))
        aura.setColorAt(0.78, QColor(*accent, 14 + int(activity * 20)))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(aura))
        p.drawEllipse(QRectF(cx - aura_r, cy - aura_r, aura_r * 2, aura_r * 2))

        # Dense, counter-rotating HUD machinery surrounds the consciousness.
        # Broken sectors and radial contacts echo a projected Iron-Man-style interface.
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        ring_specs = (
            (1.34, 48, 4.4, 0.33, 58),
            (1.25, 32, 6.8, -0.52, 94),
            (1.15, 24, 9.5, 0.82, 128),
            (1.04, 18, 13.0, -1.08, 158),
            (0.88, 12, 19.5, 1.34, 120),
        )
        for ring_index, (scale, segments, span, speed, base_alpha) in enumerate(ring_specs):
            rr = radius * scale
            rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
            offset = self._avatar_angle * speed + ring_index * 17.0
            for segment in range(segments):
                if (segment + ring_index * 2) % (7 if ring_index < 2 else 9) == 0:
                    continue
                pulse = max(0.0, math.sin(scan_phase := self._energy_phase * 2.0 + segment * 0.41))
                alpha = min(245, int(base_alpha + activity * 52 + pulse * 28))
                color = QColor(*accent, alpha) if segment % 11 == 0 else QColor(*primary, alpha)
                width = (2.4 if ring_index == 2 and segment % 4 == 0 else 0.85 + ring_index * 0.14)
                p.setPen(QPen(color, width))
                start = offset + segment * (360.0 / segments)
                p.drawArc(rect, int(start * 16), int(span * 16))

        # Mechanical blocks sit on the middle disk and rotate as one assembly.
        p.translate(cx, cy)
        p.rotate(-self._avatar_angle * 0.24)
        block_r = radius * 1.205
        for index in range(24):
            if index % 6 == 4:
                continue
            angle = index * 15.0
            p.save()
            p.rotate(angle)
            width = radius * (0.105 if index % 3 == 0 else 0.065)
            height = max(2.0, radius * (0.024 if index % 2 else 0.038))
            p.setPen(QPen(QColor(*primary, 90 + int(activity * 65)), 0.7))
            p.setBrush(QBrush(QColor(*primary, 20 + int(activity * 18))))
            p.drawRoundedRect(QRectF(block_r - width * 0.5, -height * 0.5, width, height), 1.2, 1.2)
            p.restore()

        # Long circuit spokes flash from speech bands toward the inner reactor.
        for index in range(16):
            angle = index * math.pi / 8 + math.radians(self._avatar_angle * 0.18)
            band = self._voice_bands[index % len(self._voice_bands)]
            inner = radius * (0.91 - band * 0.06)
            outer = radius * (1.10 + band * 0.09)
            p.setPen(QPen(QColor(*accent if index % 4 == 0 else primary, 54 + int(band * 145 + activity * 35)), 0.75 + band))
            p.drawLine(
                QPointF(math.cos(angle) * inner, math.sin(angle) * inner),
                QPointF(math.cos(angle) * outer, math.sin(angle) * outer),
            )
        p.restore()

        # Dark glass underlay gives the face and telemetry enough contrast.
        glass_r = radius * 0.80
        glass = QRadialGradient(QPointF(cx, cy), glass_r)
        glass.setColorAt(0.0, QColor(0, 4, 9, 205))
        glass.setColorAt(0.70, QColor(0, 8, 15, 152))
        glass.setColorAt(1.0, QColor(*primary, 8))
        p.setPen(QPen(QColor(*primary, 55), 0.8))
        p.setBrush(QBrush(glass))
        p.drawEllipse(QRectF(cx - glass_r, cy - glass_r, glass_r * 2, glass_r * 2))

        points = self._project_consciousness(cx, cy, radius)
        old_points = self._project_consciousness(cx, cy, radius, self._mesh_y - (2.8 + activity * 4.0))

        # Neural links form the body instead of a bitmap shell.
        for edge_index, (a, b) in enumerate(self._sphere_edges):
            axp, ayp, az, _ = points[a]
            bxp, byp, bz, _ = points[b]
            depth = max(0.0, min(1.0, ((az + bz) * 0.25) + 0.5))
            band = self._voice_bands[edge_index % len(self._voice_bands)]
            pulse = max(0.0, math.sin(self._energy_phase * 2.7 + edge_index * 0.37))
            alpha = int((24 + depth * 92 + band * 90 + pulse * activity * 80) * state_gain)
            alpha = max(0, min(230, alpha))
            if edge_index % 9 == 0:
                color = QColor(*accent, max(18, alpha // 2))
            else:
                color = QColor(*primary, alpha)
            p.setPen(QPen(color, 0.7 + band * 1.5 + activity * 0.35))
            p.drawLine(QPointF(axp, ayp), QPointF(bxp, byp))

        # Moving sparks leave short 3D trails, making rotation readable.
        for index, ((x, y, z, phase), (old_x, old_y, _, _)) in enumerate(zip(points, old_points)):
            depth = max(0.0, min(1.0, (z + 1.0) * 0.5))
            wave = abs(self._waveform[index % len(self._waveform)])
            pulse = max(0.0, math.sin(phase + self._energy_phase * (3.1 if thinking else 1.6)))
            alpha = int(55 + depth * 170 + pulse * 40 * state_gain)
            size = 0.8 + depth * 1.7 + wave * 3.2 + activity * 0.8
            p.setPen(QPen(QColor(*primary, max(20, alpha // 3)), max(0.6, size * 0.52)))
            p.drawLine(QPointF(old_x, old_y), QPointF(x, y))
            node_color = QColor(255, 245, 218, min(255, alpha)) if z > 0 else QColor(*primary, min(190, alpha))
            if index % 17 == 0:
                node_color = QColor(*accent, min(235, alpha))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(node_color))
            p.drawEllipse(QPointF(x, y), size, size)

        # Voice waveform wraps around the sphere as a living corona.
        wave_path = QPainterPath()
        wave_count = 96
        for index in range(wave_count + 1):
            angle = (index / wave_count) * math.pi * 2 - math.pi / 2
            sample = abs(self._waveform[index % len(self._waveform)])
            synthetic = (math.sin(angle * 7 + self._energy_phase * 3) + 1.0) * 0.5
            spike = (sample * activity + synthetic * (0.025 if self.speaking else 0.006)) * radius * 0.28
            crown_r = radius * 1.04 + spike
            x = cx + math.cos(angle) * crown_r
            y = cy + math.sin(angle) * crown_r
            if index == 0:
                wave_path.moveTo(x, y)
            else:
                wave_path.lineTo(x, y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(*primary, 45 + int(activity * 95)), 4.5))
        p.drawPath(wave_path)
        p.setPen(QPen(QColor(*primary, 145 + int(activity * 100)), 1.1 + activity * 1.7))
        p.drawPath(wave_path)

        # Counter-rotating energy orbits with bright carriers.
        orbit_specs = (
            (1.18, 0.34, 18.0, 1.0, QColor(*primary, 205)),
            (1.10, 0.48, -42.0, -0.72, QColor(*accent, 175)),
            (0.90, 0.29, 71.0, 1.45, QColor(*primary, 190)),
        )
        for orbit_index, (rx_mul, ry_mul, rotation, speed, color) in enumerate(orbit_specs):
            p.save()
            p.translate(cx, cy)
            p.rotate(rotation + math.sin(self._energy_phase + orbit_index) * 6.0)
            rx, ry = radius * rx_mul, radius * ry_mul
            rect = QRectF(-rx, -ry, rx * 2, ry * 2)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, 1.0 + activity * 1.1))
            start = (self._avatar_angle * speed + orbit_index * 110) % 360
            p.drawArc(rect, int(start * 16), int((205 + activity * 85) * 16))
            carrier_angle = math.radians(start + 205 + activity * 85)
            carrier = QPointF(math.cos(carrier_angle) * rx, -math.sin(carrier_angle) * ry)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            carrier_size = 2.5 + activity * 4.2
            p.drawEllipse(carrier, carrier_size, carrier_size)
            p.restore()

        # Scanning planes cut through the volume.
        p.save()
        clip = QPainterPath()
        clip.addEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        p.setClipPath(clip)
        scan_offset = (self._tick * (3 if thinking else 1.25)) % max(1.0, radius * 2)
        for line_index in range(7):
            y = cy - radius + ((scan_offset + line_index * radius * 0.34) % (radius * 2))
            alpha = 25 + int(activity * 45)
            p.setPen(QPen(QColor(*primary, alpha), 0.7))
            p.drawLine(QPointF(cx - radius, y), QPointF(cx + radius, y))
        p.restore()

        # A smoked holographic visor quiets the neural mesh where the face resolves.
        visor = QRadialGradient(QPointF(cx, cy + radius * 0.02), radius * 0.72)
        visor.setColorAt(0.0, QColor(0, 3, 8, 218))
        visor.setColorAt(0.64, QColor(0, 5, 11, 182))
        visor.setColorAt(1.0, QColor(0, 8, 15, 12))
        p.setPen(QPen(QColor(*primary, 38 + int(activity * 22)), 0.7))
        p.setBrush(QBrush(visor))
        p.drawEllipse(QRectF(cx - radius * 0.69, cy - radius * 0.53, radius * 1.38, radius * 1.18))

        # Sharp helmet crest replaces the generic forehead orb.
        crest_y = cy - radius * 0.455
        crest = QPainterPath()
        crest.moveTo(cx, crest_y - radius * 0.095)
        crest.lineTo(cx - radius * 0.050, crest_y + radius * 0.018)
        crest.lineTo(cx, crest_y + radius * 0.075)
        crest.lineTo(cx + radius * 0.050, crest_y + radius * 0.018)
        crest.closeSubpath()
        crest_glow = QLinearGradient(QPointF(cx, crest_y - radius * 0.10), QPointF(cx, crest_y + radius * 0.08))
        crest_glow.setColorAt(0.0, QColor(248, 255, 255, 245))
        crest_glow.setColorAt(0.38, QColor(*accent, 220))
        crest_glow.setColorAt(1.0, QColor(*primary, 35))
        p.setPen(QPen(QColor(*accent, 210), 1.1))
        p.setBrush(QBrush(crest_glow))
        p.drawPath(crest)
        self._draw_armored_face(p, cx, cy, radius, activity, thinking)

    def _step(self):
        if getattr(self, "_reactor", None) is not None:
            self._reactor.set_status(state=self.state, speaking=self.speaking,
                                     muted=self.muted, mode=self.visual_mode)
            return
        if self._glow_only:
            self._voice_level += (self._voice_target - self._voice_level) * 0.34
            self._voice_target *= 0.82
            self._energy_phase = (self._energy_phase + 0.09 + self._voice_level * 0.24) % (math.pi * 2)
            self.update()
            return
        self._tick += 1
        self._voice_level += (self._voice_target - self._voice_level) * 0.34
        self._voice_target *= 0.82
        mouth_speed = 0.72 if self._mouth_target > self._mouth_level else 0.31
        self._mouth_level += (self._mouth_target - self._mouth_level) * mouth_speed
        self._mouth_target *= 0.68 if self.speaking else 0.48
        self._mouth_impulse *= 0.76
        for index in range(len(self._waveform)):
            target = self._waveform_target[index]
            self._waveform[index] += (target - self._waveform[index]) * 0.42
            self._waveform_target[index] *= 0.78
        self._energy_phase = (self._energy_phase + 0.075 + self._voice_level * 0.22) % (math.pi * 2)
        turn_speed = 0.18
        if self.state in {"THINKING", "PROCESSING"}:
            turn_speed = 1.35
        elif self.speaking:
            turn_speed = 0.65 + self._voice_level * 1.8
        self._avatar_angle = (self._avatar_angle + turn_speed) % 360
        mesh_speed = 0.22
        if self.state in {"THINKING", "PROCESSING"}:
            mesh_speed = 1.05
        elif self.speaking:
            mesh_speed = 0.48 + self._voice_level * 1.35
        mesh_speed *= {"evil": 1.18, "cute": 0.78, "sentinel": 1.38}.get(self.visual_mode, 1.0)
        self._mesh_y = (self._mesh_y + mesh_speed) % 360
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = 1.035 + self._voice_level * 0.13
                self._tgt_halo  = 120 + self._voice_level * 95
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            elif self.state in {"THINKING", "PROCESSING"}:
                self._tgt_scale = 1.025 + 0.012 * math.sin(self._energy_phase)
                self._tgt_halo = 105 + 20 * math.sin(self._energy_phase)
            else:
                self._tgt_scale = 1.008 + self._voice_level * 0.045
                self._tgt_halo  = random.uniform(62, 82) + self._voice_level * 55
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        particle_chance = 0.035
        if self.state in {"THINKING", "PROCESSING"}:
            particle_chance = 0.16
        elif self.speaking:
            particle_chance = 0.22 + self._voice_level * 0.42
        if random.random() < particle_chance:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * random.uniform(0.20, 0.31)
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.5, 1.6) * (1 + self._voice_level),
                math.sin(ang) * random.uniform(0.5, 1.6) * (1 + self._voice_level) - 0.25, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def _paint_speaking_glow(self, p: QPainter):
        """Small Qt-only voice indicator; no 3D scene or browser process."""
        width, height = self.width(), self.height()
        cx, cy = width / 2, height / 2
        unit = min(width, height)
        activity = min(1.0, self._voice_level * 2.8 + (0.16 if self.speaking else 0.0))
        pulse = 1.0 + (0.035 + activity * 0.10) * math.sin(self._energy_phase)
        radius = unit * 0.17 * pulse
        if self.muted:
            core, edge = QColor(130, 150, 165), QColor(90, 115, 135)
        elif self.speaking:
            core, edge = QColor(235, 251, 255), QColor(18, 192, 255)
        elif self.state in {"THINKING", "PROCESSING"}:
            core, edge = QColor(178, 239, 255), QColor(34, 133, 245)
        else:
            core, edge = QColor(145, 219, 243), QColor(20, 122, 173)

        bloom = QRadialGradient(QPointF(cx, cy), radius * 2.6)
        bloom.setColorAt(0.0, QColor(edge.red(), edge.green(), edge.blue(), 55 + int(activity * 75)))
        bloom.setColorAt(0.35, QColor(edge.red(), edge.green(), edge.blue(), 25 + int(activity * 45)))
        bloom.setColorAt(1.0, QColor(edge.red(), edge.green(), edge.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bloom))
        p.drawEllipse(QRectF(cx - radius * 2.6, cy - radius * 2.6, radius * 5.2, radius * 5.2))

        orb = QRadialGradient(QPointF(cx - radius * 0.25, cy - radius * 0.28), radius * 1.35)
        orb.setColorAt(0.0, core)
        orb.setColorAt(0.35, QColor(edge.red(), edge.green(), edge.blue(), 215))
        orb.setColorAt(0.78, QColor(edge.red() // 3, edge.green() // 3, edge.blue() // 3, 190))
        orb.setColorAt(1.0, QColor(2, 13, 22, 255))
        p.setPen(QPen(QColor(edge.red(), edge.green(), edge.blue(), 130), 1.5))
        p.setBrush(QBrush(orb))
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        ring_radius = radius * (1.25 + activity * 0.16)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(edge.red(), edge.green(), edge.blue(), 55 + int(activity * 100)), 1.4 + activity * 1.4))
        p.drawEllipse(QRectF(cx - ring_radius, cy - ring_radius, ring_radius * 2, ring_radius * 2))

    def paintEvent(self, _):
        if getattr(self, "_reactor", None) is not None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#02080d"))
            painter.end()
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        if self._glow_only:
            self._paint_speaking_glow(p)
            p.end()
            return

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # grid dots
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face = fw * 0.31

        # halo glow
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(255, int(self._halo * 0.085 * frc)))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # pulse rings
        for pr in self._pulses:
            a   = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
            col    = qcol(C.MUTED_C if self.muted else C.PRI, a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

        # scanners
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.5))
        ex = 75 if self.speaking else 44
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # tick marks
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(qcol(C.PRI, 140), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # crosshair
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(qcol(C.PRI, int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # corner brackets
        bl = 24
        bc = qcol(C.PRI, 210)
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # The main avatar is generated live from geometry and PCM audio.
        if self._avatar_mode:
            self._draw_consciousness(p, cx, cy, fw)
        elif self._face_px:
            voice_bloom = self._voice_level if self.speaking else self._voice_level * 0.35
            breath = (math.sin(self._energy_phase) + 1.0) * 0.5
            fsz = int(fw * 0.62 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.save()
            p.translate(cx, cy)
            p.drawPixmap(int(-fsz / 2), int(-fsz / 2), scaled)
            p.restore()
        else:
            orb_r = int(fw * 0.27 * self._scale)
            oc    = (200, 0, 50) if self.muted else (0, 60, 110)
            for i in range(8, 0, -1):
                r2  = int(orb_r * i / 8)
                frc = i / 8
                a   = max(0, min(255, int(self._halo * 1.1 * frc)))
                p.setBrush(QBrush(QColor(int(oc[0]*frc), int(oc[1]*frc), int(oc[2]*frc), a)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
            p.setPen(QPen(qcol(C.PRI, min(255, int(self._halo * 2))), 1))
            p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            mode_label = {"evil": "EVIL", "cute": "ANJO", "sentinel": "SENTINEL"}.get(self.visual_mode, "ONLINE")
            primary, _ = self._mode_palette()
            txt, col = f"{sym}  {mode_label}", QColor(*primary) if self.visual_mode != "normal" else qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


class VoiceLabCanvas(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(210)
        self.setMinimumWidth(260)
        self._phase = 0.0
        self._coupling = 0.0
        self._voice_name = "Charon"
        self._last_seen = {"user": 0.0, "ai": 0.0}
        self._history = {
            "user": [0.0] * 64,
            "ai": [0.0] * 64,
        }
        self._channels = {
            "user": self._blank_channel(),
            "ai": self._blank_channel(),
        }
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(80)  # Voice panel does not need 20 redraws/second

    def _blank_channel(self) -> dict:
        return {
            "level": 0.0,
            "rms": 0.0,
            "peak": 0.0,
            "dominant_hz": 0.0,
            "centroid_hz": 0.0,
            "zcr_hz": 0.0,
            "clarity": 0.0,
            "bands": [0.0] * 14,
            "waveform": [0.0] * 64,
            "sample_rate": 0,
        }

    def set_metrics(self, payload: dict):
        source = str(payload.get("source") or "user").lower()
        if source != "user":
            return

        current = dict(self._channels[source])
        for key in ("level", "rms", "peak", "dominant_hz", "centroid_hz", "zcr_hz", "clarity", "sample_rate"):
            if key in payload:
                try:
                    current[key] = float(payload.get(key) or 0.0)
                except Exception:
                    current[key] = 0.0

        bands = payload.get("bands")
        if isinstance(bands, (list, tuple)):
            clean = []
            for value in bands[:18]:
                try:
                    clean.append(max(0.0, min(1.0, float(value))))
                except Exception:
                    clean.append(0.0)
            while len(clean) < 14:
                clean.append(0.0)
            current["bands"] = clean

        waveform = payload.get("waveform")
        if isinstance(waveform, (list, tuple)):
            clean_wave = []
            for value in waveform[:96]:
                try:
                    clean_wave.append(max(-1.0, min(1.0, float(value))))
                except Exception:
                    clean_wave.append(0.0)
            while len(clean_wave) < 64:
                clean_wave.append(0.0)
            current["waveform"] = clean_wave

        self._channels[source] = current
        self._history[source].append(max(0.0, min(1.0, current["level"])))
        self._history[source] = self._history[source][-64:]
        self._last_seen[source] = time.time()

        try:
            self._coupling = max(0.0, min(1.0, float(payload.get("coupling", self._coupling))))
        except Exception:
            pass

        if payload.get("voice_name"):
            self._voice_name = str(payload.get("voice_name"))[:18]

        self.update()

    def _tick(self):
        self._phase += 0.18
        now = time.time()
        changed = False
        for source, data in self._channels.items():
            if now - self._last_seen[source] > 0.45:
                data["level"] *= 0.88
                data["peak"] *= 0.9
                data["rms"] *= 0.9
                data["clarity"] *= 0.9
                data["bands"] = [v * 0.86 for v in data.get("bands", [])]
                data["waveform"] = [v * 0.82 for v in data.get("waveform", [])]
                self._history[source].append(max(0.0, min(1.0, data["level"])))
                self._history[source] = self._history[source][-64:]
                changed = True
        if now - max(self._last_seen.values()) > 0.75:
            self._coupling *= 0.92
            changed = True
        if changed:
            self.update()

    def _draw_channel(self, p: QPainter, rect: QRectF, title: str, source: str, color: QColor):
        data = self._channels[source]

        panel = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        panel.setColorAt(0.0, qcol("#021722", 245))
        panel.setColorAt(0.55, qcol("#000d14", 240))
        panel.setColorAt(1.0, qcol("#00070c", 245))
        p.setBrush(QBrush(panel))
        border = QColor(color)
        border.setAlpha(120)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(rect, 4, 4)

        glow = QColor(color)
        glow.setAlpha(24)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -rect.height() + 18), 4, 4)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(color, 1))
        p.drawText(rect.adjusted(7, 4, -7, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, title)

        hz = data.get("dominant_hz", 0.0)
        centroid = data.get("centroid_hz", 0.0)
        lvl = data.get("level", 0.0) * 100
        peak = data.get("peak", 0.0) * 100
        clarity = data.get("clarity", 0.0)
        active_r = 2.0 + min(3.0, lvl / 28.0)
        p.setBrush(QBrush(color if lvl > 2 else qcol(C.BORDER_B)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(rect.right() - 9, rect.top() + 10), active_r, active_r)

        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(
            rect.adjusted(0, 4, -18, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            f"{lvl:02.0f}% {hz:04.0f}HZ",
        )
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(
            rect.adjusted(7, 15, -7, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"CENT {centroid:04.0f}  PEAK {peak:02.0f}",
        )

        wave_h = max(34.0, rect.height() * 0.34)
        wave = QRectF(rect.left() + 7, rect.top() + 29, rect.width() - 14, wave_h)
        mid = wave.center().y()
        p.setPen(QPen(qcol(C.BORDER, 90), 1))
        for line in range(1, 4):
            x = wave.left() + wave.width() * line / 4
            p.drawLine(QPointF(x, wave.top()), QPointF(x, wave.bottom()))
        for line in range(1, 3):
            y = wave.top() + wave.height() * line / 3
            p.drawLine(QPointF(wave.left(), y), QPointF(wave.right(), y))
        p.drawLine(QPointF(wave.left(), mid), QPointF(wave.right(), mid))

        waveform = data.get("waveform") or [0.0] * 64
        path = QPainterPath()
        for i, value in enumerate(waveform):
            x = wave.left() + (wave.width() * i / max(1, len(waveform) - 1))
            y = mid - max(-1.0, min(1.0, float(value))) * wave.height() * 0.42
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        shadow = QColor(color)
        shadow.setAlpha(50)
        p.setPen(QPen(shadow, 4.0))
        p.drawPath(path)
        p.setPen(QPen(color, 1.6))
        p.drawPath(path)

        clarity_bar = QRectF(wave.left(), wave.bottom() + 3, wave.width(), 2)
        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(clarity_bar, 1, 1)
        if clarity > 0:
            clarity_col = QColor(color)
            clarity_col.setAlpha(150)
            p.setBrush(QBrush(clarity_col))
            p.drawRoundedRect(
                QRectF(clarity_bar.left(), clarity_bar.top(), clarity_bar.width() * max(0.0, min(1.0, clarity)), clarity_bar.height()),
                1,
                1,
            )

        bands = data.get("bands") or [0.0] * 14
        band_count = max(1, min(18, len(bands)))
        spec = QRectF(
            rect.left() + 7,
            wave.bottom() + 9,
            rect.width() - 14,
            max(24.0, rect.bottom() - wave.bottom() - 23),
        )
        p.setPen(QPen(qcol(C.BORDER, 70), 1))
        p.drawLine(QPointF(spec.left(), spec.bottom()), QPointF(spec.right(), spec.bottom()))
        gap = 2.0 if spec.width() > 130 else 1.0
        bw = max(2.0, (spec.width() - gap * (band_count - 1)) / band_count)
        for idx, value in enumerate(bands[:band_count]):
            value = max(0.0, min(1.0, float(value)))
            h = max(1.0, value * spec.height())
            x = spec.left() + idx * (bw + gap)
            bar = QRectF(x, spec.bottom() - h, bw, h)
            bar_grad = QLinearGradient(bar.left(), bar.top(), bar.left(), bar.bottom())
            top_col = QColor(color)
            top_col.setAlpha(230 if value > 0.2 else 80)
            low_col = QColor(color)
            low_col.setAlpha(70 if value > 0.2 else 35)
            bar_grad.setColorAt(0.0, top_col)
            bar_grad.setColorAt(1.0, low_col)
            p.setBrush(QBrush(bar_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(bar, 1.5, 1.5)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        bg = QRadialGradient(QPointF(W * 0.5, 14), max(W, H) * 0.72)
        bg.setColorAt(0.0, qcol("#032235"))
        bg.setColorAt(0.45, qcol(C.PANEL2))
        bg.setColorAt(1.0, qcol("#00070c"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        top_glow = QLinearGradient(0, 2, W, 2)
        top_glow.setColorAt(0.0, qcol(C.GREEN, 20))
        top_glow.setColorAt(0.5, qcol(C.PRI, 160))
        top_glow.setColorAt(1.0, qcol(C.ACC2, 20))
        p.setPen(QPen(QBrush(top_glow), 1.2))
        p.drawLine(QPointF(10, 3), QPointF(W - 10, 3))

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(8, 7, W - 16, 13), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "USER VOICE SYNTHESIS")

        chip = QRectF(W - 86, 6, 78, 15)
        p.setBrush(QBrush(qcol("#001722", 210)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(chip, 3, 3)
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(chip.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, "MIC FFT")

        ch_y = 27
        ch_h = max(112, H - 86)
        ch_w = W - 14
        user_rect = QRectF(7, ch_y, ch_w, ch_h)
        self._draw_channel(p, user_rect, "USER", "user", qcol(C.GREEN))

        user_level = max(0.0, min(1.0, float(self._channels["user"].get("level") or 0.0)))
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_MED), 1))
        p.drawText(QRectF(8, H - 43, W - 16, 12), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "INPUT LEVEL")
        p.drawText(
            QRectF(8, H - 43, W - 16, 12),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{user_level * 100:02.0f}%",
        )

        bar = QRectF(8, H - 24, W - 16, 8)
        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(QPen(qcol(C.BORDER), 1))
        p.drawRoundedRect(bar, 3, 3)

        fill_w = max(0.0, bar.width() * user_level)
        if fill_w > 0:
            link_grad = QLinearGradient(bar.left(), bar.top(), bar.right(), bar.top())
            link_grad.setColorAt(0.0, qcol(C.GREEN_D))
            link_grad.setColorAt(0.58, qcol(C.ACC2))
            link_grad.setColorAt(1.0, qcol(C.GREEN))
            p.setBrush(QBrush(link_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), fill_w, bar.height()), 3, 3)

        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.setFont(QFont("Courier New", 6))
        p.drawText(QRectF(8, H - 13, W - 16, 9), Qt.AlignmentFlag.AlignCenter, "60  130  250  500  1K  2K  4K  8K")


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(12)  # Keep the typing effect without a 166 FPS timer

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class NexusLabWindow(QMainWindow):
    def __init__(self, command_cb, parent=None):
        super().__init__(parent)
        self._command_cb = command_cb
        self.setWindowTitle("J.A.R.V.I.S — Nexus Lab")
        self.setMinimumSize(760, 520)
        self.resize(940, 620)

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_stack_panel(), stretch=0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: transparent; border: none;")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        modules = QVBoxLayout(content)
        modules.setContentsMargins(0, 0, 0, 0)
        modules.setSpacing(8)

        rows = [
            [
                self._module_card(
                    "LAB",
                    "Modo laboratorio",
                    "centraliza testes sem travar a tela principal",
                    C.PRI,
                    [
                        ("STATUS", "status do modo laboratorio"),
                        ("ESTUDO", "status do modo estudo"),
                        ("CICLO", "rodar um ciclo do modo estudo"),
                    ],
                ),
                self._module_card(
                    "05",
                    "Memoria auditiva",
                    "aprende sons padrao pelo microfone ativo",
                    C.GREEN,
                    [
                        ("APRENDER", "aprende esse som"),
                        ("IDENTIFICAR", "identifica esse barulho"),
                        ("LISTAR", "lista sons aprendidos"),
                    ],
                ),
            ],
            [
                self._module_card(
                    "07",
                    "Automacao",
                    "macros, clipboard, teclado, mouse e janelas",
                    C.ACC2,
                    [
                        ("MACROS", "lista automacoes"),
                        ("JANELAS", "lista janelas abertas"),
                        ("CLIPBOARD", "le o que esta copiado"),
                    ],
                ),
                self._module_card(
                    "08",
                    "Vision Labs",
                    "ensina pessoas e objetos pela camera local",
                    C.ACC,
                    [
                        ("ABRIR LAB", "__open_vision_lab__"),
                        ("BRAILLE", "abre modo braille"),
                        ("DESENHO", "abre modo desenho"),
                    ],
                ),
            ],
            [
                self._module_card(
                    "09",
                    "Cerebro neural",
                    "mapa, Obsidian, estudo ciclico e conhecimento",
                    "#b06cff",
                    [
                        ("MAPA", "__open_neural_map__"),
                        *([] if _glow_only_mode() else [("CÉREBRO 3D", "__open_brain_3d__")]),
                        ("STATS", "estatisticas do cerebro neural"),
                        ("ESTUDO", "inicia modo estudo ciclico"),
                    ],
                ),
                self._module_card(
                    "11",
                    "Busca e assets",
                    "imagens, referencias, comandos padrao e colecao",
                    "#ff6699",
                    [
                        ("IMAGEM", "buscar imagem"),
                        ("PASTA", "configurar pasta padrao de imagens"),
                        ("COMANDOS", "listar comandos padrao"),
                    ],
                ),
            ],
            [
                self._module_card(
                    "IOS",
                    "iPhone Bridge",
                    "Phone Link, Bluetooth, chamadas, SMS e midia",
                    "#66d9ff",
                    [
                        ("CONFIG", "abre config do iphone social"),
                        ("ATALHOS", "iniciar atalhos iphone"),
                        ("APREND", "aprendizado operacional"),
                    ],
                ),
                self._module_card(
                    "SOC",
                    "Social",
                    "WhatsApp, Instagram, conversas, posts e directs",
                    "#ff7ab8",
                    [
                        ("WPP", "abre WhatsApp Web"),
                        ("IG DM", "abre Instagram Direct"),
                        ("POSTS", "abre Instagram"),
                    ],
                ),
            ],
        ]

        for row_cards in rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            for card in row_cards:
                row.addWidget(card, stretch=1)
            modules.addLayout(row)

        modules.addStretch()
        scroll.setWidget(content)
        body.addWidget(scroll, stretch=1)
        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        panel = QWidget()
        panel.setFixedHeight(62)
        panel.setStyleSheet(
            f"background: {C.PANEL}; border: 1px solid {C.BORDER_A}; border-radius: 5px;"
        )
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(14, 8, 14, 8)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("NEXUS LAB")
        title.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
        title_col.addWidget(title)
        sub = QLabel("Complementary Jarvis screen")
        sub.setFont(QFont("Courier New", 8))
        sub.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        title_col.addWidget(sub)
        lay.addLayout(title_col)
        lay.addStretch()

        close = QPushButton("CLOSE")
        close.setFixedSize(82, 30)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.RED}; border: 1px solid {C.RED};
            }}
        """)
        close.clicked.connect(self.close)
        lay.addWidget(close)
        return panel

    def _build_stack_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(180)
        panel.setStyleSheet(
            f"background: {C.DARK}; border: 1px solid {C.BORDER}; border-radius: 5px;"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(7)

        title = QLabel("ACTIVE STACK")
        title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(title)

        for number, label, color in [
            ("LAB", "sandbox", C.PRI),
            ("05", "audio memory", C.GREEN),
            ("07", "automation", C.ACC2),
            ("08", "vision", C.ACC),
            ("09", "neural", "#b06cff"),
            ("11", "assets", "#ff6699"),
            ("IOS", "iphone", "#66d9ff"),
            ("SOC", "social", "#ff7ab8"),
        ]:
            item = QLabel(f"{number}  {label.upper()}")
            item.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            item.setStyleSheet(
                f"color: {color}; background: #000d14; border: 1px solid {C.BORDER_A}; "
                f"border-radius: 3px; padding: 6px;"
            )
            lay.addWidget(item)

        lay.addStretch()
        return panel

    def _module_card(self, number: str, title: str, subtitle: str, color: str, actions: list[tuple[str, str]]) -> QWidget:
        card = QWidget()
        card.setMinimumHeight(150)
        card.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px;"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(7)

        top = QHBoxLayout()
        tag = QLabel(number)
        tag.setFixedSize(46, 30)
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        tag.setStyleSheet(
            f"color: {color}; background: #000d14; border: 1px solid {color}; border-radius: 3px;"
        )
        top.addWidget(tag)

        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(title.upper())
        name.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
        text.addWidget(name)
        sub = QLabel(subtitle)
        sub.setFont(QFont("Courier New", 7))
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        text.addWidget(sub)
        top.addLayout(text, stretch=1)
        lay.addLayout(top)
        lay.addStretch()

        row = QHBoxLayout()
        row.setSpacing(5)
        for label, command in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(27)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #000d14; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 3px;
                }}
                QPushButton:hover {{
                    color: {color}; border: 1px solid {color};
                }}
            """)
            btn.clicked.connect(lambda _, cmd=command: self._command_cb(cmd))
            row.addWidget(btn)
        lay.addLayout(row)
        return card

    def _build_footer(self) -> QWidget:
        panel = QWidget()
        panel.setFixedHeight(28)
        panel.setStyleSheet(
            f"background: {C.DARK}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(10, 0, 10, 0)
        left = QLabel("F2 TOGGLE  ·  VOICE: ABRE O LABORATORIO")
        left.setFont(QFont("Courier New", 7))
        left.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        lay.addWidget(left)
        lay.addStretch()
        status = QLabel("ONLINE")
        status.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        status.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        lay.addWidget(status)
        return panel


class ModelCard(QPushButton):
    """Compact selectable model card used by the main Jarvis console."""

    clicked_tier = pyqtSignal(str)

    def __init__(self, tier: str, title: str, model: str, effort: str, think: bool, parent=None):
        super().__init__(parent)
        self.tier = tier
        self.title = title
        self.model = model
        self.effort = effort
        self.think = think
        self._active = False
        self._phase = "standby"
        self._resident = False
        self.setMinimumWidth(108)
        self.setFixedHeight(70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self.clicked.connect(lambda: self.clicked_tier.emit(self.tier))
        self.setToolTip(f"Ativar {title}: {model}, esforço {effort}, think={'on' if think else 'off'}")
        self.apply_state(False, "standby", False)

    def apply_state(self, active: bool, phase: str, resident: bool, pulse: bool = False):
        self._active = bool(active)
        self._phase = str(phase or "standby")
        self._resident = bool(resident)
        labels = {
            "standby": "STANDBY",
            "ready": "READY",
            "selected": "READY",
            "switching": "ROUTING",
            "loading": "LOADING",
            "thinking": "THINKING",
            "responding": "RESPONDING",
            "done": "COMPLETE",
            "error": "ERROR",
        }
        phase_label = labels.get(self._phase, self._phase.upper())
        think_label = "THINK ON" if self.think else "THINK OFF"
        ram_label = "IN RAM" if self._resident else "RAM FREE"
        marker = "●" if self._active else "○"
        self.setText(
            f"{marker} {self.title}\n"
            f"{self.model}\n"
            f"{self.effort.upper()} · {think_label}\n"
            f"{phase_label} · {ram_label}"
        )

        active_phase = self._phase in {"switching", "loading", "thinking", "responding"}
        if self._phase == "error":
            color, bg, border = C.RED, "#160008", C.RED
        elif active_phase:
            color = C.ACC2 if pulse else C.PRI
            bg, border = "#071a22", color
        elif self._active:
            color, bg, border = C.GREEN, "#00170e", C.GREEN_D
        else:
            color, bg, border = C.TEXT_DIM, C.PANEL2, C.BORDER
        self.setStyleSheet(f"""
            QPushButton {{
                color: {color}; background: {bg};
                border: 1px solid {border}; border-radius: 5px;
                padding: 4px 6px; text-align: left;
            }}
            QPushButton:hover {{
                color: {C.WHITE}; border: 1px solid {C.PRI}; background: {C.PRI_GHO};
            }}
        """)


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _braille_sig = pyqtSignal(dict)
    _voice_sig = pyqtSignal(dict)
    _temp_mute_sig = pyqtSignal(bool)
    _lab_sig = pyqtSignal(str)
    _vision_lab_sig = pyqtSignal(dict)
    _model_sig = pyqtSignal(dict)
    _avatar_mode_sig = pyqtSignal(str)
    _avatar_control_sig = pyqtSignal(dict)
    _libras_sig = pyqtSignal(bool)
    _music_sig = pyqtSignal(bool)
    _brain3d_sig = pyqtSignal()
    _brain_activity_sig = pyqtSignal(dict)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self.on_model_select  = None
        self._muted           = False
        self._wake_muted      = False
        self._current_file: str | None = None
        self._lab_window: NexusLabWindow | None = None
        self._vision_lab_window = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        center = QWidget()
        center.setStyleSheet(f"background: {C.BG};")
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_lay.addWidget(self.hud, stretch=1)
        center_lay.addWidget(self._build_model_panel(), stretch=0)
        body.addWidget(center, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik güncelleme timer'ı
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._braille_sig.connect(self._update_braille_panel)
        self._voice_sig.connect(self._update_voice_panel)
        self._temp_mute_sig.connect(self._set_temporary_mute)
        self._lab_sig.connect(self._handle_lab_signal)
        self._vision_lab_sig.connect(self._handle_vision_lab_signal)
        self._model_sig.connect(self._apply_model_status)
        self._avatar_mode_sig.connect(self.hud.set_visual_mode)
        self._avatar_control_sig.connect(self._control_avatar_3d)
        self._libras_sig.connect(self._set_libras_mode)
        self._music_sig.connect(self._set_music_mode)
        self._brain3d_sig.connect(self._open_brain_3d)
        self._brain_activity_sig.connect(self._apply_brain_activity)
        if self.hud._reactor is not None:
            self.hud._reactor.textSubmitted.connect(self._submit_libras_text)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_neural = QShortcut(QKeySequence("F3"), self)
        sc_neural.activated.connect(self._open_neural_map)
        sc_brain = QShortcut(QKeySequence("Ctrl+F3"), self)
        sc_brain.activated.connect(self._open_brain_3d)
        sc_lab = QShortcut(QKeySequence("F2"), self)
        sc_lab.activated.connect(lambda: self._handle_lab_signal("toggle"))

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _handle_lab_signal(self, action: str = "open"):
        action = (action or "open").lower().strip()
        if action in {"close", "fechar"}:
            if self._lab_window is not None:
                self._lab_window.close()
                self._log.append_log("SYS: Nexus Lab closed.")
            return
        if action in {"toggle", "alternar"} and self._lab_window is not None and self._lab_window.isVisible():
            self._lab_window.close()
            self._log.append_log("SYS: Nexus Lab closed.")
            return
        self._show_lab_screen()

    def _show_lab_screen(self):
        if self._lab_window is None:
            self._lab_window = NexusLabWindow(self._dispatch_lab_command, self)
        self._lab_window.show()
        self._lab_window.raise_()
        self._lab_window.activateWindow()
        self._log.append_log("SYS: Nexus Lab opened.")

    def _handle_vision_lab_signal(self, payload: dict | None = None):
        payload = payload or {}
        action = str(payload.get("action") or "open").lower().strip()
        if action in {"close", "fechar"}:
            if self._vision_lab_window is not None:
                self._vision_lab_window.close()
                self._log.append_log("SYS: Vision Labs closed.")
            return
        if action in {"toggle", "alternar"} and self._vision_lab_window is not None and self._vision_lab_window.isVisible():
            self._vision_lab_window.close()
            self._log.append_log("SYS: Vision Labs closed.")
            return
        try:
            if self._vision_lab_window is None:
                from actions.vision_lab_ui import VisionLabWindow

                self._vision_lab_window = VisionLabWindow(self)
            self._vision_lab_window.configure(
                kind=str(payload.get("kind") or ""),
                label=str(payload.get("label") or ""),
            )
            self._vision_lab_window.show()
            self._vision_lab_window.raise_()
            self._vision_lab_window.activateWindow()
            QTimer.singleShot(100, self._vision_lab_window.start_camera)
            self._log.append_log("SYS: Vision Labs opened.")
        except Exception as exc:
            self._log.append_log(f"ERR: Vision Labs could not open: {exc}")

    def _dispatch_lab_command(self, command: str):
        command = (command or "").strip()
        if not command:
            return
        if command == "__open_neural_map__":
            self._open_neural_map()
            return
        if command == "__open_brain_3d__":
            self._open_brain_3d()
            return
        if command == "__open_vision_lab__":
            self._handle_vision_lab_signal({"action": "open"})
            return
        self._log.append_log(f"LAB: {command}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(command,), daemon=True).start()

    def _open_neural_map(self):
        """Rebuild the vault index off the UI thread, then open the map."""
        self._log.append_log("SYS: Sincronizando cofre neural antes de abrir o mapa...")

        def sync_and_open():
            try:
                import webbrowser
                from memory_visualizer import rebuild_neural_map_html

                html_path = rebuild_neural_map_html()
                webbrowser.open(html_path.resolve().as_uri())
            except Exception as exc:
                print(f"[JARVIS] Falha ao sincronizar mapa neural: {exc}")

        threading.Thread(target=sync_and_open, daemon=True, name="JarvisNeuralMapSync").start()

    def _apply_brain_activity(self, payload):
        if not isinstance(payload, dict):
            return
        current = getattr(self, "_brain_activity", {})
        if int(payload.get("revision", 0)) <= int(current.get("revision", 0)):
            return
        self._brain_activity = dict(payload)
        if not _glow_only_mode() and payload.get("active") and getattr(self, "_brain3d_dialog", None) is None:
            self._open_brain_3d()
        self._send_brain_activity()

    def _send_brain_activity(self):
        import json
        view = getattr(self, "_brain3d_view", None)
        payload = getattr(self, "_brain_activity", None)
        if view is not None and payload:
            view.page().runJavaScript("window.JarvisBrain?.readActivity(" + json.dumps(payload) + ");")

    def _open_brain_3d(self):
        """Open the current local brain inside the UI, reusing a single dialog."""
        if _glow_only_mode():
            self._log.append_log("SYS: Cérebro 3D desativado na edição leve.")
            return
        from pathlib import Path

        html_path = Path(__file__).resolve().parent / "memory_brain_3d.html"
        if not html_path.exists():
            self._log.append_log("ERR: memory_brain_3d.html não encontrado.")
            return
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtWidgets import QDialog, QVBoxLayout
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except Exception as exc:
            import webbrowser
            webbrowser.open(html_path.resolve().as_uri())
            self._log.append_log(f"SYS: WebEngine indisponível ({exc}) — cérebro 3D no navegador.")
            return
        try:
            if getattr(self, "_brain3d_dialog", None) is not None:
                self._brain3d_dialog.showNormal()
                self._brain3d_dialog.raise_()
                self._brain3d_dialog.activateWindow()
                return
            self._log.append_log("SYS: Abrindo cérebro 3D dentro da UI...")
            dlg = QDialog(self)
            dlg.setWindowTitle("JARVIS — Cérebro de memória 3D")
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            dlg.resize(1120, 760)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(0, 0, 0, 0)
            view = QWebEngineView(dlg)
            view.loadFinished.connect(lambda ok: self._send_brain_activity() if ok else None)
            view.setUrl(QUrl.fromLocalFile(str(html_path.resolve())))
            layout.addWidget(view)
            def release_brain(_result):
                if getattr(self, "_brain3d_dialog", None) is dlg:
                    self._brain3d_dialog = None
                    self._brain3d_view = None
            dlg.finished.connect(release_brain)
            self._brain3d_dialog = dlg
            self._brain3d_view = view  # segura referência contra GC
            dlg.show()
            self._log.append_log("SYS: Cérebro 3D aberto dentro da UI.")
        except Exception as exc:
            print(f"[JARVIS] Falha ao abrir cérebro 3D: {exc}")
            self._log.append_log(f"ERR: Cérebro 3D falhou: {exc}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _control_avatar_3d(self, request):
        reply = request["reply"]
        def done(result):
            if not reply.done():
                reply.set_result(result or {"ok": False, "message": "O modelo 3D não respondeu."})
        reactor = getattr(self.hud, "_reactor", None)
        if reactor is None:
            done({"ok": False, "message": "O visual 3D está indisponível."})
            return
        reactor.control_model(request["command"], done)

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge(MARK_NAME, C.PRI_DIM))
        voice_button = QPushButton("VOZ PT-BR")
        voice_button.setToolTip("Configurar Jarvis UCM PT-BR no Fish Audio")
        voice_button.setStyleSheet(f"color:{C.PRI}; background:{C.PANEL2}; padding:6px; border:1px solid {C.BORDER}; border-radius:4px;")
        voice_button.clicked.connect(self._open_fish_voice_settings)
        lay.addWidget(voice_button)
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(title)
        sub = QLabel("Just A Rather Very Intelligent System")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _open_fish_voice_settings(self):
        from actions.fish_voice_settings import FishVoiceDialog
        if not getattr(self, "_fish_voice_dialog", None):
            self._fish_voice_dialog = FishVoiceDialog(self)
        self._fish_voice_dialog.show()
        self._fish_voice_dialog.raise_()
        self._fish_voice_dialog.activateWindow()

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_model_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedHeight(132)
        panel.setStyleSheet(
            f"background: {C.DARK}; border-top: 1px solid {C.BORDER_B};"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 6, 10, 7)
        lay.setSpacing(4)

        top = QHBoxLayout()
        title = QLabel("◈ LOCAL MODEL ARRAY")
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        top.addWidget(title)
        top.addStretch()
        self._model_route_lbl = QLabel("ROUTE --")
        self._model_route_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._model_route_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        top.addWidget(self._model_route_lbl)
        lay.addLayout(top)

        cards = QHBoxLayout()
        cards.setSpacing(5)
        specs = (
            ("normal", "NORMAL", "LLAMA 3.2 · 1B", "low", False),
            ("fast", "RÁPIDO", "QWEN 3.5 · 4B", "medium", True),
            ("ultra", "ULTRA", "GEMMA 4 · 8B", "high", True),
        )
        self._model_cards: dict[str, ModelCard] = {}
        for tier, title_text, model, effort, think in specs:
            card = ModelCard(tier, title_text, model, effort, think)
            card.clicked_tier.connect(self._select_model_tier)
            self._model_cards[tier] = card
            cards.addWidget(card, stretch=1)
        lay.addLayout(cards)

        self._model_think_lbl = QLabel("THINK MONITOR // aguardando o modelo local")
        self._model_think_lbl.setFixedHeight(20)
        self._model_think_lbl.setFont(QFont("Courier New", 7))
        self._model_think_lbl.setStyleSheet(
            f"color: {C.TEXT_MED}; background: {C.PANEL}; border: 1px solid {C.BORDER}; "
            "border-radius: 3px; padding: 2px 6px;"
        )
        self._model_think_lbl.setToolTip("Exibe o trecho mais recente do raciocínio devolvido pelo Ollama.")
        lay.addWidget(self._model_think_lbl)

        self._active_model_tier = _initial_model_tier()
        self._model_phase = "ready"
        self._model_resident = False
        self._model_pulse = False
        self._model_pulse_tmr = QTimer(self)
        self._model_pulse_tmr.timeout.connect(self._pulse_model_panel)
        self._model_pulse_tmr.start(420)
        self._refresh_model_cards()
        return panel

    def _select_model_tier(self, tier: str):
        if tier not in self._model_cards:
            return
        self._active_model_tier = tier
        self._model_phase = "switching"
        self._model_resident = False
        self._model_think_lbl.setText(f"ROUTER // ativando {tier.upper()} para chat e pesquisa")
        self._refresh_model_cards()
        if self.on_model_select:
            threading.Thread(target=self.on_model_select, args=(tier,), daemon=True).start()

    def _pulse_model_panel(self):
        if self._model_phase not in {"switching", "loading", "thinking", "responding"}:
            return
        self._model_pulse = not self._model_pulse
        self._refresh_model_cards()

    def _refresh_model_cards(self):
        for tier, card in self._model_cards.items():
            phase = self._model_phase if tier == self._active_model_tier else "standby"
            resident = self._model_resident if tier == self._active_model_tier else False
            card.apply_state(tier == self._active_model_tier, phase, resident, self._model_pulse)
        self._model_route_lbl.setText(f"ROUTE {self._active_model_tier.upper()}")

    def _apply_model_status(self, payload: dict):
        tier = str(payload.get("tier") or self._active_model_tier or "normal").lower()
        if tier not in self._model_cards:
            tier = "normal"
        phase = str(payload.get("phase") or "ready").lower()
        self._active_model_tier = tier
        self._model_phase = phase
        self._model_resident = bool(payload.get("resident", phase in {"thinking", "responding"}))

        thought = " ".join(str(payload.get("thinking_preview") or "").split())
        response = " ".join(str(payload.get("response_preview") or "").split())
        error = " ".join(str(payload.get("error") or "").split())
        think_chars = int(payload.get("thinking_chars") or 0)
        if error:
            monitor = f"ERROR // {error}"
        elif thought:
            monitor = f"THINK {think_chars}c // {thought[-240:]}"
        elif phase == "loading":
            monitor = f"LOAD // preparando {tier.upper()} na CPU"
        elif phase == "thinking":
            monitor = f"THINK // {tier.upper()} analisando..."
        elif phase == "responding" and response:
            monitor = f"OUTPUT // {response[-240:]}"
        elif phase == "done":
            monitor = f"DONE // {tier.upper()} liberado da RAM"
        elif phase in {"ready", "selected"}:
            monitor = f"READY // {tier.upper()} selecionado · carregamento sob demanda"
        else:
            monitor = f"{phase.upper()} // {tier.upper()}"
        self._model_think_lbl.setText(monitor)
        self._model_think_lbl.setToolTip(monitor)
        self._refresh_model_cards()

        if phase == "done":
            expected_tier = tier
            QTimer.singleShot(1800, lambda: self._settle_model_status(expected_tier))

    def _settle_model_status(self, tier: str):
        if self._active_model_tier != tier or self._model_phase != "done":
            return
        self._model_phase = "ready"
        self._model_resident = False
        self._refresh_model_cards()

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        for txt, col in [
            ("AI CORE\nACTIVE",     C.GREEN),
            ("SEC\nCLEARED",        C.PRI),
            (f"PROTOCOLO\n{MARK_NAME.removeprefix('MARK ')}", C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("VOICE SYNTHESIS"))
        self._voice_panel = VoiceLabCanvas()
        lay.addWidget(self._voice_panel)

        voice_sep = QFrame(); voice_sep.setFrameShape(QFrame.Shape.HLine)
        voice_sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(voice_sep)

        self._braille_sec_lbl = _sec("BRAILLE TRANSLATOR")
        lay.addWidget(self._braille_sec_lbl)
        self._braille_panel = self._build_braille_panel()
        lay.addWidget(self._braille_panel)

        self._braille_sep = QFrame(); self._braille_sep.setFrameShape(QFrame.Shape.HLine)
        self._braille_sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(self._braille_sep)
        self._set_braille_panel_visible(False)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        lab_btn = QPushButton("▣  NEXUS LAB  [F2]")
        lab_btn.setFixedHeight(26)
        lab_btn.setFont(QFont("Courier New", 7))
        lab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        lab_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.PRI};
            }}
        """)
        lab_btn.clicked.connect(lambda: self._handle_lab_signal("toggle"))
        lay.addWidget(lab_btn)

        # Neural Map button
        nm_btn = QPushButton("🧠  NEURAL MAP")
        nm_btn.setFixedHeight(26)
        nm_btn.setFont(QFont("Courier New", 7))
        nm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nm_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.GREEN}; border: 1px solid {C.GREEN_D};
            }}
        """)
        nm_btn.clicked.connect(self._open_neural_map)
        brain_btn = QPushButton("CÉREBRO 3D")
        brain_btn.setObjectName("openBrain3DButton")
        brain_btn.setFixedHeight(26)
        brain_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        brain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        brain_btn.setStyleSheet(nm_btn.styleSheet())
        brain_btn.setToolTip("Abrir cérebro 3D dentro do Jarvis · Ctrl+F3")
        brain_btn.clicked.connect(self._open_brain_3d)
        if _glow_only_mode():
            brain_btn.hide()
        map_buttons = QHBoxLayout()
        map_buttons.setSpacing(4)
        map_buttons.addWidget(nm_btn)
        map_buttons.addWidget(brain_btn)
        lay.addLayout(map_buttons)

        return w

    def _build_braille_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(8)

        self._braille_symbol_lbl = QLabel("⠿")
        self._braille_symbol_lbl.setFixedSize(62, 58)
        self._braille_symbol_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._braille_symbol_lbl.setFont(QFont("Segoe UI Symbol", 28, QFont.Weight.Bold))
        self._braille_symbol_lbl.setStyleSheet(
            f"color: {C.PRI}; background: #000d14; border: 1px solid {C.BORDER_B}; border-radius: 4px;"
        )
        top.addWidget(self._braille_symbol_lbl)

        info = QVBoxLayout()
        info.setSpacing(3)
        self._braille_status_lbl = QLabel("CAMERA IDLE")
        self._braille_status_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._braille_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        info.addWidget(self._braille_status_lbl)

        self._braille_count_lbl = QLabel("-- FINGERS")
        self._braille_count_lbl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        self._braille_count_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
        info.addWidget(self._braille_count_lbl)

        self._braille_dots_lbl = QLabel("DOTS --")
        self._braille_dots_lbl.setFont(QFont("Courier New", 7))
        self._braille_dots_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        self._braille_dots_lbl.setWordWrap(True)
        info.addWidget(self._braille_dots_lbl)
        top.addLayout(info, stretch=1)
        lay.addLayout(top)

        self._braille_conf_bar = QProgressBar()
        self._braille_conf_bar.setRange(0, 100)
        self._braille_conf_bar.setValue(0)
        self._braille_conf_bar.setTextVisible(False)
        self._braille_conf_bar.setFixedHeight(5)
        self._braille_conf_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #000d14; border: 1px solid {C.BORDER}; border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {C.GREEN}; border-radius: 2px;
            }}
        """)
        lay.addWidget(self._braille_conf_bar)

        self._braille_msg_lbl = QLabel("Awaiting camera input")
        self._braille_msg_lbl.setFont(QFont("Courier New", 7))
        self._braille_msg_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        self._braille_msg_lbl.setWordWrap(True)
        lay.addWidget(self._braille_msg_lbl)

        return panel

    def _update_braille_panel(self, payload: dict):
        self._set_braille_panel_visible(True)
        detected = bool(payload.get("detected"))
        count = payload.get("finger_count")
        braille = payload.get("braille") or "⠿"
        dots = payload.get("dots") or "DOTS --"
        confidence = payload.get("confidence") or 0
        message = payload.get("message") or "Awaiting camera input"

        try:
            pct = max(0, min(100, int(float(confidence) * 100)))
        except Exception:
            pct = 0

        self._braille_symbol_lbl.setText(braille)
        self._braille_count_lbl.setText(f"{count} FINGER{'S' if count != 1 else ''}" if count is not None else "-- FINGERS")
        self._braille_dots_lbl.setText(dots.upper())
        self._braille_conf_bar.setValue(pct)
        self._braille_msg_lbl.setText(message)

        if detected:
            self._braille_status_lbl.setText("CAMERA TRANSLATING")
            self._braille_status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
            self._braille_symbol_lbl.setStyleSheet(
                f"color: {C.GREEN}; background: #00140a; border: 1px solid {C.GREEN_D}; border-radius: 4px;"
            )
        else:
            self._braille_status_lbl.setText("HAND NOT FOUND")
            self._braille_status_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
            self._braille_symbol_lbl.setStyleSheet(
                f"color: {C.ACC2}; background: #141000; border: 1px solid {C.ACC2}; border-radius: 4px;"
            )

    def _update_voice_panel(self, payload: dict):
        if hasattr(self, "_voice_panel"):
            self._voice_panel.set_metrics(payload)
        if hasattr(self, "hud"):
            self.hud.set_voice_metrics(payload)

    def _set_braille_panel_visible(self, visible: bool):
        for widget in (
            getattr(self, "_braille_sec_lbl", None),
            getattr(self, "_braille_panel", None),
            getattr(self, "_braille_sep", None),
        ):
            if widget is not None:
                widget.setVisible(visible)

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F2] Nexus Lab  ·  [F3] Neural Map  ·  [F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl(f"LRM TECNO  ·  {MARK_NAME}  ·  CLASSIFIED"))
        lay.addStretch()
        lay.addWidget(_fl("© LRM TECNO", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell JARVIS what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self._wake_muted = False
        self.hud.muted = self._muted or self._wake_muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._wake_muted and not self._muted:
            self._mute_btn.setText("🔕  WAKE WORD: JARVIS")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #161000; color: {C.ACC2};
                    border: 1px solid {C.ACC2}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #211700; }}
            """)
        elif self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _set_temporary_mute(self, enabled: bool):
        self._wake_muted = bool(enabled)
        if self._wake_muted and self._muted:
            self._muted = False
        self.hud.muted = self._muted or self._wake_muted
        self._style_mute_btn()
        self._apply_state("WAKE MUTED" if self._wake_muted else "LISTENING")

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _set_music_mode(self, enabled):
        if self.hud._reactor is not None:
            self.hud._reactor._bridge.command.emit('openMusic' if enabled else 'closeMusic')

    def _set_libras_mode(self, enabled):
        if self.hud._reactor is not None:
            self.hud._reactor._bridge.command.emit('openLibras' if enabled else 'closeLibras')

    def _submit_libras_text(self, text):
        if self.hud.state == 'SLEEPING': return
        if text == "__JARVIS_DAILY_BRIEFING__":
            self._log.append_log("SYS: Preparando briefing diário local…")
        else:
            self._log.append_log('You (Libras revisada): ' + text)
        if self.on_text_command:
            threading.Thread(target=self.on_text_command,args=(text,),daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")
        self.hud._tmr.setInterval(500 if state == "SLEEPING" else 40)

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None, startup_visible=True):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        if startup_visible:
            self._win.show()
        self.root = _RootShim(self._app)

    def set_startup_visible(self, visible: bool) -> None:
        if visible:
            self._win.show()
            self._win.raise_()
            self._win.activateWindow()
        else:
            self._win.hide()
    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_model_select(self):
        return self._win.on_model_select

    @on_model_select.setter
    def on_model_select(self, cb):
        self._win.on_model_select = cb

    def set_music_mode(self, enabled=True):
        self._win._music_sig.emit(bool(enabled))

    def set_libras_mode(self, enabled=True):
        self._win._libras_sig.emit(bool(enabled))

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def update_model_status(self, payload: dict):
        if isinstance(payload, dict):
            self._win._model_sig.emit(payload)

    def control_avatar_3d(self, parameters):
        from concurrent.futures import Future
        from actions.avatar_control import normalize_avatar_command
        reply = Future()
        try:
            command = normalize_avatar_command(parameters)
            self._win._avatar_control_sig.emit({"command": command, "reply": reply})
        except Exception as exc:
            reply.set_exception(exc)
        return reply

    def set_avatar_mode(self, mode: str):
        self._win._avatar_mode_sig.emit(str(mode or "normal"))

    def update_braille_translation(self, result):
        if isinstance(result, dict):
            payload = result
        else:
            payload = {
                "detected": getattr(result, "detected", False),
                "finger_count": getattr(result, "finger_count", None),
                "braille": getattr(result, "braille", ""),
                "dots": getattr(result, "dots", ""),
                "confidence": getattr(result, "confidence", 0.0),
                "message": getattr(result, "message", ""),
            }
        self._win._braille_sig.emit(payload)

    def update_voice_metrics(self, payload: dict):
        if isinstance(payload, dict):
            self._win._voice_sig.emit(payload)

    def set_temporary_mute(self, enabled: bool):
        self._win._temp_mute_sig.emit(bool(enabled))

    def update_brain_activity(self, payload):
        self._win._brain_activity_sig.emit(dict(payload))

    def open_brain_3d(self):
        """Queue the viewer on the Qt UI thread, including calls from voice tools."""
        self._win._brain3d_sig.emit()

    def open_lab_screen(self):
        self._win._lab_sig.emit("open")

    def close_lab_screen(self):
        self._win._lab_sig.emit("close")

    def toggle_lab_screen(self):
        self._win._lab_sig.emit("toggle")

    def open_vision_lab(self, kind: str = "", label: str = ""):
        self._win._vision_lab_sig.emit({"action": "open", "kind": kind, "label": label})

    def close_vision_lab(self):
        self._win._vision_lab_sig.emit({"action": "close"})

    def toggle_vision_lab(self):
        self._win._vision_lab_sig.emit({"action": "toggle"})

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
