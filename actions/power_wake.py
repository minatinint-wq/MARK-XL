"""Local-only wake listener. This helper exits and releases its model on wake."""
import re
import unicodedata
from pathlib import Path


def power_command(text):
    value = unicodedata.normalize('NFKD', str(text or '')).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r'[^a-z0-9 ]', ' ', value)
    value = ' '.join(value.split())
    name = r'(?:jarvis|javis|jarves|javes|jervis)'
    if re.fullmatch(name + r' (?:acorda|acorde|acordar)(?: por favor)?', value):
        return 'wake'
    if re.fullmatch(r'(?:' + name + r' )?(?:desliga|desligue|dorme|dormir)(?: por favor)?', value):
        return 'sleep'
    return None


def load_wake_model():
    # Only the already installed model is allowed; no downloads while asleep.
    cache = Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots'
    paths = sorted((p for p in cache.glob('*') if (p/'model.bin').is_file()),
                   key=lambda p:p.stat().st_mtime, reverse=True)
    if not paths:
        raise RuntimeError('Modelo local de escuta indisponivel')
    from faster_whisper import WhisperModel
    return WhisperModel(str(paths[0]), device='cpu', compute_type='int8',
                        cpu_threads=2, num_workers=1, local_files_only=True)


def hears_wake(model, samples):
    segments, _ = model.transcribe(samples, language='pt', beam_size=1,
        vad_filter=True, vad_parameters={'min_silence_duration_ms':250, 'speech_pad_ms':150},
        condition_on_previous_text=False)
    # Transcriptions are never logged, stored or sent outside this process.
    return power_command(' '.join(part.text for part in segments)) == 'wake'


def listen(device):
    import json, queue, time
    import numpy as np
    import sounddevice as sd
    import os,threading,psutil
    parent=psutil.Process(os.getppid())
    def parent_guard():
        while True:
            time.sleep(1)
            if not parent.is_running():
                os._exit(0)
    threading.Thread(target=parent_guard,daemon=True,name='JarvisWakeParent').start()
    model = load_wake_model()
    audio_queue = queue.Queue(maxsize=100)
    def capture(indata, frames, info, status):
        try:
            audio_queue.put_nowait(indata.copy().tobytes())
        except queue.Full:
            try:audio_queue.get_nowait()
            except queue.Empty:pass
    # A separate process allows the parent to stop both capture and inference
    # immediately, including while Whisper is decoding a local utterance.
    with sd.InputStream(device=device, samplerate=16000, channels=1,
                        dtype='int16', blocksize=320, latency='low', callback=capture):
        print(json.dumps({'event':'ready'}),flush=True)
        samples = bytearray()
        last_scan = time.monotonic()
        while True:
            samples.extend(audio_queue.get(timeout=3))
            if len(samples)>16000*2*4:
                del samples[:-16000*2*4]
            now=time.monotonic()
            if len(samples)<16000*2 or now-last_scan<1.2:
                continue
            last_scan=now
            pcm=np.frombuffer(bytes(samples),dtype='<i2').astype(np.float32)/32768.0
            if float(np.sqrt(np.mean(pcm*pcm)))<0.001:
                continue
            if hears_wake(model,pcm):
                print(json.dumps({'event':'wake'}),flush=True)
                return


if __name__=='__main__':
    import sys,json
    try:
        listen(int(sys.argv[1]))
    except Exception as exc:
        print(json.dumps({'event':'error','type':type(exc).__name__}),flush=True)
        raise SystemExit(2)
