import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple, List

# ====== 入出力パス（あなたのPCに合わせて変更OK） ======
FIGMENT_PATH        = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/FigmentLootPackages.json")
FIGMENT_BACKUP_PATH = Path(r"e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/Figment/Figment_LootTables/Content/DataTables/FigmentLootPackages_Backup.json")
HOTFIX_INI_PATH     = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini")  # 無ければ自動スキップ

OUT_FINAL           = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Figment/FigmentLootPackages__final.json")
# =====================================================

# DataTable名にこの語を含む行のみ Hotfix を適用
TARGET_TABLE_HINT = "/Figment_LootTables/DataTables/FigmentLootPackages"

_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")

def read_datatable_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # FModel出力（配列 or 単体）に両対応
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
    # 文字列（クォート付き）
    if (len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"))):
        return s[1:-1]
    # 数値
    if _num_re.match(s):
        try:
            return int(s)
        except Exception:
            try:
                return float(s)
            except Exception:
                pass
    # 真偽/NULL
    sl = s.lower()
    if sl == "true":  return True
    if sl == "false": return False
    if sl == "null":  return None
    # JSON 風（{} / []）
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            return json.loads(s)
        except Exception:
            return s
    # Unreal Tuple "(X=...,Y=...)" 形式
    if s.startswith("(") and s.endswith(")") and "=" in s:
        inner = s[1:-1]
        out = {}
        for seg in split_top_level(inner, ","):
            if "=" not in seg: continue
            k, v = seg.split("=", 1)
            out[k.strip()] = coerce_scalar(v.strip())
        return out
    return s

def coerce_like(existing, new_str: str):
    s = new_str.strip()
    if isinstance(existing, dict):
        if s.startswith("(") and s.endswith(")") and "=" in s:
            inner = s[1:-1]
            out = {}
            for seg in split_top_level(inner, ","):
                if "=" not in seg: continue
                k, v = seg.split("=", 1)
                out[k.strip()] = coerce_scalar(v.strip())
            return out
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return s
    if isinstance(existing, list):
        if s.startswith("(") and s.endswith(")") and "=" not in s:
            inner = s[1:-1]
            return [coerce_scalar(v.strip()) for v in split_top_level(inner, ",") if v.strip()]
        try:
            obj = json.loads(s)
            if isinstance(obj, list):
                return obj
        except Exception:
            return [coerce_scalar(x.strip()) for x in s.split(",") if x.strip()]
    return coerce_scalar(s)

def set_by_path(row: dict, field_path: str, value_str: str):
    """
    'A.B.C' のようなフィールドパスに値をセット（親が無ければ dict を作る）
    既存値の型に寄せて変換（数値/真偽/配列/辞書/Unreal Tuple 等）
    """
    cur = row
    parts = field_path.split(".")
    for k in parts[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    last = parts[-1]
    existing = cur.get(last, None)
    cur[last] = coerce_like(existing, value_str)


# 代表的な Hotfix 1行の例（ゆるくマッチ）:
# DataTable'/Figment_LootTables/DataTables/FigmentLootPackages.FigmentLootPackages' (...)
_hotfix_re = re.compile(
    r"""DataTable[^'"]*['"](?P<dt>[^'"]*?)(?:\.(?P<dtn>[^'"]+))?['"][^)]*
        RowName\s*=\s*(?P<row>"[^"]*"|'[^']*'|[^\s,()]+)\s*,\s*
        ColumnName\s*=\s*(?P<col>"[^"]*"|'[^']*'|[^\s,()]+)\s*,\s*
        Value\s*=\s*(?P<val>.+?)\)""",
    re.IGNORECASE | re.VERBOSE
)

def apply_hotfix_plus(rows: dict, hotfix_text: str, table_hint: str) -> int:
    """
    +DataTable=/...;RowUpdate;RowName;Field;Value
    +DataTable=/...;RowSet;RowName;Field;Value
    +DataTable=/...;RowDelete;RowName
    の各行を適用。DataTable が table_hint を含むものだけ対象。
    """
    applied = 0
    for line in hotfix_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("+"):
            continue
        body = line[1:]
        if "DataTable=" not in body:
            continue
        first, *rest = body.split(";")
        dt = first.split("=", 1)[1].strip()
        if table_hint.lower() not in dt.lower():
            continue
        if not rest:
            continue
        op = (rest[0] if len(rest) > 0 else "").strip()

        if op == "RowDelete":
            rn = (rest[1] if len(rest) > 1 else "").strip()
            if rn and rn in rows:
                rows.pop(rn, None)
                applied += 1
            continue

        # RowUpdate / RowSet
        if len(rest) < 4:
            continue
        rn   = rest[1].strip()
        fld  = rest[2].strip()
        val  = ";".join(rest[3:]).strip()  # 値に ';' を含んでもOK

        if rn not in rows:
            rows[rn] = {}
        set_by_path(rows[rn], fld, val)
        applied += 1
    return applied

def apply_hotfix_to_rows(rows: Dict[str, Any], hotfix_text: str) -> int:
    """
    Hotfix.ini から RowName/ColumnName/Value の行を拾って rows に適用。
    DataTable パス/名に TARGET_TABLE_HINT を含むものだけを対象。
    戻り値: 適用件数
    """
    applied = 0
    for m in _hotfix_re.finditer(hotfix_text):
        dt_full = (m.group("dt") or "") + "." + (m.group("dtn") or "")
        if TARGET_TABLE_HINT.lower() not in dt_full.lower():
            continue
        row = m.group("row").strip().strip('"\'' )
        col = m.group("col").strip().strip('"\'' )
        val_raw = m.group("val").strip()
        if val_raw.endswith(","):  # 末尾のカンマ対策
            val_raw = val_raw[:-1].rstrip()
        value = coerce_scalar(val_raw)

        r = rows.get(row)
        if r is None:
            rows[row] = {col: value}
            applied += 1
            continue
        # ネスト対応: "A.B.C" のような ColumnName
        try:
            tgt = r
            parts = col.split(".")
            for part in parts[:-1]:
                if part not in tgt or not isinstance(tgt[part], dict):
                    tgt[part] = {}
                tgt = tgt[part]
            tgt[parts[-1]] = value
            applied += 1
        except Exception:
            r[col] = value
            applied += 1
    return applied

def main():
    print("[LOAD]", FIGMENT_PATH)
    base_meta = read_datatable_json(FIGMENT_PATH)
    base_rows = base_meta.get("Rows", {})

    # ① Hotfix: FigmentLootPackages のみ適用（+形式と従来形式の両方に対応）
    if HOTFIX_INI_PATH.exists():
        print("[HOTFIX] read", HOTFIX_INI_PATH)
        hot = HOTFIX_INI_PATH.read_text(encoding="utf-8", errors="ignore")
        cnt1 = apply_hotfix_plus(base_rows, hot, TARGET_TABLE_HINT)   # +DataTable;RowUpdate 形式
        cnt2 = apply_hotfix_to_rows(base_rows, hot)                   # 従来の RowName/ColumnName/Value 形式
        print(f"[HOTFIX] applied: {cnt1 + cnt2} change(s)  (plus={cnt1}, legacy={cnt2})")
    else:
        print("[HOTFIX] skipped (not found)")


    # ② Backup を上書き（Backup優先）
    if FIGMENT_BACKUP_PATH.exists():
        print("[LOAD]", FIGMENT_BACKUP_PATH)
        backup_meta = read_datatable_json(FIGMENT_BACKUP_PATH)
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
