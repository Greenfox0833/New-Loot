import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ========== 入出力 ==========
# 🔧 パスは環境に合わせて調整してください
HOTFIX_PATH = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")
OUT_FINAL   = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/NoBuild_Comp/作業用/AthenaLootTierData_Client__final.json")

# ①〜（⑧相当）まで、LootTierの段階をこの順で適用します
# name: ログ表示用
# path: DataTable(JSON) の場所（FModel出力など）
# hotfix_keys: Hotfix.ini の +DataTable=... 部分と部分一致（大小無視）でこの段階のHotfixだけを適用
STAGES = [
    {
        "name": "① AthenaLootTierData_Client",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootTierData_Client.json"),
        "hotfix_keys": [
            "/Game/Items/Datatables/AthenaLootTierData_Client",
            "AthenaLootTierData_Client",
        ],
    },
    {
        "name": "② 上書き: LootCurrentSeasonLootTierData_Client",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/LootCurrentSeasonLootTierData_Client.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/LootCurrentSeasonLootTierData_Client",
            "LootCurrentSeasonLootTierData_Client",
        ],
    },
    {
        "name": "④ 上書き: LootCurrentSeasonLootTierData_Client_Comp",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/Comp/LootCurrentSeasonLootTierData_Client_Comp.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/Comp/LootCurrentSeasonLootTierData_Client_Comp",
            "LootCurrentSeasonLootTierData_Client_Comp",
        ],
    },
    {
        "name": "⑥ 上書き: OverrideLootTierData_NoBuildBR",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/OverrideLootTierData_NoBuildBR.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/NoBuildBR/OverrideLootTierData_NoBuildBR",
            "OverrideLootTierData_NoBuildBR",
        ],
    },
    {
        "name": "⑧ 上書き: OverrideLootTierData_NoBuildBR_Comp",
        "path": Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/LootCurrentSeason/Content/DataTables/NoBuildBR/Comp_NoBuild/OverrideLootTierData_NoBuildBR_Comp.json"),
        "hotfix_keys": [
            "/LootCurrentSeason/DataTables/NoBuildBR/Comp_NoBuild/OverrideLootTierData_NoBuildBR_Comp",
            "OverrideLootTierData_NoBuildBR_Comp",
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

def _deep_merge_dict(dst: Dict[str, Any], src: Dict[str, Any]) -> Tuple[int, int]:
    rep = add = 0
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            r, a = _deep_merge_dict(dst[k], v)
            rep += r; add += a
        else:
            if k in dst:
                rep += 1
            else:
                add += 1
            dst[k] = v
    return rep, add

def merge_rows(base_rows: Dict[str, Any], override_rows: Dict[str, Any]) -> Tuple[int, int]:
    replaced = added = 0
    for k, v in override_rows.items():
        if k in base_rows and isinstance(base_rows[k], dict) and isinstance(v, dict):
            r, a = _deep_merge_dict(base_rows[k], v)
            replaced += r; added += a
        else:
            if k in base_rows:
                replaced += 1
            else:
                added += 1
            base_rows[k] = v
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
    if inner:
        for seg in inner.split(","):
            if "=" in seg:
                k, v = seg.split("=", 1)
                out[k.strip()] = coerce_scalar(v.strip())
    return out

def parse_unreal_tuple_to_list(s: str) -> List[Any]:
    inner = s.strip()[1:-1].strip()
    return [coerce_scalar(v.strip()) for v in inner.split(",") if v.strip()] if inner else []

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
def _parse_bulk_json(text: str):
    try:
        obj = json.loads(text)
        if isinstance(obj, str):
            return json.loads(obj)
        return obj
    except Exception:
        t = text.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1]
        t = t.replace('\\"', '"')
        return json.loads(t)

def parse_hotfix_line(line: str) -> Dict[str, Any]:
    line = line.strip()
    if not line or line.startswith("#"):
        return {"op": "COMMENT"}
    if not (line.startswith("+") or line.startswith("-")):
        return {"op": "UNKNOWN"}
    after = line[1:]
    first_seg, *rest = after.split(";")
    if "DataTable=" not in first_seg:
        return {"op": "UNKNOWN"}
    dt = first_seg.split("=", 1)[1].strip()
    if not rest:
        return {"op": "UNKNOWN"}
    op = rest[0].strip()
    op_lower = op.lower()

    if op_lower == "addrow":
        joined = ";".join(rest[1:]).strip()
        payload = _parse_bulk_json(joined)
        return {"op": "AddRow", "datatable": dt, "payload": payload}

    if op_lower == "rowdelete":
        if len(rest) < 2:
            return {"op": "SKIP"}
        return {"op": "RowDelete", "datatable": dt, "row": rest[1].strip()}

    # RowUpdate / RowAdd / RowUpsert
    if len(rest) < 4:
        return {"op": "SKIP"}
    return {
        "op": rest[0].strip(),
        "datatable": dt,
        "row": rest[1].strip(),
        "field": rest[2].strip(),
        "value": ";".join(rest[3:]).strip()
    }

def normalize_addrow_payload(d: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    dd = dict(d)
    row_name = dd.pop("Name", None) or dd.pop("RowName", None)
    if not row_name or not isinstance(row_name, str):
        raise ValueError("AddRow payload に Name/RowName がありません")
    # 代表的な正規化（必要に応じて拡張）
    ql = dd.get("QuotaLevel")
    if isinstance(ql, str) and not ql.startswith("ELootQuotaLevel::"):
        if ql.lower() == "unlimited":
            dd["QuotaLevel"] = "ELootQuotaLevel::Unlimited"
    gt = dd.get("GameplayTags")
    if isinstance(gt, dict) and "GameplayTags" in gt:
        dd["GameplayTags"] = gt.get("GameplayTags", [])
    return row_name, dd

def _hotfix_match(dt_token: str, filters: List[str]) -> bool:
    d = dt_token.lower()
    return any(f and f.lower() in d for f in filters)

def apply_hotfix(rows: Dict[str, Any], hotfix_text: str, filters: List[str]) -> Tuple[int, int, int]:
    applied = skipped = deleted = 0
    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h.get("op") in ("COMMENT", "UNKNOWN", "SKIP"):
            continue
        if not _hotfix_match(h.get("datatable",""), filters):
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

        if op == "AddRow":
            try:
                obj = h["payload"]
                arr = obj if isinstance(obj, list) else [obj]
                added = 0
                for item in arr:
                    if not isinstance(item, dict):
                        continue
                    row_name, payload = normalize_addrow_payload(item)
                    rows[row_name] = payload
                    added += 1
                applied += added
                print(f"[HOTFIX:{ln}] AddRow -> added {added} row(s)")
            except Exception as e:
                skipped += 1
                print(f"[HOTFIX:{ln}] AddRow -> ERROR: {e}")
            continue

        rk, field, val = h["row"], h["field"], h["value"]
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

    # ① 読み込み（AthenaLootTierData_Client）
    first = STAGES[0]
    meta = read_datatable_json(first["path"])
    rows = meta["Rows"]

    # ① Hotfix
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
