import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

# ========= 入出力パス =========
ATHENA_CLIENT_PATH = Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")
BASE_PATH         = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootPackages_Client.json")
COMP_PATH         = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp.json")
NOBUILD_PATH      = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/AthenaCompositeLP_NoBuildBR.json")
NOBUILD_COMP_PATH = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/Comp_NoBuild/AthenaCompositeLP_NoBuildBR_Comp.json")

HOTFIX_PATH_ALL   = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")  # 1つに統一したファイル

OUT_PATH          = Path("E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/NoBuild_Comp/作業用/AthenaCompositeLP_NoBuildBR_Comp_Merged_Hotfix.json")
OUT_NAME          = "AthenaCompositeLP_NoBuildBR_Comp"
# =================================


# ---------- LootPackage変更.py と同じ I/O ユーティリティ ----------
def read_datatable_json(path: Path) -> Dict[str, Any]:
    """DataTable形式（または [meta] 配列）JSON を読み、最上位の dict(meta) を返す。"""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{path.name}: 空リストです")
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{path.name}: DataTable形式ではありません（Rowsがありません）")
    return data

def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    """meta(dict) を [meta] の形で保存（LootPackage変更.py と同じ出力形）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([meta], f, ensure_ascii=False, indent=2)


# ---------- Hotfix（既存の挙動を踏襲：ターゲット一致行のみ適用） ----------
_hotfix_pat = re.compile(r"^\+?DataTable=([^;]+);RowUpdate;([^;]+);([^;]+);(.+)$")

def parse_hotfix(hotfix_path: Path, target_datatable_substr: str):
    changes = {}
    if not hotfix_path.exists():
        return changes
    with hotfix_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            m = _hotfix_pat.match(line)
            if not m:
                continue
            datatable_path, row_key, field, value = m.groups()
            if target_datatable_substr not in datatable_path:
                continue
            changes.setdefault(row_key, {})[field] = value
    return changes

def apply_hotfix(rows: dict, changes: dict):
    """値の型変換は最小限（Weightはfloat化 / ItemDefinitionはAssetPathName差し替え）。
       それ以外は文字列のまま上書き。既存ロジックを維持。"""
    applied_count = 0
    for rk, fields in changes.items():
        if rk not in rows:
            continue
        for field, value in fields.items():
            if field == "Weight":
                try:
                    rows[rk][field] = float(value)
                except ValueError:
                    pass
            elif field == "ItemDefinition":
                if isinstance(rows[rk].get("ItemDefinition"), dict):
                    rows[rk]["ItemDefinition"]["AssetPathName"] = value
                else:
                    rows[rk]["ItemDefinition"] = {"AssetPathName": value, "SubPathString": ""}
            else:
                rows[rk][field] = value
            applied_count += 1
    return applied_count


# ---------- メイン ----------
def main():
    # 0) ベースとなる meta を取得（出力はこの meta 形に合わせる）
    base_meta = read_datatable_json(ATHENA_CLIENT_PATH)  # Rowsとメタ（Type/Name/Class/Properties）を持つ
    base_rows = base_meta["Rows"]

    # 1) 各ソースの Rows を読み込み
    rows_base        = read_datatable_json(BASE_PATH)["Rows"]
    rows_comp        = read_datatable_json(COMP_PATH)["Rows"]
    rows_nb          = read_datatable_json(NOBUILD_PATH)["Rows"]
    rows_nb_comp     = read_datatable_json(NOBUILD_COMP_PATH)["Rows"]

    # 2) マージ順は従来どおり（Athena をベースに上書き）
    merged_all = dict(base_rows)   # ベース：Athena
    merged_all.update(rows_base)   # 上書き：LootCurrent
    # 3) 通常Hotfix
    changes_client = parse_hotfix(HOTFIX_PATH_ALL, "LootCurrentSeasonLootPackages_Client")
    applied_client = apply_hotfix(merged_all, changes_client)
    # 4) 競技データ
    merged_all.update(rows_comp)
    # 5) NoBuildデータ
    merged_all.update(rows_nb)
    # 6) NoBuild競技データ
    merged_all.update(rows_nb_comp)
    # 7) 競技Hotfix（最後）
    changes_client_comp = parse_hotfix(HOTFIX_PATH_ALL, "LootCurrentSeasonLootPackages_Client_Comp")
    applied_client_comp = apply_hotfix(merged_all, changes_client_comp)

    # 8) 出力：LootPackage変更.py と同じ [meta] 形式に統一
    #    Rows 以外のメタは base_meta を流用しつつ、Name だけ目的の OUT_NAME に差し替え
    base_meta["Rows"] = merged_all
    if "Name" in base_meta:
        base_meta["Name"] = OUT_NAME  # 読みやすさのため名前は差し替え

    write_datatable_json(base_meta, OUT_PATH)

    # サマリ
    print("=== Merge Summary ===")
    print(f"Base rows         : {len(rows_base)}")
    print(f"Comp rows         : {len(rows_comp)}")
    print(f"NoBuild rows      : {len(rows_nb)}")
    print(f"NoBuild Comp rows : {len(rows_nb_comp)}")
    print(f"Hotfix applied    : {applied_client + applied_client_comp}")
    print(f"  - Client        : {applied_client}")
    print(f"  - Client_Comp   : {applied_client_comp}")
    print(f"Final merged rows : {len(merged_all)}")
    print(f"-> WRITE (datatable-like) : {OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
