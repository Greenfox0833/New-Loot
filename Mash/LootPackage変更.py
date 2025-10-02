import json
from pathlib import Path
from typing import Any, Dict, Tuple

# ==== 入出力 ====
BASE_PATH   = Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")  # 基盤
SMASH_PATH  = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LTM/Smash/Content/DataTables/Smash_LootPackages.json")  # 上書き（Smash）
HOTFIX_PATH = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")  # 任意（無ければスキップ）

OUT_FINAL   = Path("E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Mash/AthenaLootPackages_Client__final.json")
HOTFIX_TARGET_SMASH = "/Smash/DataTables/Smash_LootPackages"

# ---------- JSON I/O ----------
def read_datatable_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = data[0]
    return data

def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([meta], f, ensure_ascii=False, indent=2)

# ---------- マージ ----------
def merge_rows(base_rows: Dict[str, Any], override_rows: Dict[str, Any], stage: str) -> Tuple[int, int]:
    replaced = added = 0
    for k, v in override_rows.items():
        if k in base_rows:
            base_rows[k] = v
            replaced += 1
        else:
            base_rows[k] = v
            added += 1
    print(f"[MERGE:{stage}] replaced={replaced}, added={added}, total={len(base_rows)}")
    return replaced, added

# ---------- Hotfix ----------
def apply_hotfix(rows: Dict[str, Any], text: str, table_key: str):
    for line in text.splitlines():
        if line.startswith("+DataTable=") and table_key in line:
            # 例: +DataTable=/Smash/DataTables/Smash_LootPackages;RowDelete;RowKey
            parts = line.split(";")
            if len(parts) >= 3 and parts[1] == "RowDelete":
                rowkey = parts[2].strip()
                if rowkey in rows:
                    del rows[rowkey]
                    print(f"Hotfix: RowDelete {rowkey}")

# ---------- メイン ----------
def main():
    # ① Athena 基盤
    base_meta = read_datatable_json(BASE_PATH)
    base_rows = base_meta["Rows"]
    print(f"[LOAD] Athena rows={len(base_rows)}")

    # ② Smash 上書き
    smash_meta = read_datatable_json(SMASH_PATH)
    merge_rows(base_rows, smash_meta["Rows"], "SMASH")

    # ③ Hotfix（任意）
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8", errors="ignore")
        apply_hotfix(base_rows, text, HOTFIX_TARGET_SMASH)

    # ④ 保存
    write_datatable_json(base_meta, OUT_FINAL)
    print(f"[SAVE] {OUT_FINAL}")

if __name__ == "__main__":
    main()
