#!/usr/bin/env python3
"""
JARVIS Gemini API Key Generator
Gera novas API keys via Google AI Studio API

⚠️  REQUISITOS:
1. Ter uma conta Google com billing configurado OU
2. Usar o link direto do Google AI Studio

📋 Como usar:
1. Abra: https://aistudio.google.com/app/apikey
2. Clique em "Create API Key"
3. Copie a key e use o api_key_manager.py para adicioná-la

Ou use o script para criar via CLI (requer OAuth configurado):
"""

import sys
import webbrowser
from pathlib import Path

def open_ai_studio():
    """Abre o Google AI Studio no navegador."""
    url = "https://aistudio.google.com/app/apikey"
    print(f"🌐 Abrindo {url}...")
    webbrowser.open(url)
    print("\n📋 Passos:")
    print("  1. Faça login com sua conta Google")
    print("  2. Clique em 'Create API Key'")
    print("  3. Selecione seu projeto ou crie um novo")
    print("  4. Copie a API key gerada")
    print("  5. Use: python api_key_manager.py add SUA_KEY_AQUI")

def show_models():
    """Mostra os modelos disponíveis na API."""
    import json
    from google import genai

    config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
    with open(config_path, "r") as f:
        key = json.load(f)["gemini_api_key"]

    client = genai.Client(api_key=key)

    print("=" * 60)
    print("Modelos Gemini disponíveis")
    print("=" * 60)

    for model in client.models.list():
        name = model.name.replace("models/", "")
        print(f"  📦 {name}")

    print("\n" + "=" * 60)

    # Audio-capable models
    print("\n🔊 Modelos com suporte a áudio (Live API):")
    audio_models = [
        "gemini-2.5-flash-native-audio-preview-12-2025",
        "gemini-2.5-flash-native-audio-preview-09-2025",
        "gemini-2.5-flash-native-audio-latest",
        "gemini-2.0-flash-exp",
        "gemini-3.1-flash-live-preview",
    ]
    for m in audio_models:
        print(f"  🎙️  {m}")

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "studio":
            open_ai_studio()
        elif cmd == "models":
            show_models()
        elif cmd == "help":
            print(__doc__)
        else:
            print(f"Comando desconhecido: {cmd}")
    else:
        open_ai_studio()

if __name__ == "__main__":
    main()
