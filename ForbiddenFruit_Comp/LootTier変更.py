# LootTier変更_完全版.py
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ==== ファイルパス設定 ====
BASE_PATH   = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/ForbiddenFruitDataTables/Content/DataTables/ForbiddenFruitChapterLootTierData.json")  # ①ベース
OVERRIDE_NOBUILD_PATH = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/ForbiddenFruitDataTables/Content/DataTables/AthenaLootTierData_Client_ForbiddenFruitChapterOverride_NoBuild.json")  # ②上書き
OVERRIDE_SHOWDOWN_PATH = Path("e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/ForbiddenFruitDataTables/Content/DataTables/Showdown/NoBuild/AthenaLootTierData_Client_ForbiddenFruitChapterOverride_NoBuild_Showdown.json")  # ③最終上書き
HOTFIX_PATH = Path("e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")
OUT_FINAL   = Path("E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/ForbiddenFruit_Comp/AthenaLootTierData_Client__final.json")

HOTFIX_TARGET_TABLES = (
    "/ForbiddenFruitDataTables/DataTables/ForbiddenFruitChapterLootTierData",
    "ForbiddenFruitChapterLootTierData",
)

_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


# ---------- 基本関数 ----------
def read_datatable_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{path.name}: Rowsが見つかりません")
    return data


def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([meta], f, ensure_ascii=False, indent=2)


def _deep_merge_dict(dst: Dict[str, Any], src: Dict[str, Any]) -> Tuple[int, int]:
    rep = add = 0
    for k, v in src.items():
        if k in dst:
            if isinstance(dst[k], dict) and isinstance(v, dict):
                r, a = _deep_merge_dict(dst[k], v)
                rep += r; add += a
            else:
                dst[k] = v
                rep += 1
        else:
            dst[k] = v
            add += 1
    return rep, add


def merge_rows(base_rows: Dict[str, Any], override_rows: Dict[str, Any]) -> Tuple[int, int]:
    replaced = added = 0
    for k, v in override_rows.items():
        if k in base_rows and isinstance(base_rows[k], dict) and isinstance(v, dict):
            r, a = _deep_merge_dict(base_rows[k], v)
            replaced += r; added += a
        else:
            base_rows[k] = v
            replaced += 1
    return replaced, added


def coerce_scalar(s: str) -> Any:
    if _num_re.match(s):
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.lower() == "null":
        return None
    try:
        return json.loads(s)
    except Exception:
        return s


def parse_unreal_tuple_to_dict(s: str) -> Dict[str, Any]:
    inner = s.strip()[1:-1]
    return {k.strip(): coerce_scalar(v.strip()) for k, v in (seg.split("=", 1) for seg in inner.split(",") if "=" in seg)}


def parse_unreal_tuple_to_list(s: str) -> List[Any]:
    inner = s.strip()[1:-1]
    return [coerce_scalar(v.strip()) for v in inner.split(",") if v.strip()]


def coerce_like(existing: Any, new_str: str) -> Any:
    s = new_str.strip()
    if isinstance(existing, dict):
        if s.startswith("(") and s.endswith(")") and "=" in s:
            return parse_unreal_tuple_to_dict(s)
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return s
    if isinstance(existing, list):
        if s.startswith("(") and s.endswith(")") and "=" not in s:
            return parse_unreal_tuple_to_list(s)
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return [coerce_scalar(x.strip()) for x in s.split(",")]
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


def parse_hotfix_line(line: str) -> Dict[str, Any]:
    line = line.strip()
    if not line or line.startswith("#"):
        return {"op": "COMMENT"}
    if not line.startswith("+"):
        return {"op": "UNKNOWN"}
    after = line[1:]
    first_seg, *rest = after.split(";")
    if "DataTable=" not in first_seg:
        return {"op": "UNKNOWN"}
    dt = first_seg.split("=", 1)[1].strip()
    if not rest:
        return {"op": "UNKNOWN"}
    op = rest[0].strip()
    if op == "RowDelete":
        return {"op": op, "datatable": dt, "row": rest[1].strip()}
    if len(rest) < 4:
        return {"op": "SKIP"}
    return {"op": op, "datatable": dt, "row": rest[1].strip(), "field": rest[2].strip(), "value": ";".join(rest[3:]).strip()}


def apply_hotfix(rows: Dict[str, Any], hotfix_text: str, allowed_table_names: Tuple[str, ...]) -> None:
    print("[HOTFIX] start")
    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h["op"] in ("COMMENT", "UNKNOWN", "SKIP"):
            continue
        if not any(name.lower() in h["datatable"].lower() for name in allowed_table_names):
            continue
        if h["op"] == "RowDelete":
            if h["row"] in rows:
                rows.pop(h["row"])
                print(f"[{ln}] DELETE {h['row']}")
            continue
        if h["row"] not in rows:
            rows[h["row"]] = {}
            print(f"[{ln}] {h['op']} {h['row']} (create row)")
        ok, msg = set_by_path(rows[h["row"]], h["field"], h["value"])
        print(f"[{ln}] {h['op']} {h['row']}.{h['field']}={h['value']} -> {msg}")
    print("[HOTFIX] done")


# ---------- メイン ----------
def main():
    # 1) ベース読込
    base_meta = read_datatable_json(BASE_PATH)
    base_rows = base_meta["Rows"]

    # 2) Hotfix（ベースにのみ適用）
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        apply_hotfix(base_rows, text, HOTFIX_TARGET_TABLES)
    else:
        print("[HOTFIX] skipped (file not found)")

    # 3) NoBuild 上書き
    nobuild_meta = read_datatable_json(OVERRIDE_NOBUILD_PATH)
    rep, add = merge_rows(base_rows, nobuild_meta["Rows"])
    print(f"[MERGE Override_NoBuild] replaced={rep}, added={add}")

    # 4) Showdown 上書き
    showdown_meta = read_datatable_json(OVERRIDE_SHOWDOWN_PATH)
    rep, add = merge_rows(base_rows, showdown_meta["Rows"])
    print(f"[MERGE Override_NoBuild_Showdown] replaced={rep}, added={add}")

    # 5) 出力
    write_datatable_json(base_meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")


if __name__ == "__main__":
    main()
