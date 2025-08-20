# 比較.py
import json
import sys
from pathlib import Path

old_file = Path(sys.argv[1]) if len(sys.argv) >= 3 else Path("e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/Summary/v37.00_v1.json")
new_file = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path("e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/BR/作業用/Summary/v37.00_v2.json")

def load_json(p: Path):
    with p.open(encoding="utf-8") as f:
        return json.load(f)

old_data = load_json(old_file)
new_data = load_json(new_file)

def collect_assets_anywhere(obj):
    out = {}

    def prefer_put(ap: str, name: str):
        if not ap:
            return
        if ap not in out or (out[ap] == "???" and name and name != "???"):
            out[ap] = name or "???"

    def walk(x):
        if isinstance(x, dict):
            if "ListItems" in x and isinstance(x["ListItems"], list):
                for li in x["ListItems"]:
                    if not isinstance(li, dict):
                        continue
                    ap = li.get("AssetPathName", "")
                    name = li.get("Localized") or li.get("Name_JA") or "???"
                    prefer_put(ap, name)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return out

old_assets = collect_assets_anywhere(old_data)
new_assets = collect_assets_anywhere(new_data)

enabled = {ap: new_assets[ap] for ap in new_assets.keys() - old_assets.keys()}
disabled = {ap: old_assets[ap] for ap in old_assets.keys() - new_assets.keys()}

def format_list(title: str, names: list[str]) -> str:
    # 重複除去＆ソート
    unique_names = sorted(set(names))
    lines = [title]
    for i, name in enumerate(unique_names):
        mark = "┗" if i == len(unique_names) - 1 else "┣"
        lines.append(f"　　{mark} {name}")
    return "\n".join(lines)

enabled_names = list(enabled.values())
disabled_names = list(disabled.values())

blocks = []
if enabled_names:
    blocks.append(format_list("🔹追加", enabled_names))
if disabled_names:
    blocks.append(format_list("🔸削除", disabled_names))

print("\n\n".join(blocks) if blocks else "差分なし")
