import json

hotfix_path = "e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix.ini" #変更しない
json_path = "e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/Json_Tier合成.json" #変更しない
output_path = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/Updated_LootTier.json"

# JSONファイル読み込み
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# データ構造チェック
if isinstance(data, list) and "Rows" in data[0]:
    rows = data[0]["Rows"]
else:
    raise ValueError("不正なJSON構造です。'Rows' が見つかりません。")

# 対象データテーブル名（完全一致）
target_table_name = "/ForbiddenFruitDataTables/DataTables/LootCurrentSeasonLootTierData_Client"

# Hotfixファイル読み込みと処理
with open(hotfix_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line.startswith(f"+DataTable={target_table_name}"):
            continue  # このテーブル以外はスキップ

        try:
            parts = line.split(";")
            if len(parts) != 5:
                print(f"[!] 無効な形式: {line}")
                continue

            _, _, row_name, field_name, new_value_str = parts
            new_value = float(new_value_str)

            if row_name in rows:
                if field_name in rows[row_name]:
                    old_value = rows[row_name][field_name]
                    rows[row_name][field_name] = new_value
                    print(f"✔ {row_name} の {field_name}: {old_value} → {new_value}")
                else:
                    print(f"× {row_name} に {field_name} フィールドが存在しません")
            else:
                print(f"× 行が存在しません: {row_name}")

        except Exception as e:
            print(f"[!] エラー: {e} (行: {line})")

# 保存
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ 完了: {output_path} に保存しました")
