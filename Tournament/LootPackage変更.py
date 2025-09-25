import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ====== 入出力（必要に応じて各自のパスに変更してください） ======
BASE_FINAL_PATH = Path("BR_Comp/作業用/AthenaLootPackages_Client__final.json")          # ①ベース
LAYER_ORIG_PATH = Path("e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")                 # ②上書き
OVERRIDE_PATH   = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BRPlaylists/Content/Athena/Playlists/Showdown/OverrideLootPackagesData.json")                  # ④上書き
BACKUP_PATH     = Path("e:/Fmodel/Exports/FortniteGame/Content/Athena/Playlists/Showdown/Tournament/OverrideLootPackagesData_Backup.json")           # ⑥上書き

HOTFIX_PATH     = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")                                     # ③/⑤/⑦ で使用
OUT_FINAL       = Path("Tournament/AthenaCompositeLP_Showdown__final.json")         # 出力

# Hotfix 対象テーブル名（末尾名一致でも適用されるように簡潔名で指定）
HOTFIX_TARGET_BASE    = "AthenaLootPackages_Client"          # ③
HOTFIX_TARGET_OVERRIDE= "OverrideLootPackagesData"           # ⑤
HOTFIX_TARGET_BACKUP  = "OverrideLootPackagesData_Backup"    # ⑦
HOTFIX_TARGET_FINAL = None


# ====== 共通ユーティリティ ======
_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

def read_datatable_json(path: Path) -> Dict[str, Any]:
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

def coerce_scalar(s: str) -> Any:
    s = s.strip()
    if _num_re.match(s):
        if "." in s or "e" in s.lower():
            try: return float(s)
            except Exception: return s
        try: return int(s)
        except Exception: return s
    sl = s.lower()
    if sl in ("true", "false"): return sl == "true"
    if sl == "null": return None
    try: return json.loads(s)
    except Exception: return s

def parse_unreal_tuple_to_dict(s: str) -> Dict[str, Any]:
    inner = s.strip()[1:-1].strip()
    out: Dict[str, Any] = {}
    if not inner: return out
    for seg in inner.split(","):
        if "=" not in seg: continue
        k, v = seg.split("=", 1)
        out[k.strip()] = coerce_scalar(v.strip())
    return out

def parse_unreal_tuple_to_list(s: str) -> List[Any]:
    inner = s.strip()[1:-1].strip()
    if not inner: return []
    return [coerce_scalar(v.strip()) for v in inner.split(",") if v.strip()]

def coerce_like(existing: Any, new_str: str) -> Any:
    s = new_str.strip()
    if s.startswith("(") and s.endswith(")"):
        if "=" in s:
            try: return parse_unreal_tuple_to_dict(s)
            except Exception: pass
        else:
            try: return parse_unreal_tuple_to_list(s)
            except Exception: pass
    if isinstance(existing, dict):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict): return parsed
        except Exception: pass
        return s
    if isinstance(existing, list):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list): return parsed
        except Exception: pass
        return [coerce_scalar(x.strip()) for x in s.split(",") if x.strip()]
    return coerce_scalar(s)

def set_by_path(row: Dict[str, Any], field_path: str, value_str: str) -> Tuple[bool, str]:
    keys = field_path.split(".")
    cur = row
    for k in keys[:-1]:
        if not isinstance(cur, dict): return False, f"not a dict at '{k}'"
        if k not in cur or not isinstance(cur[k], dict): cur[k] = {}
        cur = cur[k]
    last = keys[-1]
    existing = cur.get(last, None)
    cur[last] = coerce_like(existing, value_str)
    return True, ("OK" if existing is not None else "NEW")

def parse_hotfix_line(line: str) -> Dict[str, Any]:
    # サポート:
    # +DataTable=...;RowUpdate;RowKey;Field;Value
    # +DataTable=...;RowAdd;RowKey;Field;Value
    # +DataTable=...;RowUpsert;RowKey;Field;Value
    # +DataTable=...;RowDelete;RowKey
    # +DataTable=...;AddRow;"{...json...}"
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
        if op not in ("RowUpdate", "RowAdd", "RowUpsert", "RowDelete", "AddRow"):
            return {"op": "SKIP", "datatable": dt}

        if op == "RowDelete":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            return {"op": op, "datatable": dt, "row": rest[1].strip()}

        if op == "AddRow":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            row_json = rest[1].strip()
            return {"op": "AddRow", "datatable": dt, "rowobj": row_json}

        if len(rest) < 4:
            return {"op": "SKIP", "datatable": dt}
        row_key = rest[1].strip()
        field   = rest[2].strip()
        value   = ";".join(rest[3:]).strip()
        return {"op": op, "datatable": dt, "row": row_key, "field": field, "value": value}

    except Exception:
        return {"op": "UNKNOWN"}

def apply_hotfix_for_table(rows: Dict[str, Any], hotfix_text: str, table_name_exact: str) -> None:
    print(f"[HOTFIX:{table_name_exact}] start")
    applied = skipped = deleted = 0

    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h.get("op") in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        # 末尾名一致 or 完全一致を許容
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

        if op == "AddRow":
            try:
                obj = json.loads(h.get("rowobj", ""))
                row_key = obj.get("Name") or obj.get("RowName")
                if not row_key:
                    print(f"[{ln}] AddRow -> SKIP(no Name/RowName)")
                    continue
                rows[row_key] = obj
                print(f"[{ln}] AddRow {row_key} -> NEW")
            except Exception as e:
                print(f"[{ln}] AddRow parse error: {e}")
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


# ====== メイン（7ステップ） ======
def main():
    # ① LAYER_ORIG_PATH をベース
    if LAYER_ORIG_PATH and LAYER_ORIG_PATH.exists():
        base_meta = read_datatable_json(LAYER_ORIG_PATH)
        base_rows = base_meta["Rows"]
        print("[STEP1] base = AthenaLootPackages_Client")
        # ①-Hotfix（AthenaLootPackages_Client）
        if HOTFIX_PATH and HOTFIX_PATH.exists() and HOTFIX_TARGET_BASE:
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            apply_hotfix_for_table(base_rows, text, HOTFIX_TARGET_BASE)
    else:
        raise FileNotFoundError("LAYER_ORIG_PATH が見つかりません")

    # ② OverrideLootPackagesData を上書き
    if OVERRIDE_PATH and OVERRIDE_PATH.exists():
        ov_meta = read_datatable_json(OVERRIDE_PATH)
        rep, add = merge_rows(base_rows, ov_meta["Rows"])
        print(f"[STEP2] base <- OverrideLootPackagesData : replaced={rep}, added={add}")
        # ②-Hotfix（OverrideLootPackagesData）
        if HOTFIX_PATH and HOTFIX_PATH.exists() and HOTFIX_TARGET_OVERRIDE:
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            apply_hotfix_for_table(base_rows, text, HOTFIX_TARGET_OVERRIDE)
    else:
        print("[STEP2] skipped (OverrideLootPackagesData.json not found)")

    # ③ OverrideLootPackagesData_Backup を上書き（任意）
    if BACKUP_PATH and isinstance(BACKUP_PATH, Path) and BACKUP_PATH.exists():
        bk_meta = read_datatable_json(BACKUP_PATH)
        rep, add = merge_rows(base_rows, bk_meta["Rows"])
        print(f"[STEP3] (override) <- OverrideLootPackagesData_Backup : replaced={rep}, added={add}")
        # ③-Hotfix（OverrideLootPackagesData_Backup）
        if HOTFIX_PATH and HOTFIX_PATH.exists() and HOTFIX_TARGET_BACKUP:
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            apply_hotfix_for_table(base_rows, text, HOTFIX_TARGET_BACKUP)
    else:
        print("[STEP3] skipped (OverrideLootPackagesData_Backup.json not found)")

    # ④ 最後に AthenaLootPackages_Client__final を上書き
    """if BASE_FINAL_PATH and BASE_FINAL_PATH.exists():
        final_meta = read_datatable_json(BASE_FINAL_PATH)
        rep, add = merge_rows(base_rows, final_meta["Rows"])
        print(f"[STEP4] (all) <- AthenaLootPackages_Client__final : replaced={rep}, added={add}")
        # ④-Hotfix（final 用がある場合のみ）
        if HOTFIX_PATH and HOTFIX_PATH.exists() and 'HOTFIX_TARGET_FINAL' in globals() and HOTFIX_TARGET_FINAL:
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            apply_hotfix_for_table(base_rows, text, HOTFIX_TARGET_FINAL)
    else:
        print("[STEP4] skipped (AthenaLootPackages_Client__final.json not found)")"""

    # 出力
    write_datatable_json(base_meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")


if __name__ == "__main__":
    main()
