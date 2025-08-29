# -*- coding: utf-8 -*-
import re, json, math
from pathlib import Path
from datetime import datetime
import requests
from typing import Dict, List, Tuple, Optional
import uuid
from datetime import datetime
import time

# ===== 設定 =====
BASE_DIR = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/ForbiddenFruit")
WEBHOOK_URL = "https://discord.com/api/webhooks/1410895751482970202/yvCeLIZ8efdWY00jWtFdb2nlGAR3nG59He8zm8M_6ccXCtY_cLNRgS8gNbIZneI6L0WQ"  # ←差し替え
NO_IMAGE_PATH = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/イメージなし.png")  # ←任意。無ければ自動で画像なし

def post_with_retry(url: str, *, json_payload=None, files_payload=None, max_retry: int = 5):
    """
    Discord Webhook用: 429時は retry_after 秒待ってリトライ。
    それ以外のエラーも指数バックオフで再試行。
    """
    attempt = 0
    backoff = 0.5
    while True:
        attempt += 1
        if files_payload is not None:
            r = requests.post(url, files=files_payload)
        else:
            r = requests.post(url, json=json_payload)

        if r.status_code < 300:
            return r

        if r.status_code == 429:
            try:
                data = r.json()
                wait = float(data.get("retry_after", 1.0))
            except Exception:
                wait = 1.0
            print(f"[RateLimit] {wait}秒待機して再試行します…")
            time.sleep(wait)
            continue

        print("[Webhook Error]", r.status_code, r.text)
        if attempt >= max_retry:
            return r
        time.sleep(backoff)
        backoff = min(backoff * 2, 8.0)

# 追加=緑 / 削除=赤 / 変更=黄
COLORS = {"added": 0x57F287, "removed": 0xED4245, "changed": 0xFEE75C}

# 例: Week10_2025-08-23_23-38.json
NAME_RE = re.compile(r".*?_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})\.json$", re.IGNORECASE)

def parse_dt_from_filename(name: str) -> Optional[datetime]:
    m = NAME_RE.match(name)
    if not m:
        return None
    d, t = m.groups()                    # '2025-08-23', '23-38'
    return datetime.strptime(f"{d} {t.replace('-',':')}", "%Y-%m-%d %H:%M")

def pick_latest_two_json_by_name(base_dir: Path) -> Tuple[Path, Path]:
    files = [p for p in base_dir.iterdir() if p.is_file() and p.suffix.lower()==".json"]
    parsed = []
    for f in files:
        dt = parse_dt_from_filename(f.name)
        if dt: parsed.append((dt, f))
    if len(parsed) < 2:
        raise RuntimeError("比較対象のJSONが2つ以上見つかりません。")
    parsed.sort(key=lambda x: x[0], reverse=True)
    return parsed[0][1], parsed[1][1]  # 最新, 1個前

def load_json(p: Path) -> Dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# あなたのJSON構造に合わせて、AssetPathNameごとに Percent / 名称 / レア を引ける索引を作る
def build_index(data: Dict) -> Dict[str, Dict]:
    idx = {}
    for group, block in data.items():
        for itm in block.get("Items", []):
            for pkg in itm.get("ValidLootPackages", []):
                for pk in pkg.get("Packages", []):
                    for li in pk.get("ListItems", []):
                        asset = li.get("AssetPathName")
                        wlid  = li.get("WorldListID") or ""
                        pkgid = pk.get("ID") or ""
                        if not asset:
                            continue
                        # ★ 複合キー：Group / Package / WorldListID / Asset
                        key = f"{group}|{pkgid}|{wlid}|{asset}"
                        idx[key] = {
                            "percent": _to_float(li.get("ListPercent")),
                            "name": li.get("LocalizedName", "???"),
                            "rarity": li.get("rarity", "???"),
                            "group": group,
                            "asset": asset,          # 元のパスも保持
                            "world_list_id": wlid,   # 参照用
                            "package_id": pkgid,
                        }
    return idx


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ここに追加する 👇
IMAGE_ROOT = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像/ForbiddenFruit")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

def rarity_to_tier(rarity: str | None) -> int | None:
    m = {
        "common":1,"コモン":1,"uncommon":2,"アンコモン":2,"rare":3,"レア":3,
        "epic":4,"エピック":4,"legendary":5,"legend":5,"レジェンド":5,
        "exotic":6,"エキゾチック":6,"mythic":7,"ミシック":7
    }
    return m.get(str(rarity).strip().lower()) if rarity else None

def _norm(name: str) -> str:
    return " ".join(str(name).replace("\u3000", " ").split())

def resolve_item_image_path(localized_name: str | None, rarity: str | None) -> Path | None:
    if not localized_name:
        return None
    tier = rarity_to_tier(rarity)
    if tier is None:
        return None

    name = _norm(localized_name)

    # フォルダ方式
    folder = IMAGE_ROOT / f"{name}_ティア{tier}"
    if folder.is_dir():
        for cand in [folder / f"main{ext}" for ext in IMAGE_EXTS]:
            if cand.exists():
                return cand
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                return p

    # ファイル方式
    for pattern in (f"{name} - ティア{tier}", f"{name}_ティア{tier}"):
        for ext in IMAGE_EXTS:
            p = IMAGE_ROOT / f"{pattern}{ext}"
            if p.exists():
                return p

    return None

def compare_percent_only(old_idx: Dict[str, Dict], new_idx: Dict[str, Dict]) -> List[Dict]:
    """
    差分: added/removed/changed（Percentのみ比較）
    diff = {
      "type": "...",
      "asset": str, "name": str, "rarity": str, "group": str,
      "old_percent": float|None, "new_percent": float|None,
    }
    """
    diffs = []
    old_keys = set(old_idx.keys())
    new_keys = set(new_idx.keys())

    # 追加
    for a in sorted(new_keys - old_keys):
        n = new_idx[a]
        diffs.append({
            "type": "added", "asset": a,
            "name": n["name"], "rarity": n["rarity"], "group": n["group"],
            "old_percent": None, "new_percent": n["percent"]
        })

    # 変更
    for a in sorted(new_keys & old_keys):
        o, n = old_idx[a], new_idx[a]
        op = o["percent"] if o["percent"] is not None else 0.0
        np = n["percent"] if n["percent"] is not None else 0.0
        if not math.isclose(op, np, abs_tol=1e-6):
            diffs.append({
                "type": "changed", "asset": a,
                "name": n["name"], "rarity": n["rarity"], "group": n["group"],
                "old_percent": o["percent"], "new_percent": n["percent"]
            })

    # 削除
    for a in sorted(old_keys - new_keys):
        o = old_idx[a]
        diffs.append({
            "type": "removed", "asset": a,
            "name": o["name"], "rarity": o["rarity"], "group": o["group"],
            "old_percent": o["percent"], "new_percent": None
        })

    return diffs

# グループ名の表示変換用マップ
GROUP_NAME_MAP = {
    "Loot_Random_Exotic": "ランダムエキゾチック",
    "Loot_Random_Mythic": "ランダムミシック",
    "Loot_ApolloTreasure_Rare": "レア宝箱",
    "Loot_AthenaBlitzLlama": "レア宝箱",
    "Loot_AthenaBlitzLlama": "シルバーラマ",
    "Loot_AthenaBlitzRareLlama": "レジェンドラマ",
    "Loot_AthenaFloorLoot": "フロア戦利品",
    "Loot_AthenaSupplyDrop": "補給物資",
    "Loot_AthenaTreasure": "宝箱",
    "Loot_AthenaVending": "自販機",
    "Loot_POICapture": "POIテリトリー",
    "Loot_Random_Boon": "ランダム恵み",
    "Loot_Bus_Grant": "バス降下アイテム",
    "Loot_Gold_Chest": "ゴールド宝箱",
    "Loot_Random_Medallion": "ランダムメダリオン",
}

def _short_id_from_asset(asset: str) -> str:
    return str(asset).split('.')[-1] if asset else ""

def _weapon_key(diff: Dict) -> str:
    # 「名前 + レアリティ + 短縮ID」で武器を一意化
    return f"{diff.get('name','???')}|{diff.get('rarity','???')}|{_short_id_from_asset(diff.get('asset',''))}"

def group_diffs_by_weapon(diffs: List[Dict]) -> Dict[str, List[Dict]]:
    g: Dict[str, List[Dict]] = {}
    for d in diffs:
        k = _weapon_key(d)
        g.setdefault(k, []).append(d)
    return g

def build_weapon_embed(weapon_name: str, weapon_id: str, items: List[Dict], attachment_name: Optional[str]) -> Dict:
    # タイトル（モード固定）
    title = "Blitz Royale"

    # 2段目（黒帯）＝武器名（ご要望の「上から二番目 = 武器名」）
    header = f"```\n{weapon_name}（{items[0].get('rarity','???')}）\n```"

    # 表示順：日本語ラベルの昇順（必要なら並び替え規則をここでカスタム）
    def label_of(d):
        return GROUP_NAME_MAP.get(d['group'], d['group'])

    fields = []

    # 含まれる差分の種類を調べて更新タイプを決定
    types = {d["type"] for d in items}
    if types == {"changed"}:
        type_label = "更新"
    elif types == {"added"}:
        type_label = "追加"
    elif types == {"removed"}:
        type_label = "削除"
    elif "added" in types and "removed" not in types and "changed" not in types:
        type_label = "追加"
    elif "removed" in types and "added" not in types and "changed" not in types:
        type_label = "削除"
    else:
        type_label = "更新"  # 複合の場合は「更新」

    fields.append({"name": "更新タイプ", "value": type_label, "inline": False})

    for d in sorted(items, key=label_of):
        group_label = GROUP_NAME_MAP.get(d['group'], d['group'])
        # パーセント表示（追加/削除/変更を統一表記）
        if d["type"] == "added":
            op, np = 0.0, (d["new_percent"] or 0.0)
        elif d["type"] == "removed":
            op, np = (d["old_percent"] or 0.0), 0.0
        else:
            op, np = (d["old_percent"] or 0.0), (d["new_percent"] or 0.0)
        percent_info = f"`{op:.2g}%` → **`{np:.2g}%`**"

        fields.append({
            "name": group_label,
            "value": percent_info,
            "inline": False
        })

    # 最後に武器ID
    fields.append({"name": "ID", "value": f"`{weapon_id}`", "inline": False})

    # フッター（現在時刻）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 最初のアイテムの type を代表にして色を決める
    main_type = items[0]["type"] if items else "changed"
    color = COLORS.get(main_type, 0x2B2D31)

    embed = {
        "title": title,
        "description": header,
        "color": color,
        "footer": {"text": f"更新時刻: {now_str}"},
        "fields": fields
    }

    if attachment_name:
        embed["thumbnail"] = {"url": f"attachment://{attachment_name}"}
    return embed

def send_one_weapon(weapon_name: str, rarity: str, weapon_id: str, items: List[Dict]):
    attach_name = None
    files_mp = []
    attachments_meta = None

    # 武器画像は武器名+レアで1回だけ解決
    img = resolve_item_image_path(weapon_name, rarity)
    if img and img.exists():
        safe_name = _safe_filename(img)
        attach_name = safe_name
        files_mp.append(("files[0]", (safe_name, open(img, "rb"), _guess_mime(img.suffix))))
        attachments_meta = [{"id": "0", "filename": safe_name}]
    elif NO_IMAGE_PATH.exists():
        safe_name = _safe_filename(NO_IMAGE_PATH)
        attach_name = safe_name
        files_mp.append(("files[0]", (safe_name, open(NO_IMAGE_PATH, "rb"), _guess_mime(NO_IMAGE_PATH.suffix))))
        attachments_meta = [{"id": "0", "filename": safe_name}]

    embed = build_weapon_embed(weapon_name, weapon_id, items, attach_name)

    payload = {"embeds": [embed]}
    if attachments_meta:
        payload["attachments"] = attachments_meta

    if files_mp:
        files_mp.append(("payload_json", (None, json.dumps(payload, ensure_ascii=False), "application/json")))
        r = post_with_retry(WEBHOOK_URL, files_payload=files_mp)
    else:
        r = post_with_retry(WEBHOOK_URL, json_payload=payload)

    time.sleep(0.35)
    return r


def _guess_mime(suffix: str) -> str:
    s = suffix.lower()
    if s == ".png": return "image/png"
    if s in (".jpg", ".jpeg"): return "image/jpeg"
    if s == ".webp": return "image/webp"
    return "application/octet-stream"

def _safe_filename(path: Path) -> str:
    # ランダムIDを付ける or 英数字化する
    # 日本語を含んでいても衝突しないようにする
    ext = path.suffix.lower()
    safe = uuid.uuid4().hex  # 例: "a3f0c9..."
    return f"{safe}{ext}"

def main():
    latest, prev = pick_latest_two_json_by_name(BASE_DIR)
    latest_data = load_json(latest)
    prev_data   = load_json(prev)

    latest_idx = build_index(latest_data)
    prev_idx   = build_index(prev_data)

    diffs = compare_percent_only(prev_idx, latest_idx)  # 「前→最新」で比較

    if not diffs:
        print("差分なし：送信しません。")
        return

    # 1武器 = 1メッセージ
    weapons = group_diffs_by_weapon(diffs)
    for k, items in weapons.items():
        # k = "name|rarity|id"
        parts   = k.split("|")
        w_name  = parts[0] if len(parts) > 0 else "???"
        w_rarity= parts[1] if len(parts) > 1 else "???"
        w_id    = parts[2] if len(parts) > 2 else ""
        send_one_weapon(w_name, w_rarity, w_id, items)

if __name__ == "__main__":
    main()
