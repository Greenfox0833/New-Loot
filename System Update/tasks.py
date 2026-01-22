import os
import re

from cache import (
    ICON_PATH_CACHE,
    export_by_asset_path,
    fetch_export_image_as_pil,
    get_name_by_asset,
    get_rarity_by_asset,
    icon_cache_key,
)
from config import (
    ENABLE_IMAGE_CACHE,
    ENABLE_IMAGE_CREATION,
    ICON_CACHE_DIR,
    IMAGE_DIR_MODE,
    SKIP_IF_FINAL_EXISTS,
    SKIP_IF_ICON_ALREADY_CACHED,
)
from export_api import normalize_asset_path
from image_tools import generate_weapon_card_from_export
from config import resolve_out_dir

def iter_tasks_from_summary_all(summary: dict):
    for tiergroup, tg_block in summary.items():
        for item in tg_block.get("Items", []):
            for group in item.get("ValidLootPackages", []):
                for v_pkg in group.get("Packages", []):
                    worldlist_key = v_pkg.get("Call") or "_NoWorldList"
                    out_dir = resolve_out_dir(tiergroup, worldlist_key)
                    for li in v_pkg.get("ListItems", []):
                        ap = li.get("AssetPathName")
                        if not ap:
                            continue
                        yield (ap, out_dir, None, tiergroup, worldlist_key)

def iter_tasks_from_minlist(min_items):
    DEFAULT_TG = "MinList"
    DEFAULT_WL = "_FromMinList"
    for rec in min_items:
        ap = rec.get("AssetPathName")
        if not ap:
            continue
        out_dir = resolve_out_dir(DEFAULT_TG, DEFAULT_WL)
        yield (ap, out_dir, rec.get("LocalizedName"), DEFAULT_TG, DEFAULT_WL)

def worker_task(
    asset_path: str,
    out_dir: str,
    list_percent_text: str | None,
    tiergroup: str | None = None,
    worldlist_key: str | None = None,
    preferred_name: str | None = None,
):
    wjson = export_by_asset_path(asset_path)
    if not wjson:
        return
    try:
        jo = wjson["jsonOutput"]
        data = jo[0] if isinstance(jo, list) else jo
        weapon_id = re.sub(r'[\\/:"*?<>|]', "_", data.get("Name", "Unknown"))
        loc = preferred_name or get_name_by_asset(asset_path)
        if loc == "???":
            item_key = data.get("Properties", {}).get("ItemName", {}).get("key", "")
            if loc == "???" and item_key:
                from export_api import fetch_localized_name

                loc = fetch_localized_name(item_key)
        safe = re.sub(r'[\\/:"*?<>|]', "_", loc)

        prefix = ""
        if IMAGE_DIR_MODE == "flat" and tiergroup and worldlist_key:
            prefix = f"[{tiergroup}][{worldlist_key}] "
        elif IMAGE_DIR_MODE == "tg" and worldlist_key:
            prefix = f"[{worldlist_key}] "

        rarity_ja = get_rarity_by_asset(asset_path)
        from config import RARITY_TO_TIER

        tier = RARITY_TO_TIER.get(rarity_ja, "ティア?")
        filename = f"{prefix}{safe} - {tier}.png"

        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        if SKIP_IF_FINAL_EXISTS and os.path.exists(out_path):
            print(f"[SKIP] 既存: {out_path}")
            return

        base = asset_path.strip("/").split("/")[-1].split(".")[0]
        if base in ICON_PATH_CACHE:
            cache_fp = os.path.join(ICON_CACHE_DIR, icon_cache_key(ICON_PATH_CACHE[base]))
            if SKIP_IF_ICON_ALREADY_CACHED and os.path.exists(cache_fp):
                print(f"[SKIP] 透過アイコン既存: {cache_fp}")
                return

        print(f"[...] 生成開始: {out_path}")
    except Exception:
        pass

    if ENABLE_IMAGE_CREATION:
        generate_weapon_card_from_export(wjson, asset_path, out_dir, list_percent_text)
    else:
        print(f"[SKIP] 画像作成をスキップ: {asset_path}")

def prewarm_icon_cache(summary: dict):
    if not ENABLE_IMAGE_CACHE:
        print("[i] 画像キャッシュが無効のためプリウォームはスキップ")
        return

    assets = set()
    for tg_block in summary.values():
        for item in tg_block.get("Items", []) or []:
            for group in item.get("ValidLootPackages", []) or []:
                for v_pkg in group.get("Packages", []) or []:
                    for li in v_pkg.get("ListItems", []) or []:
                        ap = li.get("AssetPathName")
                        if ap:
                            assets.add(normalize_asset_path(ap))

    for ap in sorted(assets):
        wjson = export_by_asset_path(ap)
        if not wjson:
            continue
        try:
            jo = wjson.get("jsonOutput", [])
            data = jo[0] if isinstance(jo, list) else jo
            props = data.get("Properties", {})
            data_list = props.get("DataList", [])

            def _get(entry, key):
                return (entry.get(key) or {}).get("AssetPathName") if isinstance(entry, dict) else None

            icon_path = None
            if isinstance(data_list, dict):
                icon_path = _get(data_list, "LargeIcon") or _get(data_list, "Icon")
            elif isinstance(data_list, list):
                for entry in data_list:
                    p = _get(entry, "LargeIcon")
                    if p and p.strip():
                        icon_path = p
                        break
                if not icon_path:
                    for entry in data_list:
                        p = _get(entry, "Icon")
                        if p and p.strip():
                            icon_path = p
                            break
            if not icon_path:
                icon_path = _get(props, "LargeIcon") or _get(props, "Icon")
            if not icon_path:
                continue

            icon_norm = normalize_asset_path(icon_path)
            _ = fetch_export_image_as_pil(icon_norm)

        except Exception:
            pass
