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

_qt_rules = os.environ.get("QT_LOGGING_RULES", "")
if "qt.qpa.window" not in _qt_rules:
    os.environ["QT_LOGGING_RULES"] = (_qt_rules + ";qt.qpa.window=false").strip(";")

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

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


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

        gpu = self._get_gpu()

        tmp = self._get_temp()

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
                capture_output=True, text=True, timeout=2
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
                    capture_output=True, text=True, timeout=3
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
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
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

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
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

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

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

        # face
        if self._face_px:
            fsz    = int(fw * 0.62 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
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
            txt, col = f"{sym}  ONLINE",     qcol(C.GREEN)
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
        self._tmr.start(50)

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
        self._tmr.start(6)

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
                    "Visao e camera",
                    "camera, braille, desenho e leitura de tela",
                    C.ACC,
                    [
                        ("MAO", "abre modo camera mao"),
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


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _braille_sig = pyqtSignal(dict)
    _voice_sig = pyqtSignal(dict)
    _temp_mute_sig = pyqtSignal(bool)
    _lab_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK XLI")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._wake_muted      = False
        self._current_file: str | None = None
        self._lab_window: NexusLabWindow | None = None

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

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

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

    def _dispatch_lab_command(self, command: str):
        command = (command or "").strip()
        if not command:
            return
        if command == "__open_neural_map__":
            self._open_neural_map()
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

        lay.addWidget(_badge("MARK XLI", C.PRI_DIM))
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

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

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
            ("PROTOCOL\nXXXVIII",   C.TEXT_DIM),
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
        lay.addWidget(nm_btn)

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
        lay.addWidget(_fl("LRM TECNO  ·  MARK XLI  ·  CLASSIFIED"))
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

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

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
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
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

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

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

    def open_lab_screen(self):
        self._win._lab_sig.emit("open")

    def close_lab_screen(self):
        self._win._lab_sig.emit("close")

    def toggle_lab_screen(self):
        self._win._lab_sig.emit("toggle")

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
