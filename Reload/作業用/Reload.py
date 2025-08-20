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
DO_HOTFIX = False  # Hotfixを適用するか（True/False）
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
        "WorldPKG.MythicRandom.01",
        "WorldPKG.ExoticRandom.01",
        "WorldPKG.MythicGFish.01",
        "WorldPKG.ExoticBundle.01",
        "WorldPKG.ExoticBundle.02",
        "WorldPKG.ExoticBundle.03",
        "WorldPKG.ExoticBundle.04",
        "WorldPKG.ExoticBundle.05"
    },
    "Loot_ApolloTreasure_Rare": {
        "WorldPKG.ApolloLoot.Weapon.HighShotgun.01",
        "WorldPKG.ApolloLoot.Weapon.SMG.01",
        "WorldPKG.ApolloLoot.Weapon.AssaultAuto.01",
        "WorldPKG.ApolloLoot.Weapon.Sniper.01",
        "WorldPKG.ApolloLoot.Weapon.Rocket.01",
        "WorldPKG.ApolloLoot.Weapon.HighHandgun.01",
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
        "WorldPKG.BlastBerrySupply.01",
        "WorldPKG.BlastBerrySupply.02",
        "WorldPKG.BlastBerrySupply.03",
        "WorldPKG.BlastBerrySupply.04",
        "WorldPKG.BlastBerrySupply.05",
        "WorldPKG.BlastBerrySupply.06",
        "WorldPKG.BlastBerrySupply.07",
        "WorldPKG.MythicRandomSupply.01",
        "WorldPKG.MythicRandomSupply.02",
        "WorldPKG.MythicRandomSupply.03",
        "WorldPKG.MythicRandomSupply.04",
        "WorldPKG.MythicRandomSupply.05",
        "WorldPKG.MythicRandomSupply.06",
        "WorldPKG.MythicRandomSupply.07",
        "WorldPKG.ExoticRandomSupply.01",
        "WorldPKG.ExoticRandomSupply.02",
        "WorldPKG.ExoticRandomSupply.03",
        "WorldPKG.ExoticRandomSupply.04",
        "WorldPKG.ExoticRandomSupply.05",
        "WorldPKG.ExoticRandomSupply.06",
        "WorldPKG.ExoticRandomSupply.07",
        "WorldPKG.MythicGFishSupply.01",
        "WorldPKG.MythicGFishSupply.02",
        "WorldPKG.MythicGFishSupply.03",
        "WorldPKG.MythicGFishSupply.04",
        "WorldPKG.MythicGFishSupply.05",
        "WorldPKG.MythicGFishSupply.06",
        "WorldPKG.MythicGFishSupply.07",
        "WorldPKG.ExoticBundleSupply.01",
        "WorldPKG.ExoticBundleSupply.02",
        "WorldPKG.ExoticBundleSupply.03",
        "WorldPKG.ExoticBundleSupply.04",
        "WorldPKG.ExoticBundleSupply.05",
    }
}
# 入力（LT/LPのFModelエクスポートJSON）
INPUT_LT_JSON = r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/Updated_LootTier.json"
INPUT_LP_JSON = r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/Updated_LootPackages.json"

# まとめ出力（summary.json）
OUTPUT_JSON = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/summary.json"

# 画像の保存先（親）:  <OUTPUT_BASE_DIR>/<TierGroup>/<WorldListKey>/ に振り分け保存
OUTPUT_BASE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/v37.00"

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
    subprocess.run(["python", r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/LootPackage更新.py"], check=True)
    subprocess.run(["python", r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/LootTier更新.py"], check=True)
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


# ===== ローカライズ（高速キャッシュ版・global不使用） =====
LOCALIZE_CACHE_FILE = "localize_cache.json"

try:
    with open(LOCALIZE_CACHE_FILE, "r", encoding="utf-8") as f:
        LOCALIZE_CACHE = json.load(f)
except FileNotFoundError:
    LOCALIZE_CACHE = {}

_cache_lock = threading.Lock()
_serialize_lock = threading.Lock()
_LC_STATE = {"dirty": 0}  # フラッシュ管理（global不要）

def _flush_localize_cache_if_needed(threshold: int = 200):
    """一定件数キャッシュを書いたらディスクへフラッシュ"""
    if _LC_STATE["dirty"] >= threshold:
        _LC_STATE["dirty"] = 0
        try:
            with _serialize_lock, open(LOCALIZE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(LOCALIZE_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def get_localized_name(key: str) -> str:
    """単体キーの日本語を取得（キャッシュ→API、取得結果は保存）"""
    if not key:
        return "???"

    with _cache_lock:
        hit = LOCALIZE_CACHE.get(key)
    if hit is not None:
        if DEBUG_LOCALIZE:
            print(f"[loc:CACHE] {key} -> {hit}")
        return hit

    url = "https://export-service.dillyapis.com/v1/export/localize"
    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}

    # 軽いリトライ
    for attempt in range(3):
        try:
            r = session.post(url, json=payload, timeout=10)
            if r.ok:
                arr = r.json().get("jsonOutput", [])
                value = (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
                with _cache_lock:
                    LOCALIZE_CACHE[key] = value
                if DEBUG_LOCALIZE:
                    tag = "OK" if value != "???" else "NG"
                    print(f"[loc:{tag}] {key} -> {value}")
                _LC_STATE["dirty"] += 1
                _flush_localize_cache_if_needed()
                return value
        except Exception:
            pass
        time.sleep(0.6 * (attempt + 1))  # 429/5xx想定の待機

    # 失敗時も「???」で埋めて次回以降は即返す
    with _cache_lock:
        if key not in LOCALIZE_CACHE:
            LOCALIZE_CACHE[key] = "???"
            _LC_STATE["dirty"] += 1
            _flush_localize_cache_if_needed()
    if DEBUG_LOCALIZE:
        print(f"[loc:FAIL] {key} -> ???")
    return "???"

def get_localized_batch(keys: list[str], chunk: int = 150):
    if not keys:
        return

    # まず未取得キーだけ抽出
    with _cache_lock:
        todo = [k for k in keys if k and (k not in LOCALIZE_CACHE)]
    if not todo:
        return

    url = "https://export-service.dillyapis.com/v1/export/localize"

    for i in range(0, len(todo), chunk):
        batch = todo[i:i+chunk]
        payload = {"culture": "ja", "ns": "", "values": [{"key": k} for k in batch]}
        resp = None
        for attempt in range(3):
            try:
                r = session.post(url, json=payload, timeout=15)
                if r.ok:
                    resp = r.json()
                    break
            except Exception:
                pass
            time.sleep(0.6 * (attempt + 1))

        if resp is None:
            # この塊は諦めて「???」で埋める
            with _cache_lock:
                for k in batch:
                    if k not in LOCALIZE_CACHE:
                        LOCALIZE_CACHE[k] = "???"
            _LC_STATE["dirty"] += len(batch)
            _flush_localize_cache_if_needed()
            if DEBUG_LOCALIZE:
                print(f"[loc:BATCH FAIL] {len(batch)} keys -> all ???")
            continue

        arr = resp.get("jsonOutput", []) or []
        # key->value マップ（順序に依存しない）
        got = {}
        for obj in arr:
            if isinstance(obj, dict):
                k = obj.get("key")
                v = obj.get("value") or "???"
                if k:
                    got[k] = v

        with _cache_lock:
            for k in batch:
                LOCALIZE_CACHE[k] = got.get(k, "???")

        if DEBUG_LOCALIZE:
            ok_cnt = sum(1 for k in batch if LOCALIZE_CACHE.get(k) != "???")
            print(f"[loc:BATCH OK] {ok_cnt}/{len(batch)} resolved")

        _LC_STATE["dirty"] += len(batch)
        _flush_localize_cache_if_needed()

# ==== AssetPathName -> 日本語名 キャッシュ ====
ASSET_LOC_CACHE_FILE = "asset_localize_cache.json"
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

# ===== Export API ヘルパ =====
def normalize_asset_path(asset_path: str) -> str:
    if not asset_path: return ""
    return asset_path.strip().split(".", 1)[0]  # ".以降カット"

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
            if item_key and item_key in LOCALIZE_CACHE:
                weapon_name = LOCALIZE_CACHE[item_key]
            elif item_key:
                weapon_name = get_localized_name(item_key)
            else:
                weapon_name = props.get("ItemName", {}).get("sourceString", "???")

        # アイコンパス
        icon_path = None
        data_list = props.get("DataList", [])
        def pick_icon(entry):
            if isinstance(entry, dict):
                if "LargeIcon" in entry and "AssetPathName" in entry["LargeIcon"]:
                    return entry["LargeIcon"]["AssetPathName"]
            return None
        if isinstance(data_list, dict):
            icon_path = pick_icon(data_list)
        elif isinstance(data_list, list):
            for entry in data_list:
                icon_path = pick_icon(entry)
                if icon_path: break
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
            icon_clean = icon_path.strip("/").split(".")[0]
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
        # 3) 既存のキーキャッシュを優先
        name = LOCALIZE_CACHE.get(key)
        if not name:
            name = get_localized_name(key)  # ミス時だけAPI
        # 4) Asset側にも保存
        ASSET_LOC_CACHE[norm] = name or "???"
        _ASSET_LC_STATE["dirty"] += 1
        _flush_asset_loc_cache_if_needed()
        if DEBUG_LOCALIZE:
            print(f"[asset-loc:SET] {norm} -> {ASSET_LOC_CACHE[norm]}")
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
            for v_pkg in item.get("ValidLootPackages", []) or []:
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
            for v_pkg in item.get("ValidLootPackages", []) or []:
                for li in v_pkg.get("ListItems", []) or []:
                    ap = li.get("AssetPathName")
                    if not ap:
                        continue
                    norm = normalize_asset_path(ap)
                    li["Localized"] = ASSET_LOC_CACHE.get(norm, "???")

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

def build_summary(rows_lt: dict, rows_lp: dict):
    id_to_call = {k: v.get("LootPackageCall", "") for k, v in rows_lp.items()}

    # WorldList.* の中身（重み＆AssetPath）
    worldlist_map = defaultdict(list)
    for row_key, row in rows_lp.items():
        wl_id = row.get("LootPackageID", "")
        worldlist_map[wl_id].append({
            "Key": row_key,
            "Weight": row.get("Weight", 0.0),
            "AssetPathName": row.get("ItemDefinition", {}).get("AssetPathName", ""),
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

        valid_list = []
        for i, bit in enumerate(weight_array, start=1):
            if bit >= 1:
                pkg_id = f"{loot_pkg}.{i:02d}"
                call = id_to_call.get(pkg_id, "")
                list_items = []
                if call:
                    for c in worldlist_map.get(call, []):
                        if c["Weight"] != 0.0:
                            list_items.append({
                                "Weight": c["Weight"],
                                "AssetPathName": c["AssetPathName"],
                                # 追加: worldlist_map に持たせた CountItem を踏襲
                                "CountItem": c.get("CountItem")
                            })
                total_list_weight = sum(li["Weight"] for li in list_items)
                valid_list.append({
                    "ID": pkg_id,
                    "Call": call,
                    "Count": int(bit),
                    "TotalListWeight": round(total_list_weight, 6),
                    "ListItems": list_items
                })


        entry = {
            "RowName": row_name,
            "Weight": round(row.get("Weight", 0.0), 6),
            "LootPackage": loot_pkg
        }
        if valid_list:
            entry["ValidLootPackages"] = valid_list
        by_group[tg].append(entry)

    # 整形（Percent, ListPercent）
    result = {}
    for tg, items in sorted(by_group.items()):
        total_weight = sum(item.get("Weight", 0.0) for item in items)
        for idx, item in enumerate(items):
            percent = round((item["Weight"] / total_weight) * 100, 4) if total_weight else 0.0
            if "ValidLootPackages" in item:
                for v_pkg in item["ValidLootPackages"]:
                    tw = v_pkg.get("TotalListWeight", 0.0)
                    new_list_items = []

                    for li in v_pkg.get("ListItems", []):
                        targets = SPECIAL_LIST_PERCENT_RULES.get(tg, set())
                        full_id = v_pkg.get("ID", "")
                        m = re.match(r"^(.*)\.(\d{2})$", full_id)
                        family = m.group(1) if m else full_id

                        exact = {t for t in targets if re.search(r"\.\d{2}$", t)}
                        families = {t for t in targets if not re.search(r"\.\d{2}$", t)}
                        use_special = (full_id in exact) or any(family.startswith(t) for t in families)

                        if tw > 0:
                            list_percent = round(
                                (percent * (li["Weight"] / tw)) if use_special
                                else ((li["Weight"] / tw) * 100), 4
                            )
                        else:
                            list_percent = 0.0

                        # （任意）ListItemごとの日本語名も付加
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

# ===== summary から画像化タスクを作る（TierGroup/WorldListごと保存先） =====
def iter_tasks_from_summary(summary: dict):
    """
    yield (asset_path, out_dir, list_percent_text)
    out_dir = OUTPUT_BASE_DIR / <TierGroup> / <WorldListKey>
    """
    for tiergroup, tg_block in summary.items():
        items = tg_block.get("Items", [])
        for item in items:
            for v_pkg in item.get("ValidLootPackages", []):
                worldlist_key = v_pkg.get("Call") or "_NoWorldList"
                out_dir = os.path.join(OUTPUT_BASE_DIR, tiergroup, worldlist_key)
                for li in v_pkg.get("ListItems", []):
                    ap = li.get("AssetPathName")
                    if not ap:
                        continue
                    # 画像に描くパーセント表示（任意）
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
            if item_key and item_key in LOCALIZE_CACHE:
                loc = LOCALIZE_CACHE[item_key]
            elif item_key:
                loc = get_localized_name(item_key)
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

def get_next_version_filename(base_name: str, ext: str = ".json") -> str:
    existing_versions = []
    for f in Path(".").glob(f"{base_name}_v*{ext}"):
        m = re.search(r"_v(\d+)", f.stem)
        if m:
            existing_versions.append(int(m.group(1)))
    next_version = max(existing_versions, default=0) + 1
    return f"{base_name}_v{next_version}{ext}"

def main():
    # 1) まとめ作成
    rows_lt = load_rows(INPUT_LT_JSON)
    rows_lp = load_rows(INPUT_LP_JSON)
    summary = build_summary(rows_lt, rows_lp)

    # 2) Localized 名を後付け（必ず実行）
    enrich_summary_with_names(summary)

    # 3) JSON保存（常に実行）
    versioned_filename = get_next_version_filename(VERSION_PREFIX)
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

    # 並列生成
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(worker_task, ap, od, txt) for ap, od, txt in uniq]
        for _ in as_completed(futs):
            pass
    print("✅ 画像生成 完了（TierGroup/WorldListごとに保存）")


if __name__ == "__main__":
    main()
