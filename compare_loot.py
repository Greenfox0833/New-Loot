import argparse
import json
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

# デフォルトの比較対象（必要に応じてここを書き換えてください）
DEFAULT_OLD = "戦利品データ/BR/LootPercent/BR_LootData_2025-10-04_08-24.json"
DEFAULT_NEW = "戦利品データ/BR/LootPercent/BR_LootData_2025-10-09_17-28.json"


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def iter_loot_numbers(items_obj: Any) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(items_obj, list):
        for entry in items_obj:
            if isinstance(entry, dict):
                for k, v in entry.items():
                    if isinstance(k, str) and k.startswith("LootNumber_") and isinstance(v, dict):
                        out.append((k, v))
    elif isinstance(items_obj, dict):
        for k, v in items_obj.items():
            if isinstance(k, str) and k.startswith("LootNumber_") and isinstance(v, dict):
                out.append((k, v))
    return out


def key_for_package(pkg: Dict[str, Any]) -> str:
    if isinstance(pkg, dict):
        if "ID" in pkg and isinstance(pkg["ID"], str):
            return pkg["ID"]
        call = pkg.get("Call")
        count = pkg.get("Count")
        return f"{call}|{count}"
    return str(pkg)


def key_for_list_item(item: Dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return str(item)
    if item.get("AssetPathName"):
        return str(item["AssetPathName"])  # 最も安定
    if item.get("WorldListID"):
        return str(item["WorldListID"])   # 次点
    if item.get("LocalizedName"):
        return str(item["LocalizedName"]) # 最終手段
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def display_for_item(item: Dict[str, Any]) -> str:
    name = (
        item.get("LocalizedName")
        or item.get("WorldListID")
        or item.get("AssetPathName")
        or "Unknown Item"
    )
    rarity = item.get("rarity")
    if rarity:
        return f"{name}（{rarity}）"
    return str(name)


def shorten_id(id_str: str) -> str:
    try:
        if not isinstance(id_str, str):
            return str(id_str)
        if "/" in id_str:
            return id_str.rsplit("/", 1)[-1]
        return id_str
    except Exception:
        return str(id_str)


def dict_without_keys(d: Dict[str, Any], ignore: List[str]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if k not in ignore}


def compare_scalars(old: Any, new: Any) -> List[str]:
    changes = []
    if old != new:
        changes.append(f"-> {old} => {new}")
    return changes


def diff_group(name: str, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    # Top-level scalar changes in a group
    for field in ["TotalWeight"]:
        if field in old or field in new:
            if old.get(field) != new.get(field):
                lines.append(f"  field {field}: {old.get(field)} => {new.get(field)}")

    # LootNumber_* blocks
    old_loots = {k: v for k, v in iter_loot_numbers(old.get("Items", []))}
    new_loots = {k: v for k, v in iter_loot_numbers(new.get("Items", []))}

    for loot_k in sorted(set(old_loots) - set(new_loots)):
        lines.append(f"  removed {loot_k}")
    for loot_k in sorted(set(new_loots) - set(old_loots)):
        lines.append(f"  added   {loot_k}")

    for loot_k in sorted(set(old_loots) & set(new_loots)):
        old_pkg_list = old_loots[loot_k].get("Packages", []) or []
        new_pkg_list = new_loots[loot_k].get("Packages", []) or []

        # Compare packages by stable key
        old_pkgs = {key_for_package(p): p for p in old_pkg_list if isinstance(p, dict)}
        new_pkgs = {key_for_package(p): p for p in new_pkg_list if isinstance(p, dict)}

        removed_pkgs = sorted(set(old_pkgs) - set(new_pkgs))
        added_pkgs = sorted(set(new_pkgs) - set(old_pkgs))
        for k in removed_pkgs:
            lines.append(f"  {loot_k} removed package: {k}")
        for k in added_pkgs:
            lines.append(f"  {loot_k} added package: {k}")

        for k in sorted(set(old_pkgs) & set(new_pkgs)):
            o = old_pkgs[k]
            n = new_pkgs[k]
            # Compare common package scalar fields
            for field in ["Call", "Count", "weight", "TotalListWeight"]:
                if o.get(field) != n.get(field):
                    lines.append(
                        f"  {loot_k} package {k} field {field}: {o.get(field)} => {n.get(field)}"
                    )

            # Compare ListItems
            o_items = o.get("ListItems", []) or []
            n_items = n.get("ListItems", []) or []
            o_map = {key_for_list_item(it): it for it in o_items if isinstance(it, dict)}
            n_map = {key_for_list_item(it): it for it in n_items if isinstance(it, dict)}

            for item_k in sorted(set(o_map) - set(n_map)):
                lines.append(f"  {loot_k} package {k} removed item: {item_k}")
            for item_k in sorted(set(n_map) - set(o_map)):
                lines.append(f"  {loot_k} package {k} added item: {item_k}")

            common_items = sorted(set(o_map) & set(n_map))
            for item_k in common_items:
                oi = o_map[item_k]
                ni = n_map[item_k]
                # Ignore identity keys when comparing
                ignore_keys = ["AssetPathName", "WorldListID", "LocalizedName"]
                o_body = dict_without_keys(oi, ignore_keys)
                n_body = dict_without_keys(ni, ignore_keys)
                if o_body != n_body:
                    # Field-wise differences
                    all_fields = set(o_body) | set(n_body)
                    for field in sorted(all_fields):
                        if o_body.get(field) != n_body.get(field):
                            lines.append(
                                f"  {loot_k} package {k} item {item_k} field {field}: {o_body.get(field)} => {n_body.get(field)}"
                            )

    return lines


def diff_loot(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    old_groups = set(old.keys())
    new_groups = set(new.keys())

    for g in sorted(old_groups - new_groups):
        lines.append(f"REMOVED group: {g}")

    for g in sorted(new_groups - old_groups):
        lines.append(f"ADDED   group: {g}")

    for g in sorted(old_groups & new_groups):
        group_changes = diff_group(g, old[g], new[g])
        if group_changes:
            lines.append(f"CHANGED group: {g}")
            lines.extend(group_changes)

    return lines


def diff_loot_structured(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "added_groups": [],
        "removed_groups": [],
        "changed_groups": {},
    }

    old_groups = set(old.keys())
    new_groups = set(new.keys())

    for g in sorted(old_groups - new_groups):
        result["removed_groups"].append(g)

    for g in sorted(new_groups - old_groups):
        result["added_groups"].append(g)

    for g in sorted(old_groups & new_groups):
        group_changes: Dict[str, Any] = {}
        old_g = old[g]
        new_g = new[g]

        # Top-level field changes
        fields_diff: Dict[str, Dict[str, Any]] = {}
        for field in ["TotalWeight"]:
            if old_g.get(field) != new_g.get(field):
                fields_diff[field] = {"old": old_g.get(field), "new": new_g.get(field)}
        if fields_diff:
            group_changes["fields"] = fields_diff

        # LootNumber_* blocks
        old_loots = {k: v for k, v in iter_loot_numbers(old_g.get("Items", []))}
        new_loots = {k: v for k, v in iter_loot_numbers(new_g.get("Items", []))}

        loot_section: Dict[str, Any] = {"added": [], "removed": [], "changed": {}}
        removed_loots = sorted(set(old_loots) - set(new_loots))
        added_loots = sorted(set(new_loots) - set(old_loots))
        if removed_loots:
            loot_section["removed"] = removed_loots
        if added_loots:
            loot_section["added"] = added_loots

        for loot_k in sorted(set(old_loots) & set(new_loots)):
            old_pkg_list = old_loots[loot_k].get("Packages", []) or []
            new_pkg_list = new_loots[loot_k].get("Packages", []) or []

            old_pkgs = {key_for_package(p): p for p in old_pkg_list if isinstance(p, dict)}
            new_pkgs = {key_for_package(p): p for p in new_pkg_list if isinstance(p, dict)}

            loot_change: Dict[str, Any] = {}

            removed_pkgs = sorted(set(old_pkgs) - set(new_pkgs))
            added_pkgs = sorted(set(new_pkgs) - set(old_pkgs))
            if removed_pkgs:
                loot_change.setdefault("packages", {})["removed"] = removed_pkgs
            if added_pkgs:
                loot_change.setdefault("packages", {})["added"] = added_pkgs

            changed_pkgs: Dict[str, Any] = {}
            for pk in sorted(set(old_pkgs) & set(new_pkgs)):
                o = old_pkgs[pk]
                n = new_pkgs[pk]
                pkg_diff: Dict[str, Any] = {}

                # Package fields
                fields = {}
                for field in ["Call", "Count", "weight", "TotalListWeight"]:
                    if o.get(field) != n.get(field):
                        fields[field] = {"old": o.get(field), "new": n.get(field)}
                if fields:
                    pkg_diff["fields"] = fields

                # Items diff
                o_items = o.get("ListItems", []) or []
                n_items = n.get("ListItems", []) or []
                o_map = {key_for_list_item(it): it for it in o_items if isinstance(it, dict)}
                n_map = {key_for_list_item(it): it for it in n_items if isinstance(it, dict)}

                items_sec: Dict[str, Any] = {}
                rem_items = sorted(set(o_map) - set(n_map))
                add_items = sorted(set(n_map) - set(o_map))
                if rem_items:
                    items_sec["removed"] = [
                        {"id": shorten_id(it_k), "display": display_for_item(o_map[it_k])} for it_k in rem_items
                    ]
                if add_items:
                    items_sec["added"] = [
                        {"id": shorten_id(it_k), "display": display_for_item(n_map[it_k])} for it_k in add_items
                    ]

                changed_items_list: List[Dict[str, Any]] = []
                for it_k in sorted(set(o_map) & set(n_map)):
                    oi = o_map[it_k]
                    ni = n_map[it_k]
                    ignore_keys = ["AssetPathName", "WorldListID", "LocalizedName"]
                    o_body = dict_without_keys(oi, ignore_keys)
                    n_body = dict_without_keys(ni, ignore_keys)
                    if o_body != n_body:
                        fields_ch: Dict[str, Any] = {}
                        for field in sorted(set(o_body) | set(n_body)):
                            if o_body.get(field) != n_body.get(field):
                                fields_ch[field] = {"old": o_body.get(field), "new": n_body.get(field)}
                        if fields_ch:
                            changed_items_list.append(
                                {"id": shorten_id(it_k), "display": display_for_item(ni), "fields": fields_ch}
                            )
                if changed_items_list:
                    items_sec["changed"] = changed_items_list

                if items_sec:
                    pkg_diff["items"] = items_sec

                if pkg_diff:
                    changed_pkgs[pk] = pkg_diff

            if changed_pkgs:
                loot_change.setdefault("packages", {})["changed"] = changed_pkgs

            if loot_change:
                loot_section["changed"][loot_k] = loot_change

        if loot_section["added"] or loot_section["removed"] or loot_section["changed"]:
            group_changes["loot_numbers"] = loot_section

        if group_changes:
            result["changed_groups"][g] = group_changes

    # Summary counts
    result["summary"] = {
        "groups_added": len(result["added_groups"]),
        "groups_removed": len(result["removed_groups"]),
        "groups_changed": len(result["changed_groups"]),
    }
    return result

def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two Battle Royale loot JSONs and summarize changes.")
    ap.add_argument("old", nargs="?", help="Path to older JSON (optional; uses DEFAULT_OLD if omitted)")
    ap.add_argument("new", nargs="?", help="Path to newer JSON (optional; uses DEFAULT_NEW if omitted)")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    ap.add_argument("--structured", action="store_true", help="Emit structured JSON diff (with --format json)")
    ap.add_argument("--out", help="Write output to a file (use with --format json for JSON file)")
    ap.add_argument("--summary", help="Write human-friendly Markdown summary to this path")
    args = ap.parse_args()

    old_path = args.old or DEFAULT_OLD
    new_path = args.new or DEFAULT_NEW

    try:
        old = load_json(old_path)
        newer = load_json(new_path)
    except Exception as e:
        print(f"Failed to load JSON: {e}", file=sys.stderr)
        return 1

    diffs = diff_loot(old, newer)

    if args.format == "json":
        if args.structured:
            structured = diff_loot_structured(old, newer)
            payload = {"old": old_path, "new": new_path, "diff": structured}
        else:
            payload = {"old": old_path, "new": new_path, "changes": diffs}
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Wrote JSON diff to: {args.out}")
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text_lines = []
        if not diffs:
            text_lines.append("No differences detected.")
        else:
            text_lines.append("Loot Data Differences")
            text_lines.append("-" * 80)
            text_lines.extend(diffs)

        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write("\n".join(text_lines) + "\n")
            print(f"Wrote text diff to: {args.out}")
        else:
            for line in text_lines:
                print(line)

    # Optional human-friendly summary file
    if args.summary:
        # Prefer structured diff for richer info
        structured = diff_loot_structured(old, newer)
        lines: List[str] = []
        lines.append("# 戦利品データ変更まとめ")
        lines.append("")
        lines.append(f"対象: {old_path} → {new_path}")
        lines.append("")
        s = structured.get("summary", {})
        lines.append(f"サマリ: 追加グループ {s.get('groups_added', 0)} / 削除グループ {s.get('groups_removed', 0)} / 変更グループ {s.get('groups_changed', 0)}")
        lines.append("")

        added = structured.get("added_groups", [])
        removed = structured.get("removed_groups", [])
        if added:
            lines.append("## 追加されたグループ")
            for g in added:
                lines.append(f"- {g}")
            lines.append("")
        if removed:
            lines.append("## 削除されたグループ")
            for g in removed:
                lines.append(f"- {g}")
            lines.append("")

        changed_groups = structured.get("changed_groups", {})
        if changed_groups:
            lines.append("## 変更のあるグループ")
            for g, gdiff in changed_groups.items():
                lines.append(f"### {g}")
                # Group fields (e.g., TotalWeight)
                fields = gdiff.get("fields", {})
                for field, vals in fields.items():
                    lines.append(f"- {field}: {vals.get('old')} → {vals.get('new')}")

                ln = gdiff.get("loot_numbers", {})
                if ln.get("added"):
                    lines.append(f"- 追加LootNumber: {', '.join(ln['added'])}")
                if ln.get("removed"):
                    lines.append(f"- 削除LootNumber: {', '.join(ln['removed'])}")

                changed_loots = ln.get("changed", {})
                for loot_k, c in changed_loots.items():
                    lines.append(f"- {loot_k}")
                    pkgs = c.get("packages", {})
                    # Package field changes (high-level settings)
                    for pk, pd in pkgs.get("changed", {}).items():
                        pfields = pd.get("fields", {})
                        for f, v in pfields.items():
                            lines.append(f"  - パッケージ {pk}: {f} {v.get('old')} → {v.get('new')}")
                    # Items
                    items = pkgs.get("items") or {}
                    if items.get("added"):
                        lines.append("  - 追加アイテム:")
                        for it in items["added"]:
                            lines.append(f"    - {it['display']}")
                    if items.get("removed"):
                        lines.append("  - 削除アイテム:")
                        for it in items["removed"]:
                            lines.append(f"    - {it['display']}")
                    if items.get("changed"):
                        lines.append("  - 変更アイテム:")
                        for it in items["changed"]:
                            disp = it.get("display")
                            fields_ch = it.get("fields", {})
                            if fields_ch:
                                fields_str = ", ".join(
                                    f"{k}: {v.get('old')} → {v.get('new')}" for k, v in fields_ch.items()
                                )
                                lines.append(f"    - {disp}: {fields_str}")
                lines.append("")

        with open(args.summary, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")
        print(f"Wrote human-friendly summary to: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
