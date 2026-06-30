from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "image_search.json"
DEFAULT_FOLDER = Path.home() / "Pictures" / "JARVIS Images"
DEFAULT_VIDEO_FOLDER = Path.home() / "Videos" / "JARVIS Videos"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
}
VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
    "video/x-matroska": "mkv",
}
VIDEO_EXTS = {"mp4", "webm", "mov", "avi", "mkv"}
PIL_FORMAT_EXT = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
    "BMP": "bmp",
}


def _default_config() -> dict[str, Any]:
    return {
        "default_folder": str(DEFAULT_FOLDER),
        "default_video_folder": str(DEFAULT_VIDEO_FOLDER),
        "region": "br-pt",
        "safe_search": "moderate",
        "max_file_mb": 15,
        "max_video_file_mb": 120,
        "provider_order": ["pexels", "pixabay", "unsplash", "bing", "ddg"],
        "video_provider_order": ["pexels", "pixabay"],
        "image_quality": "large2x",
        "video_quality": "large",
        "pexels_api_key": "",
        "pixabay_api_key": "",
        "unsplash_access_key": "",
    }


def _load_config() -> dict[str, Any]:
    cfg = _default_config()
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if v is not None})
    except Exception:
        pass
    return cfg


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _pictures_dir() -> Path:
    xdg = os.environ.get("XDG_PICTURES_DIR", "")
    if xdg and Path(xdg).exists():
        return Path(xdg)
    return Path.home() / "Pictures"


def _videos_dir() -> Path:
    xdg = os.environ.get("XDG_VIDEOS_DIR", "")
    if xdg and Path(xdg).exists():
        return Path(xdg)
    return Path.home() / "Videos"


def _media_type(params: dict[str, Any] | None = None, action: str = "") -> str:
    params = params or {}
    raw = str(
        params.get("media_type")
        or params.get("media")
        or params.get("kind")
        or params.get("asset_type")
        or ""
    ).lower()
    if not raw:
        raw = str(action or params.get("action") or "").lower()
    if any(token in raw for token in ("video", "videos", "clipe", "clip")):
        return "video"
    return "image"


def _resolve_folder(raw: str | None = None) -> Path:
    cfg = _load_config()
    value = str(raw or cfg.get("default_folder") or DEFAULT_FOLDER).strip()
    shortcuts = {
        "pictures": _pictures_dir() / "JARVIS Images",
        "picture": _pictures_dir() / "JARVIS Images",
        "imagens": _pictures_dir() / "JARVIS Images",
        "images": _pictures_dir() / "JARVIS Images",
        "downloads": Path.home() / "Downloads",
        "download": Path.home() / "Downloads",
        "desktop": Path.home() / "Desktop",
        "area_de_trabalho": Path.home() / "Desktop",
        "home": Path.home(),
    }
    lower = value.lower()
    if lower in shortcuts:
        return shortcuts[lower]

    value = os.path.expandvars(value)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _pictures_dir() / value
    return path


def _resolve_video_folder(raw: str | None = None) -> Path:
    cfg = _load_config()
    value = str(raw or cfg.get("default_video_folder") or DEFAULT_VIDEO_FOLDER).strip()
    shortcuts = {
        "videos": _videos_dir() / "JARVIS Videos",
        "video": _videos_dir() / "JARVIS Videos",
        "downloads": Path.home() / "Downloads",
        "download": Path.home() / "Downloads",
        "desktop": Path.home() / "Desktop",
        "area_de_trabalho": Path.home() / "Desktop",
        "home": Path.home(),
    }
    lower = value.lower()
    if lower in shortcuts:
        return shortcuts[lower]

    value = os.path.expandvars(value)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _videos_dir() / value
    return path


def _resolve_media_folder(media_type: str, raw: str | None = None) -> Path:
    return _resolve_video_folder(raw) if media_type == "video" else _resolve_folder(raw)


def _slug(text: str, fallback: str = "imagem") -> str:
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u00c0-\u017f]+", "_", text, flags=re.I)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:90] or fallback


def _unique_path(folder: Path, stem: str, ext: str) -> Path:
    ext = ext.lower().lstrip(".") or "jpg"
    target = folder / f"{stem}.{ext}"
    if not target.exists():
        return target
    for index in range(2, 1000):
        candidate = folder / f"{stem}_{index:02d}.{ext}"
        if not candidate.exists():
            return candidate
    return folder / f"{stem}_{int(time.time())}.{ext}"


def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(minimum, min(maximum, number))


def _as_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip().lower() for item in value if str(item).strip()]
    elif value:
        items = [item.strip().lower() for item in re.split(r"[,|;]", str(value)) if item.strip()]
    else:
        items = list(default)
    return items or list(default)


def _provider_order(params: dict[str, Any], cfg: dict[str, Any], media_type: str) -> list[str]:
    provider = str(params.get("provider") or "").strip().lower()
    if provider:
        return [_ALIASES_PROVIDER.get(provider, provider)]
    key = "video_provider_order" if media_type == "video" else "provider_order"
    default = _default_config()[key]
    return [_ALIASES_PROVIDER.get(item, item) for item in _as_list(params.get("providers") or cfg.get(key), default)]


def _api_key(cfg: dict[str, Any], provider: str) -> str:
    provider = _ALIASES_PROVIDER.get(provider.lower(), provider.lower())
    env_names = {
        "pexels": ("PEXELS_API_KEY",),
        "pixabay": ("PIXABAY_API_KEY",),
        "unsplash": ("UNSPLASH_ACCESS_KEY", "UNSPLASH_API_KEY"),
    }
    cfg_names = {
        "pexels": ("pexels_api_key",),
        "pixabay": ("pixabay_api_key",),
        "unsplash": ("unsplash_access_key", "unsplash_api_key"),
    }
    for name in env_names.get(provider, ()):
        value = os.environ.get(name)
        if value:
            return value.strip()
    for name in cfg_names.get(provider, ()):
        value = str(cfg.get(name) or "").strip()
        if value:
            return value
    return ""


def _mask_key(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "sem chave"
    if len(value) <= 8:
        return "ativo"
    return f"ativo (...{value[-4:]})"


def _pexels_locale(region: str) -> str:
    value = str(region or "").lower().replace("_", "-")
    if value in {"br", "pt", "br-pt", "pt-br"}:
        return "pt-BR"
    if value in {"en", "us", "en-us"}:
        return "en-US"
    if re.fullmatch(r"[a-z]{2}-[a-z]{2}", value):
        lang, country = value.split("-", 1)
        return f"{lang}-{country.upper()}"
    return "pt-BR"


def _pixabay_lang(region: str) -> str:
    value = str(region or "").lower().replace("_", "-")
    if value in {"br", "br-pt", "pt-br"}:
        return "pt"
    if "-" in value:
        return value.split("-", 1)[0]
    return value[:2] or "pt"


_ALIASES_PROVIDER = {
    "duckduckgo": "ddg",
    "duck": "ddg",
    "bing_images": "bing",
    "pexel": "pexels",
    "pix": "pixabay",
    "unsplash_api": "unsplash",
}


def _result_image_url(result: dict[str, Any]) -> str:
    for key in ("media_url", "video", "image", "url", "thumbnail"):
        value = str(result.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def _normalize_result(result: dict[str, Any]) -> dict[str, str]:
    image_url = _result_image_url(result)
    media_type = str(result.get("media_type") or "image").strip().lower()
    return {
        "title": str(result.get("title") or result.get("source") or ("video" if media_type == "video" else "imagem")).strip(),
        "media_type": media_type,
        "provider": str(result.get("provider") or "").strip(),
        "image": image_url,
        "media_url": image_url,
        "source": str(result.get("url") or result.get("source") or "").strip(),
        "thumbnail": str(result.get("thumbnail") or "").strip(),
        "width": str(result.get("width") or ""),
        "height": str(result.get("height") or ""),
        "duration": str(result.get("duration") or ""),
        "author": str(result.get("author") or result.get("photographer") or result.get("user") or ""),
        "download_location": str(result.get("download_location") or ""),
    }


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for result in results:
        item = _normalize_result(result)
        image_url = item["image"]
        if not image_url or image_url in seen:
            continue
        seen.add(image_url)
        cleaned.append(item)
    return cleaned


def _search_pexels_images(query: str, max_results: int, cfg: dict[str, Any], params: dict[str, Any]) -> list[dict[str, str]]:
    import requests

    key = _api_key(cfg, "pexels")
    if not key:
        return []
    region = str(params.get("region") or cfg.get("region") or "br-pt")
    quality = str(params.get("quality") or cfg.get("image_quality") or "large2x").lower()
    if quality not in {"original", "large2x", "large", "medium", "small", "portrait", "landscape", "tiny"}:
        quality = "large2x"
    request_params: dict[str, Any] = {
        "query": query,
        "per_page": min(max(max_results, 1), 80),
        "page": _safe_int(params.get("page"), 1, 1, 100),
        "locale": str(params.get("locale") or _pexels_locale(region)),
    }
    for optional in ("orientation", "size", "color"):
        if params.get(optional):
            request_params[optional] = params[optional]
    response = requests.get(
        "https://api.pexels.com/v1/search",
        params=request_params,
        headers={"Authorization": key, "User-Agent": USER_AGENT},
        timeout=14,
    )
    response.raise_for_status()
    photos = response.json().get("photos") or []
    raw: list[dict[str, Any]] = []
    for photo in photos:
        src = photo.get("src") or {}
        image_url = str(src.get(quality) or src.get("large2x") or src.get("large") or src.get("original") or "")
        if not image_url:
            continue
        raw.append(
            {
                "title": photo.get("alt") or f"Pexels {photo.get('id', '')}".strip(),
                "image": image_url,
                "thumbnail": src.get("medium") or src.get("small") or image_url,
                "url": photo.get("url") or "",
                "width": photo.get("width") or "",
                "height": photo.get("height") or "",
                "author": photo.get("photographer") or "",
                "provider": "pexels",
                "media_type": "image",
            }
        )
    return _dedupe_results(raw)[:max_results]


def _pick_pexels_video_file(video: dict[str, Any], quality: str) -> dict[str, Any] | None:
    files = [item for item in list(video.get("video_files") or []) if str(item.get("link") or "").startswith(("http://", "https://"))]
    if not files:
        return None
    mp4_files = [item for item in files if str(item.get("file_type") or "").lower().startswith("video/mp4")]
    files = mp4_files or files
    if quality in {"small", "sd", "low"}:
        files.sort(key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0))
    elif quality in {"medium", "hd"}:
        files.sort(key=lambda item: abs((int(item.get("width") or 0) * int(item.get("height") or 0)) - (1920 * 1080)))
    else:
        files.sort(key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0), reverse=True)
    return files[0]


def _search_pexels_videos(query: str, max_results: int, cfg: dict[str, Any], params: dict[str, Any]) -> list[dict[str, str]]:
    import requests

    key = _api_key(cfg, "pexels")
    if not key:
        return []
    region = str(params.get("region") or cfg.get("region") or "br-pt")
    request_params: dict[str, Any] = {
        "query": query,
        "per_page": min(max(max_results, 1), 80),
        "page": _safe_int(params.get("page"), 1, 1, 100),
        "locale": str(params.get("locale") or _pexels_locale(region)),
    }
    for optional in ("orientation", "size", "min_width", "min_height", "min_duration", "max_duration"):
        if params.get(optional):
            request_params[optional] = params[optional]
    response = requests.get(
        "https://api.pexels.com/v1/videos/search",
        params=request_params,
        headers={"Authorization": key, "User-Agent": USER_AGENT},
        timeout=14,
    )
    response.raise_for_status()
    quality = str(params.get("quality") or cfg.get("video_quality") or "large").lower()
    videos = response.json().get("videos") or []
    raw: list[dict[str, Any]] = []
    for video in videos:
        picked = _pick_pexels_video_file(video, quality)
        if not picked:
            continue
        raw.append(
            {
                "title": f"Pexels video {video.get('id', '')}".strip(),
                "video": picked.get("link") or "",
                "thumbnail": video.get("image") or "",
                "url": video.get("url") or "",
                "width": picked.get("width") or video.get("width") or "",
                "height": picked.get("height") or video.get("height") or "",
                "duration": video.get("duration") or "",
                "author": str((video.get("user") or {}).get("name") or ""),
                "provider": "pexels",
                "media_type": "video",
            }
        )
    return _dedupe_results(raw)[:max_results]


def _search_pixabay_images(query: str, max_results: int, cfg: dict[str, Any], params: dict[str, Any], safe_search: str) -> list[dict[str, str]]:
    import requests

    key = _api_key(cfg, "pixabay")
    if not key:
        return []
    region = str(params.get("region") or cfg.get("region") or "br-pt")
    request_params: dict[str, Any] = {
        "key": key,
        "q": query,
        "lang": _pixabay_lang(region),
        "image_type": params.get("image_type") or params.get("type") or "photo",
        "safesearch": "false" if safe_search == "off" else "true",
        "per_page": min(max(max_results, 3), 200),
        "page": _safe_int(params.get("page"), 1, 1, 100),
        "order": params.get("order") or "popular",
    }
    for optional in ("orientation", "category", "colors", "min_width", "min_height", "editors_choice"):
        if params.get(optional):
            request_params[optional] = params[optional]
    response = requests.get("https://pixabay.com/api/", params=request_params, headers={"User-Agent": USER_AGENT}, timeout=14)
    response.raise_for_status()
    raw: list[dict[str, Any]] = []
    for hit in response.json().get("hits") or []:
        image_url = hit.get("fullHDURL") or hit.get("largeImageURL") or hit.get("webformatURL") or hit.get("previewURL")
        if not image_url:
            continue
        raw.append(
            {
                "title": hit.get("tags") or f"Pixabay {hit.get('id', '')}".strip(),
                "image": image_url,
                "thumbnail": hit.get("previewURL") or hit.get("webformatURL") or image_url,
                "url": hit.get("pageURL") or "",
                "width": hit.get("imageWidth") or hit.get("webformatWidth") or "",
                "height": hit.get("imageHeight") or hit.get("webformatHeight") or "",
                "author": hit.get("user") or "",
                "provider": "pixabay",
                "media_type": "image",
            }
        )
    return _dedupe_results(raw)[:max_results]


def _pick_pixabay_video(hit: dict[str, Any], quality: str) -> dict[str, Any] | None:
    videos = hit.get("videos") or {}
    preferred = {
        "original": ("large", "medium", "small", "tiny"),
        "large": ("large", "medium", "small", "tiny"),
        "medium": ("medium", "large", "small", "tiny"),
        "small": ("small", "medium", "tiny", "large"),
        "tiny": ("tiny", "small", "medium", "large"),
        "sd": ("small", "medium", "tiny", "large"),
        "hd": ("medium", "large", "small", "tiny"),
    }.get(quality, ("large", "medium", "small", "tiny"))
    for name in preferred:
        item = videos.get(name) or {}
        if str(item.get("url") or "").startswith(("http://", "https://")):
            return item
    return None


def _search_pixabay_videos(query: str, max_results: int, cfg: dict[str, Any], params: dict[str, Any], safe_search: str) -> list[dict[str, str]]:
    import requests

    key = _api_key(cfg, "pixabay")
    if not key:
        return []
    region = str(params.get("region") or cfg.get("region") or "br-pt")
    request_params: dict[str, Any] = {
        "key": key,
        "q": query,
        "lang": _pixabay_lang(region),
        "video_type": params.get("video_type") or "all",
        "safesearch": "false" if safe_search == "off" else "true",
        "per_page": min(max(max_results, 3), 200),
        "page": _safe_int(params.get("page"), 1, 1, 100),
        "order": params.get("order") or "popular",
    }
    for optional in ("category", "min_width", "min_height", "editors_choice"):
        if params.get(optional):
            request_params[optional] = params[optional]
    response = requests.get("https://pixabay.com/api/videos/", params=request_params, headers={"User-Agent": USER_AGENT}, timeout=14)
    response.raise_for_status()
    quality = str(params.get("quality") or cfg.get("video_quality") or "large").lower()
    raw: list[dict[str, Any]] = []
    for hit in response.json().get("hits") or []:
        picked = _pick_pixabay_video(hit, quality)
        if not picked:
            continue
        raw.append(
            {
                "title": hit.get("tags") or f"Pixabay video {hit.get('id', '')}".strip(),
                "video": picked.get("url") or "",
                "thumbnail": picked.get("thumbnail") or "",
                "url": hit.get("pageURL") or "",
                "width": picked.get("width") or "",
                "height": picked.get("height") or "",
                "duration": hit.get("duration") or "",
                "author": hit.get("user") or "",
                "provider": "pixabay",
                "media_type": "video",
            }
        )
    return _dedupe_results(raw)[:max_results]


def _search_unsplash_images(query: str, max_results: int, cfg: dict[str, Any], params: dict[str, Any], safe_search: str) -> list[dict[str, str]]:
    import requests

    key = _api_key(cfg, "unsplash")
    if not key:
        return []
    quality = str(params.get("quality") or "regular").lower()
    if quality not in {"raw", "full", "regular", "small", "thumb"}:
        quality = "regular"
    content_filter = "low" if safe_search == "off" else "high"
    request_params: dict[str, Any] = {
        "query": query,
        "per_page": min(max(max_results, 1), 30),
        "page": _safe_int(params.get("page"), 1, 1, 100),
        "content_filter": params.get("content_filter") or content_filter,
        "order_by": params.get("order") or "relevant",
    }
    for optional in ("orientation", "color", "collections"):
        if params.get(optional):
            request_params[optional] = params[optional]
    response = requests.get(
        "https://api.unsplash.com/search/photos",
        params=request_params,
        headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1", "User-Agent": USER_AGENT},
        timeout=14,
    )
    response.raise_for_status()
    raw: list[dict[str, Any]] = []
    for photo in response.json().get("results") or []:
        urls = photo.get("urls") or {}
        links = photo.get("links") or {}
        user = photo.get("user") or {}
        image_url = urls.get(quality) or urls.get("regular") or urls.get("full") or urls.get("raw")
        if not image_url:
            continue
        raw.append(
            {
                "title": photo.get("alt_description") or photo.get("description") or f"Unsplash {photo.get('id', '')}".strip(),
                "image": image_url,
                "thumbnail": urls.get("thumb") or urls.get("small") or image_url,
                "url": links.get("html") or "",
                "width": photo.get("width") or "",
                "height": photo.get("height") or "",
                "author": user.get("name") or user.get("username") or "",
                "download_location": links.get("download_location") or "",
                "provider": "unsplash",
                "media_type": "image",
            }
        )
    return _dedupe_results(raw)[:max_results]


def _track_unsplash_download(result: dict[str, Any], cfg: dict[str, Any]) -> None:
    location = str(result.get("download_location") or "").strip()
    key = _api_key(cfg, "unsplash")
    if not location or not key:
        return
    try:
        import requests

        requests.get(
            location,
            headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1", "User-Agent": USER_AGENT},
            timeout=8,
        )
    except Exception:
        pass


def _search_with_ddg_endpoint(query: str, max_results: int, region: str, safe_search: str) -> list[dict[str, str]]:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    home = session.get(
        "https://duckduckgo.com/",
        params={"q": query, "iax": "images", "ia": "images"},
        timeout=12,
    )
    home.raise_for_status()
    match = re.search(r"vqd=['\"]?([^'\"&]+)", home.text)
    if not match:
        return []

    response = session.get(
        "https://duckduckgo.com/i.js",
        params={
            "l": region,
            "o": "json",
            "q": query,
            "vqd": match.group(1),
            "f": ",,,",
            "p": "1" if safe_search != "off" else "-1",
        },
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    return _dedupe_results(list(data.get("results") or []))[:max_results]


def _search_with_bing_images(query: str, max_results: int, safe_search: str) -> list[dict[str, str]]:
    import requests
    from bs4 import BeautifulSoup

    safe_map = {"on": "Strict", "moderate": "Moderate", "off": "Off"}
    response = requests.get(
        "https://www.bing.com/images/search",
        params={
            "q": query,
            "form": "HDRSC2",
            "first": "1",
            "safeSearch": safe_map.get(safe_search, "Moderate"),
        },
        headers={"User-Agent": USER_AGENT},
        timeout=14,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    raw_results: list[dict[str, str]] = []

    for anchor in soup.select("a.iusc"):
        metadata = anchor.get("m") or ""
        if not metadata:
            continue
        try:
            data = json.loads(metadata)
        except Exception:
            continue
        image_url = str(data.get("murl") or "").strip()
        if not image_url.startswith(("http://", "https://")):
            continue
        raw_results.append(
            {
                "title": str(data.get("t") or anchor.get("aria-label") or "imagem"),
                "image": image_url,
                "thumbnail": str(data.get("turl") or ""),
                "url": str(data.get("purl") or ""),
                "width": str(data.get("w") or ""),
                "height": str(data.get("h") or ""),
            }
        )
        if len(raw_results) >= max_results:
            break

    if not raw_results:
        for image in soup.select("img.mimg"):
            image_url = str(image.get("src") or image.get("data-src") or "").strip()
            if image_url.startswith(("http://", "https://")):
                raw_results.append(
                    {
                        "title": str(image.get("alt") or "imagem"),
                        "image": image_url,
                        "thumbnail": image_url,
                        "url": "",
                    }
                )
            if len(raw_results) >= max_results:
                break

    return _dedupe_results(raw_results)[:max_results]


def _search_images(params: dict[str, Any]) -> list[dict[str, str]]:
    query = str(params.get("query") or params.get("text") or params.get("value") or "").strip()
    if not query:
        return []
    cfg = _load_config()
    max_results = _safe_int(params.get("max_results") or params.get("count"), 8, 1, 30)
    region = str(params.get("region") or cfg.get("region") or "br-pt")
    safe_search = str(params.get("safe_search") or cfg.get("safe_search") or "moderate").lower()
    if safe_search in {"false", "off", "none", "desligado"}:
        safe_search = "off"
    elif safe_search not in {"on", "moderate", "off"}:
        safe_search = "moderate"

    for provider in _provider_order(params, cfg, "image"):
        try:
            if provider == "pexels":
                results = _search_pexels_images(query, max_results, cfg, params)
            elif provider == "pixabay":
                results = _search_pixabay_images(query, max_results, cfg, params, safe_search)
            elif provider == "unsplash":
                results = _search_unsplash_images(query, max_results, cfg, params, safe_search)
            elif provider == "bing":
                results = _search_with_bing_images(query, max_results, safe_search)
            elif provider == "ddg":
                results = _search_with_ddg_endpoint(query, max_results, region, safe_search)
            else:
                results = []
            if results:
                return results
        except Exception as exc:
            _ = exc
            continue
    return []


def _search_videos(params: dict[str, Any]) -> list[dict[str, str]]:
    query = str(params.get("query") or params.get("text") or params.get("value") or "").strip()
    if not query:
        return []
    cfg = _load_config()
    max_results = _safe_int(params.get("max_results") or params.get("count"), 8, 1, 30)
    safe_search = str(params.get("safe_search") or cfg.get("safe_search") or "moderate").lower()
    if safe_search in {"false", "off", "none", "desligado"}:
        safe_search = "off"
    elif safe_search not in {"on", "moderate", "off"}:
        safe_search = "moderate"

    for provider in _provider_order(params, cfg, "video"):
        try:
            if provider == "pexels":
                results = _search_pexels_videos(query, max_results, cfg, params)
            elif provider == "pixabay":
                results = _search_pixabay_videos(query, max_results, cfg, params, safe_search)
            else:
                results = []
            if results:
                return results
        except Exception as exc:
            _ = exc
            continue
    return []


def _search_media(params: dict[str, Any], media_type: str) -> list[dict[str, str]]:
    return _search_videos(params) if media_type == "video" else _search_images(params)


def _extension_from_response(url: str, content_type: str, image_format: str | None, media_type: str = "image") -> str:
    if media_type == "image" and image_format and image_format.upper() in PIL_FORMAT_EXT:
        return PIL_FORMAT_EXT[image_format.upper()]
    clean_type = content_type.split(";", 1)[0].lower().strip()
    if media_type == "video" and clean_type in VIDEO_TYPES:
        return VIDEO_TYPES[clean_type]
    if media_type == "image" and clean_type in IMAGE_TYPES:
        return IMAGE_TYPES[clean_type]
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if media_type == "video" and suffix in VIDEO_EXTS:
        return suffix
    if media_type == "image" and suffix in {"jpg", "jpeg", "png", "webp", "gif", "bmp"}:
        return "jpg" if suffix == "jpeg" else suffix
    guessed = mimetypes.guess_extension(clean_type or "")
    return (guessed or (".mp4" if media_type == "video" else ".jpg")).lstrip(".")


def _validate_image(data: bytes) -> tuple[str | None, tuple[int, int] | None]:
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as img:
            fmt = img.format
            size = img.size
            img.verify()
            return fmt, size
    except Exception as exc:
        raise ValueError(f"arquivo baixado nao parece uma imagem valida: {exc}") from exc


def _download_image(
    url: str,
    folder: Path,
    filename_hint: str,
    max_file_mb: int,
    title: str = "",
) -> dict[str, Any]:
    return _download_media(url, folder, filename_hint, max_file_mb, "image", title)


def _download_media(
    url: str,
    folder: Path,
    filename_hint: str,
    max_file_mb: int,
    media_type: str = "image",
    title: str = "",
) -> dict[str, Any]:
    import requests

    if not url.startswith(("http://", "https://")):
        raise ValueError("URL de midia invalida.")

    folder.mkdir(parents=True, exist_ok=True)
    max_bytes = max_file_mb * 1024 * 1024
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=25)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            label = "video" if media_type == "video" else "imagem"
            raise ValueError(f"{label} maior que o limite de {max_file_mb} MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ValueError("download retornou arquivo vazio")

    image_format = None
    size = None
    if media_type == "image":
        image_format, size = _validate_image(data)
    else:
        clean_type = content_type.split(";", 1)[0].lower().strip()
        suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
        if clean_type and clean_type not in VIDEO_TYPES and suffix not in VIDEO_EXTS and clean_type != "application/octet-stream":
            raise ValueError(f"arquivo baixado nao parece um video valido: {clean_type}")

    ext = _extension_from_response(url, content_type, image_format, media_type)
    fallback = "video" if media_type == "video" else "imagem"
    stem = _slug(filename_hint or title or Path(urlparse(url).path).stem or fallback, fallback)
    target = _unique_path(folder, stem, ext)
    target.write_bytes(data)
    return {
        "path": str(target),
        "name": target.name,
        "bytes": len(data),
        "format": image_format or ext.upper(),
        "size": f"{size[0]}x{size[1]}" if size else "",
        "source_url": url,
        "media_type": media_type,
    }


def _format_size(bytes_count: int) -> str:
    value = float(bytes_count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _media_label(media_type: str, plural: bool = False) -> str:
    if media_type == "video":
        return "videos" if plural else "video"
    return "imagens" if plural else "imagem"


def _list_media(folder: Path, media_type: str, limit: int = 20) -> str:
    plural = _media_label(media_type, True)
    if not folder.exists():
        return f"Pasta de {plural} ainda nao existe: {folder}"
    exts = {".mp4", ".webm", ".mov", ".avi", ".mkv"} if media_type == "video" else {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return f"Nenhum arquivo de {plural} encontrado em: {folder}"
    lines = [f"{plural.title()} em {folder} ({len(files)} arquivo(s)):"]
    for path in files[:limit]:
        lines.append(f"- {path.name} ({_format_size(path.stat().st_size)})")
    return "\n".join(lines)


def _provider_status_lines(cfg: dict[str, Any]) -> list[str]:
    return [
        f"Pexels: {_mask_key(_api_key(cfg, 'pexels'))} (imagem/video)",
        f"Pixabay: {_mask_key(_api_key(cfg, 'pixabay'))} (imagem/video)",
        f"Unsplash: {_mask_key(_api_key(cfg, 'unsplash'))} (imagem)",
        "Fallback: Bing/DDG para imagem quando APIs nao retornarem resultado",
    ]


def _format_search_results(query: str, results: list[dict[str, str]], media_type: str) -> str:
    plural = _media_label(media_type, True)
    singular = _media_label(media_type, False)
    if not results:
        return f"Nenhum {singular} encontrado para: {query}"
    lines = [f"{plural.title()} encontrados para '{query}':"]
    for index, result in enumerate(results, 1):
        title = result.get("title") or singular
        media_url = result.get("media_url") or result.get("image") or ""
        source = result.get("source") or ""
        provider = result.get("provider") or ""
        author = result.get("author") or ""
        dims = ""
        if result.get("width") and result.get("height"):
            dims = f" ({result['width']}x{result['height']})"
        duration = f" - {result['duration']}s" if result.get("duration") else ""
        suffix_bits = [bit for bit in (provider, author) if bit]
        suffix = f" [{' / '.join(suffix_bits)}]" if suffix_bits else ""
        lines.append(f"{index}. {title}{dims}{duration}{suffix}")
        lines.append(f"   URL: {media_url}")
        if result.get("thumbnail") and media_type == "video":
            lines.append(f"   Thumb: {result['thumbnail']}")
        if source:
            lines.append(f"   Fonte: {source}")
    lines.append("Para salvar, chame image_search com action='download' ou save=true.")
    return "\n".join(lines)


def image_search(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "search").lower().strip()
    cfg = _load_config()
    media_type = _media_type(params, action)

    if player:
        player.write_log(f"[ImageSearch] {action}")

    if action in {"status", "folder", "pasta", "config", "providers", "apis", "api_status"}:
        image_folder = _resolve_folder()
        video_folder = _resolve_video_folder()
        lines = [
            "Busca de midia configurada.",
            f"Pasta de imagens: {image_folder}",
            f"Pasta de videos: {video_folder}",
            f"Regiao: {cfg.get('region', 'br-pt')}",
            f"Safe search: {cfg.get('safe_search', 'moderate')}",
            f"Ordem imagens: {', '.join(_provider_order({}, cfg, 'image'))}",
            f"Ordem videos: {', '.join(_provider_order({}, cfg, 'video'))}",
            *_provider_status_lines(cfg),
        ]
        return "\n".join(lines)

    if action in {"set_api_key", "api_key", "set_key", "configurar_api", "configure_api"}:
        provider = _ALIASES_PROVIDER.get(str(params.get("provider") or "").strip().lower(), str(params.get("provider") or "").strip().lower())
        key_value = str(params.get("api_key") or params.get("key") or params.get("token") or "").strip()
        if provider not in {"pexels", "pixabay", "unsplash"}:
            return "Informe provider='pexels', 'pixabay' ou 'unsplash'."
        if not key_value:
            return f"Me passa a chave da API para {provider}."
        cfg_key = "unsplash_access_key" if provider == "unsplash" else f"{provider}_api_key"
        cfg[cfg_key] = key_value
        _save_config(cfg)
        return f"API {provider} salva ({_mask_key(key_value)})."

    if action in {"set_folder", "set_default_folder", "default_folder", "pasta_padrao", "configurar_pasta", "salvar_pasta", "set_video_folder"}:
        if action == "set_video_folder":
            media_type = "video"
        folder = _resolve_media_folder(media_type, params.get("folder") or params.get("path") or params.get("default_folder"))
        folder.mkdir(parents=True, exist_ok=True)
        cfg["default_video_folder" if media_type == "video" else "default_folder"] = str(folder)
        if params.get("region"):
            cfg["region"] = str(params["region"])
        if params.get("safe_search"):
            cfg["safe_search"] = str(params["safe_search"]).lower()
        _save_config(cfg)
        return f"Pasta padrao de {_media_label(media_type, True)} salva: {folder}"

    folder = _resolve_media_folder(media_type, params.get("folder") or params.get("path"))

    if action in {"list", "listar", "recentes"}:
        return _list_media(folder, media_type, _safe_int(params.get("limit"), 20, 1, 100))

    if action in {"save_url", "download_url", "baixar_url"}:
        url = str(params.get("url") or params.get("image_url") or params.get("video_url") or "").strip()
        if not url:
            return f"Me passa a URL do {_media_label(media_type, False)} para salvar."
        max_default = 120 if media_type == "video" else 15
        max_cfg = cfg.get("max_video_file_mb") if media_type == "video" else cfg.get("max_file_mb")
        max_file_mb = _safe_int(params.get("max_file_mb") or max_cfg, max_default, 1, 500)
        saved = _download_media(url, folder, str(params.get("filename") or _media_label(media_type, False)), max_file_mb, media_type)
        size = f", {saved.get('size')}" if saved.get("size") else ""
        return f"{_media_label(media_type, False).title()} salvo em: {saved['path']} ({saved['format']}{size})"

    query = str(params.get("query") or params.get("text") or params.get("value") or "").strip()
    if not query:
        return f"Qual {_media_label(media_type, False)} voce quer buscar?"

    download_actions = {"download", "baixar", "save", "salvar", "buscar_e_salvar", "search_and_save", "download_video", "baixar_video"}
    should_save = action in download_actions or bool(params.get("save") or params.get("download"))
    count = _safe_int(params.get("count") or params.get("limit"), 1 if should_save else 8, 1, 10)
    search_params = dict(params)
    search_params["max_results"] = max(_safe_int(params.get("max_results"), max(count * 3, 8), 1, 30), count)
    search_params["media_type"] = media_type
    results = _search_media(search_params, media_type)
    if not results:
        return f"Nao encontrei {_media_label(media_type, True)} para: {query}"

    if not should_save:
        return _format_search_results(query, results[:count], media_type)

    max_default = 120 if media_type == "video" else 15
    max_cfg = cfg.get("max_video_file_mb") if media_type == "video" else cfg.get("max_file_mb")
    max_file_mb = _safe_int(params.get("max_file_mb") or max_cfg, max_default, 1, 500)
    saved_items: list[dict[str, Any]] = []
    failures: list[str] = []
    for result in results:
        if len(saved_items) >= count:
            break
        try:
            if result.get("provider") == "unsplash":
                _track_unsplash_download(result, cfg)
            saved_items.append(
                _download_media(
                    result.get("media_url") or result["image"],
                    folder,
                    str(params.get("filename") or query),
                    max_file_mb,
                    media_type,
                    title=result.get("title", ""),
                )
            )
        except Exception as exc:
            failures.append(str(exc))
            continue

    if not saved_items:
        detail = f" Ultimo erro: {failures[-1]}" if failures else ""
        return f"Encontrei resultados, mas nao consegui salvar nenhum {_media_label(media_type, False)}.{detail}"

    lines = [f"Salvei {len(saved_items)} {_media_label(media_type, True)} em: {folder}"]
    for item in saved_items:
        size = f", {item['size']}" if item.get("size") else ""
        lines.append(f"- {item['name']} ({item['format']}{size})")
    if failures:
        lines.append(f"{len(failures)} resultado(s) foram ignorados por falha de download/validacao.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(image_search({"action": "status"}))
