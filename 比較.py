import json

# === 設定 ===
old_file = "戦利品データ/BR/v37.00_2025-08-21_22-36.json"
new_file = "戦利品データ/BR/v37.00_2025-08-23_08-38.json"

# === JSONロード ===
with open(old_file, "r", encoding="utf-8") as f:
    old_data = json.load(f)
with open(new_file, "r", encoding="utf-8") as f:
    new_data = json.load(f)


def collect_items(data):
    """Lootテーブルから (テーブル名, アイテム名, レアリティ) -> 出現率 の辞書を作成"""
    items = {}
    for table, content in data.items():
        for item in content.get("Items", []):
            for v_pkg in item.get("ValidLootPackages", []):
                for pkg in v_pkg.get("Packages", []):
                    for li in pkg.get("ListItems", []):
                        name = li.get("LocalizedName", "")
                        rarity = li.get("rarity", "")
                        percent = li.get("ListPercent", 0.0)
                        key = (table, name, rarity)
                        items[key] = percent
    return items


old_items = collect_items(old_data)
new_items = collect_items(new_data)

# === 差分抽出 ===
all_keys = set(old_items.keys()) | set(new_items.keys())
diffs = {}

for key in all_keys:
    old_val = old_items.get(key, 0.0)
    new_val = new_items.get(key, 0.0)
    if abs(old_val - new_val) > 1e-6:
        table, name, rarity = key
        diffs.setdefault(table, []).append((name, rarity, old_val, new_val))


# === 出力 ===
for table, changes in diffs.items():
    print(f"{table}")
    for name, rarity, old_val, new_val in changes:
        rarity_str = f"（{rarity}）" if rarity else ""
        print(f"　　┣ {name}{rarity_str}: {old_val:.4g}% ⇒ {new_val:.4g}%")
    print()
