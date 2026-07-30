"""Start the local JARVIS Bridge beta without opening the full voice UI."""
from __future__ import annotations

import threading

from actions.jarvis_bridge_gateway import jarvis_bridge_gateway


if __name__ == "__main__":
    print(jarvis_bridge_gateway({"action": "start"}))
    print("Pressione Ctrl+C para encerrar a Bridge.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print(jarvis_bridge_gateway({"action": "stop"}))
