import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ====== 入出力パス（あなたのPCに合わせて変更OK） ======
FIGMENT_LTD_PATH        = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/FigmentLootTierData.json")
FIGMENT_LTD_BACKUP_PATH = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/NoBuild/NoBuildFigmentLootTierData_Override.json")
HOTFIX_INI_PATH         = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")  # 無ければ自動スキップ

OUT_FINAL               = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment_NoBuild/FigmentLootTierData__final.json")
# =====================================================

# Hotfix を当てる対象テーブル名のヒント（含有判定）
TARGET_TABLE_NAMES = (
    "/Figment_LootTables/DataTables/FigmentLootTierData",
    "/Figment_LootTables/DataTables/NoBuild/NoBuildFigmentLootTierData_Override",
)

_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

# ---------- 基本I/O ----------
def read_datatable_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{path.name}: 空です")
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{path.name}: DataTable形式（Rows）が見つかりません")
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

# ---------- 値の解釈 ----------
def split_top_level(s: str, delim: str) -> List[str]:
    """かっこ/クォートに強い top-level split"""
    out, buf = [], []
    depth, in_quote, escape = 0, None, False
    for ch in s:
        if escape:
            buf.append(ch); escape = False; continue
        if ch == "\\":
            buf.append(ch); escape = True; continue
        if in_quote:
            buf.append(ch)
            if ch == in_quote: in_quote = None
            continue
        if ch in ("'", '"'):
            buf.append(ch); in_quote = ch; continue
        if ch == "(":
            buf.append(ch); depth += 1; continue
        if ch == ")":
            buf.append(ch); depth = max(0, depth-1); continue
        if ch == delim and depth == 0:
            out.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if buf: out.append("".join(buf))
    return out

def coerce_scalar(s: str):
    s = s.strip()
    if (len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"))):
        return s[1:-1]
    if _num_re.match(s):
        try:
            return int(s)
        except Exception:
            try:
                return float(s)
            except Exception:
                pass
    sl = s.lower()
    if sl == "true":  return True
    if sl == "false": return False
    if sl == "null":  return None
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            return s
    if s.startswith("(") and s.endswith(")") and "=" in s:  # "(X=...,Y=...)"
        inner = s[1:-1]
        out = {}
        for seg in split_top_level(inner, ","):
            if "=" not in seg: continue
            k, v = seg.split("=", 1)
            out[k.strip()] = coerce_scalar(v.strip())
        return out
    return s

def coerce_like(existing: Any, new_str: str) -> Any:
    s = new_str.strip()
    if isinstance(existing, dict):
        if s.startswith("(") and s.endswith(")") and "=" in s:
            # Unreal tuple to dict
            inner = s[1:-1]
            out = {}
            for seg in split_top_level(inner, ","):
                if "=" not in seg: continue
                k, v = seg.split("=", 1)
                out[k.strip()] = coerce_scalar(v.strip())
            return out
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return s
    if isinstance(existing, list):
        if s.startswith("(") and s.endswith(")") and "=" not in s:
            inner = s[1:-1]
            return [coerce_scalar(v.strip()) for v in split_top_level(inner, ",") if v.strip()]
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
        if not isinstance(cur, dict) or k not in cur:
            return False, f"missing '{k}'"
        cur = cur[k]
    last = keys[-1]
    existing = cur.get(last, None)
    cur[last] = coerce_like(existing, value_str)
    return True, "OK" if existing is not None else "NEW"

# ---------- Hotfix 解析（+区切り形式） ----------
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
        return {"op": op, "datatable": dt, "row": (rest[1].strip() if len(rest) > 1 else "")}
    if len(rest) < 4:
        return {"op": "SKIP"}
    return {
        "op": op,
        "datatable": dt,
        "row": rest[1].strip(),
        "field": rest[2].strip(),
        "value": ";".join(rest[3:]).strip(),
    }

def apply_hotfix(rows: Dict[str, Any], hotfix_text: str) -> None:
    print("[HOTFIX] start")
    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        if h["op"] in ("COMMENT", "UNKNOWN", "SKIP"):
            continue
        if not any(name.lower() in h["datatable"].lower() for name in TARGET_TABLE_NAMES):
            continue
        if h["op"] == "RowDelete":
            rn = h.get("row", "")
            if rn and rn in rows:
                rows.pop(rn)
                print(f"[{ln}] DELETE {rn}")
            continue
        rn = h["row"]
        if rn not in rows:
            rows[rn] = {}
            print(f"[{ln}] {h['op']} {rn} (create row)")
        ok, msg = set_by_path(rows[rn], h["field"], h["value"])
        print(f"[{ln}] {h['op']} {rn}.{h['field']}={h['value']} -> {msg}")
    print("[HOTFIX] done")

# ---------- メイン ----------
def main():
    print("[LOAD]", FIGMENT_LTD_PATH)
    base_meta = read_datatable_json(FIGMENT_LTD_PATH)
    base_rows = base_meta.get("Rows", {})

    # ① Hotfix: FigmentLootTierData のみ適用
    if HOTFIX_INI_PATH.exists():
        print("[HOTFIX] read", HOTFIX_INI_PATH)
        hot = HOTFIX_INI_PATH.read_text(encoding="utf-8", errors="ignore")
        apply_hotfix(base_rows, hot)
    else:
        print("[HOTFIX] skipped (not found)")

    # ② Backup を上書き（Backup優先）
    if FIGMENT_LTD_BACKUP_PATH.exists():
        print("[LOAD]", FIGMENT_LTD_BACKUP_PATH)
        backup_meta = read_datatable_json(FIGMENT_LTD_BACKUP_PATH)
        backup_rows = backup_meta.get("Rows", {})
        replaced, added = merge_rows(base_rows, backup_rows)
        print(f"[MERGE] backup override -> replaced={replaced}, added={added}")
    else:
        print("[MERGE] skipped (backup not found)")

    # 保存（メタ情報はベースを流用）
    base_meta["Rows"] = base_rows
    write_datatable_json(base_meta, OUT_FINAL)
    print("[WRITE] final ->", OUT_FINAL)

if __name__ == "__main__":
    main()
