# -*- coding: utf-8 -*-
import re, json, math
from pathlib import Path
from datetime import datetime
import requests
from typing import Dict, List, Tuple, Optional
import uuid
from datetime import datetime

# ===== 設定 =====
BASE_DIR = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/BR")
WEBHOOK_URL = "https://discord.com/api/webhooks/1410895751482970202/yvCeLIZ8efdWY00jWtFdb2nlGAR3nG59He8zm8M_6ccXCtY_cLNRgS8gNbIZneI6L0WQ"  # ←差し替え
NO_IMAGE_PATH = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/No Image.png")  # ←任意。無ければ自動で画像なし

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
IMAGE_ROOT = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像/BR")
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

def build_embed(diff: Dict, latest_name: str, prev_name: str, attachment_name: Optional[str]) -> Dict:
    title = "モード : Blitz Royale"

    group_label = GROUP_NAME_MAP.get(diff['group'], diff['group'])
    header = f"```\n{group_label}\n```"

    short_id = diff['asset'].split('.')[-1]

    type_label = {
        "added": "追加",
        "removed": "削除",
        "changed": "変更"
    }.get(diff["type"], "その他")

    # パーセントの表示を統一
    if diff["type"] == "added":
        np = diff["new_percent"] if diff["new_percent"] is not None else 0.0
        percent_info = f"`0.0%` → **`{np:.1f}%`**"
    elif diff["type"] == "removed":
        op = diff["old_percent"] if diff["old_percent"] is not None else 0.0
        percent_info = f"`{op:.1f}%` → **`0.0%`**"
    elif diff["type"] == "changed":
        op = diff["old_percent"] if diff["old_percent"] is not None else 0.0
        np = diff["new_percent"] if diff["new_percent"] is not None else 0.0
        percent_info = f"`{op:.1f}%` → **`{np:.1f}%`**"
    else:
        percent_info = "―"

    color = COLORS.get(diff["type"], 0x2B2D31)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    embed = {
        "title": title,
        "description": header,
        "color": color,
        "footer": {"text": f"更新時刻: {now_str}"},
        "fields": [
            {
                "name": "更新タイプ",
                "value": type_label,
                "inline": False
            },
            {
                "name": "Percent",
                "value": percent_info,
                "inline": False
            },
            {
                "name": "アイテム名",
                "value": diff["name"] or "―",
                "inline": True
            },
            {
                "name": "ID",
                "value": f"`{short_id}`",
                "inline": True
            },
        ]
    }

    if attachment_name:
        embed["thumbnail"] = {"url": f"attachment://{attachment_name}"}
    return embed

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

def send_one_diff(diff: Dict, latest_name: str, prev_name: str):
    attach_name = None
    files_mp = []
    attachments_meta = None

    img = resolve_item_image_path(diff["name"], diff["rarity"])
    if img and img.exists():
        # ←ここで安全な名前に置換
        safe_name = _safe_filename(img)
        attach_name = safe_name
        files_mp.append(("files[0]", (safe_name, open(img, "rb"), _guess_mime(img.suffix))))
        attachments_meta = [{"id": "0", "filename": safe_name}]
    elif NO_IMAGE_PATH.exists():
        attach_name = NO_IMAGE_PATH.name  # ここはASCIIなのでそのまま
        files_mp.append(("files[0]", (attach_name, open(NO_IMAGE_PATH, "rb"), _guess_mime(NO_IMAGE_PATH.suffix))))
        attachments_meta = [{"id": "0", "filename": attach_name}]

    embed = build_embed(diff, latest_name, prev_name, attach_name)

    payload = {"embeds": [embed]}
    if attachments_meta:
        payload["attachments"] = attachments_meta

    if files_mp:
        # multipart: files + payload_json（順序は実質無関係だが、先にfilesを渡すのが無難）
        files_mp.append(("payload_json", (None, json.dumps(payload, ensure_ascii=False), "application/json")))
        r = requests.post(WEBHOOK_URL, files=files_mp)
    else:
        r = requests.post(WEBHOOK_URL, json=payload)

    if r.status_code >= 300:
        print("[Webhook Error]", r.status_code, r.text)

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

    # 1アイテム = 1メッセージ（テスト運用）
    for d in diffs:
        send_one_diff(d, latest.name, prev.name)

if __name__ == "__main__":
    main()
