import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from diff_loot import diff_items, load_json, normalize_items


JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR / "戦利品データ"
OUTPUT_DIR = Path(r"E:\フォートナイト\Web\assets\data\Loot\diff")
INDEX_PATH = OUTPUT_DIR / "index.json"

MODE_OUTPUT_NAMES = {
    "Figment": "ORIGIN",
    "ForbiddenFruit": "Blitz",
}


def latest_two_files(folder: Path) -> tuple[Path, Path]:
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) < 2:
        raise FileNotFoundError("JSON files are less than 2 in the selected folder.")
    return files[1], files[0]


def build_output_path(mode_key: str) -> Path:
    mode_name = MODE_OUTPUT_NAMES.get(mode_key, mode_key)
    timestamp = datetime.now(JST).strftime("%Y-%m-%d_%H-%M-%S")
    name = f"{mode_name}_{timestamp}.json"
    return OUTPUT_DIR / name


def _diff_is_empty(diff: dict) -> bool:
    return not diff.get("added") and not diff.get("removed") and not diff.get("change")


def resolve_mode_folder(mode_key: str) -> Path:
    # Standard layout: 戦利品データ/<mode_key>
    direct = DATA_ROOT / mode_key
    if direct.exists() and direct.is_dir():
        return direct

    # Nested layout support: e.g. 戦利品データ/Reload/Sunflower
    nested = DATA_ROOT / Path(mode_key)
    if nested.exists() and nested.is_dir():
        return nested

    candidates = []
    for p in DATA_ROOT.rglob(mode_key):
        if p.is_dir():
            candidates.append(p)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        found = ", ".join(str(p) for p in candidates)
        raise FileNotFoundError(f"Ambiguous mode folder for '{mode_key}': {found}")
    raise FileNotFoundError(f"Folder not found for mode '{mode_key}' under: {DATA_ROOT}")


def update_diff_index(out_path: Path) -> None:
    name = out_path.name
    if INDEX_PATH.exists():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    entries = data.get("entries")
    if not isinstance(entries, list):
        entries = []

    # Keep newest entries at the end, avoid duplicates.
    entries = [e for e in entries if e != name]
    entries.append(name)

    data["entries"] = entries
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_latest_diff(mode_key: str) -> tuple[Path, dict] | None:
    folder = resolve_mode_folder(mode_key)

    try:
        old_file, new_file = latest_two_files(folder)
    except FileNotFoundError:
        return None

    old_data = load_json(old_file)
    new_data = load_json(new_file)
    old_items = normalize_items(old_data)
    new_items = normalize_items(new_data)

    diff = diff_items(old_items, new_items)
    diff["generatedAt"] = datetime.now(JST).isoformat(timespec="seconds")

    if _diff_is_empty(diff):
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = build_output_path(mode_key)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    update_diff_index(out_path)
    return out_path, diff
