import atexit
import json
import time
from pathlib import Path
from threading import Lock
from urllib.parse import quote

from http_client import session

TTL_SECONDS = 60 * 60
_BASE_DIR = Path(__file__).resolve().parent
_CACHE_DIR = _BASE_DIR / "shared" / "cache"
_EXPORT_CACHE_FILE = _CACHE_DIR / "asset_export_cache.json"
_LOCALIZE_CACHE_FILE = _CACHE_DIR / "asset_localize_ttl_cache.json"
_CACHE_LOCK = Lock()
_CACHE_STATE = {"dirty": 0}


def _load_cache_dict(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_caches() -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _EXPORT_CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_EXPORT_CACHE, f, ensure_ascii=False, indent=2)
        with _LOCALIZE_CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_LOCALIZE_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _touch_dirty(threshold: int = 200) -> None:
    _CACHE_STATE["dirty"] += 1
    if _CACHE_STATE["dirty"] >= threshold:
        _CACHE_STATE["dirty"] = 0
        _save_caches()


@atexit.register
def _save_caches_on_exit():
    if _CACHE_STATE.get("dirty", 0) > 0:
        _save_caches()


_EXPORT_CACHE = _load_cache_dict(_EXPORT_CACHE_FILE)
_LOCALIZE_CACHE = _load_cache_dict(_LOCALIZE_CACHE_FILE)


def normalize_asset_path(asset_path: str) -> str:
    if not asset_path:
        return ""
    return asset_path.strip().split(".", 1)[0]

def fetch_export_json(path_like: str) -> dict | None:
    if not path_like:
        return None

    key = normalize_asset_path(path_like)
    now = int(time.time())
    with _CACHE_LOCK:
        hit = _EXPORT_CACHE.get(key)
    if isinstance(hit, dict):
        ts = hit.get("ts")
        data = hit.get("data")
        if isinstance(ts, int) and (now - ts) <= TTL_SECONDS and isinstance(data, dict):
            return data

    url = f"https://export-service.dillyapis.com/v1/export?Path={quote(key, safe='/._')}"
    try:
        r = session.get(url, timeout=10)
        if not r.ok:
            if isinstance(hit, dict):
                return hit.get("data")
            return None
        data = r.json()
        if isinstance(data, dict):
            with _CACHE_LOCK:
                _EXPORT_CACHE[key] = {"ts": now, "data": data}
                _touch_dirty()
        return data if isinstance(data, dict) else None
    except Exception:
        if isinstance(hit, dict):
            return hit.get("data")
        return None

def extract_itemname_key(export_json: dict) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr:
        return None
    root = arr[0] if isinstance(arr, list) else arr
    props = root.get("Properties", {})
    if isinstance(props, dict):
        im = props.get("ItemName")
        if isinstance(im, dict) and im.get("key"):
            return im["key"]
    im2 = root.get("ItemName")
    if isinstance(im2, dict) and im2.get("key"):
        return im2["key"]
    return None



def extract_itemname_text(export_json: dict) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr:
        return None
    root = arr[0] if isinstance(arr, list) else arr
    props = root.get("Properties", {}) if isinstance(root, dict) else {}
    cand = None
    if isinstance(props, dict):
        im = props.get("ItemName")
        if isinstance(im, dict):
            cand = im.get("localizedString") or im.get("sourceString")
    if not cand and isinstance(root, dict):
        im2 = root.get("ItemName")
        if isinstance(im2, dict):
            cand = im2.get("localizedString") or im2.get("sourceString")
    return cand
def fetch_localized_name(key: str) -> str:
    if not key:
        return "???"

    now = int(time.time())
    with _CACHE_LOCK:
        hit = _LOCALIZE_CACHE.get(key)
    if isinstance(hit, dict):
        ts = hit.get("ts")
        val = hit.get("value")
        if isinstance(ts, int) and (now - ts) <= TTL_SECONDS and isinstance(val, str):
            return val

    url = "https://export-service.dillyapis.com/v1/export/localize"
    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}
    try:
        r = session.post(url, json=payload, timeout=10)
        if r.ok:
            arr = r.json().get("jsonOutput", [])
            value = (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
            with _CACHE_LOCK:
                _LOCALIZE_CACHE[key] = {"ts": now, "value": value}
                _touch_dirty()
            return value
    except Exception:
        pass
    if isinstance(hit, dict):
        stale_val = hit.get("value")
        if isinstance(stale_val, str):
            return stale_val
    return "???"
