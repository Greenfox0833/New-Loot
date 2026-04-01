import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
TARGET_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BASE_DIR
ASSETS_DIR = BASE_DIR.parent / "shared" / "assets"

CACHE_DIR = TARGET_DIR / "cache"
ICON_CACHE_DIR = CACHE_DIR / "icon_cache"
IMAGE_OUTPUT_DIR = TARGET_DIR / "images"

EXPORT_CACHE_FILE = CACHE_DIR / "asset_export_cache.json"
LOCALIZE_CACHE_FILE = CACHE_DIR / "asset_localize_cache.json"
RARITY_CACHE_FILE = CACHE_DIR / "asset_rarity_cache.json"
ICON_PATH_CACHE_FILE = CACHE_DIR / "asset_icon_cache.json"

FONT_PATH = Path("c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF")
RARITY_BG_DIR = ASSETS_DIR / "Rarity"
RARITY_ICON_DIR = ASSETS_DIR / "icon"
AMMO_ICON_DIR = ASSETS_DIR / "Ammo"
STAT_TEMPLATE_PATH = ASSETS_DIR / "Template.png"

SUPPORTED_SUFFIXES = {".txt", ".json", ".csv"}
SKIP_DIR_NAMES = {"cache", "images", "__pycache__"}
SKIP_FILE_NAMES = {"run.py", "README.txt"}
MAX_WORKERS = 8
CANVAS_SIZE = 600
DRAW_STATS = False

RARITY_MAP = {
    "EFortRarity::Common": "Common",
    "EFortRarity::Uncommon": "Uncommon",
    "EFortRarity::Rare": "Rare",
    "EFortRarity::Epic": "Epic",
    "EFortRarity::Legendary": "Legend",
    "EFortRarity::Mythic": "Mythic",
    "EFortRarity::Transcendent": "Exotic",
}
RARITY_JP_MAP = {
    "common": "コモン",
    "uncommon": "アンコモン",
    "rare": "レア",
    "epic": "エピック",
    "legend": "レジェンド",
    "mythic": "ミシック",
    "exotic": "エキゾチック",
}
RARITY_TO_TIER = {
    "コモン": "ティア1",
    "アンコモン": "ティア2",
    "レア": "ティア3",
    "エピック": "ティア4",
    "レジェンド": "ティア5",
    "エキゾチック": "ティア6",
    "ミシック": "ティア7",
}
RARITY_BORDER_COLORS = {
    "Common": "#afb3b6",
    "Uncommon": "#3ec509",
    "Rare": "#02effb",
    "Epic": "#db28f8",
    "Legend": "#f1b054",
    "Mythic": "#f6e289",
    "Exotic": "#0ee4f4",
}
AMMO_ICON_MAP = {}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "proto-weapon-image-generator"})


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_cache(path: Path, data: dict) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log(message: str) -> None:
    print(message, flush=True)


EXPORT_CACHE = load_json_cache(EXPORT_CACHE_FILE)
LOCALIZE_CACHE = load_json_cache(LOCALIZE_CACHE_FILE)
RARITY_CACHE = load_json_cache(RARITY_CACHE_FILE)
ICON_PATH_CACHE = load_json_cache(ICON_PATH_CACHE_FILE)


def normalize_asset_path(asset_path: str) -> str:
    return asset_path.strip().split(".", 1)[0] if asset_path else ""


def safe_name(value: str) -> str:
    return re.sub(r'[\\/:"*?<>|]', "_", value or "")


def icon_cache_key(path_like: str) -> str:
    clean = normalize_asset_path(path_like)
    return clean.strip("/").replace("/", "__") + ".png"


def fetch_export_json(path_like: str) -> dict | None:
    key = normalize_asset_path(path_like)
    if not key:
        return None
    hit = EXPORT_CACHE.get(key)
    if isinstance(hit, dict):
        log(f"[cache] export json: {key}")
        return hit

    url = f"https://export-service.dillyapis.com/v1/export?Path={quote(key, safe='/._')}"
    try:
        log(f"[api] export json: {key}")
        response = SESSION.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    if isinstance(data, dict):
        EXPORT_CACHE[key] = data
        save_json_cache(EXPORT_CACHE_FILE, EXPORT_CACHE)
        return data
    return None


def fetch_localized_name(key: str) -> str:
    if not key:
        return "???"
    hit = LOCALIZE_CACHE.get(key)
    if isinstance(hit, str) and hit:
        log(f"[cache] localize key: {key}")
        return hit

    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}
    try:
        log(f"[api] localize key: {key}")
        response = SESSION.post("https://export-service.dillyapis.com/v1/export/localize", json=payload, timeout=15)
        response.raise_for_status()
        arr = response.json().get("jsonOutput", [])
        value = (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
    except Exception:
        return "???"

    LOCALIZE_CACHE[key] = value
    save_json_cache(LOCALIZE_CACHE_FILE, LOCALIZE_CACHE)
    return value


def extract_itemname_key(export_json: dict) -> str | None:
    root = export_json.get("jsonOutput", {})
    root = root[0] if isinstance(root, list) and root else root
    props = root.get("Properties", {}) if isinstance(root, dict) else {}
    item_name = props.get("ItemName")
    if isinstance(item_name, dict) and item_name.get("key"):
        return item_name["key"]
    return None


def extract_itemname_text(export_json: dict) -> str | None:
    root = export_json.get("jsonOutput", {})
    root = root[0] if isinstance(root, list) and root else root
    props = root.get("Properties", {}) if isinstance(root, dict) else {}
    item_name = props.get("ItemName")
    if isinstance(item_name, dict):
        return item_name.get("localizedString") or item_name.get("sourceString")
    return None


def extract_raw_rarity(props: dict) -> str | None:
    raw = props.get("Rarity")
    if isinstance(raw, str) and raw:
        return raw
    data_list = props.get("DataList", [])
    if isinstance(data_list, dict):
        data_list = [data_list]
    if isinstance(data_list, list):
        for entry in data_list:
            if isinstance(entry, dict):
                raw = entry.get("Rarity")
                if isinstance(raw, str) and raw:
                    return raw
    return None


def get_rarity_by_asset(asset_path: str) -> str:
    key = normalize_asset_path(asset_path)
    hit = RARITY_CACHE.get(key)
    if isinstance(hit, str) and hit:
        log(f"[cache] rarity: {key} -> {hit}")
        return hit

    rarity_ja = "アンコモン"
    export_json = fetch_export_json(asset_path)
    if export_json:
        root = export_json.get("jsonOutput", {})
        root = root[0] if isinstance(root, list) and root else root
        props = root.get("Properties", {}) if isinstance(root, dict) else {}
        raw_rarity = extract_raw_rarity(props)
        rarity_en = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"
        rarity_ja = RARITY_JP_MAP.get(rarity_en.lower(), "アンコモン")

    RARITY_CACHE[key] = rarity_ja
    save_json_cache(RARITY_CACHE_FILE, RARITY_CACHE)
    log(f"[save] rarity: {key} -> {rarity_ja}")
    return rarity_ja


def get_name_by_asset(asset_path: str) -> str:
    key = normalize_asset_path(asset_path)
    hit = LOCALIZE_CACHE.get(key)
    if isinstance(hit, str) and hit and hit != "???":
        log(f"[cache] name: {key} -> {hit}")
        return hit

    export_json = fetch_export_json(asset_path)
    if not export_json:
        return "???"

    item_key = extract_itemname_key(export_json)
    name = fetch_localized_name(item_key) if item_key else None
    if not name or name == "???":
        name = extract_itemname_text(export_json) or "???"

    LOCALIZE_CACHE[key] = name
    save_json_cache(LOCALIZE_CACHE_FILE, LOCALIZE_CACHE)
    log(f"[save] name: {key} -> {name}")
    return name


def find_icon_path(props: dict, asset_path: str) -> str | None:
    def get_path(entry: dict, key: str) -> str | None:
        value = entry.get(key)
        if isinstance(value, dict):
            asset = value.get("AssetPathName")
            if isinstance(asset, str) and asset.strip():
                return asset
        return None

    data_list = props.get("DataList", [])
    if isinstance(data_list, dict):
        data_list = [data_list]

    if isinstance(data_list, list):
        for pref in ("LargeIcon", "Icon"):
            for entry in data_list:
                if isinstance(entry, dict):
                    icon = get_path(entry, pref)
                    if icon:
                        return icon

    for pref in ("LargeIcon", "Icon"):
        icon = get_path(props, pref)
        if icon:
            return icon

    base = normalize_asset_path(asset_path).split("/")[-1]
    hit = ICON_PATH_CACHE.get(base)
    return hit if isinstance(hit, str) else None


def fetch_export_image_as_pil(path_like: str) -> Image.Image | None:
    key = icon_cache_key(path_like)
    icon_file = ICON_CACHE_DIR / key
    if icon_file.exists():
        try:
            log(f"[cache] icon: {path_like}")
            return Image.open(icon_file).convert("RGBA")
        except Exception:
            pass

    clean = normalize_asset_path(path_like)
    if not clean:
        return None

    url = f"https://export-service.dillyapis.com/v1/export/?Path={quote(clean, safe='/._')}"
    try:
        log(f"[api] icon: {clean}")
        response = SESSION.get(url, timeout=15)
        response.raise_for_status()
        raw = response.content
        image = Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        return None

    ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    icon_file.write_bytes(raw)
    return image


def fit_font(draw: ImageDraw.ImageDraw, text: str, width: int, max_size: int = 28, min_size: int = 14) -> ImageFont.FreeTypeFont:
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        if draw.textlength(text, font=font) <= width:
            return font
    return ImageFont.truetype(str(FONT_PATH), min_size)


def get_weapon_stats(props: dict) -> dict | None:
    try:
        stat_handle = props.get("WeaponStatHandle", {})
        data_table = stat_handle.get("DataTable", {})
        object_path = data_table.get("ObjectPath", "")
        row_name = stat_handle.get("RowName", "")
        if not object_path or not row_name:
            return None
        clean_path = object_path.replace(".0", "").lstrip("/")
        url = f"https://export-service.dillyapis.com/v1/export/?Path={quote(clean_path, safe='/._')}"
        response = SESSION.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        json_output = data.get("jsonOutput", {})
        if isinstance(json_output, list):
            json_output = json_output[0]
        rows = json_output.get("Rows", {})
        stat_row = rows.get(row_name, {})
        damage = stat_row.get("DmgPB", 0)
        bullet_count = stat_row.get("BulletsPerCartridge", 1)
        critical = stat_row.get("DamageZone_Critical", 1.0)
        max_damage = stat_row.get("MaxDamagePerCartridge", -1)
        firing_rate = stat_row.get("FiringRate", "?")
        reload_time = stat_row.get("ReloadTime", "?")
        clip_size = stat_row.get("ClipSize", "?")
        if isinstance(firing_rate, (int, float)):
            firing_rate = round(firing_rate, 1)
        if isinstance(reload_time, (int, float)):
            reload_time = round(reload_time, 1)
        base_damage = round(damage * bullet_count)
        headshot = round(base_damage * critical)
        if isinstance(max_damage, (int, float)) and max_damage != -1 and headshot > max_damage:
            headshot = int(max_damage)
        return {
            "ダメージ": base_damage,
            "建築ダメージ": headshot,
            "連射速度": firing_rate,
            "リロード時間": reload_time,
            "マガジン": clip_size,
        }
    except Exception:
        return None


def overlay_stat_template_with_numbers(canvas: Image.Image, stats: dict) -> None:
    try:
        if not STAT_TEMPLATE_PATH.exists():
            return
        template = Image.open(STAT_TEMPLATE_PATH).convert("RGBA")
        canvas.paste(template, (10, 10), template)
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(str(FONT_PATH), 15)
        values = {
            "ダメージ": f"{stats.get('ダメージ', '?')}({stats.get('建築ダメージ', '?')})",
            "連射速度": f"{stats.get('連射速度', '?')}/s",
            "リロード時間": f"{stats.get('リロード時間', '?')}s",
            "マガジン": f"{stats.get('マガジン', '?')}",
        }
        positions = {
            "ダメージ": (65, 28),
            "連射速度": (190, 28),
            "リロード時間": (285, 28),
            "マガジン": (380, 28),
        }
        for key, pos in positions.items():
            draw.text(pos, values.get(key, "?"), font=font, fill="white")
    except Exception:
        pass


def generate_weapon_card(asset_path: str) -> None:
    log(f"[start] {asset_path}")
    export_json = fetch_export_json(asset_path)
    if not export_json:
        log(f"[×] export取得失敗: {asset_path}")
        return

    root = export_json.get("jsonOutput", {})
    root = root[0] if isinstance(root, list) and root else root
    props = root.get("Properties", {}) if isinstance(root, dict) else {}

    weapon_name = get_name_by_asset(asset_path)
    rarity_ja = get_rarity_by_asset(asset_path)
    tier = RARITY_TO_TIER.get(rarity_ja, "ティア?")
    out_path = IMAGE_OUTPUT_DIR / f"{safe_name(weapon_name)} - {tier}.png"
    if out_path.exists():
        log(f"[skip] 既存画像: {out_path}")
        return

    raw_rarity = extract_raw_rarity(props)
    rarity = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"
    icon_path = find_icon_path(props, asset_path)
    if not icon_path:
        log(f"[×] アイコンなし: {asset_path}")
        return

    icon_clean = normalize_asset_path(icon_path)
    icon_image = fetch_export_image_as_pil(icon_clean)
    if icon_image is None:
        log(f"[×] アイコン取得失敗: {asset_path}")
        return

    bg_path = RARITY_BG_DIR / f"{rarity}.png"
    if not bg_path.exists():
        log(f"[×] 背景なし: {bg_path}")
        return

    base = normalize_asset_path(asset_path).split("/")[-1]
    ICON_PATH_CACHE[base] = icon_clean
    save_json_cache(ICON_PATH_CACHE_FILE, ICON_PATH_CACHE)

    canvas = Image.open(bg_path).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE))
    icon_resized = icon_image.resize((400, 400), Image.LANCZOS)
    canvas.paste(icon_resized, ((canvas.width - icon_resized.width) // 2, (canvas.height - icon_resized.height) // 2), icon_resized)

    ammo_data = props.get("AmmoData")
    ammo_asset = ammo_data.get("AssetPathName") if isinstance(ammo_data, dict) else None
    ammo_key = ammo_asset.split("/")[-1].split(".")[0] if isinstance(ammo_asset, str) and ammo_asset else None
    ammo_icon_name = AMMO_ICON_MAP.get(ammo_key) if ammo_key else None
    if ammo_icon_name:
        ammo_path = AMMO_ICON_DIR / ammo_icon_name
        if ammo_path.exists():
            try:
                ammo_icon = Image.open(ammo_path).convert("RGBA").resize((30, 30), Image.LANCZOS)
                canvas.paste(ammo_icon, (canvas.width - 35, 10), ammo_icon)
            except Exception:
                pass

    stats = get_weapon_stats(props) if DRAW_STATS else None
    if stats:
        overlay_stat_template_with_numbers(canvas, stats)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([(0, 500), (canvas.width, 600)], fill=(0, 0, 0, 128))
    canvas = Image.alpha_composite(canvas, overlay)

    draw = ImageDraw.Draw(canvas)
    rarity_icon_path = RARITY_ICON_DIR / f"{rarity}.png"
    if rarity_icon_path.exists():
        try:
            rarity_icon = Image.open(rarity_icon_path).convert("RGBA")
            target_h = 32
            target_w = int(target_h * rarity_icon.width / rarity_icon.height)
            rarity_icon = rarity_icon.resize((target_w, target_h), Image.LANCZOS)
            canvas.paste(rarity_icon, ((canvas.width - target_w) // 2, 515), rarity_icon)
        except Exception:
            pass

    font = fit_font(draw, weapon_name, canvas.width - 40)
    bbox = draw.textbbox((0, 0), weapon_name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_y = 500 + (100 - text_h) // 2 + 14
    draw.text(((canvas.width - text_w) // 2, text_y), weapon_name, font=font, fill="white")

    border_color = RARITY_BORDER_COLORS.get(rarity, "#ffffff")
    draw.rectangle([(0, 0), (canvas.width - 1, canvas.height - 1)], outline=border_color, width=2)

    IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    log(f"[✔] 生成: {out_path}")


def iter_input_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def extract_assets_from_json(data) -> list[str]:
    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        assets: list[str] = []
        for item in data:
            assets.extend(extract_assets_from_json(item))
        return assets
    if isinstance(data, dict):
        value = data.get("AssetPathName")
        if isinstance(value, str) and value.strip():
            return [value]
    return []


def read_assets(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if suffix == ".json":
        try:
            return [item.strip() for item in extract_assets_from_json(json.loads(path.read_text(encoding="utf-8"))) if item.strip()]
        except Exception:
            return []
    if suffix == ".csv":
        assets: list[str] = []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames and "AssetPathName" in reader.fieldnames:
                    for row in reader:
                        value = (row.get("AssetPathName") or "").strip()
                        if value:
                            assets.append(value)
                    return assets
        except Exception:
            pass
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip().split(",", 1)[0].strip()
            if value and value != "AssetPathName":
                assets.append(value)
        return assets
    return []


def collect_assets(root: Path) -> list[str]:
    files = iter_input_files(root)
    if not files:
        return []

    seen: set[str] = set()
    assets: list[str] = []
    for path in files:
        current = read_assets(path)
        log(f"[input] {path.relative_to(root)}: {len(current)}件")
        for asset in current:
            norm = normalize_asset_path(asset)
            if norm and norm not in seen:
                seen.add(norm)
                assets.append(norm)
            elif norm:
                log(f"[skip] 重複: {norm}")
    return assets


def main() -> int:
    if not TARGET_DIR.exists():
        log(f"[!] フォルダが見つかりません: {TARGET_DIR}")
        return 1

    log(f"[info] 対象フォルダ: {TARGET_DIR}")
    log(f"[info] 出力先: {IMAGE_OUTPUT_DIR}")
    log(f"[info] キャッシュ: {CACHE_DIR}")
    assets = collect_assets(TARGET_DIR)
    if not assets:
        log(f"[!] AssetPathName が見つかりません: {TARGET_DIR}")
        return 1

    log(f"[info] 対象武器数: {len(assets)}")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(generate_weapon_card, asset) for asset in assets]
        for _ in as_completed(futures):
            pass

    log(f"[✓] 完了: {IMAGE_OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
