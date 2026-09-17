import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "hotfix_profiles.json"
_SECTION_RE = re.compile(r"^;\s*=+\s*([0-9a-f]{32})\s*=+\s*$", re.IGNORECASE)


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {"default": {"enabled": True, "excludeSections": []}, "profiles": {}}
    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Hotfix設定JSONの形式が不正です: {SETTINGS_PATH}")
    return data


def get_hotfix_settings(profile_name: str) -> dict:
    data = _load_settings()
    default = data.get("default") if isinstance(data.get("default"), dict) else {}
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    requested = str(profile_name or "BR").replace("\\", "/").casefold()
    selected = next(
        (value for key, value in profiles.items() if str(key).replace("\\", "/").casefold() == requested),
        {},
    )
    if not isinstance(selected, dict):
        selected = {}
    return {
        "enabled": bool(selected.get("enabled", default.get("enabled", True))),
        "excludeSections": selected.get("excludeSections", default.get("excludeSections", [])) or [],
    }


def is_hotfix_enabled(profile_name: str) -> bool:
    return get_hotfix_settings(profile_name)["enabled"]


def filter_hotfix_sections(hotfix_text: str, profile_name: str) -> str:
    settings = get_hotfix_settings(profile_name)
    if not settings["enabled"]:
        return ""
    excluded = {str(value).strip().casefold() for value in settings["excludeSections"] if str(value).strip()}
    if not excluded:
        return hotfix_text

    output = []
    include = False
    for line in hotfix_text.splitlines():
        match = _SECTION_RE.match(line.strip())
        if match:
            include = match.group(1).casefold() not in excluded
        if include:
            output.append(line)
    return "\n".join(output)
