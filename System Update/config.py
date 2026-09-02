import os
import runpy
from pathlib import Path

# System Update 内で完結するため、基準ディレクトリをここに固定
BASE_DIR = Path(__file__).resolve().parent
COMMON_DIR = BASE_DIR

# ---------------- 設定（シンプル版） ----------------
VERSION_PREFIX = "v37.50"  # 必要に応じて変更

# 実行プロファイル：
# "pipeline" : JSON作成 → アイコンDL(プリウォーム) → 画像生成
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
    "skip_if_icon_cached": False,  # pipelineではFalseにして、キャッシュがあっても画像は作る
    "enable_image_cache": True,    # エクスポートPNGのローカルキャッシュを使う
}

# ---- プロファイル定義（内部フラグに展開） ----
PROFILE_PRESETS = {
    "pipeline": dict(do_hotfix=True, enable_icon_cache_prewarm=True, enable_image_creation=True),
    "images": dict(do_hotfix=True, enable_icon_cache_prewarm=False, enable_image_creation=True),
    "prewarm": dict(do_hotfix=True, enable_icon_cache_prewarm=True, enable_image_creation=False),
    "json": dict(do_hotfix=True, enable_icon_cache_prewarm=False, enable_image_creation=False),
    "dryrun": dict(do_hotfix=True, enable_icon_cache_prewarm=False, enable_image_creation=False),
}
_p = PROFILE_PRESETS.get(RUN_MODE, PROFILE_PRESETS["pipeline"])

# 以降のコードが参照する既存フラグにマッピング
DRAW_STATS = RUN_OPTIONS["draw_stats"]
SHOW_PERCENT = RUN_OPTIONS["show_percent"]
DEBUG_LOCALIZE = RUN_OPTIONS["debug_localize"]
DO_HOTFIX = _p["do_hotfix"]
ENABLE_ICON_CACHE_PREWARM = _p["enable_icon_cache_prewarm"]
ENABLE_IMAGE_CREATION = _p["enable_image_creation"]
ENABLE_IMAGE_CACHE = RUN_OPTIONS["enable_image_cache"]
SKIP_IF_FINAL_EXISTS = RUN_OPTIONS["skip_if_final_exists"]
SKIP_IF_ICON_ALREADY_CACHED = RUN_OPTIONS["skip_if_icon_cached"]

# --- 生成対象フィルタ（任意） ---
ONLY_TIERGROUPS = {
    "Loot_AthenaTreasure",
    "Loot_AthenaFloorLoot",
    "Loot_ApolloTreasure_Rare",
    "LTG_MilitaryRank_A",
    "LTG_MilitaryRank_B",
    "LTG_MilitaryRank_S",
    "LTG_MilitaryRank_SPlus",
    "LTG_Drop_Premium_Squad",
    "LTG_Drop_Premium_Solo",
    "LTG_Drop_Premium_Duo",
    "LTG_Drop_Premium_Trio",
    "LTG_Chest_Special",
    "LTG_Bomber",
    "LTG_Swarmer",
}
ONLY_ROWS = None
ONLY_WORLDLIST_KEYS = None

# 入力（LT/LPのFModelエクスポートJSON）
INPUT_MINLIST_JSON = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/items_unique_min.json"

# 画像の保存先
OUTPUT_BASE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像/BR"
IMAGE_DIR_MODE = "flat"  # tg_wl | tg | flat

def resolve_out_dir(tiergroup: str, worldlist_key: str) -> str:
    if IMAGE_DIR_MODE == "tg_wl":
        return os.path.join(OUTPUT_BASE_DIR, tiergroup, worldlist_key)
    if IMAGE_DIR_MODE == "tg":
        return os.path.join(OUTPUT_BASE_DIR, tiergroup)
    return OUTPUT_BASE_DIR

# キャッシュ保存先
RARITY_CACHE_FILE = str(COMMON_DIR / "shared" / "cache" / "asset_rarity_cache.json")
ASSET_LOC_CACHE_FILE = str(COMMON_DIR / "shared" / "cache" / "asset_localize_cache.json")
ICON_CACHE_DIR = str(COMMON_DIR / "shared" / "icon_cache")
ICON_CACHE_FILE = str(COMMON_DIR / "shared" / "cache" / "asset_icon_cache.json")

ICON_CACHE_DIR_SECONDARY = r"E:/フォートナイト/Web/loot/images"
ICON_CACHE_FILE_SECONDARY = r"E:/フォートナイト/Web/loot/data/asset_icon_cache.json"

# 画像素材など
FONT_PATH = "c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF"
RARITY_BG_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Rarity"
RARITY_ICON_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/icon"
AMMO_ICON_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Ammo"
STAT_TEMPLATE_PATH = r"E:/フォートナイト/Picture/Loot Pool/TEST4/Template.png"

# スレッド数
MAX_WORKERS = 8

# TierGroupで絞りたい場合は指定
FILTER_TIERGROUP = None  # 例: "Loot_AthenaFloorLoot"

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

AMMO_ICON_MAP = {}

# パス一式
PATH_BR_DISCORD = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データDiscord/BR_Discor.py"
PATH_LOOT_SUMMARY = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/LootSummary.py"
PATH_VERSION_SAVE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/BR"
PATH_LT_JSON = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/AthenaLootTierData_Client__final.json"
PATH_LP_JSON = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/AthenaLootPackages_Client__final.json"
PATH_MINLIST_JSON = INPUT_MINLIST_JSON
PATH_LOOTDATA_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/BR/LootPercent"
PATH_REPO_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot"

# パス解決（BASE/SEASON を使う場合）
AUTO_RESOLVE_PATHS = False
PROFILE_NAME = os.getenv("SYSTEM_PROFILE", "").strip() or "BR"
BASE_PATHS = []
SEASON_PATHS = []

# プロファイル上書き（System Update/<PROFILE>/config.py）
_profile_name = os.getenv("SYSTEM_PROFILE", "").strip()
if _profile_name:
    _profile_path = Path(__file__).resolve().parent / _profile_name / "config.py"
    if _profile_path.exists():
        _overrides = runpy.run_path(str(_profile_path))
        for k, v in _overrides.items():
            if k.isupper():
                globals()[k] = v

def _as_list(value, max_items=10):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return items[:max_items]
    if isinstance(value, str):
        items = [v.strip() for v in value.split(",") if v.strip()]
        return items[:max_items]
    return []

BASE_PATHS = _as_list(BASE_PATHS, 10)
SEASON_PATHS = _as_list(SEASON_PATHS, 10)

def _iter_base_season():
    seasons = SEASON_PATHS[:] if SEASON_PATHS else [""]
    for base in BASE_PATHS:
        for season in seasons:
            yield base, season

def _resolve_first_existing(suffixes):
    for base, season in _iter_base_season():
        for suffix in suffixes:
            sfx = suffix.format(profile=PROFILE_NAME)
            path = os.path.join(base, season, sfx) if season else os.path.join(base, sfx)
            if os.path.exists(path):
                return path
    return ""

def _resolve_first_dir(suffixes):
    for base, season in _iter_base_season():
        for suffix in suffixes:
            sfx = suffix.format(profile=PROFILE_NAME)
            path = os.path.join(base, season, sfx) if season else os.path.join(base, sfx)
            if os.path.isdir(path):
                return path
    return ""

def _prompt(label, default):
    try:
        value = input(f"{label} [{default}]: ").strip()
    except EOFError:
        value = ""
    return value or default

def _apply_interactive_overrides():
    global OUTPUT_BASE_DIR, IMAGE_DIR_MODE
    global PATH_BR_DISCORD, PATH_LOOT_SUMMARY, PATH_VERSION_SAVE_DIR
    global PATH_LT_JSON, PATH_LP_JSON, PATH_MINLIST_JSON, PATH_LOOTDATA_DIR
    global INPUT_MINLIST_JSON

    OUTPUT_BASE_DIR = _prompt("OUTPUT_BASE_DIR", OUTPUT_BASE_DIR)
    IMAGE_DIR_MODE = _prompt("IMAGE_DIR_MODE (flat/tg/tg_wl)", IMAGE_DIR_MODE)
    if IMAGE_DIR_MODE not in ("flat", "tg", "tg_wl"):
        IMAGE_DIR_MODE = "flat"

    PATH_LT_JSON = _prompt("LT_JSON", PATH_LT_JSON)
    PATH_LP_JSON = _prompt("LP_JSON", PATH_LP_JSON)
    PATH_MINLIST_JSON = _prompt("MINLIST_JSON", PATH_MINLIST_JSON)
    INPUT_MINLIST_JSON = PATH_MINLIST_JSON
    PATH_VERSION_SAVE_DIR = _prompt("VERSION_SAVE_DIR", PATH_VERSION_SAVE_DIR)
    PATH_LOOTDATA_DIR = _prompt("LOOTDATA_DIR", PATH_LOOTDATA_DIR)
    PATH_LOOT_SUMMARY = _prompt("LOOT_SUMMARY_PY", PATH_LOOT_SUMMARY)
    PATH_BR_DISCORD = _prompt("DISCORD_SCRIPT", PATH_BR_DISCORD)

if os.getenv("BR_INTERACTIVE") == "1":
    _apply_interactive_overrides()

if AUTO_RESOLVE_PATHS and BASE_PATHS:
    lt_suffixes = [
        "{profile}/作業用/AthenaLootTierData_Client__final.json",
        "{profile}/作業用/AthenaLootTierData_Client.json",
        "FortniteGame/Content/Items/DataTables/AthenaLootTierData_Client.json",
        "AthenaLootTierData_Client__final.json",
        "AthenaLootTierData_Client.json",
    ]
    lp_suffixes = [
        "{profile}/作業用/AthenaLootPackages_Client__final.json",
        "{profile}/作業用/AthenaLootPackages_Client.json",
        "FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json",
        "AthenaLootPackages_Client__final.json",
        "AthenaLootPackages_Client.json",
    ]
    minlist_suffixes = [
        "{profile}/作業用/items_unique_min.json",
        "items_unique_min.json",
    ]
    loot_summary_suffixes = [
        "{profile}/作業用/LootSummary.py",
        "LootSummary.py",
    ]
    discord_suffixes = [
        "戦利品データDiscord/{profile}_Discor.py",
    ]
    version_dir_suffixes = [
        "戦利品データ/{profile}",
    ]
    lootdata_dir_suffixes = [
        "戦利品データ/{profile}/LootPercent",
    ]
    output_dir_suffixes = [
        "アイテム画像/{profile}",
    ]

    _lt = _resolve_first_existing(lt_suffixes)
    _lp = _resolve_first_existing(lp_suffixes)
    _min = _resolve_first_existing(minlist_suffixes)
    _sum = _resolve_first_existing(loot_summary_suffixes)
    _dis = _resolve_first_existing(discord_suffixes)
    _ver = _resolve_first_dir(version_dir_suffixes)
    _ld = _resolve_first_dir(lootdata_dir_suffixes)
    _out = _resolve_first_dir(output_dir_suffixes)

    if _lt:
        PATH_LT_JSON = _lt
    if _lp:
        PATH_LP_JSON = _lp
    if _min:
        PATH_MINLIST_JSON = _min
        INPUT_MINLIST_JSON = _min
    if _sum:
        PATH_LOOT_SUMMARY = _sum
    if _dis:
        PATH_BR_DISCORD = _dis
    if _ver:
        PATH_VERSION_SAVE_DIR = _ver
    if _ld:
        PATH_LOOTDATA_DIR = _ld
    if _out:
        OUTPUT_BASE_DIR = _out


