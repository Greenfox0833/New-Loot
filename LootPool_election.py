"""
Loot pool viewer (simple configuration at top).
- Set LOOT_FILE to your JSON path.
- Set ITEMS to the items you want, e.g.:
    ITEMS = {
        "ストライカー アサルトライフル",
        "サイレンサー付きアサルトライフル",
    }
  Leave ITEMS empty/None to show all items.
Run: python LootPool_election.py
"""

import json
import pathlib
import sys
from collections import defaultdict
from typing import Iterable, Mapping

# ==== EDIT HERE =============================================================
LOOT_FILE = pathlib.Path("戦利品データ/BR/LootPercent/BR_LootData_2025-11-21_06-38.json")
# 例: {"ストライカー アサルトライフル", "サイレンサー付きアサルトライフル"}
# 空のセット/リスト、または None なら全アイテムを表示
ITEMS = {
    "ストライカー アサルトライフル",
}

# ===========================================================================


def load_json(path: pathlib.Path) -> Mapping[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"File not found: {path}")
    except OSError as exc:
        sys.exit(f"Failed to read {path}: {exc}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.exit(f"Invalid JSON in {path}: {exc}")

    if not isinstance(data, dict):
        sys.exit("Unexpected JSON root type; expected object")

    return data


def build_index(data: Mapping[str, object]):
    index: dict[str, set[str]] = defaultdict(set)
    for group, gdata in data.items():
        if not isinstance(gdata, dict):
            continue
        for item_block in gdata.get("Items", []):
            if not isinstance(item_block, dict):
                continue
            for entry in item_block.values():
                if not isinstance(entry, dict):
                    continue
                for pkg in entry.get("Packages", []):
                    if not isinstance(pkg, dict):
                        continue
                    for li in pkg.get("ListItems", []):
                        if not isinstance(li, dict):
                            continue
                        name = li.get("LocalizedName")
                        if name:
                            index[name].add(group)
    return index


def print_item(name: str, locations: set[str]):
    if not locations:
        print(f"{name}: not found")
        return
    print(name)
    for loc in sorted(locations):
        print(f"  - {loc}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = load_json(LOOT_FILE)
    index = build_index(data)

    # Normalize ITEMS to a list; empty/None => all items
    if ITEMS:
        selected = list(ITEMS)
    else:
        selected = []

    if selected:
        for name in selected:
            print_item(name, index.get(name, set()))
    else:
        for name in sorted(index):
            print_item(name, index[name])


if __name__ == "__main__":
    main()
