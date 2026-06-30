#!/usr/bin/env python3
"""
JARVIS API Key Manager
Gerencia múltiplas API keys do Gemini
"""

import json
import sys
from pathlib import Path
from google import genai

def load_keys() -> dict:
    """Carrega API keys do arquivo."""
    config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
    with open(config_path, "r") as f:
        return json.load(f)

def save_keys(keys: dict) -> None:
    """Salva API keys no arquivo."""
    config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
    with open(config_path, "w") as f:
        json.dump(keys, f, indent=4)
    print(f"[OK] Keys salvas em {config_path}")

def test_api_key(api_key: str) -> dict:
    """Testa uma API key e retorna informações."""
    try:
        client = genai.Client(api_key=api_key)
        models = list(client.models.list())

        # Count available models
        model_count = sum(1 for _ in models)

        return {
            "status": "OK",
            "models_available": model_count,
            "key": api_key[:20] + "...",
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)[:100],
            "key": api_key[:20] + "...",
        }

def list_available_keys():
    """Lista todas as API keys configuradas."""
    keys = load_keys()
    current = keys.get("gemini_api_key", "")

    print("=" * 60)
    print("JARVIS API Key Manager")
    print("=" * 60)

    # Check if there are multiple keys stored
    if "additional_keys" in keys:
        print("\n📋 Keys configuradas:")
        for i, key in enumerate(keys["additional_keys"]):
            status = "✅" if key == current else "  "
            print(f"  {status} {i+1}. {key[:25]}...")

    print(f"\n🔑 Key atual: {current[:25]}...")

    # Test current key
    print("\n⏳ Testando key atual...")
    result = test_api_key(current)
    print(f"  Status: {result['status']}")
    if result['status'] == 'OK':
        print(f"  Models disponíveis: {result['models_available']}")
    else:
        print(f"  Erro: {result['error']}")

    print("\n" + "=" * 60)

def add_key(new_key: str):
    """Adiciona uma nova API key."""
    keys = load_keys()

    if "additional_keys" not in keys:
        keys["additional_keys"] = []

    # Add to additional keys
    if new_key not in keys["additional_keys"] and new_key != keys.get("gemini_api_key"):
        keys["additional_keys"].append(new_key)
        save_keys(keys)
        print(f"[OK] Key adicionada: {new_key[:25]}...")
    else:
        print("[!] Key já existe")

def use_key(key_index: int):
    """Muda para usar uma das keys adicionais."""
    keys = load_keys()

    if "additional_keys" not in keys or key_index >= len(keys["additional_keys"]):
        print(f"[!] Key {key_index + 1} não encontrada")
        return

    old_key = keys.get("gemini_api_key", "")
    new_key = keys["additional_keys"][key_index]

    # Test new key first
    print(f"⏳ Testando key {key_index + 1}...")
    result = test_api_key(new_key)

    if result["status"] != "OK":
        print(f"[!] Key inválida: {result['error']}")
        return

    # Swap keys
    keys["gemini_api_key"] = new_key
    keys["additional_keys"][key_index] = old_key
    save_keys(keys)

    print(f"[OK] Key trocada para: {new_key[:25]}...")
    print(f"[OK] Key antiga movida para posição {key_index + 1}")

def test_all_keys():
    """Testa todas as keys disponíveis."""
    keys = load_keys()
    all_keys = [keys.get("gemini_api_key", "")] + keys.get("additional_keys", [])

    print("=" * 60)
    print("Testando todas as API keys...")
    print("=" * 60)

    for i, key in enumerate(all_keys):
        print(f"\n📋 Key {i + 1}: {key[:30]}...")
        result = test_api_key(key)
        if result["status"] == "OK":
            print(f"  ✅ OK - {result['models_available']} models disponíveis")
        else:
            print(f"  ❌ ERRO - {result['error']}")

def main():
    if len(sys.argv) < 2:
        list_available_keys()
        print("\n📖 Uso:")
        print("  python api_key_manager.py list          - Lista keys")
        print("  python api_key_manager.py add <KEY>     - Adiciona nova key")
        print("  python api_key_manager.py use <INDEX>   - Usa key (0, 1, 2...)")
        print("  python api_key_manager.py test         - Testa todas as keys")
        print("\n🔗 Gerar novas keys:")
        print("  https://aistudio.google.com/app/apikey")
        return

    cmd = sys.argv[1].lower()

    if cmd == "list":
        list_available_keys()

    elif cmd == "add" and len(sys.argv) >= 3:
        add_key(sys.argv[2])

    elif cmd == "use" and len(sys.argv) >= 3:
        try:
            use_key(int(sys.argv[2]) - 1)
        except ValueError:
            print("[!] Índice inválido")

    elif cmd == "test":
        test_all_keys()

    else:
        print(f"[!] Comando desconhecido: {cmd}")

if __name__ == "__main__":
    main()
