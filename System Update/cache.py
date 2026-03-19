import atexit
import json
import os
from io import BytesIO
import shutil

from PIL import Image

from config import (
    ASSET_LOC_CACHE_FILE,
    DEBUG_LOCALIZE,
    ENABLE_IMAGE_CACHE,
    ICON_CACHE_DIR,
    ICON_CACHE_FILE,
    ICON_CACHE_DIR_SECONDARY,
    ICON_CACHE_FILE_SECONDARY,
    RARITY_CACHE_FILE,
    RARITY_JP_MAP,
    RARITY_MAP,
)
from export_api import (
    extract_itemname_key,
    extract_itemname_text,
    fetch_export_json,
    fetch_localized_name,
    normalize_asset_path,
)
from http_client import session

try:
    with open(ICON_CACHE_FILE, "r", encoding="utf-8") as f:
        ICON_PATH_CACHE = json.load(f)
except FileNotFoundError:
    ICON_PATH_CACHE = {}
try:
    if ICON_CACHE_FILE_SECONDARY:
        with open(ICON_CACHE_FILE_SECONDARY, "r", encoding="utf-8") as f:
            _secondary_cache = json.load(f)
        if isinstance(_secondary_cache, dict):
            for k, v in _secondary_cache.items():
                ICON_PATH_CACHE.setdefault(k, v)
except FileNotFoundError:
    pass
except Exception:
    pass

def icon_cache_key(path_like: str) -> str:
    clean = path_like.strip().strip("/").split(".")[0]
    return clean.replace("\\", "/").replace("/", "__") + ".png"

def extract_raw_rarity(props: dict) -> str | None:
    if not isinstance(props, dict):
        return None

    raw_rarity = props.get("Rarity")
    if isinstance(raw_rarity, str) and raw_rarity:
        return raw_rarity

    data_list = props.get("DataList", [])
    if isinstance(data_list, dict):
        data_list = [data_list]

    if isinstance(data_list, list):
        for entry in data_list:
            if not isinstance(entry, dict):
                continue
            raw_rarity = entry.get("Rarity")
            if isinstance(raw_rarity, str) and raw_rarity:
                return raw_rarity

    return None

def _mirror_cache_file(src: str, dst: str) -> None:
    try:
        if not src or not dst:
            return
        if not os.path.exists(src) or os.path.exists(dst):
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    except Exception:
        pass

def load_icon_from_cache(path_like: str):
    if not ENABLE_IMAGE_CACHE:
        return None
    try:
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        fp_primary = os.path.join(ICON_CACHE_DIR, icon_cache_key(path_like))
        if os.path.exists(fp_primary):
            if ICON_CACHE_DIR_SECONDARY:
                fp_secondary = os.path.join(ICON_CACHE_DIR_SECONDARY, icon_cache_key(path_like))
                _mirror_cache_file(fp_primary, fp_secondary)
            return Image.open(fp_primary).convert("RGBA")
    except Exception:
        pass
    try:
        if ICON_CACHE_DIR_SECONDARY:
            os.makedirs(ICON_CACHE_DIR_SECONDARY, exist_ok=True)
            fp_secondary = os.path.join(ICON_CACHE_DIR_SECONDARY, icon_cache_key(path_like))
            if os.path.exists(fp_secondary):
                fp_primary = os.path.join(ICON_CACHE_DIR, icon_cache_key(path_like))
                _mirror_cache_file(fp_secondary, fp_primary)
                return Image.open(fp_secondary).convert("RGBA")
    except Exception:
        pass
    return None

def save_icon_to_cache(path_like: str, content: bytes) -> None:
    if not ENABLE_IMAGE_CACHE:
        return
    try:
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        fp = os.path.join(ICON_CACHE_DIR, icon_cache_key(path_like))
        if not os.path.exists(fp):
            with open(fp, "wb") as f:
                f.write(content)
    except Exception:
        pass
    try:
        if ICON_CACHE_DIR_SECONDARY:
            os.makedirs(ICON_CACHE_DIR_SECONDARY, exist_ok=True)
            fp2 = os.path.join(ICON_CACHE_DIR_SECONDARY, icon_cache_key(path_like))
            if not os.path.exists(fp2):
                with open(fp2, "wb") as f:
                    f.write(content)
    except Exception:
        pass

def fetch_export_image_as_pil(path_like: str):
    # 1) cache
    im = load_icon_from_cache(path_like)
    if im is not None:
        return im

    # 2) download
    clean = path_like.strip().strip("/").split(".")[0]
    url = f"https://export-service.dillyapis.com/v1/export/?Path={clean}"
    try:
        r = session.get(url, timeout=10)
        if not r.ok:
            return None
        raw = r.content
        im = Image.open(BytesIO(raw)).convert("RGBA")
        save_icon_to_cache(path_like, raw)
        return im
    except Exception:
        return None

def save_icon_cache() -> None:
    try:
        with open(ICON_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ICON_PATH_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        if ICON_CACHE_FILE_SECONDARY:
            with open(ICON_CACHE_FILE_SECONDARY, "w", encoding="utf-8") as f:
                json.dump(ICON_PATH_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ==== AssetPathName -> 日本語名 キャッシュ ====
try:
    with open(ASSET_LOC_CACHE_FILE, "r", encoding="utf-8") as f:
        ASSET_LOC_CACHE = json.load(f)
except FileNotFoundError:
    ASSET_LOC_CACHE = {}

# ==== Rarity キャッシュ ====
try:
    with open(RARITY_CACHE_FILE, "r", encoding="utf-8") as f:
        RARITY_CACHE = json.load(f)
except FileNotFoundError:
    RARITY_CACHE = {}

if RARITY_CACHE:
    changed = False
    for k, v in list(RARITY_CACHE.items()):
        if isinstance(v, str):
            jp = RARITY_JP_MAP.get(v.lower())
            if jp and jp != v:
                RARITY_CACHE[k] = jp
                changed = True
    if changed:
        try:
            with open(RARITY_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(RARITY_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

try:
    with open(RARITY_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(RARITY_CACHE, f, ensure_ascii=False, indent=2)
except Exception:
    pass

_RARITY_STATE = {"dirty": 0}

def _flush_rarity_cache_if_needed(threshold: int = 200):
    if _RARITY_STATE["dirty"] >= threshold:
        _RARITY_STATE["dirty"] = 0
        try:
            with open(RARITY_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(RARITY_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

@atexit.register
def _save_rarity_cache_on_exit():
    if _RARITY_STATE.get("dirty", 0) > 0:
        try:
            with open(RARITY_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(RARITY_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def get_rarity_by_asset(asset_path: str) -> str:
    if not asset_path:
        return "アンコモン"

    norm = normalize_asset_path(asset_path)
    if norm in RARITY_CACHE:
        return RARITY_CACHE[norm]

    rarity_ja = "アンコモン"
    try:
        export_json = export_by_asset_path(asset_path)
        if export_json:
            jo = export_json.get("jsonOutput", [])
            data = jo[0] if isinstance(jo, list) else jo
            props = data.get("Properties", {})
            raw_rarity = extract_raw_rarity(props)
            rarity_en = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"
            rarity_ja = RARITY_JP_MAP.get(rarity_en.lower(), "アンコモン")
    except Exception:
        rarity_ja = "アンコモン"

    RARITY_CACHE[norm] = rarity_ja
    _RARITY_STATE["dirty"] += 1
    _flush_rarity_cache_if_needed()
    return rarity_ja

_ASSET_LC_STATE = {"dirty": 0}

def _flush_asset_loc_cache_if_needed(threshold: int = 200):
    if _ASSET_LC_STATE["dirty"] >= threshold:
        _ASSET_LC_STATE["dirty"] = 0
        try:
            with open(ASSET_LOC_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(ASSET_LOC_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def _flush_asset_loc_cache_force():
    try:
        with open(ASSET_LOC_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ASSET_LOC_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@atexit.register
def _save_asset_loc_cache_on_exit():
    if _ASSET_LC_STATE.get("dirty", 0) > 0:
        _flush_asset_loc_cache_force()

def export_by_asset_path(asset_path: str) -> dict | None:
    clean = normalize_asset_path(asset_path)
    return fetch_export_json(clean)

def get_name_by_asset(asset_path: str) -> str:
    if not asset_path:
        return "???"
    norm = normalize_asset_path(asset_path)

    hit = ASSET_LOC_CACHE.get(norm)
    if hit and hit != "???":
        if DEBUG_LOCALIZE:
            print(f"[asset-loc:CACHE] {norm} -> {hit}")
        return hit

    export_json = export_by_asset_path(asset_path)
    if not export_json:
        return "???"

    key = extract_itemname_key(export_json)
    if key:
        name = fetch_localized_name(key)
        if not name or name == "???":
            fallback = extract_itemname_text(export_json)
            name = fallback or name
        if name and name != "???":
            ASSET_LOC_CACHE[norm] = name
            _ASSET_LC_STATE["dirty"] += 1
            _flush_asset_loc_cache_if_needed()
            return ASSET_LOC_CACHE[norm]
        return "???"

    fallback = extract_itemname_text(export_json)
    if fallback and fallback != "???":
        ASSET_LOC_CACHE[norm] = fallback
        _ASSET_LC_STATE["dirty"] += 1
        _flush_asset_loc_cache_if_needed()
        return ASSET_LOC_CACHE[norm]
    return "???"

def enrich_summary_with_names(summary: dict):
    if not isinstance(summary, dict) or not summary:
        return

    assets = set()
    item_first_asset = {}

    for tg_block in summary.values():
        items = tg_block.get("Items", []) or []
        for item in items:
            rep = None
            for group in item.get("ValidLootPackages", []) or []:
                for v_pkg in group.get("Packages", []) or []:
                    for li in v_pkg.get("ListItems", []) or []:
                        ap = li.get("AssetPathName")
                        if ap:
                            norm = normalize_asset_path(ap)
                            assets.add(norm)
                            if rep is None:
                                rep = norm
                if rep:
                    break
            if rep:
                item_first_asset[id(item)] = rep

    for ap in assets:
        try:
            _ = get_name_by_asset(ap)
        except Exception:
            pass

    for tg_block in summary.values():
        items = tg_block.get("Items", []) or []
        for item in items:
            for group in item.get("ValidLootPackages", []) or []:
                for v_pkg in group.get("Packages", []) or []:
                    for li in v_pkg.get("ListItems", []) or []:
                        ap = li.get("AssetPathName")
                        if not ap:
                            continue
                        norm = normalize_asset_path(ap)
                        li["LocalizedName"] = ASSET_LOC_CACHE.get(norm, "???")
