import json
from collections import defaultdict
from datetime import datetime

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
                        v_pkg["PackagePercent"] = package_percent

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


def _build_list_source_index(rows_lp: dict) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for row_key, row in rows_lp.items():
        if not isinstance(row, dict):
            continue
        list_id = row.get("LootPackageID", "")
        if list_id:
            index[list_id].append({"key": row_key, "row": row})
    return index


def _resolution_state(call: str, items: list, source_index: dict) -> tuple[bool, bool, str | None]:
    if call == "LIST_Empty":
        return True, True, None
    if not call:
        return False, False, "invalid_reference"
    source_rows = source_index.get(call)
    if not source_rows:
        return False, False, "loot_list_not_found"
    if items:
        return True, False, None

    # A source row exists, but the existing parser could not produce an item.
    # Do not guess that this is an intentional empty list.
    return False, False, "unsupported_structure"


def build_schema_v2(summary: dict, rows_lp: dict, game_mode: str = "BR_Comp_TEST") -> dict:
    """Convert the existing resolved summary to the web-facing schema v2."""
    if game_mode == "BR_Comp_Test":
        game_mode = "BR_Comp_TEST"
    source_index = _build_list_source_index(rows_lp)
    warnings = []
    loot_tables = {}

    for tg, tg_block in summary.items():
        loot_groups = []
        ln_to_packages = {}
        ln_seen_calls = {}

        for tier_row in (tg_block or {}).get("Items", []) or []:
            for group in tier_row.get("ValidLootPackages", []) or []:
                loot_number = group.get("LootNumber")
                if not isinstance(loot_number, int):
                    continue
                ln_to_packages.setdefault(loot_number, [])
                ln_seen_calls.setdefault(loot_number, set())

                for package in group.get("Packages", []) or []:
                    call = package.get("Call") or ""
                    if call in ln_seen_calls[loot_number]:
                        continue
                    ln_seen_calls[loot_number].add(call)

                    source_items = package.get("ListItems", []) or []
                    resolved, is_empty, reason = _resolution_state(call, source_items, source_index)
                    list_total_weight = package.get("TotalListWeight") if resolved else None
                    items = []
                    for item in source_items:
                        name = item.get("LocalizedName")
                        if isinstance(name, str):
                            name = name.strip()
                        items.append(
                            {
                                "id": item.get("WorldListID"),
                                "name": name,
                                "rarity": item.get("rarity"),
                                "assetPath": item.get("AssetPathName"),
                                "quantity": item.get("CountItem"),
                                "weight": item.get("Weight"),
                                "localPercent": item.get("ListPercentLocal"),
                                "effectivePercent": item.get("EffectivePercentPerRoll"),
                            }
                        )

                    package_id = package.get("ID")
                    converted = {
                        "key": f"{tg}:{loot_number}:{package_id}",
                        "id": package_id,
                        "call": call,
                        "rollCount": package.get("Count"),
                        "weight": package.get("weight", package.get("Weight")),
                        "packagePercent": package.get("PackagePercent"),
                        "resolved": resolved,
                        "isEmpty": is_empty,
                        "resolutionReason": reason,
                        "listTotalWeight": list_total_weight,
                        "items": items,
                    }
                    ln_to_packages[loot_number].append(converted)

                    if not resolved:
                        warnings.append(
                            {
                                "type": "unresolved_list",
                                "lootTable": tg,
                                "lootNumber": loot_number,
                                "packageId": package_id,
                                "call": call,
                                "message": {
                                    "loot_list_not_found": "参照先の戦利品リストが見つかりませんでした。",
                                    "invalid_reference": "戦利品リストの参照が空、または不正です。",
                                    "parse_error": "戦利品リストの解析に失敗しました。",
                                    "unsupported_structure": "参照先は存在しますが、現在未対応の構造のためアイテムを解決できませんでした。",
                                }.get(reason, "戦利品リストを解決できませんでした。"),
                            }
                        )

        for loot_number in sorted(ln_to_packages):
            loot_groups.append(
                {
                    "lootNumber": loot_number,
                    "packages": ln_to_packages[loot_number],
                }
            )

        loot_tables[tg] = {
            "totalWeight": (tg_block or {}).get("TotalWeight", 0.0),
            "lootGroups": loot_groups,
        }

    return {
        "meta": {
            "schemaVersion": 2,
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "gameMode": game_mode,
        },
        "lootTables": loot_tables,
        "warnings": warnings,
    }


def validate_schema_v2(payload: dict, tolerance: float = 1e-4) -> list[dict]:
    errors = []

    def add(code, path, message):
        errors.append({"type": code, "path": path, "message": message})

    for tg, table in payload.get("lootTables", {}).items():
        previous_loot_number = None
        for group_index, group in enumerate(table.get("lootGroups", [])):
            loot_number = group.get("lootNumber")
            group_path = f"lootTables.{tg}.lootGroups[{group_index}]"
            if not isinstance(loot_number, int):
                add("invalid_loot_number", group_path, "lootNumberは整数である必要があります。")
            if previous_loot_number is not None and isinstance(loot_number, int) and loot_number < previous_loot_number:
                add("unsorted_loot_number", group_path, "lootGroupsはlootNumberの昇順である必要があります。")
            previous_loot_number = loot_number if isinstance(loot_number, int) else previous_loot_number

            for package_index, package in enumerate(group.get("packages", [])):
                package_path = f"{group_path}.packages[{package_index}]"
                resolved = package.get("resolved") is True
                is_empty = package.get("isEmpty") is True
                items = package.get("items", [])
                if resolved and not is_empty and not items:
                    add("resolved_list_without_items", package_path, "解決済みの空ではないリストにitemsがありません。")
                if not resolved and package.get("listTotalWeight") is not None:
                    add("unresolved_weight_not_null", package_path, "未解決リストのlistTotalWeightはnullである必要があります。")
                if package.get("call") == "LIST_Empty" and not (resolved and is_empty):
                    add("invalid_list_empty", package_path, "LIST_Emptyは解決済みかつ空である必要があります。")

                total_item_weight = 0.0
                local_percent_sum = 0.0
                all_local_percent = bool(items)
                for item_index, item in enumerate(items):
                    item_path = f"{package_path}.items[{item_index}]"
                    quantity = item.get("quantity")
                    if not isinstance(quantity, (int, float)) or quantity <= 0:
                        add("invalid_quantity", item_path, "quantityは0より大きい必要があります。")
                    weight = item.get("weight")
                    if not isinstance(weight, (int, float)) or weight < 0:
                        add("invalid_weight", item_path, "weightを負数にはできません。")
                    else:
                        total_item_weight += float(weight)
                    for field in ("localPercent", "effectivePercent"):
                        value = item.get(field)
                        if value is not None and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
                            add(f"invalid_{field}", item_path, f"{field}は0から100の範囲である必要があります。")
                    local_percent = item.get("localPercent")
                    if local_percent is None:
                        all_local_percent = False
                    else:
                        local_percent_sum += float(local_percent)
                    name = item.get("name")
                    if isinstance(name, str) and name != name.strip():
                        add("untrimmed_name", item_path, "nameの先頭または末尾に不要な空白があります。")

                list_total = package.get("listTotalWeight")
                if resolved and not is_empty and isinstance(list_total, (int, float)):
                    if abs(float(list_total) - total_item_weight) > tolerance:
                        add("list_weight_mismatch", package_path, "listTotalWeightとitemsのweight合計が一致しません。")
                if resolved and not is_empty and all_local_percent and abs(local_percent_sum - 100.0) > tolerance:
                    add("local_percent_sum", package_path, "localPercentの合計が約100%になっていません。")

    # Explicitly verify serializability as part of validation.
    try:
        json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        add("json_serialize_error", "$", str(exc))
    return errors


def build_validated_schema_v2(summary: dict, rows_lp: dict, game_mode: str) -> dict:
    payload = build_schema_v2(summary, rows_lp, game_mode)
    errors = validate_schema_v2(payload)
    if errors:
        preview = json.dumps(errors[:5], ensure_ascii=False)
        raise ValueError(f"schema v2検証で{len(errors)}件のエラーが見つかりました: {preview}")
    return payload
