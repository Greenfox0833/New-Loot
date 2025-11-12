# -*- coding: utf-8 -*-
"""
抽出→比較を1本で実行。
- 抽出: 戦利品データ\BR 内の最新JSONから3項目(AssetPathName/LocalizedName/rarity)のミニリストを作成し、
        戦利品変更履歴\BR_YYYYMMDD_HHMM\items_unique_min.json に保存
- 比較: 戦利品データ\BR 内の最新2つの"元JSON"を読み込み、それぞれをミニリスト化して差分(追加/削除/変更)を作成。
        戦利品変更履歴\BR_DIFF_YYYYMMDD_HHMM\items_unique_min_diff.json に保存
オプション:
--scan      : 抽出に使う最新JSONを探すフォルダ(再帰)。既定=BRフォルダ
--diff-scan : 比較に使う最新2つのJSONを探すフォルダ(再帰)。既定=BRフォルダ
--rarity    : 指定レアリティだけ抽出(例: レア)。未指定で全件
"""

import os, glob, json, argparse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# ===== 既定パス（/ でOK） =====
DEFAULT_SCAN_DIR      = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/Reload/Sunflower"
DEFAULT_DIFF_SCAN_DIR = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/Reload/Sunflower"
HISTORY_BASE_DIR      = "E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品変更履歴"

JST = timezone(timedelta(hours=9))

# ---------- 共通 ----------
def read_json_any(path: str) -> Any:
    for enc in ("utf-8", "cp932", "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except Exception:
            pass
    raise RuntimeError(f"JSON読み込み失敗: {path}")

def glob_latest_json(base_dir: str) -> Optional[str]:
    pats = glob.glob(os.path.join(base_dir, "**", "*.json"), recursive=True)
    if not pats: return None
    pats.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return pats[0]

def glob_latest_two_json(base_dir: str) -> List[str]:
    pats = glob.glob(os.path.join(base_dir, "**", "*.json"), recursive=True)
    pats = [p for p in pats if os.path.isfile(p)]
    pats.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return pats[:2]

def walk_collect_asset_nodes(node: Any, out_list: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if "AssetPathName" in node:
            out_list.append(node)
        for v in node.values():
            walk_collect_asset_nodes(v, out_list)
    elif isinstance(node, list):
        for v in node:
            walk_collect_asset_nodes(v, out_list)

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

# ---------- 抽出(元JSON→ミニリスト) ----------
def to_min_list(src_json_path: str, rarity_filter: Optional[str]) -> List[Dict[str, Any]]:
    data = read_json_any(src_json_path)
    bucket: List[Dict[str, Any]] = []
    walk_collect_asset_nodes(data, bucket)

    seen = set()
    out: List[Dict[str, Any]] = []
    for it in bucket:
        ap = it.get("AssetPathName")
        if not ap or not isinstance(ap, str):
            continue
        if rarity_filter is not None and it.get("rarity") != rarity_filter:
            continue
        if ap in seen:
            continue
        seen.add(ap)
        out.append({
            "AssetPathName": ap,
            "LocalizedName": it.get("LocalizedName") or "",
            "rarity": it.get("rarity") or ""
        })

    # LocalizedName 昇順（空は最後）
    out.sort(key=lambda x: (x["LocalizedName"] in (None, ""), x["LocalizedName"]))
    return out

def save_current_min_list(min_list: List[Dict[str, Any]], out_dir: str) -> str:
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, "items_unique_min.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(min_list, f, ensure_ascii=False, indent=2)
    return out_path


# ---------- 比較(ミニリスト同士) ----------
def index_by_ap(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx = {}
    for it in items:
        ap = it.get("AssetPathName")
        if not ap: continue
        idx[ap] = {"LocalizedName": it.get("LocalizedName") or "", "rarity": it.get("rarity") or ""}
    return idx

def diff_min_lists(base_items: List[Dict[str, Any]], target_items: List[Dict[str, Any]]):
    base = index_by_ap(base_items)
    tgt  = index_by_ap(target_items)
    k_base, k_tgt = set(base.keys()), set(tgt.keys())

    added_keys   = sorted(k_tgt - k_base)
    removed_keys = sorted(k_base - k_tgt)
    common_keys  = k_base & k_tgt

    modified = []
    unchanged = 0
    for k in sorted(common_keys):
        b, t = base[k], tgt[k]
        if b["LocalizedName"] != t["LocalizedName"] or b["rarity"] != t["rarity"]:
            modified.append({"AssetPathName": k, "before": b, "after": t})
        else:
            unchanged += 1

    added   = [{"AssetPathName": k, **tgt[k]}  for k in added_keys]
    removed = [{"AssetPathName": k, **base[k]} for k in removed_keys]
    return added, removed, modified, unchanged

def save_diff_report(base_src: str, target_src: str, added, removed, modified, unchanged, out_dir: str) -> str:
    ensure_dir(out_dir)
    out = {
        "base_source": base_src,
        "target_source": target_src,
        "summary": {"added": len(added), "removed": len(removed), "modified": len(modified), "unchanged": unchanged},
        "added": added, "removed": removed, "modified": modified
    }
    out_path = os.path.join(out_dir, "items_unique_min_diff.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out_path


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan",      default=DEFAULT_SCAN_DIR,      help="抽出に使う最新JSONを探すフォルダ")
    ap.add_argument("--diff-scan", default=DEFAULT_DIFF_SCAN_DIR, help="比較に使う最新2つのJSONを探すフォルダ")
    ap.add_argument("--rarity",    default=None,                  help="このレアリティのみ抽出（例: レア）。未指定で全件")
    args = ap.parse_args()

    # ---------- 抽出 ----------
    latest = glob_latest_json(args.scan)
    if not latest:
        print(f"❌ JSONが見つかりません（抽出探索先: {args.scan}）")
        return
    print(f"🔎 抽出用: 最新ファイル = {latest}")

    current_min = to_min_list(latest, args.rarity)

    # 抽出の保存先は固定ディレクトリ（上書き更新）
    extract_dir = r"E:\フォートナイト\Picture\Loot Pool\TEST4\New Loot\Reload\Sunflower\作業用"
    ensure_dir(extract_dir)
    out_min_path = os.path.join(extract_dir, "items_unique_min.json")
    with open(out_min_path, "w", encoding="utf-8") as f:
        json.dump(current_min, f, ensure_ascii=False, indent=2)

    print(f"✅ 抽出件数: {len(current_min)}")
    print(f"💾 保存: {out_min_path}")

    # ---------- 比較 ----------
    two = glob_latest_two_json(args.diff_scan)
    if len(two) < 2:
        print(f"ℹ️ 比較対象が1件以下のため比較スキップ（探索先: {args.diff_scan}）")
        return

    base_src, target_src = two[1], two[0]  # 1つ前, 最新
    print(f"🔎 比較用: base   = {base_src}")
    print(f"🔎 比較用: target = {target_src}")

    base_min   = to_min_list(base_src, args.rarity)
    target_min = to_min_list(target_src, args.rarity)

    added, removed, modified, unchanged = diff_min_lists(base_min, target_min)

    # 比較の保存先は日付入りの履歴フォルダ
    now = datetime.now(JST)
    diff_dir = os.path.join(HISTORY_BASE_DIR, f"Reload_Sunflower_{now.strftime('%Y%m%d_%H%M')}")
    ensure_dir(diff_dir)

    diff_obj = {
        "base_source":   base_src,
        "target_source": target_src,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": unchanged
        },
        "added": added,
        "removed": removed,
        "modified": modified
    }
    diff_path = os.path.join(diff_dir, "items_unique_min_diff.json")
    with open(diff_path, "w", encoding="utf-8") as f:
        json.dump(diff_obj, f, ensure_ascii=False, indent=2)

    print("✅ 差分作成 完了")
    print(f"  追加   : {len(added)} / 削除 : {len(removed)} / 変更 : {len(modified)} / 変化なし : {unchanged}")
    print(f"💾 差分: {diff_path}")

if __name__ == "__main__":
    main()
