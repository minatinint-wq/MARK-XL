# audio_fallback.py - Fallback TTS using gTTS when Gemini audio fails
import tempfile
import threading
import time
from pathlib import Path

try:
    from gtts import gTTS
    _GTTS_OK = True
except ImportError:
    _GTTS_OK = False

try:
    import sounddevice as sd
    _SD_OK = True
except ImportError:
    _SD_OK = False

def speak_text(text: str, lang: str = "pt-br") -> bool:
    """Speak text using gTTS fallback. Returns True if successful."""
    if not _GTTS_OK:
        print("[TTS] ⚠️ gTTS not installed")
        return False

    try:
        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            temp_path = f.name

        # Generate speech
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_path)

        if _SD_OK:
            # Play using sounddevice with playsound fallback
            _play_audio_async(temp_path)
        else:
            try:
                import playsound
                playsound.playsound(temp_path)
            except ImportError:
                print(f"[TTS] Playing: {temp_path}")

        # Clean up temp file after a delay
        def cleanup():
            time.sleep(2)
            try:
                Path(temp_path).unlink()
            except:
                pass
        threading.Thread(target=cleanup, daemon=True).start()

        return True
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return False

def _play_audio_async(file_path: str) -> None:
    """Play audio file in background thread."""
    try:
        import subprocess
        # Use Windows built-in player or any available player
        subprocess.run(['powershell', '-c', f'(New-Object System.Media.SoundPlayer """{file_path}""").PlaySync()'],
                      capture_output=True, timeout=10)
    except Exception as e:
        print(f"[TTS] Play error: {e}")

if __name__ == "__main__":
    # Test
    test_text = "Olá, eu sou o JARVIS. Estou funcionando."
    print(f"[TTS] Testing: {test_text}")
    speak_text(test_text)
