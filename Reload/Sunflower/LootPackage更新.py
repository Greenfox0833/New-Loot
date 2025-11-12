import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ==== 入出力（必要なら名前だけ変えてOK）====

# ① Athena（親1）
ATHENA_PATH = Path(
    "e:/Fmodel/Exports/FortniteGame/Content/Items/DataTables/AthenaLootPackages_Client.json"
)

# ② BlastBerry 基底（親2）
BLASTBERRY_BASE_PATH = Path(
    "e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/BlastBerryLootPackages.json"
)

# ③ BlastBerry 上書き（親3）
BLASTBERRY_OVERRIDE_PATH = Path(
    "e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/AthenaLootPackages_Client_BlastBerryOverride.json"
)

# ④ BlastBerry 上書き（親4）
BLASTBERRY_PARENT4_PATH = Path(
    "e:/Fmodel/Exports/FortniteGame/Plugins/GameFeatures/BlastBerryLoot/Content/DataTables/Sunflower/SunflowerLootPackages.json"
)


# （任意）Hotfix INI
HOTFIX_PATH = Path(
    "e:/フォートナイト/Picture/Loot Pool/TEST4/Hotfix/Hotfix.ini"
)

# 出力先
OUT_FINAL = Path(
    "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/Reload/Sunflower/AthenaLootPackages_Client__final_LP.json"
)

# Hotfix の対象テーブル名（段階ごとに限定）
HOTFIX_TARGET_ATHENA   = "/Game/Items/Datatables/AthenaLootPackages_Client"
HOTFIX_TARGET_BB_BASE     = "/BlastBerryLoot/DataTables/BlastBerryLootPackages"
HOTFIX_TARGET_BB_OVERRIDE = "/BlastBerryLoot/DataTables/AthenaLootPackages_Client_BlastBerryOverride"
HOTFIX_TARGET_BB_PARENT4 = "/BlastBerryLoot/DataTables/Sunflower/SunflowerLootPackages"

_num_re = re.compile(r"^[+-]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")
_num_head = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')  # ★先頭の数値だけ抜く用

# ---------- 基本処理 ----------
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
    # "(X=1,Y=2)" -> {"X":1, "Y":2}
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
    # "(1,2,3)" -> [1,2,3]
    inner = s.strip()[1:-1].strip()
    if not inner:
        return []
    return [coerce_scalar(v.strip()) for v in inner.split(",") if v.strip()]


def coerce_like(existing: Any, new_str: str) -> Any:
    s = new_str.strip()

    # 既存型に関係なく Unreal 形式を優先解釈
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

    # 既存が dict のときは dict を優先
    if isinstance(existing, dict):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return s

    # 既存が list のときは list を優先
    if isinstance(existing, list):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [coerce_scalar(x.strip()) for x in s.split(",") if x.strip()]

    # ★ここがポイント：既存が数値型なら、行に余計な文字が付いていても
    # 「先頭の数値だけ」を採用（例: "0.070000+DataTable=..." -> 0.07）
    if isinstance(existing, (int, float)):
        m = _num_head.match(s)
        if m:
            num = m.group(0)
            return float(num) if ('.' in num or 'e' in num.lower()) else int(num)

    # それ以外は通常スカラー解釈
    return coerce_scalar(s)

def set_by_path(row: Dict[str, Any], field_path: str, value_str: str) -> Tuple[bool, str]:
    keys = field_path.split(".")
    cur = row
    for k in keys[:-1]:
        if not isinstance(cur, dict):
            return False, f"not a dict at '{k}'"
        # 中間が無い/辞書でない場合は作る
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    last = keys[-1]
    existing = cur.get(last, None)
    cur[last] = coerce_like(existing, value_str)
    return True, ("OK" if existing is not None else "NEW")


# ---------- Addrow 整形（TableUpdate用） ----------
def _flatten_gameplay_tags(src: Any) -> List[str]:
    # Hotfix 側は {"GameplayTags":[...], "ParentTags":[...]} のことが多い
    if isinstance(src, dict):
        tags = src.get("GameplayTags", [])
        return tags if isinstance(tags, list) else []
    if isinstance(src, list):
        return src
    return []


def _default_required_tag_query() -> Dict[str, Any]:
    return {
        "TokenStreamVersion": 0,
        "TagDictionary": [],
        "QueryTokenStream": [],
        "UserDescription": "",
        "AutoDescription": "",
    }


def _build_annotation(lp_id: str, item_def: str) -> str:
    tail = ""
    if isinstance(item_def, str) and item_def and item_def != "None":
        tail = item_def.split("/")[-1].split(".")[-1]
    return f";List:{lp_id}.C0;Item:{tail}" if lp_id else (f";Item:{tail}" if tail else "")


def normalize_addrow_object(obj: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Hotfix TableUpdate 1要素を DataTable Rows 1行に整形
    戻り値: (row_key, row_dict)
    """
    row_key = obj.get("Name", "")
    lp_id   = obj.get("LootPackageID", "")
    itemdef = obj.get("ItemDefinition", "None")

    row = {
        "LootPackageID": lp_id,
        "Weight": obj.get("Weight", 0.0),
        "NamedWeightMult": obj.get("NamedWeightMult", "None"),
        "PotentialNamedWeights": obj.get("PotentialNamedWeights", []),
        "CountRange": obj.get("CountRange", {"X": 1, "Y": 1}),
        "LootPackageCategory": obj.get("LootPackageCategory", 0),
        "GameplayTags": _flatten_gameplay_tags(obj.get("GameplayTags", [])),
        "RequiredLootGroupTag": obj.get("RequiredLootGroupTag", {"TagName": "None"}),
        "RequiredTagQuery": obj.get("RequiredTagQuery", _default_required_tag_query()),
        "LootPackageCall": obj.get("LootPackageCall", ""),
        "ItemDefinition": {
            "AssetPathName": itemdef if isinstance(itemdef, str) else "None",
            "SubPathString": ""
        },
        "PersistentLevel": obj.get("PersistentLevel", ""),
        "MinWorldLevel": obj.get("MinWorldLevel", -1),
        "MaxWorldLevel": obj.get("MaxWorldLevel", -1),
        "bAllowBonusDrops": obj.get("bAllowBonusDrops", True),
        "Annotation": obj.get("Annotation") or _build_annotation(lp_id, itemdef),
        "DurabilityPercentageOverride": obj.get("DurabilityPercentageOverride", 1.0),
    }
    return row_key, row


# ---------- Hotfix パーサ ----------
def parse_hotfix_line(line: str) -> Dict[str, Any]:
    """
    +DataTable=<path>;RowUpdate;RowKey;Field;Value
    +DataTable=<path>;RowAdd;...
    +DataTable=<path>;RowUpsert;...
    +DataTable=<path>;RowDelete;RowKey
    +DataTable=<path>;TableUpdate;"[{...},{...}]"
    """
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

        # ---- TableUpdate ----
        if op == "TableUpdate":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            raw = ";".join(rest[1:]).strip()
            try:
                # たいてい "..." で JSON 文字列がエスケープされているため二段階デコード
                if raw.startswith('"') and raw.endswith('"'):
                    raw = json.loads(raw)  # 外側の "" を unescape
                rows_array = json.loads(raw)  # 実体の配列を読む
                if not isinstance(rows_array, list):
                    return {"op": "SKIP", "datatable": dt}
                return {"op": "TableUpdate", "datatable": dt, "rows": rows_array}
            except Exception:
                return {"op": "SKIP", "datatable": dt}

        # ---- RowDelete ----
        if op == "RowDelete":
            if len(rest) < 2:
                return {"op": "SKIP", "datatable": dt}
            return {"op": op, "datatable": dt, "row": rest[1].strip()}

        # ---- Row* 系 ----
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
    """
    指定テーブルだけを対象に Hotfix を適用。
    - TableUpdate（= Addrow まとめ投入）対応
    - RowAdd/RowUpsert/RowUpdate/RowDelete 対応
    """
    print(f"[HOTFIX:{stage_name}] target={table_key}")
    applied = deleted = skipped = 0
    has_addrow = False

    for ln, line in enumerate(hotfix_text.splitlines(), 1):
        h = parse_hotfix_line(line)
        op = h.get("op")
        if op in ("COMMENT", "UNKNOWN", "SKIP"):
            continue

        dt = h.get("datatable", "")
        if not dt:
            continue

        # 完全一致 or 末尾一致で紐づけ
        if (dt != table_key) and (dt.split("/")[-1] != table_key.split("/")[-1]):
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

        if op == "TableUpdate":
            arr = h.get("rows", [])
            if not arr:
                continue
            has_addrow = True
            for obj in arr:
                rk, new_row = normalize_addrow_object(obj)
                if not rk:
                    skipped += 1
                    print(f"[{ln}] TableUpdate (no Name) -> SKIP")
                    continue
                rows[rk] = new_row
                applied += 1
                print(f"[{ln}] TableUpdate -> ADD {rk}")
            continue

        # RowAdd / RowUpsert / RowUpdate
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

    if not has_addrow:
        print(f"[HOTFIX:{stage_name}] Addrow(TableUpdate) なし -> スキップ")
    print(f"[HOTFIX:{stage_name}] done: applied={applied}, deleted={deleted}, skipped={skipped}")


# ---------- メイン ----------
def main():
    # ① Athena を読み込み
    athena_meta = read_datatable_json(ATHENA_PATH)
    rows = athena_meta["Rows"]
    print(f"[LOAD] Athena rows = {len(rows)}")

    # ② Hotfix: Athena に対して
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        apply_hotfix_for_table(rows, text, HOTFIX_TARGET_ATHENA, stage_name="ATHENA")
    else:
        print("[HOTFIX] file not found -> skip ATHENA stage")

    # ③ BlastBerry 基底を上書き
    bb_base_meta = read_datatable_json(BLASTBERRY_BASE_PATH)
    rep_bb_base, add_bb_base = merge_rows(rows, bb_base_meta["Rows"])
    print(f"[MERGE] Athena <- BlastBerryBase : replaced={rep_bb_base}, added={add_bb_base}")

    # ④ Hotfix: BlastBerryBase
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        apply_hotfix_for_table(rows, text, HOTFIX_TARGET_BB_BASE, stage_name="BLASTBERRY_BASE")
    else:
        print("[HOTFIX] file not found -> skip BLASTBERRY_BASE stage")

    # ⑤ BlastBerry Override を上書き
    bb_override_meta = read_datatable_json(BLASTBERRY_OVERRIDE_PATH)
    rep_bb_ov, add_bb_ov = merge_rows(rows, bb_override_meta["Rows"])
    print(f"[MERGE] (BB Base) <- BlastBerryOverride : replaced={rep_bb_ov}, added={add_bb_ov}")

    # ⑥ Hotfix: BlastBerryOverride
    if HOTFIX_PATH.exists():
        text = HOTFIX_PATH.read_text(encoding="utf-8")
        apply_hotfix_for_table(rows, text, HOTFIX_TARGET_BB_OVERRIDE, stage_name="BLASTBERRY_OVERRIDE")
    else:
        print("[HOTFIX] file not found -> skip BLASTBERRY_OVERRIDE stage")

        # ⑦ BlastBerry 親4 を上書き（なければ追加）
    if BLASTBERRY_PARENT4_PATH.exists():
        bb_parent4_meta = read_datatable_json(BLASTBERRY_PARENT4_PATH)
        rep_bb_p4, add_bb_p4 = merge_rows(rows, bb_parent4_meta["Rows"])
        print(f"[MERGE] (BB Override) <- BlastBerry Parent4 : replaced={rep_bb_p4}, added={add_bb_p4}")

        # ⑧ Hotfix: BlastBerry 親4
        if HOTFIX_PATH.exists():
            text = HOTFIX_PATH.read_text(encoding="utf-8")
            apply_hotfix_for_table(rows, text, HOTFIX_TARGET_BB_PARENT4, stage_name="BLASTBERRY_PARENT4")
        else:
            print("[HOTFIX] file not found -> skip BLASTBERRY_PARENT4 stage")
    else:
        print(f"[MERGE] BlastBerry Parent4 file not found -> skip (path: {BLASTBERRY_PARENT4_PATH})")


    # 書き出し（Athena のメタを流用して最終Rowsを保存）
    write_datatable_json(athena_meta, OUT_FINAL)
    print(f"[WRITE] final -> {OUT_FINAL.resolve()}")

if __name__ == "__main__":
    main()
