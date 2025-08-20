import json
import re
from pathlib import Path

# ========= 入出力パス =========
ATHENA_CLIENT_PATH = Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")
BASE_PATH         = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootPackages_Client.json")
COMP_PATH         = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp.json")
NOBUILD_PATH      = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/AthenaCompositeLP_NoBuildBR.json")
NOBUILD_COMP_PATH = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/Comp_NoBuild/AthenaCompositeLP_NoBuildBR_Comp.json")

HOTFIX_PATH_ALL   = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix.ini")  # ← 1つに統一したファイル

OUT_PATH          = Path("E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/NoBuild_Comp/AthenaCompositeLP_NoBuildBR_Comp_Merged_Hotfix.json")
OUT_NAME          = "AthenaCompositeLP_NoBuildBR_Comp"
# =================================

def load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def extract_rows(payload):
    if isinstance(payload, dict):
        rows = payload.get("Rows")
        return rows if isinstance(rows, dict) else {}
    if isinstance(payload, list):
        for obj in payload:
            if isinstance(obj, dict) and isinstance(obj.get("Rows"), dict):
                return obj["Rows"]
    return {}

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

def main():
    # データ読み込み
    rows_base     = extract_rows(load_json(BASE_PATH))
    rows_comp     = extract_rows(load_json(COMP_PATH))
    rows_nb       = extract_rows(load_json(NOBUILD_PATH))
    rows_nb_comp  = extract_rows(load_json(NOBUILD_COMP_PATH))

    # 1. 通常データ（Athena をベースに LootCurrent で上書き）
    rows_athena_client = extract_rows(load_json(ATHENA_CLIENT_PATH))
    merged_all = dict(rows_athena_client)   # ベース：Athena
    merged_all.update(rows_base)            # 上書き：LootCurrent

    # 2. 通常Hotfix
    changes_client = parse_hotfix(HOTFIX_PATH_ALL, "LootCurrentSeasonLootPackages_Client")
    applied_client = apply_hotfix(merged_all, changes_client)

    # 3. 競技データ
    merged_all.update(rows_comp)

    # 4. NoBuildデータ
    merged_all.update(rows_nb)

    # 5. NoBuild競技データ
    merged_all.update(rows_nb_comp)

    # 6. 競技Hotfix（最後）
    changes_client_comp = parse_hotfix(HOTFIX_PATH_ALL, "LootCurrentSeasonLootPackages_Client_Comp")
    applied_client_comp = apply_hotfix(merged_all, changes_client_comp)

    # 出力
    composite = [{
        "Type": "CompositeDataTable",
        "Name": OUT_NAME,
        "Class": "UScriptClass'CompositeDataTable'",
        "Flags": "RF_Public | RF_Standalone | RF_Transactional | RF_WasLoaded | RF_LoadCompleted",
        "Properties": {
            "ParentTables": [
                {"ObjectName": "DataTable'LootCurrentSeasonLootPackages_Client'",
                 "ObjectPath": "/LootCurrentSeason/DataTables/LootCurrentSeasonLootPackages_Client.0"},
                {"ObjectName": "DataTable'LootCurrentSeasonLootPackages_Client_Comp'",
                 "ObjectPath": "/LootCurrentSeason/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp.0"},
                {"ObjectName": "DataTable'OverrideLootPackagesData_NoBuildBR'",
                 "ObjectPath": "/LootCurrentSeason/DataTables/NoBuildBR/OverrideLootPackagesData_NoBuildBR.0"},
                {"ObjectName": "DataTable'OverrideLootPackagesData_NoBuildBR_Comp'",
                 "ObjectPath": "/LootCurrentSeason/DataTables/NoBuildBR/Comp_NoBuild/OverrideLootPackagesData_NoBuildBR_Comp.0"}
            ],
            "RowStruct": {
                "ObjectName": "Class'FortLootPackageData'",
                "ObjectPath": "/Script/FortniteGame"
            }
        },
        "Rows": merged_all
    }]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(composite, f, ensure_ascii=False, indent=2)

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
    print(f"-> OUTPUT: {OUT_PATH}")



if __name__ == "__main__":
    main()
