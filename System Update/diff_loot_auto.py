import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from diff_loot import diff_items, load_json, normalize_items


JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR / "戦利品データ"
WEB_ROOT_ENV = "FORTNITE_WEB_ROOT"

MODE_OUTPUT_NAMES = {
    "Figment": "ORIGIN",
    "ForbiddenFruit": "Blitz",
}


def resolve_web_root() -> Path:
    """Webリポジトリを環境変数、または現在の配置から検出する。"""
    configured = os.environ.get(WEB_ROOT_ENV)
    if configured:
        web_root = Path(configured).expanduser().resolve()
        if (web_root / "loot" / "data").is_dir():
            return web_root
        raise FileNotFoundError(
            f"{WEB_ROOT_ENV} がWebリポジトリを指していません: {web_root}"
        )

    candidates = []
    for parent in (BASE_DIR, *BASE_DIR.parents):
        candidates.extend((parent / "Web", parent))

    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "loot" / "data").is_dir():
            return resolved

    raise FileNotFoundError(
        "Webリポジトリを自動検出できません。環境変数 "
        f"{WEB_ROOT_ENV} にWebリポジトリのパスを設定してください。"
    )


def get_web_lootpool_path(mode_key: str, filename: str | None = None) -> Path:
    """モードのWeb公開JSONパスを返す。公開名が異なる場合はfilenameを渡す。"""
    output_name = filename or f"{mode_key}_LootPool.json"
    if Path(output_name).name != output_name:
        raise ValueError(f"Web LootPoolのファイル名が不正です: {output_name}")
    return resolve_web_root() / "loot" / "data" / output_name


def get_diff_output_dir() -> Path:
    return resolve_web_root() / "loot" / "data" / "diff"


def latest_two_files(folder: Path) -> tuple[Path, Path]:
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) < 2:
        raise FileNotFoundError("JSON files are less than 2 in the selected folder.")
    return files[1], files[0]


def build_output_path(mode_key: str) -> Path:
    mode_name = MODE_OUTPUT_NAMES.get(mode_key, mode_key)
    timestamp = datetime.now(JST).strftime("%Y-%m-%d_%H-%M-%S")
    name = f"{mode_name}_{timestamp}.json"
    return get_diff_output_dir() / name


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
    index_path = get_diff_output_dir() / "index.json"
    name = out_path.name
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
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
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_diff_data(mode_key: str, old_data, new_data) -> tuple[Path, dict] | None:
    """指定された前回データと今回データから差分を作成する。"""
    if old_data is None or new_data is None:
        return None

    old_items = normalize_items(old_data)
    new_items = normalize_items(new_data)

    diff = diff_items(old_items, new_items)
    diff["generatedAt"] = datetime.now(JST).isoformat(timespec="seconds")

    if _diff_is_empty(diff):
        return None

    get_diff_output_dir().mkdir(parents=True, exist_ok=True)
    out_path = build_output_path(mode_key)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    update_diff_index(out_path)
    return out_path, diff


def run_latest_diff(mode_key: str) -> tuple[Path, dict] | None:
    folder = resolve_mode_folder(mode_key)

    try:
        old_file, new_file = latest_two_files(folder)
    except FileNotFoundError:
        return None

    old_data = load_json(old_file)
    new_data = load_json(new_file)
    return run_diff_data(mode_key, old_data, new_data)
