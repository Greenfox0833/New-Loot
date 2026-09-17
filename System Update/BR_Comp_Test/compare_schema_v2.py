import json
import sys
from pathlib import Path


def flatten_legacy(payload):
    tables = set(payload)
    packages = {}
    for table_id, table in payload.items():
        for block in table.get("Items", []) or []:
            for loot_key, group in block.items():
                if not loot_key.startswith("LootNumber_"):
                    continue
                loot_number = int(loot_key.removeprefix("LootNumber_"))
                for package in group.get("Packages", []) or []:
                    key = (table_id, loot_number, package.get("ID"), package.get("Call"))
                    packages[key] = package
    return tables, packages


def flatten_v2(payload):
    tables = set(payload.get("lootTables", {}))
    packages = {}
    for table_id, table in payload.get("lootTables", {}).items():
        for group in table.get("lootGroups", []):
            loot_number = group.get("lootNumber")
            for package in group.get("packages", []):
                key = (table_id, loot_number, package.get("id"), package.get("call"))
                packages[key] = package
    return tables, packages


def item_map(items, id_field):
    return {(item.get(id_field), item.get("AssetPathName", item.get("assetPath"))): item for item in items}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: compare_schema_v2.py LEGACY_JSON SCHEMA_V2_JSON")
    legacy_path, new_path = map(Path, sys.argv[1:])
    legacy = json.loads(legacy_path.read_text(encoding="utf-8-sig"))
    new = json.loads(new_path.read_text(encoding="utf-8-sig"))
    old_tables, old_packages = flatten_legacy(legacy)
    new_tables, new_packages = flatten_v2(new)

    common_packages = old_packages.keys() & new_packages.keys()
    mismatches = {
        "packageWeight": 0,
        "rollCount": 0,
        "itemSet": 0,
        "itemWeight": 0,
        "quantity": 0,
        "assetPath": 0,
        "rarity": 0,
        "nameExceptTrim": 0,
        "localPercent": 0,
        "effectivePercent": 0,
    }
    old_item_count = new_item_count = 0
    for key in common_packages:
        old_package, new_package = old_packages[key], new_packages[key]
        if old_package.get("weight") != new_package.get("weight"):
            mismatches["packageWeight"] += 1
        if old_package.get("Count") != new_package.get("rollCount"):
            mismatches["rollCount"] += 1
        old_items = item_map(old_package.get("ListItems", []), "WorldListID")
        new_items = item_map(new_package.get("items", []), "id")
        old_item_count += len(old_items)
        new_item_count += len(new_items)
        if old_items.keys() != new_items.keys():
            mismatches["itemSet"] += 1
        for item_key in old_items.keys() & new_items.keys():
            old_item, new_item = old_items[item_key], new_items[item_key]
            checks = (
                ("itemWeight", old_item.get("Weight"), new_item.get("weight")),
                ("quantity", old_item.get("CountItem"), new_item.get("quantity")),
                ("assetPath", old_item.get("AssetPathName"), new_item.get("assetPath")),
                ("rarity", old_item.get("rarity"), new_item.get("rarity")),
            )
            for field, old_value, new_value in checks:
                if old_value != new_value:
                    mismatches[field] += 1
            old_name = old_item.get("LocalizedName")
            if isinstance(old_name, str):
                old_name = old_name.strip()
            if old_name != new_item.get("name"):
                mismatches["nameExceptTrim"] += 1
            for old_field, new_field, mismatch_field in (
                ("ListPercentLocal", "localPercent", "localPercent"),
                ("EffectivePercentPerRoll", "effectivePercent", "effectivePercent"),
            ):
                if old_field in old_item and old_item.get(old_field) != new_item.get(new_field):
                    mismatches[mismatch_field] += 1

    report = {
        "legacy": str(legacy_path.resolve()),
        "schemaV2": str(new_path.resolve()),
        "lootTables": {
            "legacy": len(old_tables),
            "schemaV2": len(new_tables),
            "missing": sorted(old_tables - new_tables),
            "added": sorted(new_tables - old_tables),
        },
        "packages": {
            "legacy": len(old_packages),
            "schemaV2": len(new_packages),
            "missing": len(old_packages.keys() - new_packages.keys()),
            "added": len(new_packages.keys() - old_packages.keys()),
        },
        "items": {"legacy": old_item_count, "schemaV2": new_item_count},
        "mismatches": mismatches,
    }
    report_path = new_path.with_suffix(".comparison.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**report, "report": str(report_path.resolve())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
