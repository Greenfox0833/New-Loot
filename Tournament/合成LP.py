import json
from pathlib import Path

def overwrite_lootpackages(client_path, showdown_path, out_path):
    # ファイルを読み込み
    with open(client_path, "r", encoding="utf-8") as f:
        client_data = json.load(f)

    with open(showdown_path, "r", encoding="utf-8") as f:
        showdown_data = json.load(f)

    # Rows の位置を特定
    client_rows = client_data[0].get("Rows", {})
    showdown_rows = showdown_data[0].get("Rows", {})

    # Showdown の Rows を上書き
    client_rows.update(showdown_rows)

    # 上書きした Rows を戻す
    client_data[0]["Rows"] = client_rows

    # 出力
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(client_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 出力完了: {out_path}")

if __name__ == "__main__":
    client_file = Path("Tournament/AthenaCompositeLP_Showdown__final.json")
    showdown_file = Path("BR_Comp/作業用/AthenaLootPackages_Client__final.json")
    out_file = Path("Tournament/AthenaLootPackages_Client__merged.json")

    overwrite_lootpackages(client_file, showdown_file, out_file)
