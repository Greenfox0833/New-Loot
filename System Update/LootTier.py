import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from http_client import session

# prefer profile-specific config if available
BASE_DIR = Path(__file__).resolve().parent
PROFILE = os.getenv("SYSTEM_PROFILE", "BR").strip() or "BR"

def _resolve_profile_dir(base_dir: Path, profile: str) -> Path | None:
    candidates = [
        base_dir / profile,
        base_dir / "期間限定" / profile,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

PROFILE_DIR = _resolve_profile_dir(BASE_DIR, PROFILE)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if PROFILE_DIR is not None and str(PROFILE_DIR) not in sys.path:
    sys.path.insert(0, str(PROFILE_DIR))

from config import (
    HOTFIX_LT_INI_PATH,
    HOTFIX_LT_MAX_PATHS,
    HOTFIX_LT_OUT_FINAL,
    HOTFIX_LT_PATHS,
    HOTFIX_LT_TARGETS,
)

# ==== 入出力（config.py 側で管理）====
PATH_LIST = [str(p) for p in (HOTFIX_LT_PATHS or [])][: int(HOTFIX_LT_MAX_PATHS or 10)]
HOTFIX_PATH = Path(HOTFIX_LT_INI_PATH)
OUT_FINAL = Path(HOTFIX_LT_OUT_FINAL)

# Hotfix の対象テーブル名（PATHSと同じ順で適用）
TARGET_LIST = list(HOTFIX_LT_TARGETS or [])


_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


def _source_name(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        query = parse_qs(parsed.query)
        asset_path = query.get("path", query.get("Path", [parsed.path]))[0]
        return Path(unquote(asset_path)).stem
    return Path(source).stem


def read_datatable_json(source: str) -> Dict[str, Any]:
    if source is None:
        raise ValueError("read_datatable_json: source is None（引数がNoneです）")
    parsed = urlparse(source)
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError(f"{source}: HTTPはlocalhostのみ指定できます")
    if parsed.scheme in ("http", "https"):
        response = session.get(source, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "jsonOutput" in data:
            data = data["jsonOutput"]
    else:
        path = Path(source)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{_source_name(source)}: 空リストです")
        data = data[0]
    if not isinstance(data, dict) or "Rows" not in data:
        raise ValueError(f"{_source_name(source)}: DataTable形式ではないか、Rowsがありません")

    rows = data.get("Rows")
    if rows is None:
        data["Rows"] = {}
    elif not isinstance(rows, dict):
        raise ValueError(f"{_source_name(source)}: Rowsがdictではありません: {type(rows).__name__}")

    return data


def write_datatable_json(meta: Dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump([meta], f, ensure_ascii=False, indent=2)


def _write_per_input_outputs(meta: Dict[str, Any], out_final: Path, path_list: List[str]) -> None:
    out_dir = out_final.parent
    written = set()
    try:
        written.add(out_final.resolve())
    except Exception:
        written.add(out_final)
    for p in path_list:
        stem = _source_name(p)
        out_path = out_dir / f"{stem}__final.json"
        try:
            key = out_path.resolve()
        except Exception:
            key = out_path
        if key in written:
            continue
        write_datatable_json(meta, out_path)
        print(f"[WRITE] per-input -> {out_path.resolve()}")
        written.add(key)

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

        if op == "AddRow":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            raw = ";".join(rest[1:]).strip()
            try:
                if raw.startswith("\"") and raw.endswith("\""):
                    raw = json.loads(raw)
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    return {"op": "SKIP", "datatable": dt}
                return {"op": "AddRow", "datatable": dt, "rowobj": obj}
            except Exception:
                return {"op": "SKIP", "datatable": dt}

        if op == "RowDelete":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            return {"op": op, "datatable": dt, "row": rest[1].strip()}

        if op not in ("RowUpdate", "RowAdd", "RowUpsert"):
            return {"op": "SKIP", "datatable": dt}

        if len(rest) < 4:
            return {"op": "SKIP", "datatable": dt}
        row_key = rest[1].strip()
        field = rest[2].strip()
        value = ";".join(rest[3:]).strip()
        return {"op": op, "datatable": dt, "row": row_key, "field": field, "value": value}
    except Exception:
        return {"op": "UNKNOWN"}


def apply_hotfix_for_table(rows: Dict[str, Any], hotfix_text: str, table_key: str, stage_name: str) -> None:
    print(f"[HOTFIX:{stage_name}] target={table_key}")
    applied = deleted = skipped = 0

    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        op = h.get("op")
        if op in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        if not dt:
            continue

        if (dt != table_key) and (dt.split("/")[-1] != table_key.split("/")[-1]):
            continue

        if op == "AddRow":
            obj = h.get("rowobj")
            if not isinstance(obj, dict):
                skipped += 1
                print(f"[{ln}] AddRow -> SKIP")
                continue
            rk = obj.get("Name", "")
            if not rk:
                skipped += 1
                print(f"[{ln}] AddRow (no Name) -> SKIP")
                continue
            rows[rk] = obj
            applied += 1
            print(f"[{ln}] AddRow -> ADD {rk}")
            continue

        if op == "RowDelete":
            rk = h["row"]
            if rk in rows:
                rows.pop(rk, None)
                deleted += 1
                print(f"[{ln}] RowDelete {rk} -> DELETED")
            else:
                print(f"[{ln}] RowDelete {rk} -> SKIP(no row)")
            continue

        rk, field, val = h.get("row"), h.get("field"), h.get("value")
        if rk is None or field is None:
            skipped += 1
            continue

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

    print(f"[HOTFIX:{stage_name}] done: applied={applied}, deleted={deleted}, skipped={skipped}")


def main():
    if not PATH_LIST:
        raise ValueError("HOTFIX_LT_PATHS が空です")
    base_meta = read_datatable_json(PATH_LIST[0])
    base_rows = base_meta["Rows"]
    hotfix_text = HOTFIX_PATH.read_text(encoding="utf-8") if HOTFIX_PATH.exists() else None
    if hotfix_text is None:
        print("[HOTFIX] skipped (file not found)")

    print(f"[STEP1-1] base {PATH_LIST[0]}")
    for idx, p in enumerate(PATH_LIST, 1):
        if idx >= 2:
            meta = read_datatable_json(p)
            rows = meta["Rows"]
            rep, add = merge_rows(base_rows, rows)
            print(f"[STEP1-{idx}] merge {p} : replaced={rep}, added={add}")

        target = TARGET_LIST[idx - 1] if idx - 1 < len(TARGET_LIST) else ""
        if not hotfix_text:
            continue
        if not target:
            print(f"[HOTFIX:SEASON{idx}] skipped (target not configured)")
            continue
        apply_hotfix_for_table(base_rows, hotfix_text, target, f"SEASON{idx}")

    write_datatable_json(base_meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")
    _write_per_input_outputs(base_meta, OUT_FINAL, PATH_LIST)


if __name__ == "__main__":
    main()

