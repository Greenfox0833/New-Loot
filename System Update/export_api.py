from urllib.parse import quote

from http_client import session

def normalize_asset_path(asset_path: str) -> str:
    if not asset_path:
        return ""
    return asset_path.strip().split(".", 1)[0]

def fetch_export_json(path_like: str) -> dict | None:
    if not path_like:
        return None
    url = f"https://export-service.dillyapis.com/v1/export?Path={quote(path_like, safe='/._')}"
    try:
        r = session.get(url, timeout=10)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None

def extract_itemname_key(export_json: dict) -> str | None:
    arr = (export_json or {}).get("jsonOutput") or []
    if not arr:
        return None
    root = arr[0] if isinstance(arr, list) else arr
    props = root.get("Properties", {})
    if isinstance(props, dict):
        im = props.get("ItemName")
        if isinstance(im, dict) and im.get("key"):
            return im["key"]
    im2 = root.get("ItemName")
    if isinstance(im2, dict) and im2.get("key"):
        return im2["key"]
    return None

def fetch_localized_name(key: str) -> str:
    url = "https://export-service.dillyapis.com/v1/export/localize"
    payload = {"culture": "ja", "ns": "", "values": [{"key": key}]}
    try:
        r = session.post(url, json=payload, timeout=10)
        if r.ok:
            arr = r.json().get("jsonOutput", [])
            return (arr[0].get("value") if arr and isinstance(arr[0], dict) else None) or "???"
    except Exception:
        pass
    return "???"
