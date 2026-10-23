"""Maximum capture volume and sensitive, peak-safe microphone gain."""
import numpy as np
from actions.noise_suppression import NoiseSuppressor

class MicrophoneGain:
    def __init__(self, max_gain=16.0):
        self.max_gain = float(max_gain)
        self.gain = 1.0
        self.noise = NoiseSuppressor()
        if self.noise.active:
            print("[JARVIS] Supressor de ruido RNNoise ativo (local).", flush=True)
    def process(self, pcm):
        if not pcm or len(pcm) % 2:
            return pcm
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)
        peak = float(np.max(np.abs(samples)))
        if peak < 1.0:
            return self.noise.process(pcm)
        rms = float(np.sqrt(np.mean(samples * samples)))
        desired = max(1.0, min(self.max_gain, 4587.0 / max(rms, 1.0)))
        rate = .55 if desired < self.gain else .18
        self.gain += (desired - self.gain) * rate
        applied = min(self.gain, 31128.0 / peak)
        amplified = np.clip(samples * applied, -31128.0, 31128.0).astype('<i2').tobytes()
        return self.noise.process(amplified)

def ensure_microphone_max():
    """Release all COM references on their owning thread, before CoUninitialize."""
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    comtypes.CoInitialize()
    device = interface = volume = None
    try:
        device = AudioUtilities.GetMicrophone()
        interface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        # QueryInterface owns an independent reference. ctypes.cast can retain a
        # cyclic pointer graph that a different thread later releases during GC.
        volume = interface.QueryInterface(IAudioEndpointVolume)
        if float(volume.GetMasterVolumeLevelScalar()) < .999:
            volume.SetMasterVolumeLevelScalar(1.0, None)
        return round(float(volume.GetMasterVolumeLevelScalar()) * 100)
    except Exception:
        return None
    finally:
        volume = None
        interface = None
        device = None
        comtypes.CoUninitialize()
