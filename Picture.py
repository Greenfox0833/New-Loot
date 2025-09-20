import json
import math
import re
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ==========================
# 🛠 設定エリア（ここだけ編集）
# ==========================
JSON_PATH   = Path(r"e:/フォートナイト/Picture/Loot Pool/TEST4/New Loot/戦利品データ/Figment/v37.10_2025-09-18_17-39.json")
TARGET      = "Loot_BirthdayGiftBox"  # 例: "Loot_AthenaTreasure" / "LTG_ArmoryBriefing" など
ICONS_ROOT  = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像")  # ここに<MODE>サブフォルダ
MODE        = "Figment"                    # "BR" や "ZB" など自由
OUT_DIR     = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/アイテム画像")  # 出力先
NOIMAGE_DIR = Path(r"E:/フォートナイト/Picture/Loot Pool/TEST4/NoImage")    # NoImage格納フォルダ
SHOW_PERCENT = True                   # True=％表示オン / False=オフ
SORT_BY_PERCENT_DESC = True
DEDUP_BY_NAME_RARITY_PERCENT = True

# 画像と文字のスタイル
DEFAULT_FONT_PATH = r"c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF"  # 既定フォント（日本語可）
TILE_SIZE  = 128
TILE_PAD   = 12
MAX_PER_ROW = 25
SECTION_TITLE_FONT_SIZE = 26
PERCENT_FONT_SIZE       = 18
HEADER_VPAD = 10
SECTION_BOTTOM_VPAD = 24
CANVAS_BG  = (18, 18, 18)
TITLE_FG   = (230, 230, 230)
PERCENT_BG = (0, 0, 0, 128)
PERCENT_FG = (255, 255, 255, 255)
# ==========================

RARITY_TO_TIER = {
    "コモン": 1,
    "アンコモン": 2,
    "レア": 3,
    "エピック": 4,
    "レジェンド": 5,
    "エキゾチック": 6,
    "ミシック": 7,
}

def sort_key_by_percent_desc(it: dict):
    # None は一番後ろ、そのほかは大きい値ほど先頭へ
    p = it.get("ListPercent", None)
    # 同率時はレアリティ（高い→低い）、名前（昇順）で安定化
    rarity = it.get("rarity") or "コモン"
    name = (it.get("LocalizedName") or "").strip()
    return (
        p is None,                      # False(0)=先、True(1)=後
        -(p if p is not None else 0),   # 大きいほど先
        -RARITY_TO_TIER.get(rarity, 1), # ティア高いほど先
        name                             # 名前昇順
    )

def _percent_display_key(p):
    if p is None:
        return None
    # バッジ表示と合わせる（{pct:.4g}%）→ 4桁有効数字で丸め
    return f"{p:.4g}"

def dedup_items_by_name_rarity_percent(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        name   = (it.get("LocalizedName") or "").strip()
        rarity = (it.get("rarity") or "コモン").strip()
        pkey   = _percent_display_key(it.get("ListPercent"))
        key = (name, rarity, pkey)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

INVALID_CHARS = r'[\\/:*?"<>|]'

def decide_cols(num_items: int) -> int:
    """
    列数を決める。MAX_PER_ROW > 0 ならその値を優先（固定）、
    0 の場合はアイテム数に応じて自動調整。
    """
    if MAX_PER_ROW > 0:
        return min(MAX_PER_ROW, num_items)

    # === 自動ルール（好みに合わせて調整OK）===
    if num_items <= 8:
        return num_items                # 少数は1行に収める
    elif num_items <= 50:
        return 12
    elif num_items <= 100:
        return 16
    elif num_items <= 200:
        return 20
    else:
        return 25

def safe_name(name: str) -> str:
    name = re.sub(INVALID_CHARS, " ", name)
    return re.sub(r"\s+", " ", name).strip()

def open_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        try:
            return ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", size=size)
        except Exception:
            return ImageFont.load_default()

def chunk_every(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def find_icon_file(icons_root: Path, mode: str, localized_name: str, rarity: str) -> Path | None:
    tier = RARITY_TO_TIER.get(rarity, 1)
    fname = f"{safe_name(localized_name)} - ティア{tier}.png"
    p = icons_root / mode / fname
    return p if p.is_file() else None

def load_image(path: Path, size=(TILE_SIZE, TILE_SIZE)) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return im

def draw_percent_badge(base: Image.Image, percent_text: str, font: ImageFont.FreeTypeFont):
    w, h = base.size
    pad = 4

    # まずは透明の一時レイヤーを用意
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")

    tw, th = d.textbbox((0, 0), percent_text, font=font)[2:]
    bw, bh = tw + pad*2, th + pad*2
    x0 = w - bw - 4    # 右上
    y0 = 4

    # 半透明の角丸黒帯 + 文字を一時レイヤーに描く
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=6, fill=PERCENT_BG)
    d.text((x0 + pad, y0 + pad), percent_text, font=font, fill=PERCENT_FG)

    # レイヤーをタイルに合成（ここでアルファが確実に効く）
    base.alpha_composite(overlay)

def measure_section_height(num_items: int, title_font: ImageFont.FreeTypeFont, cols: int) -> int:
    rows = math.ceil(num_items / cols) if num_items else 0
    title_h = title_font.size + HEADER_VPAD * 2
    grid_h = rows * TILE_SIZE + (rows - 1) * TILE_PAD if rows > 0 else 0
    return title_h + grid_h + SECTION_BOTTOM_VPAD

def collect_calls_from_json(data: dict, target: str):
    if target not in data:
        raise KeyError(f"target '{target}' がJSONに見つかりません。")

    merged = {}  # call名ごとにまとめる
    for itm in data[target].get("Items", []):
        for vlp in itm.get("ValidLootPackages", []):
            for pkg in vlp.get("Packages", []):
                call = pkg.get("Call", "")
                list_items = pkg.get("ListItems", []) or []
                normalized = []
                for li in list_items:
                    normalized.append({
                        "LocalizedName": (li.get("LocalizedName") or "").strip() or "NO NAME",
                        "rarity": (li.get("rarity") or "").strip() or "コモン",
                        "ListPercent": li.get("ListPercent", None),
                    })

                if call not in merged:
                    merged[call] = {"call": call, "items": []}
                merged[call]["items"].extend(normalized)

    # dict → list に変換
    return list(merged.values())

def build_canvas_width(cols: int) -> int:
    tiles_width = cols * TILE_SIZE + (cols - 1) * TILE_PAD
    return tiles_width + 24 * 2  # 左右マージン

def _read_text_auto(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"デコード失敗: {p}")

def _looks_like_json(text: str) -> bool:
    s = text.lstrip()
    return bool(s) and s[0] in "[{"

def _maybe_extract_path(line: str) -> Path | None:
    first = line.strip()
    if (first.startswith('"') and first.endswith('"')) or (first.startswith("'") and first.endswith("'")):
        first = first[1:-1]
    p = Path(first)
    return p if p.is_file() else None  # ← フォルダは弾く

def _extract_json_from_text(text: str):
    # テキスト中で最初に出現する { または [ から末尾を JSON 候補として試す
    m = re.search(r'[\[{]', text)
    if not m:
        return None
    candidate = text[m.start():]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def load_json_resolving_redirect(json_path: Path) -> dict:
    if not json_path.is_file():
        raise FileNotFoundError(f"JSONが見つかりません: {json_path}")

    text = _read_text_auto(json_path)

    # まずはテキスト内から最初の JSON ブロックを抽出して試す
    data = _extract_json_from_text(text)
    if data is not None:
        return data

    # JSON っぽくない → リダイレクト（単独行のパス）の可能性を検査
    # ※ “説明＋JSON” のように複数行ある場合は誤検出を避けるため無視
    nonempty = [ln for ln in (ln.strip() for ln in text.splitlines()) if ln]
    if len(nonempty) == 1:
        redirect = _maybe_extract_path(nonempty[0])
        if redirect and redirect.resolve() != json_path.resolve():
            text2 = _read_text_auto(redirect)
            data2 = _extract_json_from_text(text2)
            if data2 is not None:
                print(f"[info] JSONの中身がパスでした。実体を読み直しました: {redirect}")
                return data2
            head2 = text2.lstrip()[:200]
            raise ValueError(f"再解決先もJSONではありません。先頭={head2!r} / path={redirect}")

    head = text.lstrip()[:200]
    raise ValueError(f"JSONとして解釈できませんでした。先頭={head!r} / path={json_path}")


def main():
    # 入力確認
    if not JSON_PATH.is_file():
        raise FileNotFoundError(f"JSONが見つかりません: {JSON_PATH}")
    if not ICONS_ROOT.is_dir():
        raise NotADirectoryError(f"ICONS_ROOTが見つかりません: {ICONS_ROOT}")
    (OUT_DIR).mkdir(parents=True, exist_ok=True)

    # フォント
    title_font = open_font(DEFAULT_FONT_PATH, SECTION_TITLE_FONT_SIZE)
    percent_font = open_font(DEFAULT_FONT_PATH, PERCENT_FONT_SIZE)

    # JSONロード（堅牢化） & Call収集
    # 1) 物理存在とサイズ確認
    if not JSON_PATH.is_file():
        raise FileNotFoundError(f"JSONが見つかりません: {JSON_PATH}")
    size = JSON_PATH.stat().st_size
    if size == 0:
        raise ValueError(f"JSONファイルが空です（サイズ0）: {JSON_PATH}")

    data = load_json_resolving_redirect(JSON_PATH)
    calls = [c for c in collect_calls_from_json(data, TARGET) if c["items"]]

    for c in calls:
        if DEDUP_BY_NAME_RARITY_PERCENT:
            c["items"] = dedup_items_by_name_rarity_percent(c["items"])
        if SORT_BY_PERCENT_DESC:
            c["items"].sort(key=sort_key_by_percent_desc)
        if not calls:
            raise RuntimeError("表示対象の ListItems がありません。")

    # セクションごとの列数を先に決定
    cols_list = [decide_cols(len(c["items"])) for c in calls]

    # キャンバス計測（幅は一番広いセクションに合わせる）
    canvas_w = max(build_canvas_width(cols) for cols in cols_list) if cols_list else build_canvas_width(1)
    total_h = sum(
        measure_section_height(len(c["items"]), title_font, cols_list[i])
        for i, c in enumerate(calls)
    )

    canvas = Image.new("RGBA", (canvas_w, total_h), CANVAS_BG + (255,))
    draw = ImageDraw.Draw(canvas)
    x_margin = 24
    y = 0

    for idx, section in enumerate(calls):
        call_name = section["call"] or "(Callなし)"
        items = section["items"]
        cols = cols_list[idx]

        if SORT_BY_PERCENT_DESC:
            items.sort(key=sort_key_by_percent_desc)

        # 見出し
        draw.text((x_margin, y + HEADER_VPAD), call_name, font=title_font, fill=TITLE_FG)
        y += title_font.size + HEADER_VPAD * 2

        # グリッド
        for row in chunk_every(items, cols):
            x = x_margin
            for it in row:
                ln = it["LocalizedName"]
                rarity = it["rarity"]
                pct = it.get("ListPercent")

                icon_path = find_icon_file(ICONS_ROOT, MODE, ln, rarity)
                if icon_path and icon_path.is_file():
                    tile = load_image(icon_path)
                else:
                    noimg = NOIMAGE_DIR / "NoImage.png"
                    if noimg.is_file():
                        tile = load_image(noimg)
                    else:
                        tile = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (60, 60, 60, 255))
                        ImageDraw.Draw(tile).text((8, 8), "NO IMAGE", font=percent_font, fill=(255, 255, 255, 255))

                if SHOW_PERCENT and pct is not None:
                    draw_percent_badge(tile, f"{pct:.4g}%", percent_font)

                canvas.alpha_composite(tile, (x, y))
                x += TILE_SIZE + TILE_PAD
            y += TILE_SIZE
            if len(row) > 0:
                y += TILE_PAD

        y -= TILE_PAD  # 最終行の余白調整
        y += SECTION_BOTTOM_VPAD

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{MODE}_{ts}.png"
    canvas.convert("RGB").save(out_path, format="PNG")
    print(f"✅ 保存完了: {out_path}")

if __name__ == "__main__":
    main()
