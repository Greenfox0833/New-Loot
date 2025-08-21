import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ==== 入出力（必要なら名前だけ変えてOK）====
BASE_PATH    = Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")  # ①ベース
SEASON_PATH  = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootPackages_Client.json")  # ①上書き対象
OVERRIDE_PATH= Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/OverrideLootPackagesData_NoBuildBR.json")  # ③最終上書き
HOTFIX_PATH  = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")  # ② 任意（無ければスキップ）

OUT_FINAL    = Path("E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Nobuild/作業用/AthenaLootPackages_Client__final.json")

# Hotfixを適用する“対象テーブル名”を厳密にシーズン表に限定
HOTFIX_TARGET_TABLE = {
    "/LootCurrentSeason/DataTables/LootCurrentSeasonLootPackages_Client",
    "/Game/Items/Datatables/AthenaLootPackages_Client"
}

_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

# ---------- 基本処理 ----------
def read_datatable_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # DataTable JSON は [ { .. Rows .. } ] か { .. Rows .. } 想定
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{path.name}: 空リストです")
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{path.name}: DataTable形式ではありません（Rowsがありません）")
    return data

def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump([meta], f, ensure_ascii=False, indent=2)

def merge_rows(base_rows: Dict[str, Any], override_rows: Dict[str, Any]) -> Tuple[int, int]:
    replaced = added = 0
    for k, v in override_rows.items():
        if k in base_rows:
            base_rows[k] = v
            replaced += 1
        else:
            base_rows[k] = v
            added += 1
    return replaced, added

# ---------- 値の型合わせ（数値/真偽/NULL/Unreal形式など） ----------
def coerce_scalar(s: str) -> Any:
    s = s.strip()
    if _num_re.match(s):
        if "." in s or "e" in s.lower():
            try:
                return float(s)
            except Exception:
                return s
        try:
            return int(s)
        except Exception:
            return s
    sl = s.lower()
    if sl in ("true", "false"):
        return sl == "true"
    if sl == "null":
        return None
    try:
        return json.loads(s)
    except Exception:
        return s

def parse_unreal_tuple_to_dict(s: str) -> Dict[str, Any]:
    inner = s.strip()[1:-1].strip()
    out: Dict[str, Any] = {}
    if not inner:
        return out
    for seg in inner.split(","):
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        out[k.strip()] = coerce_scalar(v.strip())
    return out

def parse_unreal_tuple_to_list(s: str) -> List[Any]:
    inner = s.strip()[1:-1].strip()
    if not inner:
        return []
    return [coerce_scalar(v.strip()) for v in inner.split(",") if v.strip()]

def coerce_like(existing: Any, new_str: str) -> Any:
    s = new_str.strip()

    # Unreal 形式を優先解釈
    if s.startswith("(") and s.endswith(")"):
        if "=" in s:
            try:
                return parse_unreal_tuple_to_dict(s)
            except Exception:
                pass
        else:
            try:
                return parse_unreal_tuple_to_list(s)
            except Exception:
                pass

    if isinstance(existing, dict):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return s

    if isinstance(existing, list):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [coerce_scalar(x.strip()) for x in s.split(",") if x.strip()]

    return coerce_scalar(s)

def set_by_path(row: Dict[str, Any], field_path: str, value_str: str) -> Tuple[bool, str]:
    keys = field_path.split(".")
    cur = row
    for k in keys[:-1]:
        if not isinstance(cur, dict):
            return False, f"not a dict at '{k}'"
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    last = keys[-1]
    existing = cur.get(last, None)
    cur[last] = coerce_like(existing, value_str)
    return True, ("OK" if existing is not None else "NEW")

# ---------- Hotfix ----------
def parse_hotfix_line(line: str) -> Dict[str, Any]:
    # +DataTable=...;RowUpdate;RowKey;Field;Value
    line = line.strip()
    if not line or line.startswith("#"):
        return {"op": "COMMENT"}
    if not (line.startswith("+") or line.startswith("-")):
        return {"op": "UNKNOWN"}

    try:
        after = line[1:]
        first_seg, *rest = after.split(";")
        if "DataTable=" not in first_seg:
            return {"op": "UNKNOWN"}
        dt = first_seg.split("=", 1)[1].strip()
        if not rest:
            return {"op": "UNKNOWN"}

        op = rest[0].strip()
        if op not in ("RowUpdate", "RowAdd", "RowUpsert", "RowDelete"):
            return {"op": "SKIP", "datatable": dt}

        if op == "RowDelete":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            return {"op": op, "datatable": dt, "row": rest[1].strip()}

        if len(rest) < 4:
            return {"op": "SKIP", "datatable": dt}
        row_key = rest[1].strip()
        field = rest[2].strip()
        value = ";".join(rest[3:]).strip()
        return {"op": op, "datatable": dt, "row": row_key, "field": field, "value": value}
    except Exception:
        return {"op": "UNKNOWN"}

def apply_hotfix_for_table(rows: Dict[str, Any], hotfix_text: str, table_name_exact: str) -> None:
    """
    Hotfixを“特定のDataTable名だけ”に適用。
    """
    print(f"[HOTFIX:{table_name_exact}] start")
    applied = skipped = deleted = 0

    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h.get("op") in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        # 完全一致のみ許可（誤適用防止）
        if dt.split("/")[-1] != table_name_exact and dt != table_name_exact:
            continue

        op = h["op"]
        if op == "RowDelete":
            rk = h["row"]
            if rk in rows:
                rows.pop(rk, None)
                deleted += 1
                print(f"[{ln}] RowDelete {rk} -> DELETED")
            else:
                print(f"[{ln}] RowDelete {rk} -> SKIP(no row)")
            continue

        rk, field, val = h["row"], h["field"], h["value"]

        if rk not in rows:
            if op in ("RowAdd", "RowUpsert"):
                rows[rk] = {}
                print(f"[{ln}] {op} {rk} (create row)")
            else:
                skipped += 1
                print(f"[{ln}] {op} {rk}.{field}={val} -> SKIP(no row)")
                continue

        if not isinstance(rows[rk], dict):
            rows[rk] = {}
        ok, msg = set_by_path(rows[rk], field, val)

        if ok:
            applied += 1
            print(f"[{ln}] {op} {rk}.{field}={val} -> {msg}")
        else:
            skipped += 1
            print(f"[{ln}] {op} {rk}.{field}={val} -> NG({msg})")

    print(f"[HOTFIX:{table_name_exact}] done: applied={applied}, deleted={deleted}, skipped={skipped}")

# ---------- メイン ----------
def main():
    # ① Athena をベース、Season で上書き
    base_meta   = read_datatable_json(BASE_PATH)
    season_meta = read_datatable_json(SEASON_PATH)
    base_rows   = base_meta["Rows"]
    season_rows = season_meta["Rows"]

    rep1, add1 = merge_rows(base_rows, season_rows)
    print(f"[STEP1 MERGE] base <- season : replaced={rep1}, added={add1}")

    # ② Hotfix を“LootCurrentSeasonLootPackages_Client”にだけ適用
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        # シーズン差分に対して適用しても結果は同じだが、
        # 指示に忠実に「①の上書き後の状態（= base_rows内の該当行）」へ適用する。
        apply_hotfix_for_table(base_rows, text, HOTFIX_TARGET_TABLE)
    else:
        print("[HOTFIX] skipped (file not found)")

    # ③ Override で最終上書き
    override_meta = read_datatable_json(OVERRIDE_PATH)
    override_rows = override_meta["Rows"]
    rep3, add3 = merge_rows(base_rows, override_rows)
    print(f"[STEP3 MERGE] (hotfixed) <- override : replaced={rep3}, added={add3}")

    # 出力（メタ情報は base_meta のまま、Rows は最終状態）
    write_datatable_json(base_meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")

if __name__ == "__main__":
    main()
