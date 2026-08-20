import atexit
import json
import os
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
_LOCAL_JUNO_LOCALIZE_ROOT = Path(r"E:\Fmodel\Exports\FortniteGame\Plugins\GameFeatures\Juno")
_LOCAL_JUNO_LOCALIZE_MAP = None
_LOCAL_JUNO_LOCALIZE_LOCK = Lock()
_JUNO_TABASCO_LOCRES_EXPORT_PATH = (
    "FortniteGame/Plugins/GameFeatures/Juno/JunoTabascoGameplay/Content/Localization/"
    "JunoTabascoGameplay/ja/JunoTabascoGameplay.locres"
)
_JUNO_TABASCO_LOCRES_MAP = None
_JUNO_TABASCO_LOCRES_LOCK = Lock()

# Newly shipped GameFeature text can lag behind the localization endpoint (or
# be returned as "???").  Keep narrowly-scoped, verified Japanese values here
# so an English asset-text fallback does not become the persistent display
# name in asset_localize_cache.json.
_LOCALIZATION_OVERRIDES_JA = {
    "35586C9143E960CB0792ECBABF59B476": "8ビットショットガン",
}


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


def _iter_local_localization_values(data) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}

    out: dict[str, str] = {}
    stack = [data]
    while stack:
        cur = stack.pop()
        if not isinstance(cur, dict):
            continue
        for k, v in cur.items():
            if isinstance(v, dict):
                stack.append(v)
            elif isinstance(k, str) and isinstance(v, str) and k:
                out.setdefault(k, v)
    return out


def _load_local_juno_localize_map() -> dict[str, str]:
    global _LOCAL_JUNO_LOCALIZE_MAP

    if _LOCAL_JUNO_LOCALIZE_MAP is not None:
        return _LOCAL_JUNO_LOCALIZE_MAP

    with _LOCAL_JUNO_LOCALIZE_LOCK:
        if _LOCAL_JUNO_LOCALIZE_MAP is not None:
            return _LOCAL_JUNO_LOCALIZE_MAP

        mapping: dict[str, str] = {}
        try:
            if _LOCAL_JUNO_LOCALIZE_ROOT.exists():
                for path in _LOCAL_JUNO_LOCALIZE_ROOT.glob("**/Localization/**/ja/*.json"):
                    try:
                        with path.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                        for k, v in _iter_local_localization_values(data).items():
                            mapping.setdefault(k, v)
                    except Exception:
                        continue
        except Exception:
            mapping = {}

        _LOCAL_JUNO_LOCALIZE_MAP = mapping
        return _LOCAL_JUNO_LOCALIZE_MAP


def _lookup_local_juno_localized_name(key: str) -> str | None:
    if not key:
        return None
    mapping = _load_local_juno_localize_map()
    value = mapping.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _is_juno_tabasco_profile() -> bool:
    return (os.getenv("SYSTEM_PROFILE", "").strip() or "") == "Juno_Tabasco"


def _load_juno_tabasco_locres_map() -> dict[str, str]:
    global _JUNO_TABASCO_LOCRES_MAP

    if _JUNO_TABASCO_LOCRES_MAP is not None:
        return _JUNO_TABASCO_LOCRES_MAP

    with _JUNO_TABASCO_LOCRES_LOCK:
        if _JUNO_TABASCO_LOCRES_MAP is not None:
            return _JUNO_TABASCO_LOCRES_MAP

        mapping: dict[str, str] = {}
        try:
            data = fetch_export_json(_JUNO_TABASCO_LOCRES_EXPORT_PATH)
            json_output = (data or {}).get("jsonOutput", {})
            if isinstance(json_output, dict):
                for k, v in _iter_local_localization_values(json_output).items():
                    mapping.setdefault(k, v)
        except Exception:
            mapping = {}

        _JUNO_TABASCO_LOCRES_MAP = mapping
        return _JUNO_TABASCO_LOCRES_MAP


def _lookup_juno_tabasco_locres_name(key: str) -> str | None:
    if not key or not _is_juno_tabasco_profile():
        return None

    mapping = _load_juno_tabasco_locres_map()
    value = mapping.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def normalize_asset_path(asset_path: str) -> str:
    if not asset_path:
        return ""
    if asset_path.strip().lower().endswith(".locres"):
        return asset_path.strip()
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
    return extract_text_key(export_json, "ItemName")


def extract_text_key(export_json: dict, field_name: str) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr:
        return None
    root = arr[0] if isinstance(arr, list) else arr
    props = root.get("Properties", {})
    if isinstance(props, dict):
        im = props.get(field_name)
        if isinstance(im, dict):
            key = im.get("key") or im.get("Key")
            if key:
                return key
    im2 = root.get(field_name)
    if isinstance(im2, dict):
        key = im2.get("key") or im2.get("Key")
        if key:
            return key
    return None



def extract_itemname_text(export_json: dict) -> str | None:
    return extract_text_value(export_json, "ItemName")


def extract_itemdescription_key(export_json: dict) -> str | None:
    return extract_text_key(export_json, "ItemDescription")


def extract_itemdescription_text(export_json: dict) -> str | None:
    return extract_text_value(export_json, "ItemDescription")


def extract_text_value(export_json: dict, field_name: str) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr:
        return None
    root = arr[0] if isinstance(arr, list) else arr
    props = root.get("Properties", {}) if isinstance(root, dict) else {}
    cand = None
    if isinstance(props, dict):
        im = props.get(field_name)
        if isinstance(im, dict):
            cand = (
                im.get("localizedString")
                or im.get("LocalizedString")
                or im.get("sourceString")
                or im.get("SourceString")
            )
    if not cand and isinstance(root, dict):
        im2 = root.get(field_name)
        if isinstance(im2, dict):
            cand = (
                im2.get("localizedString")
                or im2.get("LocalizedString")
                or im2.get("sourceString")
                or im2.get("SourceString")
            )
    return cand
def fetch_localized_name(key: str) -> str:
    if not key:
        return "???"

    override = _LOCALIZATION_OVERRIDES_JA.get(key)
    if override:
        return override

    now = int(time.time())
    with _CACHE_LOCK:
        hit = _LOCALIZE_CACHE.get(key)
    if isinstance(hit, dict):
        ts = hit.get("ts")
        val = hit.get("value")
        if isinstance(ts, int) and (now - ts) <= TTL_SECONDS and isinstance(val, str) and val != "???":
            return val

    url = "https://export-service.dillyapis.com/v1/export/localize"
    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}
    try:
        r = session.post(url, json=payload, timeout=10)
        if r.ok:
            arr = r.json().get("jsonOutput", [])
            value = (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
            if value == "???":
                value = _lookup_juno_tabasco_locres_name(key) or value
            if value == "???":
                value = _lookup_local_juno_localized_name(key) or value
            with _CACHE_LOCK:
                _LOCALIZE_CACHE[key] = {"ts": now, "value": value}
                _touch_dirty()
            return value
    except Exception:
        pass

    locres_value = _lookup_juno_tabasco_locres_name(key)
    if isinstance(locres_value, str):
        with _CACHE_LOCK:
            _LOCALIZE_CACHE[key] = {"ts": now, "value": locres_value}
            _touch_dirty()
        return locres_value

    local_value = _lookup_local_juno_localized_name(key)
    if isinstance(local_value, str):
        with _CACHE_LOCK:
            _LOCALIZE_CACHE[key] = {"ts": now, "value": local_value}
            _touch_dirty()
        return local_value

    if isinstance(hit, dict):
        stale_val = hit.get("value")
        if isinstance(stale_val, str):
            return stale_val
    return "???"
