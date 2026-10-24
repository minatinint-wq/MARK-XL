"""Offline RNNoise filter for mono PCM16/16 kHz. No microphone I/O here."""
from pathlib import Path
import ctypes
import logging
import os
import weakref
import numpy as np

class NoiseSuppressor:
    def __init__(self, library=None):
        self.active = False
        self._release = None
        # On a PC where RNNoise removes quiet speech, allow a no-filter
        # diagnostic without changing the capture device or network path.
        if os.environ.get("MARK_XL_MIC_RAW") == "1":
            return
        try:
            path = Path(library) if library else Path(__file__).resolve().parents[1] / 'assets' / 'audio' / 'rnnoise' / 'rnnoise.dll'
            self._lib = ctypes.CDLL(str(path))
            lib = self._lib
            lib.rnnoise_create.argtypes = [ctypes.c_void_p]
            lib.rnnoise_create.restype = ctypes.c_void_p
            lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
            lib.rnnoise_destroy.restype = None
            lib.rnnoise_get_frame_size.argtypes = []
            lib.rnnoise_get_frame_size.restype = ctypes.c_int
            lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
            lib.rnnoise_process_frame.restype = ctypes.c_float
            if lib.rnnoise_get_frame_size() != 480:
                raise RuntimeError('Unexpected RNNoise frame size')
            self._state = lib.rnnoise_create(None)
            if not self._state:
                raise MemoryError('RNNoise state allocation failed')
            self._release = weakref.finalize(self, lib.rnnoise_destroy, self._state)
            # Causal 16 <-> 48 kHz FIR resampling, state preserved across packets.
            t = np.arange(63, dtype=np.float32) - 31
            taps = .30 * np.sinc(.30 * t) * np.hamming(63)
            self._taps = (taps / taps.sum()).astype(np.float32)
            self._up_history = np.zeros(62, np.float32)
            self._down_history = np.zeros(62, np.float32)
            self._input = np.empty(0, np.float32)
            # One frame of headroom preserves packet length with no drops.
            self._output = np.zeros(160, np.float32)
            self.active = True
        except Exception as exc:
            self.close()
            logging.getLogger(__name__).warning('Supressor indisponivel; microfone preservado (%s).', type(exc).__name__)

    def close(self):
        self.active = False
        if self._release is not None:
            self._release()

    def process(self, pcm):
        if not self.active or not pcm or len(pcm) % 2:
            return pcm
        try:
            samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)
            self._input = np.concatenate((self._input, samples))
            frames = []
            consumed = 0
            for start in range(0, len(self._input) - 159, 160):
                block = self._input[start:start+160]
                up = np.zeros(480, np.float32)
                up[::3] = block
                joined = np.concatenate((self._up_history, up))
                self._up_history = joined[-62:].copy()
                frame = np.ascontiguousarray(np.convolve(joined, self._taps * 3, 'valid'), dtype=np.float32)
                ptr = frame.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                self._lib.rnnoise_process_frame(self._state, ptr, ptr)
                joined = np.concatenate((self._down_history, frame))
                self._down_history = joined[-62:].copy()
                frames.append(np.convolve(joined, self._taps, 'valid')[::3])
                consumed += 160
            self._input = self._input[consumed:].copy()
            if frames:
                self._output = np.concatenate((self._output, *frames))
            count = len(samples)
            result = self._output[:count]
            self._output = self._output[count:].copy()
            if len(result) != count or not np.isfinite(result).all():
                raise RuntimeError('Invalid noise suppression output')
            return np.clip(result, -32768, 32767).astype('<i2').tobytes()
        except Exception as exc:
            self.close()
            logging.getLogger(__name__).warning('Supressor interrompido; microfone preservado (%s).', type(exc).__name__)
            return pcm
