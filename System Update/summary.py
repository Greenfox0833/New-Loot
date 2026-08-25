import json
from collections import defaultdict

from cache import get_rarity_by_asset
from config import FILTER_TIERGROUP, ONLY_ROWS, ONLY_TIERGROUPS, ONLY_WORLDLIST_KEYS
from utils import _asset_path_from_row, as_float, key_suffix_num

def load_rows(path: str, rows_key: str = "Rows"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    obj = data[0] if isinstance(data, list) else data
    return obj.get(rows_key, {})

def load_minlist(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print("⚠️ items_unique_min.json の形式が不正です")
            return []
        return data
    except FileNotFoundError:
        print(f"❌ {path} が見つかりません")
        return []

def build_summary(rows_lt: dict, rows_lp: dict):
    id_to_call = {k: v.get("LootPackageCall", "") for k, v in rows_lp.items()}

    lp_by_idcat = defaultdict(list)
    for row_key, row in rows_lp.items():
        lp_id = row.get("LootPackageID", "")
        lp_cat = row.get("LootPackageCategory", 0)
        try:
            lp_cat = int(lp_cat)
        except Exception:
            lp_cat = 0
        lp_call = row.get("LootPackageCall", "") or ""
        lp_weight = as_float(row.get("Weight", row.get("weight", 0.0)))

        lp_by_idcat[(lp_id, lp_cat)].append(
            {
                "Key": row_key,
                "Call": lp_call,
                "Weight": lp_weight,
            }
        )

    for k in lp_by_idcat:
        lp_by_idcat[k].sort(key=lambda d: key_suffix_num(d["Key"]))

    worldlist_map = defaultdict(list)
    for row_key, row in rows_lp.items():
        if not isinstance(row, dict):
            continue
        wl_id = row.get("LootPackageID", "")
        count_range = row.get("CountRange") or {}
        worldlist_map[wl_id].append(
            {
                "Key": row_key,
                "Weight": as_float(row.get("Weight", row.get("weight", 0.0))),
                "AssetPathName": _asset_path_from_row(row),
                "CountItem": count_range.get("X", count_range.get("x")),
            }
        )

    for wl_id in worldlist_map:
        worldlist_map[wl_id].sort(key=lambda x: key_suffix_num(x["Key"]))

    by_group = defaultdict(list)

    for row_name, row in rows_lt.items():
        tg = row.get("TierGroup", "")
        if not tg or (FILTER_TIERGROUP and tg != FILTER_TIERGROUP):
            continue
        if as_float(row.get("Weight", row.get("weight", 0.0))) == 0.0:
            continue

        loot_pkg = row.get("LootPackage", "")
        valid_groups = []
        min_array = row.get("LootPackageCategoryMinArray", []) or []
        weight_array = row.get("LootPackageCategoryWeightArray", []) or []
        group_len = max(len(min_array), len(weight_array))

        for ln in range(group_len):
            min_val = min_array[ln] if ln < len(min_array) else 0
            weight_val = as_float(weight_array[ln] if ln < len(weight_array) else 0.0)
            if min_val < 1 and weight_val <= 0.0:
                continue

            matches = lp_by_idcat.get((loot_pkg, ln), [])
            packages = []
            for m in matches:
                call = m["Call"]

                list_items = []
                if call:
                    for c in worldlist_map.get(call, []):
                        if c["Weight"] > 0.0 and c.get("AssetPathName"):
                            list_items.append(
                                {
                                    "WorldListID": c["Key"],
                                    "Weight": c["Weight"],
                                    "AssetPathName": c["AssetPathName"],
                                    "CountItem": c.get("CountItem"),
                                }
                            )

                total_list_weight = sum(li["Weight"] for li in list_items) if list_items else 0.0

                pkg_weight = as_float(m.get("Weight", m.get("weight", 0.0)))
                if pkg_weight <= 0.0:
                    continue

                packages.append(
                    {
                        "ID": m["Key"],
                        "Call": call,
                        "Count": max(1, int(min_val)),
                        "weight": round(pkg_weight, 6),
                        "TotalListWeight": round(total_list_weight, 6),
                        "ListItems": list_items,
                    }
                )

            if packages:
                valid_groups.append({"LootNumber": ln, "Packages": packages})

        entry = {
            "RowName": row_name,
            "Weight": round(as_float(row.get("Weight", row.get("weight", 0.0))), 6),
            "LootPackage": loot_pkg,
        }
        if valid_groups:
            entry["ValidLootPackages"] = valid_groups
        by_group[tg].append(entry)

    result = {}
    for tg, items in sorted(by_group.items()):
        total_weight = sum(item.get("Weight", 0.0) for item in items)
        for idx, item in enumerate(items):
            percent = round((item["Weight"] / total_weight) * 100, 4) if total_weight else 0.0
            if "ValidLootPackages" in item:
                for group in item["ValidLootPackages"]:
                    pkg_sum_in_group = (
                        sum(as_float(p.get("weight", p.get("Weight", 0.0))) for p in group.get("Packages", []))
                        or 0.0
                    )

                    for v_pkg in group.get("Packages", []):
                        tw = v_pkg.get("TotalListWeight", 0.0)
                        new_list_items = []

                        pkg_weight = v_pkg.get("weight", v_pkg.get("Weight", 0.0))
                        package_percent = round((as_float(pkg_weight) / pkg_sum_in_group) * 100, 6) if pkg_sum_in_group > 0 else 0.0

                        for li in v_pkg.get("ListItems", []):
                            list_percent_local = round((li["Weight"] / tw) * 100, 6) if tw > 0 else 0.0
                            effective_percent_per_roll = round(
                                (percent / 100.0) * (package_percent / 100.0) * list_percent_local,
                                6,
                            )
                            asset_path = li.get("AssetPathName")

                            new_list_items.append(
                                {
                                    "WorldListID": li.get("WorldListID"),
                                    "Weight": li["Weight"],
                                    "ListPercentLocal": list_percent_local,
                                    "EffectivePercentPerRoll": effective_percent_per_roll,
                                    "rarity": get_rarity_by_asset(asset_path),
                                    "AssetPathName": asset_path,
                                    "CountItem": li.get("CountItem"),
                                }
                            )

                        v_pkg["ListItems"] = new_list_items

            ordered = {
                "RowName": item["RowName"],
                "Weight": item["Weight"],
                "Percent": percent,
            }
            for k, v in item.items():
                if k not in ("RowName", "Weight"):
                    ordered[k] = v
            items[idx] = ordered
        result[tg] = {"TotalWeight": round(total_weight, 6), "Items": items}

    return result

def _allow_emit(tg: str, rowname: str, worldlist_key: str) -> bool:
    if ONLY_TIERGROUPS and tg not in ONLY_TIERGROUPS:
        return False
    if ONLY_ROWS and rowname not in ONLY_ROWS:
        return False
    if ONLY_WORLDLIST_KEYS and worldlist_key not in ONLY_WORLDLIST_KEYS:
        return False
    return True

def build_br_lootdata_compact_all(summary: dict, target_tg: str = "Loot_ApolloTreasure_Rare") -> dict:
    if not isinstance(summary, dict) or target_tg not in summary:
        return {}

    tg_block = summary[target_tg]
    items = tg_block.get("Items", []) or []

    ln_to_packages: dict[int, list] = {}
    ln_seen_calls: dict[int, set] = {}

    for item in items:
        for group in (item.get("ValidLootPackages") or []):
            ln = group.get("LootNumber")
            if not isinstance(ln, int):
                continue

            if ln not in ln_to_packages:
                ln_to_packages[ln] = []
                ln_seen_calls[ln] = set()

            for pkg in (group.get("Packages") or []):
                call = (pkg.get("Call") or "").strip()
                if call in ln_seen_calls[ln]:
                    continue
                ln_seen_calls[ln].add(call)
                ln_to_packages[ln].append(pkg)

    ln_blocks = {}
    for ln in sorted(ln_to_packages.keys()):
        pkgs = ln_to_packages[ln]
        call_count = len(pkgs)
        for _p in pkgs:
            for _li in (_p.get("ListItems") or []):
                if call_count <= 1:
                    _li.pop("EffectivePercentPerRoll", None)
                else:
                    _li.pop("ListPercentLocal", None)
        ln_blocks[f"LootNumber_{ln}"] = {"Packages": pkgs}

    return {
        target_tg: {
            "TotalWeight": tg_block.get("TotalWeight", 0.0),
            "Items": [ln_blocks] if ln_blocks else [],
        }
    }

def build_br_lootdata_all_tgs(summary: dict) -> dict:
    if not isinstance(summary, dict):
        return {}

    out = {}
    for tg, tg_block in summary.items():
        items = (tg_block or {}).get("Items", []) or []

        ln_to_packages = {}
        ln_seen_calls = {}

        for item in items:
            for group in (item.get("ValidLootPackages") or []):
                ln = group.get("LootNumber")
                if not isinstance(ln, int):
                    continue
                ln_to_packages.setdefault(ln, [])
                ln_seen_calls.setdefault(ln, set())

                for pkg in (group.get("Packages") or []):
                    call = (pkg.get("Call") or "").strip()
                    if call in ln_seen_calls[ln]:
                        continue
                    ln_seen_calls[ln].add(call)
                    ln_to_packages[ln].append(pkg)

        ln_blocks = {}
        for ln in sorted(ln_to_packages.keys()):
            pkgs = ln_to_packages[ln]
            call_count = len(pkgs)
            for _p in pkgs:
                for _li in (_p.get("ListItems") or []):
                    if call_count <= 1:
                        _li.pop("EffectivePercentPerRoll", None)
                    else:
                        _li.pop("ListPercentLocal", None)
            ln_blocks[f"LootNumber_{ln}"] = {"Packages": pkgs}

        out[tg] = {
            "TotalWeight": tg_block.get("TotalWeight", 0.0),
            "Items": [ln_blocks] if ln_blocks else [],
        }
    return out
