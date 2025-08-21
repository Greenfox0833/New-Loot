# ============================
# 戦利品まとめ + ローカライズ + 画像生成（Loot/TierGroup→WorldListごと保存） 完全版
# ============================

import os
import re
import json
import atexit
import threading
import time
from io import BytesIO
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from PIL import Image, ImageDraw, ImageFont

# ---------------- 設定（要調整） ----------------
DRAW_STATS = False  # ステータスを描画するか（True/False）
SHOW_PERCENT = False  # パーセントを描画するか（True/False）
DO_HOTFIX = True  # Hotfixを適用するか（True/False）
ENABLE_IMAGE_CREATION = False  # 画像生成を有効にするか（True/False）
DEBUG_LOCALIZE = False  # ローカライズ取得のデバッグログを出力するか（True/False）
VERSION_PREFIX = "v37.00"

# ---------------- 設定に追加 ----------------
# 特別計算ルール: (RowName, ValidLootPackages.ID) のタプルで指定
# True = Percent×(Weight÷TotalListWeight)
# False = (Weight÷TotalListWeight)×100
SPECIAL_LIST_PERCENT_RULES = {
    "Loot_AthenaFloorLoot": {
        "WorldPKG.AthenaLoot.Weapon.Shotgun.01",
        "WorldPKG.AthenaLoot.Weapon.Handgun.01",
        "WorldPKG.AthenaLoot.Weapon.SMG",
        "WorldPKG.AthenaLoot.Weapon.AssaultAuto.01",
        "WorldPKG.AthenaLoot.Weapon.Sniper.01",
        "WorldPKG.AthenaLoot.Weapon.Rocket.01",
        "WorldPKG.AthenaLoot.Consumable.01",
        "WorldPKG.AthenaLoot.Ammo",
        "WorldPKG.AthenaLoot.Resources",
        "WorldList.AthenaLoot.Empty",
    },
    "Loot_AthenaTreasure": {
        "WorldPKG.AthenaLoot.Weapon.HighShotgun.01",
        "WorldPKG.AthenaLoot.Weapon.HighSMG.01",
        "WorldPKG.AthenaLoot.Weapon.HighAssaultAuto.01",
        "WorldPKG.AthenaLoot.Weapon.HighSniper.01",
        "WorldPKG.AthenaLoot.Weapon.HighRocket.01",
        "WorldPKG.AthenaLoot.Weapon.HighHandgun.01",
        "WorldPKG.AthenaLoot.Weapon.Exotic.01",
        "WorldPKG.AthenaLoot.Weapon.Mythic.01",
    },
    "Loot_ApolloTreasure_Rare": {
        "WorldPKG.ApolloLoot.Weapon.HighShotgun.01",
        "WorldPKG.ApolloLoot.Weapon.SMG.01",
        "WorldPKG.ApolloLoot.Weapon.AssaultAuto.01",
        "WorldPKG.ApolloLoot.Weapon.Sniper.01",
        "WorldPKG.ApolloLoot.Weapon.Rocket.01",
        "WorldPKG.ApolloLoot.Weapon.HighHandgun.01",
        "WorldPKG.ApolloLoot.Weapon.Sp.01",
        "WorldPKG.ApolloLoot.Weapon.Ex.01",
        "WorldPKG.ApolloLoot.Weapon.Mythic.01",
        "WorldPKG.MythicRandom.01",
        "WorldPKG.ExoticRandom.01",
        "WorldPKG.MythicGFish.01",
        "WorldPKG.ExoticBundle.01",
        "WorldPKG.ExoticBundle.02",
        "WorldPKG.ExoticBundle.03",
        "WorldPKG.ExoticBundle.04",
        "WorldPKG.ExoticBundle.05"
    },
    "Loot_AthenaSupplyDrop": {
        "WorldPKG.AthenaSupplyDrop.Weapon.Assault.01",
        "WorldPKG.AthenaSupplyDrop.Weapon.Shotgun.01",
        "WorldPKG.AthenaSupplyDrop.Weapon.Handgun.01",
        "WorldPKG.AthenaSupplyDrop.Weapon.SMG.01",
        "WorldPKG.AthenaSupplyDrop.Sp.Weapon.01",
        "WorldPKG.AthenaSupplyDrop.Ex.01",
        "WorldPKG.AthenaSupplyDrop.Mythic.01",
    },
    "LTG_Swarmer": {
        "WorldPKG_Swarmer.01",
        "WorldPKG_Swarmer.02",
        "WorldPKG_Swarmer.03",
    }
}

# --- 生成対象フィルタ（任意） ---
# いずれも None なら無効、セット/リストなら一致したものだけ画像を作る
ONLY_TIERGROUPS = None
ONLY_ROWS = None
ONLY_WORLDLIST_KEYS = None


# 入力（LT/LPのFModelエクスポートJSON）
INPUT_LT_JSON = r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment_NoBuild/FigmentLootTierData__final.json"
INPUT_LP_JSON = r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment_NoBuild/FigmentLootPackages__final.json"

# 画像の保存先（親）:  <OUTPUT_BASE_DIR>/<TierGroup>/<WorldListKey>/ に振り分け保存
OUTPUT_BASE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/v37.00"

# 画像素材など
FONT_PATH = "C:/Windows/Fonts/MSYHBD.TTC"
RARITY_BG_DIR   = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Rarity"
RARITY_ICON_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/icon"
AMMO_ICON_DIR   = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Ammo"
STAT_TEMPLATE_PATH = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Template.png"  # 任意（無ければ描画スキップ）

# スレッド数
MAX_WORKERS = 8

# TierGroupで絞りたい場合は指定
FILTER_TIERGROUP = None  # 例: "Loot_AthenaFloorLoot" など。Noneなら全体

# --- 先にHotfix適用 ---
import subprocess
if DO_HOTFIX:
    subprocess.run(["python", r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment_NoBuild/LootPackage変更.py"], check=True)
    subprocess.run(["python", r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment_NoBuild/LootTier変更.py"], check=True)
# --- Hotfix適用ここまで ---

# リトライ付きHTTPセッション
try:
    from urllib3.util.retry import Retry
except Exception:
    class Retry:
        def __init__(self, total=3, backoff_factor=0.6, status_forcelist=(429,500,502,503,504)):
            self.total=total; self.backoff_factor=backoff_factor; self.status_forcelist=set(status_forcelist)

session = requests.Session()
if 'Retry' in globals():
    retry = Retry(total=3, backoff_factor=0.6,
                  status_forcelist=(429,500,502,503,504),
                  allowed_methods=frozenset(["GET","POST"]))
    # プールサイズ拡大で同時接続を増やす
    adapter = HTTPAdapter(max_retries=retry, pool_connections=64, pool_maxsize=64)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
# Keep-Alive（明示）
session.headers.update({"Connection": "keep-alive"})


# ==== AssetPathName -> 日本語名 キャッシュ ====
ASSET_LOC_CACHE_FILE = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/asset_localize_cache.json"
try:
    with open(ASSET_LOC_CACHE_FILE, "r", encoding="utf-8") as f:
        ASSET_LOC_CACHE = json.load(f)
except FileNotFoundError:
    ASSET_LOC_CACHE = {}

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
    """dirty 件数に関わらず、即座にキャッシュを書き出す"""
    try:
        with open(ASSET_LOC_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ASSET_LOC_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@atexit.register
def _save_asset_loc_cache_on_exit():
    """プロセス終了時、未保存分があれば必ず保存"""
    if _ASSET_LC_STATE.get("dirty", 0) > 0:
        _flush_asset_loc_cache_force()

def fetch_localized_name(key: str) -> str:
    url = "https://export-service.dillyapis.com/v1/export/localize"
    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}
    try:
        r = session.post(url, json=payload, timeout=10)
        if r.ok:
            arr = r.json().get("jsonOutput", [])
            return (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
    except Exception:
        pass
    return "???"

# 追加（Figment/Juno 補正用）
import re as _re_fix

def _drop_suffix_after_dot(p: str) -> str:
    # "/A/B/C.Name" -> "/A/B/C"
    return p.split(".", 1)[0] if "." in p else p

def _insert_content_once(path: str) -> str:
    # 既に /Content/ があればそのまま
    if "/Content/" in path or "/content/" in path:
        return path
    # 最初の Gameplay / Items の直前に Content/ を1回だけ差し込む
    return _re_fix.sub(r"/(Gameplay|Items)/", r"/Content/\1/", path, count=1, flags=_re_fix.IGNORECASE)


# 変更後（Figment/Juno 仕様に対応）
def normalize_asset_path(asset_path: str) -> str:
    if not asset_path:
        return ""
    p = asset_path.strip().replace("\\", "/")
    p = _drop_suffix_after_dot(p)
    p = p.lstrip("/")

    # /Game 系はそのまま
    if p.lower().startswith("game/"):
        return p

    # Figment 系: 先頭 Figment_... をプラグイン実パスへ + Content 挿入
    q = p
    if q.startswith("Figment_"):
        q = f"FortniteGame/Plugins/GameFeatures/Figment/{q}"
        q = _insert_content_once(q)
        return q

    # 既に Figment プラグイン配下だが Content が無い場合は補正
    if "FortniteGame/Plugins/GameFeatures/Figment/" in p and "/Content/" not in p:
        p = _insert_content_once(p)
        return p.lstrip("/")

    # Juno 系（ピンポイント）
    if "JunoBuildingCosmetics" in p:
        head, tail = p.split("JunoBuildingCosmetics/", 1)
        return f"FortniteGame/Plugins/GameFeatures/Juno/JunoBuildingCosmetics/Content/{tail}"

    # Juno/<pack>/... をプラグイン実パスへ + Content 挿入
    if p.startswith("Juno/") or "/Juno/" in "/" + p:
        parts = p.lstrip("/").split("/", 2)  # Juno/<pack>/rest
        if len(parts) >= 2:
            pack = parts[1]
            rest = parts[2] if len(parts) >= 3 else ""
            return f"FortniteGame/Plugins/GameFeatures/Juno/{pack}/Content/{rest}"

    return p

def fetch_export_json(path_like: str) -> dict | None:
    if not path_like: return None
    url = f"https://export-service.dillyapis.com/v1/export?Path={quote(path_like, safe='/._')}"
    try:
        r = session.get(url, timeout=10)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None

# (ユーティリティ：まだ無ければ追加)
def extract_itemname_key(export_json: dict) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr: return None
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


# ===== DataTable（武器ステ） =====
def get_weapon_stats(props):
    try:
        stat_handle = props.get("WeaponStatHandle", {})
        data_table = stat_handle.get("DataTable", {})
        object_path = data_table.get("ObjectPath", "")
        row_name = stat_handle.get("RowName", "")
        if not object_path or not row_name:
            return None
        clean_path = object_path.replace(".0", "").lstrip("/")
        url = f"https://export-service.dillyapis.com/v1/export/?Path={clean_path}"
        response = session.get(url, timeout=30)
        data = response.json()
        json_output = data.get("jsonOutput", {})
        if isinstance(json_output, list):
            json_output = json_output[0]
        rows = json_output.get("Rows", {})
        stat_row = rows.get(row_name, {})
        dmg = stat_row.get("DmgPB", 0)
        bullet_count = stat_row.get("BulletsPerCartridge", 1)
        critical = stat_row.get("DamageZone_Critical", 1.0)
        max_dmg = stat_row.get("MaxDamagePerCartridge", -1)
        firing_rate = stat_row.get("FiringRate", "?")
        if isinstance(firing_rate, (int, float)):
            firing_rate = round(firing_rate, 1)
        reload_time = stat_row.get("ReloadTime", "?")
        if isinstance(reload_time, (int, float)):
            reload_time = round(reload_time, 1)
        clip_size = stat_row.get("ClipSize", "?")
        base_damage = round(dmg * bullet_count)
        headshot = round(base_damage * critical)
        if isinstance(max_dmg, (int, float)) and max_dmg != -1 and headshot > max_dmg:
            headshot = int(max_dmg)
        return {
            "ダメージ": base_damage,
            "建築ダメージ": headshot,
            "連射速度": firing_rate,
            "リロード時間": reload_time,
            "マガジン": clip_size
        }
    except Exception:
        return None

# ===== レアリティ関連 =====
RARITY_MAP = {
    "EFortRarity::Common": "Common",
    "EFortRarity::Uncommon": "Uncommon",
    "EFortRarity::Rare": "Rare",
    "EFortRarity::Epic": "Epic",
    "EFortRarity::Legendary": "Legend",
    "EFortRarity::Mythic": "Mythic",
    "EFortRarity::Transcendent": "Exotic",
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
AMMO_ICON_MAP = {}  # 必要に応じて追記

# ===== 画像合成 =====
def overlay_stat_template_with_numbers(canvas, stats, template_path):
    try:
        if not os.path.exists(template_path):
            return
        template = Image.open(template_path).convert("RGBA")
        canvas.paste(template, (10, 10), template)
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(FONT_PATH, 15)
        values = {
            "ダメージ": f"{stats.get('ダメージ', '?')}({stats.get('建築ダメージ', '?')})",
            "連射速度": f"{stats.get('連射速度', '?')}/s",
            "リロード時間": f"{stats.get('リロード時間', '?')}s",
            "マガジン": f"{stats.get('マガジン', '?')}"
        }
        positions = {
            "ダメージ": (65, 28),
            "連射速度": (190, 28),
            "リロード時間": (285, 28),
            "マガジン": (380, 28),
        }
        for key, (x, y) in positions.items():
            draw.text((x, y), values.get(key, "?"), font=font, fill="white")
    except Exception:
        pass

def fit_font(draw, text, width, max_size=28, min_size=14):
    for sz in range(max_size, min_size-1, -1):
        font = ImageFont.truetype(FONT_PATH, sz)
        w = draw.textlength(text, font=font)
        if w <= width:
            return font
    return ImageFont.truetype(FONT_PATH, min_size)

def draw_percent_badge(canvas, text):
    # 右上に半透明バッジでパーセント表示（"12.34%" など）
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_PATH, 18)
    pad = 8
    tw = draw.textlength(text, font=font)
    th = 22
    x1 = canvas.width - tw - pad*2 - 10
    y1 = 10
    x2 = canvas.width - 10
    y2 = y1 + th + pad
    overlay = Image.new("RGBA", canvas.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([x1, y1, x2, y2], fill=(0,0,0,140))
    canvas.alpha_composite(overlay)
    draw.text((x2 - tw - pad, y1 + (th - 16)//2), text, font=font, fill="white")


def generate_weapon_card_from_export(weapon_json, asset_path: str, out_dir: str, list_percent_text: str | None):
    try:
        jo = weapon_json["jsonOutput"]
        data = jo[0] if isinstance(jo, list) else jo
        props = data["Properties"]

        # レアリティ
        raw_rarity = props.get("Rarity")
        rarity = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"

        # 名前（ローカライズ）
        weapon_name = get_name_by_asset(asset_path)
        if weapon_name == "???":
            # フォールバック（既存キーキャッシュ or 元文字列）
            item_key = props.get("ItemName", {}).get("key", "")
            if item_key:
                weapon_name = fetch_localized_name(item_key)
            else:
                weapon_name = props.get("ItemName", {}).get("sourceString", "???")

        # アイコンパス（LargeIcon を DataList 全体で最優先）
        icon_path = None
        data_list = props.get("DataList", [])

        def _get(entry, key):
            return (entry.get(key) or {}).get("AssetPathName") if isinstance(entry, dict) else None

        if isinstance(data_list, dict):
            # dict の場合はシンプルに LargeIcon -> Icon
            icon_path = _get(data_list, "LargeIcon") or _get(data_list, "Icon")

        elif isinstance(data_list, list):
            # Pass 1: DataList 全体から LargeIcon を探す（最優先）
            for entry in data_list:
                p = _get(entry, "LargeIcon")
                if p and isinstance(p, str) and p.strip():
                    icon_path = p
                    break
            # Pass 2: LargeIcon が見つからなければ Icon を探す
            if not icon_path:
                for entry in data_list:
                    p = _get(entry, "Icon")
                    if p and isinstance(p, str) and p.strip():
                        icon_path = p
                        break

        # 最後のフォールバック：Properties 直下の LargeIcon / Icon
        if not icon_path:
            icon_path = _get(props, "LargeIcon") or _get(props, "Icon")

        if not icon_path:
            return

        # 背景
        canvas_size = 600
        bg_path = os.path.join(RARITY_BG_DIR, f"{rarity}.png")
        try:
            bg_image = Image.open(bg_path).convert("RGBA").resize((canvas_size, canvas_size))
        except Exception:
            return
        canvas = bg_image.copy()

        # 弾薬アイコン（任意）
        ammo_data = props.get("AmmoData")
        if ammo_data and "AssetPathName" in ammo_data:
            ammo_key = ammo_data["AssetPathName"].split("/")[-1].split(".")[0]
            ammo_icon_filename = AMMO_ICON_MAP.get(ammo_key)
            if ammo_icon_filename:
                ammo_icon_path = os.path.join(AMMO_ICON_DIR, ammo_icon_filename)
                if os.path.exists(ammo_icon_path):
                    try:
                        ammo_icon = Image.open(ammo_icon_path).convert("RGBA").resize((30, 30), Image.LANCZOS)
                        canvas.paste(ammo_icon, (canvas.width - 35, 10), ammo_icon)
                    except Exception:
                        pass

        # アイテムアイコンを合成（中央）
        try:
            icon_clean = normalize_asset_path(icon_path)
            icon_url = f"https://export-service.dillyapis.com/v1/export/?Path={icon_clean}"
            icon_response = session.get(icon_url, timeout=10)
            icon_image = Image.open(BytesIO(icon_response.content)).convert("RGBA")
        except Exception:
            return
        icon_resized = icon_image.resize((400, 400), resample=Image.LANCZOS)
        pos_x = (canvas.width - icon_resized.width) // 2
        pos_y = (canvas.height - icon_resized.height) // 2
        canvas.paste(icon_resized, (pos_x, pos_y), icon_resized)

        # ステータス（フラグで制御）
        if DRAW_STATS:
            stats = get_weapon_stats(props)
            if stats:
                overlay_stat_template_with_numbers(canvas, stats, STAT_TEMPLATE_PATH)

        # 下部バー（半透明）
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([(0, 500), (canvas.width, 600)], fill=(0, 0, 0, 128))
        canvas = Image.alpha_composite(canvas, overlay)

        draw = ImageDraw.Draw(canvas)

        # レアリティアイコン（テキストより先に描画して、文字が上に来るようにする）
        rarity_icon_path = os.path.join(RARITY_ICON_DIR, f"{rarity}.png")
        if os.path.exists(rarity_icon_path):
            try:
                rimg = Image.open(rarity_icon_path).convert("RGBA")
                target_h = 32
                tw = int(target_h * rimg.width / rimg.height)
                rimg = rimg.resize((tw, target_h), Image.LANCZOS)
                canvas.paste(rimg, ((canvas.width - tw)//2, 515), rimg)
            except Exception:
                pass

        # アイテム名（最後に描画して最前面にする）
        font = fit_font(draw, weapon_name, canvas.width - 40, max_size=28, min_size=14)
        bbox = draw.textbbox((0, 0), weapon_name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_y = 500 + (100 - text_h)//2 + 14
        draw.text(((canvas.width - text_w)//2, text_y), weapon_name, font=font, fill="white")

        # 右上パーセント表示
        if SHOW_PERCENT and list_percent_text:
            draw_percent_badge(canvas, list_percent_text)

        # 枠線
        border_color = RARITY_BORDER_COLORS.get(rarity, "#ffffff")
        draw.rectangle([(0, 0), (canvas.width - 1, canvas.height - 1)], outline=border_color, width=2)

        # 保存
        weapon_id = re.sub(r'[\\/:"*?<>|]', "_", data.get("Name", "Unknown"))
        safe_weapon_name = re.sub(r'[\\/:"*?<>|]', "_", weapon_name)
        filename = f"{weapon_id} - {safe_weapon_name}.png"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        if os.path.exists(out_path):
            return
        canvas.save(out_path)
        print(f"[✔] 生成: {out_path}")
    except Exception as e:
        print(f"[×] カード生成失敗: {e}")

def get_name_by_asset(asset_path: str) -> str:
    """
    AssetPathName を主キーに日本語名を返す。
    1) ASSET_LOC_CACHE を最優先
    2) 無ければ 1回だけ Export → ItemName.key を抽出
    3) key が取れたら LOCALIZE_CACHE を優先参照、無ければ get_localized_name()
    4) 結果を ASSET_LOC_CACHE に保存（以後はキーを読まずに即ヒット）
    """
    if not asset_path:
        return "???"
    norm = normalize_asset_path(asset_path)

    # 1) Assetキャッシュ
    hit = ASSET_LOC_CACHE.get(norm)
    if hit:
        if DEBUG_LOCALIZE:
            print(f"[asset-loc:CACHE] {norm} -> {hit}")
        return hit

    # 2) 初回だけ Export → ItemKey 抽出
    export_json = export_by_asset_path(asset_path)
    if not export_json:
        ASSET_LOC_CACHE[norm] = "???"
        _ASSET_LC_STATE["dirty"] += 1
        _flush_asset_loc_cache_if_needed()
        return "???"

    key = extract_itemname_key(export_json)
    if key:
        # 直接 API で日本語名を取得
        name = fetch_localized_name(key)  # 新しく軽量API呼び出し関数を作る
        ASSET_LOC_CACHE[norm] = name or "???"
        _ASSET_LC_STATE["dirty"] += 1
        _flush_asset_loc_cache_if_needed()
        return ASSET_LOC_CACHE[norm]

    # keyが取れなかった場合
    ASSET_LOC_CACHE[norm] = "???"
    _ASSET_LC_STATE["dirty"] += 1
    _flush_asset_loc_cache_if_needed()
    return "???"

def enrich_summary_with_names(summary: dict):
    """
    summary に日本語名を後付けする（ビルド後の一括処理）。
    - 各 ListItem に Name_JA を追加
    - 各 item に代表名 ItemName_JA を追加（最初に見つかったアセット名を代表に）
    ※ 取得は get_name_by_asset() を使うため、ASSET_LOC_CACHE が優先され、
      未解決のみ Export/Localize が走る（重複アクセスは発生しない）
    """
    if not isinstance(summary, dict) or not summary:
        return

    # 1) すべての AssetPath を重複排除で収集 ＆ 各 item の代表AssetPathも控える
    assets = set()
    item_first_asset = {}  # id(item) -> norm_asset_path

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


    # 2) まとめて名前解決（ASSET_LOC_CACHE 優先。未ヒットのみHTTP）
    for ap in assets:
        try:
            _ = get_name_by_asset(ap)
        except Exception:
            pass

    # 3) 反映：ListItems[].Name_JA と item.ItemName_JA
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
                        # 既存は "Localized" だが、サンプルに合わせるなら "LocalizedName" にする：
                        li["LocalizedName"] = ASSET_LOC_CACHE.get(norm, "???")


def export_by_asset_path(asset_path: str) -> dict | None:
    clean = normalize_asset_path(asset_path)
    return fetch_export_json(clean)

# ===== まとめ生成（LT/LP → summary.json） =====
def load_rows(path: str, rows_key: str = "Rows"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    obj = data[0] if isinstance(data, list) else data
    return obj.get(rows_key, {})

import re as _re
_num_suffix = _re.compile(r".*?\.([0-9]{2})$")
def key_suffix_num(key: str) -> int:
    m = _num_suffix.match(key)
    return int(m.group(1)) if m else 0

def _asset_path_from_row(row: dict) -> str:
    """ItemDefinition が dict/str/None のどれでも安全に AssetPathName を返す"""
    idf = row.get("ItemDefinition")
    if isinstance(idf, dict):
        return idf.get("AssetPathName", "") or ""
    if isinstance(idf, str):
        return idf
    return ""

def build_summary(rows_lt: dict, rows_lp: dict):
    id_to_call = {k: v.get("LootPackageCall", "") for k, v in rows_lp.items()}


        # (LootPackageID, LootPackageCategory) -> [.NN行…] の索引
    lp_by_idcat = defaultdict(list)
    for row_key, row in rows_lp.items():
        lp_id = row.get("LootPackageID", "")
        lp_cat = row.get("LootPackageCategory", 0)
        try:
            lp_cat = int(lp_cat)
        except Exception:
            lp_cat = 0
        lp_call   = row.get("LootPackageCall", "") or ""
        lp_weight = row.get("Weight", 0.0)

        lp_by_idcat[(lp_id, lp_cat)].append({
            "Key": row_key,      # 例: WorldPKG.AthenaLoot.Weapon.HighShotgun.03
            "Call": lp_call,     # 例: WorldList.AthenaHighConsumables
            "Weight": lp_weight, # LP行のWeight（Packagesに書く）
        })

    # .NN の昇順で安定化
    for k in lp_by_idcat:
        lp_by_idcat[k].sort(key=lambda d: key_suffix_num(d["Key"]))


    # WorldList.* の中身（重み＆AssetPath）
    worldlist_map = defaultdict(list)
    for row_key, row in rows_lp.items():
        if not isinstance(row, dict):
            continue  # 行そのものがdictじゃない場合はスキップ（任意）
        wl_id = row.get("LootPackageID", "")
        worldlist_map[wl_id].append({
            "Key": row_key,
            "Weight": row.get("Weight", 0.0),
            "AssetPathName": _asset_path_from_row(row),
            # 追加: このリスト行の CountRange.X を保持（無ければ None）
            "CountItem": (row.get("CountRange") or {}).get("X")
        })



    for wl_id in worldlist_map:
        worldlist_map[wl_id].sort(key=lambda x: key_suffix_num(x["Key"]))

    by_group = defaultdict(list)

    for row_name, row in rows_lt.items():
        tg = row.get("TierGroup", "")
        if not tg or (FILTER_TIERGROUP and tg != FILTER_TIERGROUP):
            continue
        if row.get("Weight", 0.0) == 0.0:
            continue

        loot_pkg = row.get("LootPackage", "")
        weight_array = row.get("LootPackageCategoryMinArray", [])

                # LootNumber 構造（Category の内容を導入）
        valid_groups = []
        min_array = row.get("LootPackageCategoryMinArray", [])
        for ln, val in enumerate(min_array):  # LootNumber = 0,1,2,...
            if val >= 1:
                matches = lp_by_idcat.get((loot_pkg, ln), [])
                packages = []
                for m in matches:
                    call = m["Call"]

                    # ListItems（Weight>0 & AssetPathNameありのみ）
                    list_items = []
                    if call:
                        # '.' / '_' ゆれは不要なら省略可（必要なら keys = (call, call.replace(".", "_"), call.replace("_", ".")) で回す）
                        for c in worldlist_map.get(call, []):
                            if c["Weight"] > 0.0 and c.get("AssetPathName"):
                                list_items.append({
                                    "Weight": c["Weight"],
                                    "AssetPathName": c["AssetPathName"],
                                    "CountItem": c.get("CountItem"),
                                })

                    total_list_weight = sum(li["Weight"] for li in list_items) if list_items else 0.0

                    packages.append({
                        "ID": m["Key"],                 # 例: WorldPKG.AthenaLoot.Weapon.HighShotgun.03
                        "Call": call,
                        "Count": int(val),              # MinArray の値
                        "weight": round(m["Weight"], 6),# ← 各WorldPKG(.NN)のWeightを付与
                        "TotalListWeight": round(total_list_weight, 6),
                        "ListItems": list_items
                    })

                if packages:
                    valid_groups.append({
                        "LootNumber": ln,
                        "Packages": packages
                    })

        entry = {
            "RowName": row_name,
            "Weight": round(row.get("Weight", 0.0), 6),
            "LootPackage": loot_pkg
        }
        if valid_groups:
            entry["ValidLootPackages"] = valid_groups
        by_group[tg].append(entry)

    # 整形（Percent, ListPercent）
    result = {}
    for tg, items in sorted(by_group.items()):
        total_weight = sum(item.get("Weight", 0.0) for item in items)
        for idx, item in enumerate(items):
            percent = round((item["Weight"] / total_weight) * 100, 4) if total_weight else 0.0
            if "ValidLootPackages" in item:
                for group in item["ValidLootPackages"]:
                    for v_pkg in group.get("Packages", []):
                        tw = v_pkg.get("TotalListWeight", 0.0)
                        new_list_items = []

                        # SPECIAL 判定は v_pkg["ID"]（= 各 .NN のID）で行う
                        targets = SPECIAL_LIST_PERCENT_RULES.get(tg, set())
                        full_id = v_pkg.get("ID", "")
                        m = re.match(r"^(.*)\.(\d{2})$", full_id)
                        family = m.group(1) if m else full_id
                        exact = {t for t in targets if re.search(r"\.\d{2}$", t)}
                        families = {t for t in targets if not re.search(r"\.\d{2}$", t)}
                        use_special = (full_id in exact) or any(family.startswith(t) for t in families)

                        # 追加：パッケージの weight（小文字優先、無ければ大文字Weight）
                        pkg_weight = v_pkg.get("weight", v_pkg.get("Weight", 0.0))

                        for li in v_pkg.get("ListItems", []):
                            if tw > 0:
                                if use_special:
                                    # SPECIAL かつ percent==100 → weight * (li/tw)
                                    if percent == 100:
                                        list_percent = round(pkg_weight * (li["Weight"] / tw)*100, 4)
                                    else:
                                        list_percent = round(percent * (li["Weight"] / tw), 4)
                                else:
                                    list_percent = round((li["Weight"] / tw) * 100, 4)
                            else:
                                list_percent = 0.0

                            asset_path = li.get("AssetPathName")
                            new_list_items.append({
                                "Weight": li["Weight"],
                                "ListPercent": list_percent,
                                "AssetPathName": asset_path,
                                "CountItem": li.get("CountItem")
                            })

                        v_pkg["ListItems"] = new_list_items

            ordered = {
                "RowName": item["RowName"],
                "Weight": item["Weight"],
                "Percent": percent
            }
            for k, v in item.items():
                if k not in ("RowName", "Weight"):
                    ordered[k] = v
            items[idx] = ordered
        result[tg] = {"TotalWeight": round(total_weight, 6), "Items": items}
    return result

def _allow_emit(tg: str, rowname: str, worldlist_key: str) -> bool:
    if ONLY_TIERGROUPS and tg not in ONLY_TIERGROUPS:
        return False
    if ONLY_ROWS and rowname not in ONLY_ROWS:
        return False
    if ONLY_WORLDLIST_KEYS and worldlist_key not in ONLY_WORLDLIST_KEYS:
        return False
    return True


# ===== summary から画像化タスクを作る（TierGroup/WorldListごと保存先） =====
def iter_tasks_from_summary(summary: dict):
    """
    yield (asset_path, out_dir, list_percent_text)
    out_dir = OUTPUT_BASE_DIR / <TierGroup> / <WorldListKey>
    """
    for tiergroup, tg_block in summary.items():
        items = tg_block.get("Items", [])
        for item in items:
            rowname = item.get("RowName", "")
            for group in item.get("ValidLootPackages", []):
                for v_pkg in group.get("Packages", []):
                    worldlist_key = v_pkg.get("Call") or "_NoWorldList"
                    if not _allow_emit(tiergroup, rowname, worldlist_key):
                        continue
                    out_dir = os.path.join(OUTPUT_BASE_DIR, tiergroup, worldlist_key)
                    for li in v_pkg.get("ListItems", []):
                        ap = li.get("AssetPathName")
                        if not ap:
                            continue
                        lp = li.get("ListPercent", 0.0)
                        txt = f"{lp:.2f}%" if SHOW_PERCENT else None
                        yield (ap, out_dir, txt)

def worker_task(asset_path: str, out_dir: str, list_percent_text: str | None):
    wjson = export_by_asset_path(asset_path)
    if not wjson:
        return
    # 保存先に同名があればスキップ（軽減）
    try:
        jo = wjson["jsonOutput"]
        data = jo[0] if isinstance(jo, list) else jo
        weapon_id = re.sub(r'[\\/:"*?<>|]', "_", data.get("Name", "Unknown"))
        loc = get_name_by_asset(asset_path)  # Asset キャッシュ優先
        if loc == "???":
            # 念のためのフォールバック（既存キーキャッシュ）
            item_key = data.get("Properties", {}).get("ItemName", {}).get("key", "")
            if loc == "???" and item_key:
                loc = fetch_localized_name(item_key)

        safe = re.sub(r'[\\/:"*?<>|]', "_", loc)
        filename = f"{weapon_id} - {safe}.png"
        os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(os.path.join(out_dir, filename)):
            return
    except Exception:
        pass
    if ENABLE_IMAGE_CREATION:
        generate_weapon_card_from_export(wjson, asset_path, out_dir, list_percent_text)
    else:
        print(f"[SKIP] 画像作成をスキップ: {asset_path}")

from datetime import datetime

def get_versioned_filename(prefix, save_dir):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")  # 例: 2025-08-20_23-25
    filename = save_dir / f"{prefix}_{now}.json"
    return str(filename)


def main():
    # 1) まとめ作成
    rows_lt = load_rows(INPUT_LT_JSON)
    rows_lp = load_rows(INPUT_LP_JSON)
    summary = build_summary(rows_lt, rows_lp)

    # 2) Localized 名を後付け（必ず実行）
    enrich_summary_with_names(summary)

    # 3) JSON保存（常に実行）
    versioned_filename = get_versioned_filename(
        VERSION_PREFIX,
        r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/Figment_NoBuild"
    )
    Path(versioned_filename).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"✅ JSONファイルを作成しました: {versioned_filename}")

    # 4) 画像生成（フラグで可否を切替）
    if not ENABLE_IMAGE_CREATION:
        return  # ← ここで終了。以降の画像処理は走らない

    # タスク収集（TierGroup/WorldListごと保存）
    tasks = list(iter_tasks_from_summary(summary))

    # 重複除去（同じAssetPathName + 同じ保存先）
    uniq = []
    seen = set()
    for ap, od, txt in tasks:
        key = (normalize_asset_path(ap), od)
        if key not in seen:
            seen.add(key)
            uniq.append((ap, od, txt))
    print(f"[i] 画像化タスク数: {len(uniq)}")

    # 4) 並列生成
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(worker_task, ap, od, txt) for ap, od, txt in uniq]
        for _ in as_completed(futs):
            pass
    print("✅ 画像生成 完了（TierGroup/WorldListごとに保存）")

if __name__ == "__main__":
    main()
