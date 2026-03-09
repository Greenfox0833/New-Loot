import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from config import RARITY_TO_TIER
from export_api import normalize_asset_path


def _safe_name(value: str) -> str:
    return re.sub(r'[\\/:"*?<>|]', "_", value or "")


def _build_asset_maps(minlist_path: Path) -> tuple[dict, dict]:
    name_map: dict[str, str] = {}
    rarity_map: dict[str, str] = {}
    try:
        data = json.loads(minlist_path.read_text(encoding="utf-8"))
    except Exception:
        return name_map, rarity_map

    if not isinstance(data, list):
        return name_map, rarity_map

    for rec in data:
        if not isinstance(rec, dict):
            continue
        ap = rec.get("AssetPathName")
        if not ap:
            continue
        norm = normalize_asset_path(ap)
        name = rec.get("LocalizedName")
        rarity = rec.get("rarity")
        if isinstance(name, str) and name.strip():
            name_map[norm] = name
        if isinstance(rarity, str) and rarity.strip():
            rarity_map[norm] = rarity
    return name_map, rarity_map


def copy_new_item_images(
    profile_name: str,
    diff: dict,
    source_dir: Path,
    minlist_path: Path,
) -> tuple[Path | None, int, int]:
    added = (diff or {}).get("added") or []
    if not isinstance(added, list) or not added:
        return None, 0, 0

    source_dir = Path(source_dir)
    if not source_dir.exists():
        return None, 0, len(added)

    name_map, rarity_map = _build_asset_maps(Path(minlist_path))

    copied = 0
    missing = 0
    copied_sources: set[Path] = set()
    dest_dir: Path | None = None

    for rec in added:
        if not isinstance(rec, dict):
            missing += 1
            continue
        ap = rec.get("AssetPathName")
        if not ap:
            missing += 1
            continue
        norm = normalize_asset_path(ap)

        localized = rec.get("LocalizedName") or name_map.get(norm)
        rarity = rec.get("rarity") or rarity_map.get(norm)
        tier = RARITY_TO_TIER.get(rarity)

        if not localized or not tier:
            missing += 1
            continue

        src_filename = f"{_safe_name(localized)} - {tier}.png"
        src = source_dir / src_filename
        if not src.exists():
            missing += 1
            continue
        if src in copied_sources:
            continue

        if dest_dir is None:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            common_dir = Path(__file__).resolve().parent
            dest_dir = common_dir / "shared" / "images" / profile_name / "AddedItems" / now
            dest_dir.mkdir(parents=True, exist_ok=True)

        dest_filename = f"{tier} - {_safe_name(localized)}.png"
        shutil.copy2(src, dest_dir / dest_filename)
        copied_sources.add(src)
        copied += 1

    return dest_dir, copied, missing

