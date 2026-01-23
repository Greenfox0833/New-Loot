import os
from pathlib import Path

# ---------------- 設定（System Update/Figment_NoBuild 完結版） ----------------
VERSION_PREFIX = "v39.30"  # 必要に応じて変更

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

# ログ設定（詳細ログを残す）
LOG_LEVEL = "INFO"
LOG_EVERY = 50  # 進捗ログの間隔（画像生成の完了数）

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

# ---- パス（System Update/NoBuild 内で完結） ----
BASE_DIR = Path(__file__).resolve().parent
COMMON_DIR = BASE_DIR.parent
PROJECT_ROOT = COMMON_DIR.parent

SCRIPTS_DIR = BASE_DIR / "scripts"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = COMMON_DIR / "shared" / "cache"
ICON_CACHE_DIR = str(COMMON_DIR / "shared" / "icon_cache")

# 入力（LT/LPのFModelエクスポートJSON）
INPUT_MINLIST_JSON = str(INPUT_DIR / "items_unique_min.json")

# 画像の保存先
OUTPUT_BASE_DIR = r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像/Figment_NoBuild"
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
ICON_CACHE_FILE = str(COMMON_DIR / "shared" / "cache" / "asset_icon_cache.json")

# 画像素材など（必要なら System Update/NoBuild/assets に移して更新）
FONT_PATH = "c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF"
RARITY_BG_DIR = str(COMMON_DIR / "shared" / "assets" / "Rarity")
RARITY_ICON_DIR = str(COMMON_DIR / "shared" / "assets" / "icon")
AMMO_ICON_DIR = str(COMMON_DIR / "shared" / "assets" / "Ammo")
STAT_TEMPLATE_PATH = str(COMMON_DIR / "shared" / "assets" / "Template.png")

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
PATH_BR_DISCORD = str(SCRIPTS_DIR / "BR_Discor.py")
PATH_HOTFIX_LP = str(COMMON_DIR / "LootPackage.py")
PATH_HOTFIX_LT = str(COMMON_DIR / "LootTier.py")
PATH_LOOT_SUMMARY = str(SCRIPTS_DIR / "LootSummary.py")
PATH_VERSION_SAVE_DIR = str(OUTPUT_DIR / "summary")
PATH_LT_JSON = str(INPUT_DIR / "AthenaLootTierData_Client__final.json")
PATH_LP_JSON = str(INPUT_DIR / "AthenaLootPackages_Client__final.json")
PATH_MINLIST_JSON = INPUT_MINLIST_JSON
PATH_LOOTDATA_DIR = str(COMMON_DIR / "戦利品データ" / "Figment_NoBuild" )
PATH_REPO_DIR = str(PROJECT_ROOT)

# Hotfix設定（LootPackage）
HOTFIX_LP_PATHS = [
    "E:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/FigmentLootPackages.json",
    "E:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/NoBuild/NoBuildFigmentLootPackages_Override.json",
]
HOTFIX_LP_MAX_PATHS = 10
HOTFIX_LP_INI_PATH = "E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini"
HOTFIX_LP_OUT_FINAL = str(INPUT_DIR / "AthenaLootPackages_Client__final.json")
HOTFIX_LP_TARGETS = [
    "/Figment_LootTables/DataTables/FigmentLootPackages",
    "/Figment_LootTables/DataTables/NoBuild/NoBuildFigmentLootPackages_Override",
]

# Hotfix設定（LootTier）
HOTFIX_LT_PATHS = [
    "E:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/FigmentLootTierData.json",
    "E:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/NoBuild/NoBuildFigmentLootTierData_Override.json",
]
HOTFIX_LT_MAX_PATHS = 10
HOTFIX_LT_INI_PATH = "E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini"
HOTFIX_LT_OUT_FINAL = str(INPUT_DIR / "AthenaLootTierData_Client__final.json")
HOTFIX_LT_TARGETS = [
    "/Figment_LootTables/DataTables/FigmentLootPackages",
    "/Figment_LootTables/DataTables/NoBuild/NoBuildFigmentLootPackages_Override",
]

# パス解決（System Update 完結のため無効化）
AUTO_RESOLVE_PATHS = False
PROFILE_NAME = "Figment_NoBuild"
BASE_PATHS = []
SEASON_PATHS = []
