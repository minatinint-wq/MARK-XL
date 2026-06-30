#web_search.py
import json
import sys
import time
import random
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_all_keys() -> list[str]:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    keys = [data.get("gemini_api_key", "")]
    keys.extend(data.get("additional_keys", []))
    return [k for k in keys if k]


_key_failures: dict[str, float] = {}
_key_index: int = 0


def _next_key() -> str:
    global _key_index
    keys = _get_all_keys()
    if not keys:
        return ""
    now = time.time()
    # Try keys in rotation, skip ones that failed in last 60s
    for _ in range(len(keys) * 2):
        key = keys[_key_index % len(keys)]
        _key_index = (_key_index + 1) % len(keys)
        if key not in _key_failures or now - _key_failures[key] > 60:
            return key
    # All keys failed recently — reset and return first
    _key_failures.clear()
    return keys[0]


def _mark_failure(key: str):
    _key_failures[key] = time.time()


def _gemini_search(query: str, retries: int = 3) -> str:
    from google import genai
    from google.genai import errors as genai_errors

    last_err = ""
    for attempt in range(retries + 1):
        key = _next_key()
        if not key:
            raise RuntimeError("No API keys available")
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=query,
                config={"tools": [{"google_search": {}}]},
            )
            text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
            text = text.strip()
            if not text:
                raise ValueError("Gemini returned an empty response.")
            # Success — clear this key's failures
            _key_failures.pop(key, None)
            return text
        except genai_errors.APIError as e:
            code = e.status_code if hasattr(e, "status_code") else 0
            _mark_failure(key)
            if code == 429:
                last_err = f"429 (quota)"
                if attempt < retries:
                    delay = random.uniform(0.3, 1.0)
                    time.sleep(delay)
                continue
            elif code >= 500:
                last_err = f"{code} (server error)"
                time.sleep(1.0)
                continue
            else:
                raise
        except Exception as e:
            _mark_failure(key)
            last_err = str(e)
            if attempt < retries:
                time.sleep(1.0)
                continue
            raise RuntimeError(f"Gemini failed after {retries+1} attempts: {last_err}")

    raise RuntimeError(f"Gemini failed after {retries+1} attempts: {last_err}")


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    results = []

    try:
        from duckduckgo_search import DDGS

        # Nova API do ddgs
        with DDGS() as ddgs:
            ddgs_results = ddgs.text(query, max_results=max_results)
            for r in ddgs_results:
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })

    except Exception as e:
        print(f"[WebSearch] DDG error: {e}")

        # Fallback: usar requests direto se ddgs falhar
        try:
            import requests
            headers = {"User-Agent": "Mozilla/5.0"}
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                for result in soup.select('.result'):
                    title = result.select_one('.result__title')
                    snippet = result.select_one('.result__snippet')
                    link = result.select_one('.result__url')
                    if title:
                        results.append({
                            "title": title.get_text(strip=True),
                            "snippet": snippet.get_text(strip=True) if snippet else "",
                            "url": link.get_text(strip=True) if link else ""
                        })
                        if len(results) >= max_results:
                            break
        except Exception as e2:
            print(f"[WebSearch] Fallback error: {e2}")

    return results


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()

def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        return _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini compare failed: {e} — falling back to DDG")

    # DDG fallback: fetch results per item and merge
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
    return "\n".join(lines)

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 Query: {query!r}  Mode: {mode}")

    try:
        if mode == "compare" and items:
            print(f"[WebSearch] 📊 Comparing: {items}")
            result = _compare(items, aspect)
            print("[WebSearch] ✅ Compare done.")
            return result

        print("[WebSearch] 🌐 Trying Gemini...")
        try:
            result = _gemini_search(query)
            print("[WebSearch] ✅ Gemini OK.")
            return result
        except Exception as e:
            print(f"[WebSearch] ⚠️ Gemini failed ({e}) — trying DDG...")
            results = _ddg_search(query)
            result  = _format_ddg(query, results)
            print(f"[WebSearch] ✅ DDG: {len(results)} result(s).")
            return result

    except Exception as e:
        print(f"[WebSearch] ❌ All backends failed: {e}")
        return f"Search failed, sir: {e}"