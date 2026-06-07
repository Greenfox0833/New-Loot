import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
COMMON_DIR = BASE_DIR.parent
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from cache import get_name_by_asset


def walk_list_items(node):
    if isinstance(node, dict):
        list_items = node.get("ListItems")
        if isinstance(list_items, list):
            for item in list_items:
                if isinstance(item, dict):
                    yield item
        for value in node.values():
            yield from walk_list_items(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_list_items(value)


def fill_unknown_names(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    seen = set()
    changed = 0
    unresolved = 0

    for item in walk_list_items(data):
        if item.get("LocalizedName") != "???":
            continue
        asset_path = item.get("AssetPathName")
        if not asset_path:
            unresolved += 1
            continue
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        name = get_name_by_asset(asset_path)
        if name and name != "???":
            item["LocalizedName"] = name
            changed += 1
        else:
            unresolved += 1

    if changed > 0:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return changed, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Target BR_LootData json path")
    args = ap.parse_args()

    path = Path(args.path)
    changed, unresolved = fill_unknown_names(path)
    print(json.dumps({
        "path": str(path),
        "changed": changed,
        "unresolved": unresolved,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
