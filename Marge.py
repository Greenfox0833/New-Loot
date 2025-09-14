import json
from pathlib import Path

# ===== 設定 =====
TARGET_FILE = Path(r"ForbiddenFruit/作業用/AthenaLootPackages_Client__final.json")  # 追記先
ASHTON_FILE = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/AshtonGameplay/Content/Datatables/AshtonGameplayLootPackages.json")        # 追加元

def main():
    # 元データを読み込み
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        target_data = json.load(f)

    # Ashtonデータを読み込み
    with open(ASHTON_FILE, "r", encoding="utf-8") as f:
        ashton_data = json.load(f)

    # target_data の Rows を取得
    target_rows = target_data[0].setdefault("Rows", {})

    # 追加元ファイルの Name を取得
    ashton_name = ashton_data[0]["Name"]

    # ashton_data の Rows を取得
    ashton_rows = ashton_data[0].get("Rows", {})

    # Ashton の Rows をすべて追加（RowName に .<追加元ファイル名> を付与）
    added = 0
    for row_name, row_value in ashton_rows.items():
        new_row_name = f"{row_name}.{ashton_name}"
        target_rows[new_row_name] = row_value
        added += 1

    # 保存
    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        json.dump(target_data, f, indent=2, ensure_ascii=False)

    print(f"✅ {added} 件の Rows を追加しました（RowName に .{ashton_name} を付与）")
    print(f"💾 保存完了: {TARGET_FILE}")

if __name__ == "__main__":
    main()
