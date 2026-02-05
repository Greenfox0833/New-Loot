import argparse
import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        return json.load(f)


def _normalize_from_list(items: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError("list items must be objects with an 'id' field")
        item_id = str(item["id"])
        if item_id in out:
            raise ValueError(f"duplicate id found: {item_id}")
        out[item_id] = {
            "asset_path": item.get("AssetPathName"),
            "localized_name": item.get("LocalizedName"),
            "rarity": item.get("rarity"),
            "label": item.get("label"),
            "group": item.get("group"),
            "groups": _group_list_from_value(item.get("group")),
            "probability": item.get("probability"),
            "group_probabilities": _group_probabilities_from_value(
                item.get("group"), item.get("probability")
            ),
        }
    return out


def _normalize_from_mapping(mapping: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be an object")
    out: Dict[str, Dict[str, Any]] = {}
    for key, value in mapping.items():
        if not isinstance(value, dict):
            raise ValueError("mapping values must be objects")
        item_id = str(key)
        out[item_id] = {
            "asset_path": value.get("AssetPathName"),
            "localized_name": value.get("LocalizedName"),
            "rarity": value.get("rarity"),
            "label": value.get("label"),
            "group": value.get("group"),
            "groups": _group_list_from_value(value.get("group")),
            "probability": value.get("probability"),
            "group_probabilities": _group_probabilities_from_value(
                value.get("group"), value.get("probability")
            ),
        }
    return out


def _iter_loot_items(group_obj: Any) -> list[dict]:
    items: list[dict] = []
    if not isinstance(group_obj, dict):
        return items
    group_items = group_obj.get("Items", [])
    if isinstance(group_items, dict):
        group_items = [group_items]
    if not isinstance(group_items, list):
        return items
    for entry in group_items:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            if not (isinstance(key, str) and key.startswith("LootNumber_")):
                continue
            if not isinstance(value, dict):
                continue
            for pkg in value.get("Packages", []) or []:
                if not isinstance(pkg, dict):
                    continue
                for list_item in pkg.get("ListItems", []) or []:
                    if isinstance(list_item, dict):
                        items.append(list_item)
    return items


def _group_list_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _group_probabilities_from_value(group: Any, probability: Any) -> dict[str, float]:
    if not isinstance(probability, (int, float)):
        return {}
    groups = _group_list_from_value(group)
    return {g: float(probability) for g in groups}


def _normalize_from_lootpercent(data: dict) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    asset_path_map: Dict[str, str] = {}
    localized_name_map: Dict[str, str] = {}
    rarity_map: Dict[str, str] = {}
    label_sets: Dict[str, set[str]] = {}
    group_sets: Dict[str, set[str]] = {}
    probability_sums: Dict[str, float] = {}
    group_probabilities: Dict[str, Dict[str, float]] = {}
    for group_key, group_obj in data.items():
        if not isinstance(group_obj, dict) or "Items" not in group_obj:
            continue
        for item in _iter_loot_items(group_obj):
            item_id = item.get("AssetPathName") or item.get("WorldListID") or item.get("LocalizedName")
            if not item_id:
                continue
            item_id = str(item_id)
            label = item.get("LocalizedName") or item.get("WorldListID") or item.get("AssetPathName") or item_id
            label_sets.setdefault(item_id, set()).add(str(label))
            group_sets.setdefault(item_id, set()).add(str(group_key))
            if item.get("AssetPathName") and item_id not in asset_path_map:
                asset_path_map[item_id] = str(item.get("AssetPathName"))
            if item.get("LocalizedName") and item_id not in localized_name_map:
                localized_name_map[item_id] = str(item.get("LocalizedName"))
            if item.get("rarity") and item_id not in rarity_map:
                rarity_map[item_id] = str(item.get("rarity"))
            # Prefer ListPercentLocal; fall back to EffectivePercentPerRoll when local percent is absent.
            prob = item.get("ListPercentLocal")
            if not isinstance(prob, (int, float)):
                prob = item.get("EffectivePercentPerRoll")
            if isinstance(prob, (int, float)):
                probability_sums[item_id] = probability_sums.get(item_id, 0.0) + float(prob)
                group_probabilities.setdefault(item_id, {})
                group_probabilities[item_id][str(group_key)] = (
                    group_probabilities[item_id].get(str(group_key), 0.0) + float(prob)
                )

    for item_id in sorted(group_sets):
        labels = sorted(label_sets.get(item_id, {item_id}))
        groups = sorted(group_sets.get(item_id, {"Unknown"}))
        out[item_id] = {
            "asset_path": asset_path_map.get(item_id, item_id),
            "localized_name": localized_name_map.get(item_id),
            "rarity": rarity_map.get(item_id),
            "label": " / ".join(labels),
            "group": "|".join(groups),
            "groups": groups,
            "probability": probability_sums.get(item_id),
            "group_probabilities": group_probabilities.get(item_id, {}),
        }
    if not out:
        raise ValueError("lootpercent structure was not detected")
    return out


def normalize_items(data: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(data, dict) and any(
        isinstance(v, dict) and "Items" in v for v in data.values()
    ):
        return _normalize_from_lootpercent(data)
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return _normalize_from_list(data["items"])
    if isinstance(data, list):
        return _normalize_from_list(data)
    if isinstance(data, dict):
        return _normalize_from_mapping(data)
    raise ValueError("unsupported JSON structure for items")


def _normalize_probability(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return None


def diff_items(old_items: Dict[str, Dict[str, Any]], new_items: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    old_ids = set(old_items.keys())
    new_ids = set(new_items.keys())

    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    common_ids = sorted(old_ids & new_ids)

    added = [
        {
            "id": item_id,
            "asset_path": new_items[item_id].get("asset_path", item_id),
            "localized_name": new_items[item_id].get("localized_name"),
            "rarity": new_items[item_id].get("rarity"),
            "label": new_items[item_id].get("label"),
            "group": new_items[item_id].get("group"),
            "groups": new_items[item_id].get("groups", []),
        }
        for item_id in added_ids
    ]
    removed = [
        {
            "id": item_id,
            "asset_path": old_items[item_id].get("asset_path", item_id),
            "localized_name": old_items[item_id].get("localized_name"),
            "rarity": old_items[item_id].get("rarity"),
            "label": old_items[item_id].get("label"),
            "group": old_items[item_id].get("group"),
            "groups": old_items[item_id].get("groups", []),
        }
        for item_id in removed_ids
    ]

    moved = []
    probability_changed_items = []
    prob_added_entries = []
    prob_removed_entries = []
    for item_id in common_ids:
        old_group = old_items[item_id].get("group")
        new_group = new_items[item_id].get("group")
        if old_group != new_group:
            moved.append(
                {
                    "id": item_id,
                    "before": {"group": old_group, "groups": old_items[item_id].get("groups", [])},
                    "after": {"group": new_group, "groups": new_items[item_id].get("groups", [])},
                }
            )
        old_group_probs = old_items[item_id].get("group_probabilities", {}) or {}
        new_group_probs = new_items[item_id].get("group_probabilities", {}) or {}
        group_keys = sorted(set(old_group_probs) | set(new_group_probs))
        for group_key in group_keys:
            before_prob = _normalize_probability(old_group_probs.get(group_key))
            after_prob = _normalize_probability(new_group_probs.get(group_key))
            if before_prob == after_prob:
                continue
            if before_prob is None and after_prob is not None:
                prob_added_entries.append(
                    {
                        "id": item_id,
                        "group": group_key,
                    }
                )
                continue
            if before_prob is not None and after_prob is None:
                prob_removed_entries.append(
                    {
                        "id": item_id,
                        "group": group_key,
                    }
                )
                continue
            probability_changed_items.append(
                {
                    "id": item_id,
                    "group": group_key,
                    "before": {"probability": before_prob},
                    "after": {"probability": after_prob},
                }
            )

    added_out = [
        {
            "AssetPathName": entry["asset_path"],
            "LocalizedName": entry["localized_name"],
            "rarity": entry["rarity"],
            "addrow": entry["groups"],
        }
        for entry in added
    ]
    removed_out = [
        {
            "AssetPathName": entry["asset_path"],
            "LocalizedName": entry["localized_name"],
            "rarity": entry["rarity"],
            "removedrow": entry["groups"],
        }
        for entry in removed
    ]
    for entry in prob_added_entries:
        item_id = entry["id"]
        group_key = entry["group"]
        added_out.append(
            {
                "AssetPathName": new_items[item_id].get("asset_path", item_id),
                "LocalizedName": new_items[item_id].get("localized_name"),
                "rarity": new_items[item_id].get("rarity"),
                "addrow": [group_key],
            }
        )
    for entry in prob_removed_entries:
        item_id = entry["id"]
        group_key = entry["group"]
        removed_out.append(
            {
                "AssetPathName": old_items[item_id].get("asset_path", item_id),
                "LocalizedName": old_items[item_id].get("localized_name"),
                "rarity": old_items[item_id].get("rarity"),
                "removedrow": [group_key],
            }
        )

    change_out = []
    for item_id in common_ids:
        changes_for_item = [
            c for c in probability_changed_items if c["id"] == item_id
        ]
        if not changes_for_item:
            continue
        percent_block: Dict[str, Any] = {}
        for change in changes_for_item:
            percent_block[change["group"]] = {
                "before": change["before"],
                "after": change["after"],
            }
        change_out.append(
            {
                "AssetPathName": new_items[item_id].get("asset_path", item_id),
                "LocalizedName": new_items[item_id].get("localized_name"),
                "rarity": new_items[item_id].get("rarity"),
                "Percent": percent_block,
            }
        )

    return {
        "added": added_out,
        "removed": removed_out,
        "change": change_out,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff two loot JSON files by id/label/group.")
    parser.add_argument("old_json", type=Path, help="Path to old.json")
    parser.add_argument("new_json", type=Path, help="Path to new.json")
    parser.add_argument("out_json", type=Path, help="Path to output diff.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    old_data = load_json(args.old_json)
    new_data = load_json(args.new_json)

    old_items = normalize_items(old_data)
    new_items = normalize_items(new_data)

    diff = diff_items(old_items, new_items)

    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    print(
        f"added={len(diff['added'])} removed={len(diff['removed'])} change={len(diff['change'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
