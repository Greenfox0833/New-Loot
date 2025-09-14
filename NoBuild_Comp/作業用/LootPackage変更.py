import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ========== 入出力 ==========
# 🔧 ここをあなたの環境に合わせて設定してください
HOTFIX_PATH = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")
OUT_FINAL   = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/NoBuild_Comp/作業用/AthenaLootPackages_Client__final.json")

# ①〜⑧の順で「データを読み込み → Hotfix適用 → 次のテーブルで上書き → Hotfix適用 …」を行う
# path: そのテーブルの DataTable(JSON) へのパス
# hotfix_keys: Hotfix.ini の `+DataTable=...` の “...（識別子）” と突き合わせるフィルタ（部分一致/大小無視）
STAGES = [
    {
        "name": "① AthenaLootPackages_Client",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json"),
        "hotfix_keys": [
            "/Game/Items/Datatables/AthenaLootPackages_Client",
            "AthenaLootPackages_Client",
        ],
    },
    {
        "name": "② 上書き: LootCurrentSeasonLootPackages_Client",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootPackages_Client.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/LootCurrentSeasonLootPackages_Client",
            "LootCurrentSeasonLootPackages_Client",
        ],
    },
    {
        "name": "④ 上書き: LootCurrentSeasonLootPackages_Client_Comp",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/Comp/LootCurrentSeasonLootPackages_Client_Comp",
            "LootCurrentSeasonLootPackages_Client_Comp",
        ],
    },
    {
        "name": "⑥ 上書き: OverrideLootPackagesData_NoBuildBR",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/OverrideLootPackagesData_NoBuildBR.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/NoBuildBR/OverrideLootPackagesData_NoBuildBR",
            "OverrideLootPackagesData_NoBuildBR",
        ],
    },
    {
        "name": "⑧ 上書き: OverrideLootPackagesData_NoBuildBR_Comp",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/Comp_NoBuild/OverrideLootPackagesData_NoBuildBR_Comp.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/NoBuildBR/Comp_NoBuild/OverrideLootPackagesData_NoBuildBR_Comp",
            "OverrideLootPackagesData_NoBuildBR_Comp",
        ],
    },
]

# ========== 以降は原則そのままでOK ==========

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

# ---------- 値の型合わせ ----------
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
        op_lower = op.lower()

        # AddRow （JSON丸ごと）
        if op_lower == "addrow":
            raw = ";".join(rest[1:]).strip()
            if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
            if raw.startswith('{') and '\\"' in raw:
                raw = raw.replace('\\"', '"')
            if not (raw.lstrip().startswith("{") and raw.rstrip().endswith("}")):
                op = "RowAdd"
            else:
                try:
                    row_data = json.loads(raw)
                    row_key = row_data.get("Name")
                    if not row_key:
                        return {"op": "SKIP", "datatable": dt}
                    return {"op": "RowAddJSON", "datatable": dt, "row": row_key, "data": row_data}
                except Exception:
                    return {"op": "SKIP", "datatable": dt}

        if op not in ("RowUpdate", "RowAdd", "RowUpsert", "RowDelete", "RowAddJSON"):
            return {"op": "SKIP", "datatable": dt}

        if op == "RowDelete":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            return {"op": op, "datatable": dt, "row": rest[1].strip()}

        if op == "RowAddJSON":
            pass  # すでにreturn済み

        if len(rest) < 4:
            return {"op": "SKIP", "datatable": dt}
        row_key = rest[1].strip()
        field = rest[2].strip()
        value = ";".join(rest[3:]).strip()
        return {"op": op, "datatable": dt, "row": row_key, "field": field, "value": value}
    except Exception:
        return {"op": "UNKNOWN"}

def _hotfix_match(dt_token: str, filters: List[str]) -> bool:
    d = dt_token.lower()
    for f in filters:
        if f and f.lower() in d:
            return True
    return False

def apply_hotfix(rows: Dict[str, Any], hotfix_text: str, filters: List[str]) -> Tuple[int, int, int]:
    """
    指定filters（DataTable識別子の部分一致）にヒットする命令のみ rows に適用。
    rows は “現在までの累積合成結果” に対して直接変化させる。
    """
    applied = skipped = deleted = 0
    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h.get("op") in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        if not _hotfix_match(dt, filters):
            continue

        op = h["op"]

        if op == "RowDelete":
            rk = h["row"]
            if rk in rows:
                rows.pop(rk, None)
                deleted += 1
                print(f"[HOTFIX:{ln}] RowDelete {rk} -> DELETED")
            else:
                print(f"[HOTFIX:{ln}] RowDelete {rk} -> SKIP(no row)")
            continue

        if op == "RowAddJSON":
            rk = h["row"]
            rows[rk] = h["data"]
            applied += 1
            print(f"[HOTFIX:{ln}] RowAddJSON {rk} -> CREATED")
            continue

        rk, field, val = h["row"], h["field"], h["value"]

        # RowAdd/Upsertで行が無ければ作る
        if rk not in rows and op in ("RowAdd", "RowUpsert"):
            rows[rk] = {}
            print(f"[HOTFIX:{ln}] {op} {rk} (create row)")

        if rk not in rows:
            skipped += 1
            print(f"[HOTFIX:{ln}] {op} {rk}.{field}={val} -> SKIP(no row)")
            continue

        if not isinstance(rows[rk], dict):
            rows[rk] = {}

        ok, msg = set_by_path(rows[rk], field, val)
        if ok:
            applied += 1
            print(f"[HOTFIX:{ln}] {op} {rk}.{field}={val} -> {msg}")
        else:
            skipped += 1
            print(f"[HOTFIX:{ln}] {op} {rk}.{field}={val} -> NG({msg})")

    return applied, deleted, skipped

# ---------- メイン ----------
def main():
    if not STAGES:
        raise RuntimeError("STAGES が空です")

    # ① 読み込み（AthenaLootPackages_Client）
    first = STAGES[0]
    meta = read_datatable_json(first["path"])
    if "Rows" not in meta:
        raise ValueError(f"{first['path'].name}: Rowsがありません")
    rows = meta["Rows"]

    # ① Hotfix（AthenaLootPackages_Client 向け）
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        a, d, s = apply_hotfix(rows, text, first["hotfix_keys"])
        print(f"[{first['name']}] Hotfix: applied={a}, deleted={d}, skipped={s}")
    else:
        print(f"[{first['name']}] Hotfix: skipped (file not found)")

    # ②以降：上書き → 直後にそのテーブル用Hotfix
    for i in range(1, len(STAGES)):
        st = STAGES[i]
        print(f"[MERGE] {st['name']}")
        over_meta = read_datatable_json(st["path"])
        rep, add = merge_rows(rows, over_meta["Rows"])
        print(f"  merged: replaced={rep}, added={add}")

        if HOTFIX_PATH.exists():
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            a, d, s = apply_hotfix(rows, text, st["hotfix_keys"])
            print(f"  Hotfix({st['name']}): applied={a}, deleted={d}, skipped={s}")
        else:
            print(f"  Hotfix({st['name']}): skipped (file not found)")

    # 保存（最終合成結果）
    meta["Rows"] = rows
    OUT_FINAL.parent.mkdir(parents=True, exist_ok=True)
    write_datatable_json(meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")

if __name__ == "__main__":
    main()
