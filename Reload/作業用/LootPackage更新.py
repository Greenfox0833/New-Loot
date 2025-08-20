import json

# === ファイルパス ===
hotfix_path = "e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix.ini"  # 変更しない
json_path = "e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/BlastBerryComposite_LP.json"  # 変更しない
output_path = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用//Updated_LootPackages.json"  # 変更しない

# === HotfixからWeight変更対象行だけ抽出（Compは除外）===
hotfix_weights = {}
hotfix_itemdefs = {}

with open(hotfix_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        # Weightの更新処理
        if (
            "BlastBerryLootPackages" in line and
            ";RowUpdate;" in line and
            ";Weight;" in line
        ):
            parts = line.split(";")
            if len(parts) >= 5:
                row_key = parts[2].strip()
                try:
                    weight = float(parts[4].strip())
                    hotfix_weights[row_key] = weight
                except ValueError:
                    continue

        # ItemDefinitionの更新処理
        if (
            "BlastBerryLootPackages" in line and
            ";RowUpdate;" in line and
            ";ItemDefinition;" in line
        ):
            parts = line.split(";")
            if len(parts) >= 5:
                row_key = parts[2].strip()
                itemdef = parts[4].strip()
                hotfix_itemdefs[row_key] = itemdef

# === 元のJSONファイル読み込み ===
with open(json_path, "r", encoding="utf-8") as f:
    json_data = json.load(f)

# === JSONにHotfixを適用 ===
weight_updated_count = 0
itemdef_updated_count = 0

for entry in json_data:
    if isinstance(entry, dict) and "Rows" in entry:
        rows = entry["Rows"]
        print(f"[DEBUG] JSON側の行数: {len(rows)}")

        # Weightの更新
        matched_weights = set(hotfix_weights.keys()).intersection(rows.keys())
        print(f"[DEBUG] 一致したWeight行数: {len(matched_weights)}")
        print(f"[DEBUG] 一致したWeightキー: {matched_weights}")
        for row_name in matched_weights:
            rows[row_name]["Weight"] = hotfix_weights[row_name]
            weight_updated_count += 1

        # ItemDefinitionの更新
        matched_itemdefs = set(hotfix_itemdefs.keys()).intersection(rows.keys())
        print(f"[DEBUG] 一致したItemDefinition行数: {len(matched_itemdefs)}")
        print(f"[DEBUG] 一致したItemDefinitionキー: {matched_itemdefs}")
        for row_name in matched_itemdefs:
            if "ItemDefinition" in rows[row_name] and isinstance(rows[row_name]["ItemDefinition"], dict):
                rows[row_name]["ItemDefinition"]["AssetPathName"] = hotfix_itemdefs[row_name]
            itemdef_updated_count += 1

# === 保存 ===
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(json_data, f, indent=2, ensure_ascii=False)

print(f"[完了] {weight_updated_count}件のWeightを更新、{itemdef_updated_count}件のItemDefinitionを更新しました。出力: {output_path}")
