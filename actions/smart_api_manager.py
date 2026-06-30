# smart_api_manager.py - Intelligent API key management with auto-switch
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional, Callable

try:
    from google import genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False

class SmartAPIManager:
    """Manages multiple API keys with automatic failover."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        self.config_path = Path(config_path)
        self._keys: dict = {}
        self._current_index: int = 0
        self._lock = threading.Lock()
        self._on_switch_callback: Optional[Callable] = None
        self._load_keys()

    def _load_keys(self) -> None:
        """Load all API keys from config."""
        try:
            with open(self.config_path, "r") as f:
                self._keys = json.load(f)
        except Exception as e:
            print(f"[API Manager] ⚠️ Could not load keys: {e}")
            self._keys = {}

    def _save_keys(self) -> None:
        """Save API keys to config."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._keys, f, indent=4)
        except Exception as e:
            print(f"[API Manager] ⚠️ Could not save keys: {e}")

    @property
    def current_key(self) -> str:
        """Get current active API key."""
        return self._keys.get("gemini_api_key", "")

    @property
    def all_keys(self) -> list[str]:
        """Get all available API keys."""
        keys = [self._keys.get("gemini_api_key", "")]
        keys.extend(self._keys.get("additional_keys", []))
        return [k for k in keys if k]

    def on_switch(self, callback: Callable) -> None:
        """Set callback to be called when key switches."""
        self._on_switch_callback = callback

    def is_quota_error(self, error: Exception) -> bool:
        """Check if error is a quota exhaustion error."""
        error_str = str(error).lower()
        return any(x in error_str for x in [
            "429", "quota", "resource_exhausted",
            "exceeded", "rate limit", "limit exceeded"
        ])

    def test_key(self, api_key: str) -> dict:
        """Test an API key and return info."""
        if not _GENAI_OK:
            return {"status": "OK", "models": 0}

        try:
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
            return {
                "status": "OK",
                "models": sum(1 for _ in models),
                "key": api_key[:20] + "..."
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e)[:100]}

    def switch_to_next_key(self) -> tuple[bool, str]:
        """
        Switch to next available API key.
        Returns (success, message)
        """
        with self._lock:
            all_keys = self.all_keys
            if len(all_keys) <= 1:
                return False, "No additional keys available"

            old_key = self.current_key
            current_idx = self._current_index

            # Find next working key
            tried = 0
            idx = (current_idx + 1) % len(all_keys)

            while tried < len(all_keys) and idx != current_idx:
                test_key = all_keys[idx]
                result = self.test_key(test_key)

                if result["status"] == "OK":
                    # Found a working key!
                    self._current_index = idx
                    self._keys["gemini_api_key"] = test_key

                    # If we're switching from an additional key back to primary, or vice versa
                    if old_key in self._keys.get("additional_keys", []):
                        # Update additional keys list
                        additional = [k for k in self._keys.get("additional_keys", []) if k != test_key]
                        if old_key not in additional:
                            additional.append(old_key)
                        self._keys["additional_keys"] = additional
                    elif test_key in self._keys.get("additional_keys", []):
                        # Move current key to additional, set new as primary
                        additional = self._keys.get("additional_keys", [])
                        if old_key not in additional:
                            additional.append(old_key)
                        self._keys["additional_keys"] = [k for k in additional if k != test_key]

                    self._save_keys()

                    # Call callback if set
                    if self._on_switch_callback:
                        try:
                            self._on_switch_callback(test_key)
                        except Exception as e:
                            print(f"[API Manager] ⚠️ Callback error: {e}")

                    return True, f"Switched to key {idx + 1}: {test_key[:25]}..."

                tried += 1
                idx = (idx + 1) % len(all_keys)

            return False, "No working keys available"

    def add_key(self, new_key: str) -> bool:
        """Add a new API key."""
        with self._lock:
            if "additional_keys" not in self._keys:
                self._keys["additional_keys"] = []

            if new_key not in self._keys["additional_keys"] and new_key != self.current_key:
                self._keys["additional_keys"].append(new_key)
                self._save_keys()
                return True
            return False

    def get_status(self) -> dict:
        """Get API manager status."""
        all_keys = self.all_keys
        current = self.current_key

        status = {
            "current_key": current[:20] + "..." if current else "None",
            "total_keys": len(all_keys),
            "current_index": self._current_index,
            "available": []
        }

        for i, key in enumerate(all_keys):
            result = self.test_key(key)
            status["available"].append({
                "index": i,
                "key": key[:20] + "...",
                "status": result["status"],
                "is_current": key == current
            })

        return status

    def announce_switch(self, speak_func: Optional[Callable] = None) -> None:
        """Announce key switch via TTS if available."""
        message = "Sir, I've switched to a backup API key as the previous one ran out of quota."

        if speak_func:
            try:
                speak_func(message)
            except Exception:
                print(f"[API Manager] Would say: {message}")
        else:
            print(f"[API Manager] 📢 {message}")


# Global instance
_api_manager: Optional[SmartAPIManager] = None
_manager_lock = threading.Lock()

def get_api_manager() -> SmartAPIManager:
    """Get or create the global API manager instance."""
    global _api_manager
    with _manager_lock:
        if _api_manager is None:
            _api_manager = SmartAPIManager()
        return _api_manager

def handle_api_error(error: Exception, speak_func: Optional[Callable] = None) -> bool:
    """
    Handle API error, auto-switch key if quota error.
    Returns True if key was switched, False otherwise.
    """
    manager = get_api_manager()

    if manager.is_quota_error(error):
        print("[API Manager] ⚠️ Quota exceeded detected, switching key...")
        success, msg = manager.switch_to_next_key()

        if success:
            manager.announce_switch(speak_func)
            return True
        else:
            msg = "Sir, all API keys have exceeded their quota. Please add new keys."
            if speak_func:
                try:
                    speak_func(msg)
                except Exception:
                    print(f"[API Manager] 📢 {msg}")
            else:
                print(f"[API Manager] 📢 {msg}")
            return False
        return False

    return False

if __name__ == "__main__":
    # Test
    manager = SmartAPIManager()
    print("=" * 50)
    print("JARVIS Smart API Manager - Test")
    print("=" * 50)

    status = manager.get_status()
    print(f"\nStatus: {json.dumps(status, indent=2)}")

    print("\n📋 All keys:")
    for i, key in enumerate(manager.all_keys):
        result = manager.test_key(key)
        marker = "→ " if i == 0 else "  "
        print(f"  {marker} {i+1}. {key[:30]}... [{result['status']}]")

    print("\n" + "=" * 50)
