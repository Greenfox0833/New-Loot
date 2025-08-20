import json
from pathlib import Path
from collections import OrderedDict
import argparse
import sys

def load_json_ordered(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)

def save_json_ordered(data, path: Path):
    # 既存の並びを保ったまま出力（indent=2 / UTF-8 / 改行あり）
    text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(
        description="一致するキーは更新せず、Athena にしかない Rows だけを Current に追記するマージツール"
    )
    ap.add_argument("--current", "-c", type=Path, default=Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootTierData_Client.json"),
                    help="ベース（追記先）JSONパス")
    ap.add_argument("--athena", "-a", type=Path, default=Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootTierData_Client.json"),
                    help="追記元（Athena）JSONパス")
    ap.add_argument("--out", "-o", type=Path, default=Path("e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/Json_Tier合成.json"),
                    help="出力先 JSON パス")
    ap.add_argument("--dry-run", action="store_true", help="書き込みせず差分件数のみ表示")
    args = ap.parse_args()

    # 読み込み（順序保持）
    try:
        current = load_json_ordered(args.current)
        athena = load_json_ordered(args.athena)
    except Exception as e:
        print(f"[ERROR] JSON 読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # 期待フォーマット: [ { ... DataTable ... } ] の配列
    def get_rows(root, label):
        if not isinstance(root, list) or len(root) == 0 or not isinstance(root[0], dict):
            raise ValueError(f"{label}: 先頭が DataTable オブジェクトの配列になっていません")
        table0 = root[0]
        rows = table0.get("Rows")
        if not isinstance(rows, dict):
            raise ValueError(f"{label}: 'Rows' が見つからないか辞書ではありません")
        # OrderedDict に包み直し（json.loadで既にOrdered化されているが念のため）
        return table0, OrderedDict(rows)

    try:
        cur_table, cur_rows = get_rows(current, "Current")
        _, ath_rows = get_rows(athena, "Athena")
    except Exception as e:
        print(f"[ERROR] フォーマット検証で失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 既存キーは保持、Athena にしかないキーだけを Athena の順序で末尾に追加
    added = OrderedDict()
    for key, value in ath_rows.items():
        if key not in cur_rows:
            # value も順序保持でそのまま入れる
            if not isinstance(value, OrderedDict):
                value = OrderedDict(value)
            added[key] = value

    # 追記
    for k, v in added.items():
        cur_rows[k] = v

    # 追記した Rows をもとのテーブルに戻す（他のトップレベル要素は一切触らない）
    cur_table["Rows"] = cur_rows

    print(f"[INFO] Current 既存行数: {len(cur_rows) - len(added)}")
    print(f"[INFO] Athena 総行数   : {len(ath_rows)}")
    print(f"[INFO] 追加行数         : {len(added)}")

    if args.dry_run:
        print("[DRY-RUN] ファイル出力は行いません。")
        return

    # 出力
    try:
        save_json_ordered(current, args.out)
        print(f"[OK] 出力しました → {args.out}")
    except Exception as e:
        print(f"[ERROR] 出力に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
