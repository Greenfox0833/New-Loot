# ============================
# 戦利品まとめ + ローカライズ + 画像生成（Loot/TierGroup→WorldListごと保存） 完全版
# ============================

import os
import re
import json
import atexit
from io import BytesIO
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from PIL import Image, ImageDraw, ImageFont
import subprocess, sys
from pathlib import Path

# ---------------- 設定（シンプル版） ----------------
VERSION_PREFIX = "v37.10"  # 必要に応じて変更

# 実行プロファイル：
# "pipeline" : JSON作成 → アイコンDL(プリウォーム) → 画像生成   ← これがご希望の流れ
# "images"   : JSON作成 → 画像生成（プリウォームはしない）
# "prewarm"  : JSON作成 → アイコンDLのみ（画像は作らない）
# "json"     : JSON作成のみ
# "dryrun"   : 何もしない
RUN_MODE = "pipeline"

# 追加オプション（必要時だけ調整）
RUN_OPTIONS = {
    "draw_stats": False,
    "show_percent": False,
    "debug_localize": False,

    # スキップ方針
    "skip_if_final_exists": True,  # 生成済み最終pngがあればスキップ
    "skip_if_icon_cached": False,  # ★pipelineではFalseにして、キャッシュがあっても画像は作る
    "enable_image_cache": True,    # エクスポートPNGのローカルキャッシュを使う

    # ★追加: 描画の無効化スイッチ
    "disable_text_and_bar": True,  # 黒帯（下部の半透明バー）とアイテム名テキストを無効化
    "disable_rarity_icon":  True,  # レアリティアイコン（センター下の小アイコン）を無効化
}

# ---- プロファイル定義（内部フラグに展開） ----
PROFILE_PRESETS = {
    "pipeline": dict(do_hotfix=True,  enable_icon_cache_prewarm=True,  enable_image_creation=True),
    "images":   dict(do_hotfix=True,  enable_icon_cache_prewarm=False, enable_image_creation=True),
    "prewarm":  dict(do_hotfix=True, enable_icon_cache_prewarm=True,  enable_image_creation=False),
    "json":     dict(do_hotfix=True,  enable_icon_cache_prewarm=False, enable_image_creation=False),
    "dryrun":   dict(do_hotfix=True, enable_icon_cache_prewarm=False, enable_image_creation=False),
}
_p = PROFILE_PRESETS.get(RUN_MODE, PROFILE_PRESETS["pipeline"])

# 以降のコードが参照する既存フラグにマッピング
DRAW_STATS                 = RUN_OPTIONS["draw_stats"]
SHOW_PERCENT               = RUN_OPTIONS["show_percent"]
DEBUG_LOCALIZE             = RUN_OPTIONS["debug_localize"]
DO_HOTFIX                  = _p["do_hotfix"]
ENABLE_ICON_CACHE_PREWARM  = _p["enable_icon_cache_prewarm"]
ENABLE_IMAGE_CREATION      = _p["enable_image_creation"]
ENABLE_IMAGE_CACHE         = RUN_OPTIONS["enable_image_cache"]
SKIP_IF_FINAL_EXISTS       = RUN_OPTIONS["skip_if_final_exists"]
SKIP_IF_ICON_ALREADY_CACHED= RUN_OPTIONS["skip_if_icon_cached"]
DISABLE_TEXT_AND_BAR       = RUN_OPTIONS["disable_text_and_bar"]
DISABLE_RARITY_ICON        = RUN_OPTIONS["disable_rarity_icon"]

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
INPUT_MINLIST_JSON = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/items_unique_min.json"


# 画像の保存先（親）:  <OUTPUT_BASE_DIR>/<TierGroup>/<WorldListKey>/ に振り分け保存
OUTPUT_BASE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像/Figment_IconOnly"
IMAGE_DIR_MODE = "flat"  # tg_wl:従来どおり | tg:<OUTPUT_BASE_DIR>/<TierGroup> | flat:<OUTPUT_BASE_DIR> にすべて平置き

def resolve_out_dir(tiergroup: str, worldlist_key: str) -> str:
    if IMAGE_DIR_MODE == "tg_wl":
        return os.path.join(OUTPUT_BASE_DIR, tiergroup, worldlist_key)
    elif IMAGE_DIR_MODE == "tg":
        return os.path.join(OUTPUT_BASE_DIR, tiergroup)
    else:
        return OUTPUT_BASE_DIR


# キャッシュ保存先
RARITY_CACHE_FILE = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/asset_rarity_cache.json"
ASSET_LOC_CACHE_FILE = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/asset_localize_cache.json"
ICON_CACHE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイコンキャッシュ"
ICON_CACHE_FILE = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/asset_icon_cache.json"
try:
    with open(ICON_CACHE_FILE, "r", encoding="utf-8") as f:
        ICON_PATH_CACHE = json.load(f)
except FileNotFoundError:
    ICON_PATH_CACHE = {}


# 画像素材など
FONT_PATH = "c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF"
RARITY_BG_DIR   = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Rarity"
RARITY_ICON_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/icon"
AMMO_ICON_DIR   = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Ammo"
STAT_TEMPLATE_PATH = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Template.png"  # 任意（無ければ描画スキップ）

# スレッド数
MAX_WORKERS = 8

# TierGroupで絞りたい場合は指定
FILTER_TIERGROUP = None  # 例: "Loot_AthenaFloorLoot" など。Noneなら全体

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

# ★追加：英語→日本語の表示名マップ
RARITY_JP_MAP = {
    "common": "コモン",
    "uncommon": "アンコモン",
    "rare": "レア",
    "epic": "エピック",
    "legend": "レジェンド",
    "mythic": "ミシック",
    "exotic": "エキゾチック",
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

RARITY_TO_TIER = {
    "コモン": "ティア1",
    "アンコモン": "ティア2",
    "レア": "ティア3",
    "エピック": "ティア4",
    "レジェンド": "ティア5",
    "エキゾチック": "ティア6",
    "ミシック": "ティア7",
}

AMMO_ICON_MAP = {}  # 必要に応じて追記

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
session.headers.update({"Connection": "keep-alive"})

# ★追加: 画像キャッシュ（ExportのPNG）
from io import BytesIO
from PIL import Image

def icon_cache_key(path_like: str) -> str:
    """Export Pathをキャッシュ用ファイル名に変換"""
    clean = path_like.strip().strip("/").split(".")[0]
    return clean.replace("\\", "/").replace("/", "__") + ".png"

def load_icon_from_cache(path_like: str):
    if not ENABLE_IMAGE_CACHE:
        return None
    try:
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        fp = os.path.join(ICON_CACHE_DIR, icon_cache_key(path_like))
        if os.path.exists(fp):
            return Image.open(fp).convert("RGBA")
    except Exception:
        pass
    return None

def save_icon_to_cache(path_like: str, content: bytes) -> None:
    if not ENABLE_IMAGE_CACHE:
        return
    try:
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        fp = os.path.join(ICON_CACHE_DIR, icon_cache_key(path_like))
        # ★既にキャッシュが存在するなら何もしない
        if os.path.exists(fp):
            return
        with open(fp, "wb") as f:
            f.write(content)
    except Exception:
        pass


def fetch_export_image_as_pil(path_like: str):
    """
    Export API の画像（PNG）を PIL.Image で返す。
    1) キャッシュ命中ならそれを返す
    2) 無ければDL→キャッシュ保存→返す
    """
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
            print(f"[HTTP×] {r.status_code} {url}")
            return None
        raw = r.content
        im = Image.open(BytesIO(raw)).convert("RGBA")
        save_icon_to_cache(path_like, raw)
        return im
    except Exception:
        return None



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

# ★追加：英語が残っている既存キャッシュを日本語に正規化
if RARITY_CACHE:
    changed = False
    for k, v in list(RARITY_CACHE.items()):
        if isinstance(v, str):
            jp = RARITY_JP_MAP.get(v.lower())
            if jp and jp != v:
                RARITY_CACHE[k] = jp
                changed = True
    if changed:
        # すぐ保存しておくと後続ロジックで揺れが出ない
        try:
            with open(RARITY_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(RARITY_CACHE, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# すぐ保存（任意）
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
            raw_rarity = props.get("Rarity")
            # 1) エンジン表記 → 英語（"Epic"など）
            rarity_en = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"
            # 2) 英語 → 日本語
            rarity_ja = RARITY_JP_MAP.get(rarity_en.lower(), "アンコモン")
    except Exception:
        rarity_ja = "アンコモン"

    # 日本語で保存
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
    if "/Content/" in path or "/content/" in path:
        return path
    # Gameplay / Items に加えて UI / Textures / Icons にも対応
    return _re_fix.sub(r"/(Gameplay|Items|UI|Textures|Icons)/",
                       r"/Content/\1/", path, count=1, flags=_re_fix.IGNORECASE)

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

def save_icon_cache():
    """ICON_PATH_CACHE をファイルに保存"""
    try:
        with open(ICON_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(ICON_PATH_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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

        # ★追加: キャッシュ参照（AssetPathName の末尾キーで探す）
        if not icon_path:
            base = asset_path.split("/")[-1].split(".")[0]
            icon_path = ICON_PATH_CACHE.get(base)

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
            # ★ Figment/Juno補正 + /Content 挿入などを必ず適用
            icon_norm = normalize_asset_path(icon_path)
            icon_image = fetch_export_image_as_pil(icon_norm)
            if icon_image is None:
                print(f"[×] アイコン画像取得失敗(URL用パス): {icon_norm}")
                return

            # ★ キャッシュ登録も正規化後のキーで
            base = asset_path.split("/")[-1].split(".")[0]
            if base not in ICON_PATH_CACHE:
                ICON_PATH_CACHE[base] = icon_norm
                save_icon_cache()
        except Exception as e:
            print(f"[×] アイコン合成処理例外: {e}")
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

        # === 下部バー（半透明）＋レアリティアイコン＋アイテム名テキスト ===
        # それぞれ個別にON/OFFできるように分岐
        draw = ImageDraw.Draw(canvas)

        # 黒帯＋テキストを描く場合のみ、下地となる半透明バーを描画
        if not DISABLE_TEXT_AND_BAR:
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.rectangle([(0, 500), (canvas.width, 600)], fill=(0, 0, 0, 128))
            canvas = Image.alpha_composite(canvas, overlay)
            draw = ImageDraw.Draw(canvas)  # 合成後に描画対象を更新

        # レアリティアイコン（個別に制御）
        if not DISABLE_RARITY_ICON:
            rarity_icon_path = os.path.join(RARITY_ICON_DIR, f"{rarity}.png")
            if os.path.exists(rarity_icon_path):
                try:
                    rimg = Image.open(rarity_icon_path).convert("RGBA")
                    target_h = 32
                    tw = int(target_h * rimg.width / rimg.height)
                    rimg = rimg.resize((tw, target_h), Image.LANCZOS)
                    # 黒帯あり：従来どおり 515px 近辺に配置
                    # 黒帯なし：同位置にそのまま配置（必要なら後で調整可）
                    canvas.paste(rimg, ((canvas.width - tw)//2, 515), rimg)
                except Exception:
                    pass

        # アイテム名（個別に制御）
        if not DISABLE_TEXT_AND_BAR:
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
        safe_weapon_name = re.sub(r'[\\/:"*?<>|]', "_", weapon_name)

        # レアリティを日本語に変換してティアを取得
        rarity_ja = RARITY_JP_MAP.get(rarity.lower(), rarity)
        tier = RARITY_TO_TIER.get(rarity_ja, "ティア?")

        # 保存名 = アイテム名 - ティアX.png
        filename = f"{safe_weapon_name} - {tier}.png"
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

def load_minlist(path: str):
    """items_unique_min.json を読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print("⚠️ items_unique_min.json の形式が不正です")
            return []
        return data
    except FileNotFoundError:
        print(f"❌ {path} が見つかりません")
        return []

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
                                    "WorldListID": c["Key"],           # ★ 追加：WorldList の行キー（例: WorldList.ApolloLoot... .01）
                                    "Weight": c["Weight"],
                                    "AssetPathName": c["AssetPathName"],
                                    "CountItem": c.get("CountItem")
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
                                "WorldListID": li.get("WorldListID"),            # ★ 追加：①で入れたIDを引き継ぐ
                                "Weight": li["Weight"],
                                "ListPercent": list_percent,
                                "rarity": get_rarity_by_asset(asset_path),
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
def iter_tasks_from_summary_all(summary: dict):
    """summaryに含まれる全AssetPathNameを必ず対象にする版"""
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
                        # パーセントは無くてもOK
                        yield (ap, out_dir, None, tiergroup, worldlist_key)

def iter_tasks_from_minlist(min_items):
    """
    items_unique_min.json から画像生成タスクを作る
    """
    DEFAULT_TG = "MinList"
    DEFAULT_WL = "_FromMinList"
    for rec in min_items:
        ap = rec.get("AssetPathName")
        if not ap:
            continue
        out_dir = resolve_out_dir(DEFAULT_TG, DEFAULT_WL)
        # LocalizedName を優先的に使えるようにタスクに含める
        yield (ap, out_dir, rec.get("LocalizedName"), DEFAULT_TG, DEFAULT_WL)

def worker_task(asset_path: str, out_dir: str, list_percent_text: str | None,
                tiergroup: str | None = None, worldlist_key: str | None = None,
                preferred_name: str | None = None):
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
                loc = fetch_localized_name(item_key)
        safe = re.sub(r'[\\/:"*?<>|]', "_", loc)

        # モード別のファイル名（flat/tg では衝突回避のため接頭辞を付与）
        prefix = ""
        if IMAGE_DIR_MODE == "flat" and tiergroup and worldlist_key:
            prefix = f"[{tiergroup}][{worldlist_key}] "
        elif IMAGE_DIR_MODE == "tg" and worldlist_key:
            prefix = f"[{worldlist_key}] "

        rarity_ja = get_rarity_by_asset(asset_path)  # 日本語レアリティ
        tier = RARITY_TO_TIER.get(rarity_ja, "ティア?")
        filename = f"{prefix}{safe} - {tier}.png"

        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        if SKIP_IF_FINAL_EXISTS and os.path.exists(out_path):
            print(f"[SKIP] 既存: {out_path}")
            return

        # 透過アイコンが既にキャッシュ済みでも、pipeline では作り続ける（オプション）
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


# ★追加：プリウォーム関数（画像生成はせず、アイコンだけキャッシュ）
def prewarm_icon_cache(summary: dict):
    """
    summary に含まれる全アイテムの AssetPath から
    アイコンPNGを取得してキャッシュに保存する。
    """
    if not ENABLE_IMAGE_CACHE:
        print("[i] 画像キャッシュが無効のためプリウォームはスキップ")
        return

    assets = set()
    # ListItems を総なめして AssetPathName を収集
    for tg_block in summary.values():
        for item in tg_block.get("Items", []) or []:
            for group in item.get("ValidLootPackages", []) or []:
                for v_pkg in group.get("Packages", []) or []:
                    for li in v_pkg.get("ListItems", []) or []:
                        ap = li.get("AssetPathName")
                        if ap:
                            assets.add(normalize_asset_path(ap))

    # 各Assetからアイコンパスを探してキャッシュ
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
                        icon_path = p; break
                if not icon_path:
                    for entry in data_list:
                        p = _get(entry, "Icon")
                        if p and p.strip():
                            icon_path = p; break
            if not icon_path:
                icon_path = _get(props, "LargeIcon") or _get(props, "Icon")
            if not icon_path:
                continue

            icon_norm = normalize_asset_path(icon_path)
            _ = fetch_export_image_as_pil(icon_norm)  # ★正規化済みでプリウォーム

        except Exception:
            pass

from datetime import datetime

def get_versioned_filename(prefix, save_dir):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")  # 例: 2025-08-20_23-25
    filename = save_dir / f"{prefix}_{now}.json"
    return str(filename)


def main():
    # ===== パス設定 =====
    br_discord       = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データDiscord/Figment_Discor.py")
    loot_summary_py  = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/LootSummary.py")
    version_save_dir = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/Figment")  # まとめJSONの保存先
    lt_json_path     = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/FigmentLootTierData__final.json")
    lp_json_path     = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/FigmentLootPackages__final.json")
    minlist_path     = Path(INPUT_MINLIST_JSON)  # 例: E:/.../BR/作業用/items_unique_min.json

    try:
        print("===== BR: pipeline start =====")

        # 0) Hotfix（必要時のみ実行）
        if DO_HOTFIX:
            subprocess.run([sys.executable, r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/LootPackage変更.py"], check=True)
            subprocess.run([sys.executable, r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/LootTier変更.py"], check=True)
            print("✓ Hotfix 適用完了")

        # 1) まとめJSONの作成（LT/LP → summary）と保存
        rows_lt = load_rows(str(lt_json_path))
        rows_lp = load_rows(str(lp_json_path))
        summary = build_summary(rows_lt, rows_lp)
        try:
            enrich_summary_with_names(summary)  # あれば実行（失敗しても続行）
        except Exception:
            pass

        version_save_dir.mkdir(parents=True, exist_ok=True)
        versioned_filename = get_versioned_filename(VERSION_PREFIX, str(version_save_dir))
        Path(versioned_filename).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ まとめJSONを作成: {versioned_filename}")

        # 2) LootSummary を実行（抽出 → 比較）
        subprocess.run(
            [sys.executable, str(loot_summary_py),
             "--scan", str(version_save_dir),
             "--diff-scan", str(version_save_dir)],
            check=True
        )
        print("✅ LootSummary 実行完了（抽出→比較）")

        # 3) MinList を読み込み（items_unique_min.json）
        try:
            with open(minlist_path, "r", encoding="utf-8") as f:
                min_items = json.load(f)
            if not isinstance(min_items, list) or not min_items:
                print(f"[!] MinList が空です: {minlist_path}")
                return
        except FileNotFoundError:
            print(f"[!] 見つかりません: {minlist_path}")
            return

        # 4) タスク化（MinListベースで画像生成）
        DEFAULT_TG = "MinList"
        DEFAULT_WL = "_FromMinList"
        tasks = []
        for rec in min_items:
            ap = (rec or {}).get("AssetPathName")
            if not ap:
                continue
            out_dir = resolve_out_dir(DEFAULT_TG, DEFAULT_WL)
            preferred = rec.get("LocalizedName")
            # list_percent_text=None / preferred_name=preferred で worker に渡す
            tasks.append((ap, out_dir, None, DEFAULT_TG, DEFAULT_WL, preferred))

        # 5) 重複除去（flat/tg でも衝突しないようにキーに TG/WL を含める）
        uniq, seen = [], set()
        for ap, od, _txt, tg, wl, preferred in tasks:
            key = (normalize_asset_path(ap), od, tg, wl)
            if key not in seen:
                seen.add(key)
                uniq.append((ap, od, None, tg, wl, preferred))

        print(f"[i] 画像化タスク数: {len(uniq)}")

        # 6) 画像生成（並列）
        if ENABLE_IMAGE_CREATION:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futs = [ex.submit(worker_task, ap, od, None, tg, wl, preferred)
                        for ap, od, _txt, tg, wl, preferred in uniq]
                for _ in as_completed(futs):
                    pass
            print("✅ 画像生成 完了（MinListベース）")
        else:
            print("ℹ️ ENABLE_IMAGE_CREATION=False のため画像生成はスキップ")

    except Exception as e:
        print("[!] main 内でエラー:", e)

    finally:
        # 7) Discord 送信（常時オン）
        try:
            if br_discord.exists():
                subprocess.run([sys.executable, str(br_discord)], check=True)
                print("✓ BR_Discord 実行完了")
            else:
                print(f"ℹ️ BR_Discord が見つかりません: {br_discord}")
        except Exception as e:
            print("[!] BR_Discord 実行に失敗:", e)

        # 8) GitHub に Push
        try:
            repo_dir = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot")
            # BR関連ファイルをすべて add → commit → push
            subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
            msg = f"Figment update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", msg], check=False)
            subprocess.run(["git", "-C", str(repo_dir), "push"], check=True)
            print("✓ GitHub Push 完了")
        except Exception as e:
            print("[!] GitHub Push に失敗:", e)

        print("===== BR: pipeline end =====")

if __name__ == "__main__":
    main()
