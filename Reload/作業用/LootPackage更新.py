import json, re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ==== 入出力パス（環境に合わせて調整OK）====
PATH_ATHENA = Path(r"e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json")
PATH_BB     = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/BlastBerryLootPackages.json")
PATH_BB_OVR = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/AthenaLootPackages_Client_BlastBerryOverride.json")

HOTFIX_PATH = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")

OUT_FINAL   = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/作業用/AthenaLootPackages_Client__final_LP.json")

# ---- ユーティリティ ----
_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

def read_datatable_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{path.name}: 空です")
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{path.name}: DataTable形式ではありません（Rowsが無い）")
    return data


def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def set_by_path(row: Dict[str, Any], field_path: str, value_str: str):
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


def parse_hotfix_line(line: str) -> Dict[str, Any]:
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


def apply_hotfix_for_table(rows: Dict[str, Any], hotfix_text: str, table_keys) -> None:
    """
    Hotfixを“指定テーブル”だけに適用。
    table_keys: 受け付ける値の例
      - "AthenaLootPackages_Client"
      - "/BlastBerryLoot/DataTables/BlastBerryLootPackages"
      - {"AthenaLootPackages_Client", "/Game/Items/Datatables/AthenaLootPackages_Client"}
    """
    if isinstance(table_keys, str):
        table_keys = {table_keys}
    # 許容キーを（末尾名 / フルパス）両対応で持つ
    accept_tail = set(k.split("/")[-1] for k in table_keys)
    accept_full = set(table_keys)

    print(f"[HOTFIX:{','.join(sorted(accept_tail))}] start")
    applied = skipped = deleted = 0

    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h.get("op") in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        tail = dt.split("/")[-1]
        if (tail not in accept_tail) and (dt not in accept_full):
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

    print(f"[HOTFIX:{','.join(sorted(accept_tail))}] done: applied={applied}, deleted={deleted}, skipped={skipped}")


def main():
    # メタ（ベースはAthenaのメタを利用）
    meta_athena = read_datatable_json(PATH_ATHENA)
    rows_athena = meta_athena["Rows"]

    meta_bb     = read_datatable_json(PATH_BB)
    rows_bb     = meta_bb["Rows"]

    meta_ovr    = read_datatable_json(PATH_BB_OVR)
    rows_ovr    = meta_ovr["Rows"]

    # Hotfixテキスト
    hotfix_text = HOTFIX_PATH.read_text(encoding="utf-8") if HOTFIX_PATH.exists() else ""

    # ① AthenaLootPackages_Client に Hotfix
    if hotfix_text:
        apply_hotfix_for_table(rows_athena, hotfix_text, {"AthenaLootPackages_Client", "/Game/Items/Datatables/AthenaLootPackages_Client"})
    else:
        print("[HOTFIX] skipped (file not found)")

    # ② Athena に BlastBerryLootPackages を上書き
    rep, add = merge_rows(rows_athena, rows_bb)
    print(f"[STEP2] Athena <- BlastBerry : replaced={rep}, added={add}")

    # ③ BlastBerryLootPackages に Hotfix
    if hotfix_text:
        apply_hotfix_for_table(rows_bb, hotfix_text, {"/BlastBerryLoot/DataTables/BlastBerryLootPackages", "BlastBerryLootPackages"})

    # ④ BlastBerryLootPackages に AthenaLootPackages_Client_BlastBerryOverride を上書き
    rep, add = merge_rows(rows_bb, rows_ovr)
    print(f"[STEP4] BlastBerry <- BlastBerryOverride : replaced={rep}, added={add}")

    # ⑤ AthenaLootPackages_Client_BlastBerryOverride に Hotfix
    if hotfix_text:
        apply_hotfix_for_table(rows_ovr, hotfix_text, {"AthenaLootPackages_Client_BlastBerryOverride", "/BlastBerryLoot/DataTables/AthenaLootPackages_Client_BlastBerryOverride"})

    # --- 最終合体：Athena に（Hotfix後の）BB → OVR を順に反映 ---
    final_rows = rows_athena
    rep_b, add_b = merge_rows(final_rows, rows_bb)
    rep_o, add_o = merge_rows(final_rows, rows_ovr)
    print(f"[FINAL MERGE] Athena <- (BB, OVR) : replaced={rep_b+rep_o}, added={add_b+add_o}")

    # 出力（メタはAthenaのまま、Rowsは最終状態）
    write_datatable_json(meta_athena, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")


if __name__ == "__main__":
    main()
