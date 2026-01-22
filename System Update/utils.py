import re

def as_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, bool):
            return float(int(x))
        return float(x)
    except Exception:
        return default

def key_suffix_num(s: str) -> int:
    m = re.search(r"\.(\d{2})$", str(s))
    return int(m.group(1)) if m else 0

def _asset_path_from_row(row: dict) -> str:
    try:
        idef = row.get("ItemDefinition")
        if isinstance(idef, dict):
            ap = idef.get("AssetPathName", "")
            if ap:
                return ap
        if isinstance(idef, str):
            return idef
        return row.get("AssetPathName", "") or ""
    except Exception:
        return ""
