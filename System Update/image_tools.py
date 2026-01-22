import os
import re

from PIL import Image, ImageDraw, ImageFont

from cache import (
    ICON_PATH_CACHE,
    fetch_export_image_as_pil,
    get_name_by_asset,
    save_icon_cache,
)
from config import (
    AMMO_ICON_DIR,
    AMMO_ICON_MAP,
    DRAW_STATS,
    FONT_PATH,
    RARITY_BG_DIR,
    RARITY_BORDER_COLORS,
    RARITY_ICON_DIR,
    RARITY_JP_MAP,
    RARITY_MAP,
    RARITY_TO_TIER,
    SHOW_PERCENT,
    STAT_TEMPLATE_PATH,
)
from export_api import fetch_localized_name
from http_client import session

def get_weapon_stats(props):
    try:
        stat_handle = props.get("WeaponStatHandle", {})
        data_table = stat_handle.get("DataTable", {})
        object_path = data_table.get("ObjectPath", "")
        row_name = stat_handle.get("RowName", "")
        if not object_path or not row_name:
            return None
        clean_path = object_path.replace(".0", "").lstrip("/")
        url = f"https://export-service.dillyapis.com/v1/export/?Path={clean_path}"
        response = session.get(url, timeout=30)
        data = response.json()
        json_output = data.get("jsonOutput", {})
        if isinstance(json_output, list):
            json_output = json_output[0]
        rows = json_output.get("Rows", {})
        stat_row = rows.get(row_name, {})
        dmg = stat_row.get("DmgPB", 0)
        bullet_count = stat_row.get("BulletsPerCartridge", 1)
        critical = stat_row.get("DamageZone_Critical", 1.0)
        max_dmg = stat_row.get("MaxDamagePerCartridge", -1)
        firing_rate = stat_row.get("FiringRate", "?")
        if isinstance(firing_rate, (int, float)):
            firing_rate = round(firing_rate, 1)
        reload_time = stat_row.get("ReloadTime", "?")
        if isinstance(reload_time, (int, float)):
            reload_time = round(reload_time, 1)
        clip_size = stat_row.get("ClipSize", "?")
        base_damage = round(dmg * bullet_count)
        headshot = round(base_damage * critical)
        if isinstance(max_dmg, (int, float)) and max_dmg != -1 and headshot > max_dmg:
            headshot = int(max_dmg)
        return {
            "ダメージ": base_damage,
            "建築ダメージ": headshot,
            "連射速度": firing_rate,
            "リロード時間": reload_time,
            "マガジン": clip_size,
        }
    except Exception:
        return None

def overlay_stat_template_with_numbers(canvas, stats, template_path):
    try:
        if not os.path.exists(template_path):
            return
        template = Image.open(template_path).convert("RGBA")
        canvas.paste(template, (10, 10), template)
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(FONT_PATH, 15)
        values = {
            "ダメージ": f"{stats.get('ダメージ', '?')}({stats.get('建築ダメージ', '?')})",
            "連射速度": f"{stats.get('連射速度', '?')}/s",
            "リロード時間": f"{stats.get('リロード時間', '?')}s",
            "マガジン": f"{stats.get('マガジン', '?')}",
        }
        positions = {
            "ダメージ": (65, 28),
            "連射速度": (190, 28),
            "リロード時間": (285, 28),
            "マガジン": (380, 28),
        }
        for key, (x, y) in positions.items():
            draw.text((x, y), values.get(key, "?"), font=font, fill="white")
    except Exception:
        pass

def fit_font(draw, text, width, max_size=28, min_size=14):
    for sz in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(FONT_PATH, sz)
        w = draw.textlength(text, font=font)
        if w <= width:
            return font
    return ImageFont.truetype(FONT_PATH, min_size)

def draw_percent_badge(canvas, text):
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_PATH, 18)
    pad = 8
    tw = draw.textlength(text, font=font)
    th = 22
    x1 = canvas.width - tw - pad * 2 - 10
    y1 = 10
    x2 = canvas.width - 10
    y2 = y1 + th + pad
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([x1, y1, x2, y2], fill=(0, 0, 0, 140))
    canvas.alpha_composite(overlay)
    draw.text((x2 - tw - pad, y1 + (th - 16) // 2), text, font=font, fill="white")

def generate_weapon_card_from_export(weapon_json, asset_path: str, out_dir: str, list_percent_text: str | None):
    try:
        jo = weapon_json["jsonOutput"]
        data = jo[0] if isinstance(jo, list) else jo
        props = data["Properties"]

        raw_rarity = props.get("Rarity")
        rarity = RARITY_MAP.get(raw_rarity, "Uncommon") if raw_rarity else "Uncommon"

        weapon_name = get_name_by_asset(asset_path)
        if weapon_name == "???":
            item_key = props.get("ItemName", {}).get("key", "")
            if item_key:
                weapon_name = fetch_localized_name(item_key)
            else:
                weapon_name = props.get("ItemName", {}).get("sourceString", "???")

        icon_path = None
        data_list = props.get("DataList", [])

        def _get(entry, key):
            return (entry.get(key) or {}).get("AssetPathName") if isinstance(entry, dict) else None

        if isinstance(data_list, dict):
            icon_path = _get(data_list, "LargeIcon") or _get(data_list, "Icon")
        elif isinstance(data_list, list):
            for entry in data_list:
                p = _get(entry, "LargeIcon")
                if p and isinstance(p, str) and p.strip():
                    icon_path = p
                    break
            if not icon_path:
                for entry in data_list:
                    p = _get(entry, "Icon")
                    if p and isinstance(p, str) and p.strip():
                        icon_path = p
                        break

        if not icon_path:
            icon_path = _get(props, "LargeIcon") or _get(props, "Icon")

        if not icon_path:
            base = asset_path.split("/")[-1].split(".")[0]
            icon_path = ICON_PATH_CACHE.get(base)

        if not icon_path:
            return

        canvas_size = 600
        bg_path = os.path.join(RARITY_BG_DIR, f"{rarity}.png")
        try:
            bg_image = Image.open(bg_path).convert("RGBA").resize((canvas_size, canvas_size))
        except Exception:
            return
        canvas = bg_image.copy()

        ammo_data = props.get("AmmoData")
        if ammo_data and "AssetPathName" in ammo_data:
            ammo_key = ammo_data["AssetPathName"].split("/")[-1].split(".")[0]
            ammo_icon_filename = AMMO_ICON_MAP.get(ammo_key)
            if ammo_icon_filename:
                ammo_icon_path = os.path.join(AMMO_ICON_DIR, ammo_icon_filename)
                if os.path.exists(ammo_icon_path):
                    try:
                        ammo_icon = Image.open(ammo_icon_path).convert("RGBA").resize((30, 30), Image.LANCZOS)
                        canvas.paste(ammo_icon, (canvas.width - 35, 10), ammo_icon)
                    except Exception:
                        pass

        try:
            icon_clean = icon_path.strip("/").split(".")[0]
            icon_image = fetch_export_image_as_pil(icon_clean)
            if icon_image is None:
                return
            base = asset_path.split("/")[-1].split(".")[0]
            if base not in ICON_PATH_CACHE:
                ICON_PATH_CACHE[base] = icon_clean
                save_icon_cache()
        except Exception:
            return
        icon_resized = icon_image.resize((400, 400), resample=Image.LANCZOS)
        pos_x = (canvas.width - icon_resized.width) // 2
        pos_y = (canvas.height - icon_resized.height) // 2
        canvas.paste(icon_resized, (pos_x, pos_y), icon_resized)

        if DRAW_STATS:
            stats = get_weapon_stats(props)
            if stats:
                overlay_stat_template_with_numbers(canvas, stats, STAT_TEMPLATE_PATH)

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([(0, 500), (canvas.width, 600)], fill=(0, 0, 0, 128))
        canvas = Image.alpha_composite(canvas, overlay)

        draw = ImageDraw.Draw(canvas)

        rarity_icon_path = os.path.join(RARITY_ICON_DIR, f"{rarity}.png")
        if os.path.exists(rarity_icon_path):
            try:
                rimg = Image.open(rarity_icon_path).convert("RGBA")
                target_h = 32
                tw = int(target_h * rimg.width / rimg.height)
                rimg = rimg.resize((tw, target_h), Image.LANCZOS)
                canvas.paste(rimg, ((canvas.width - tw) // 2, 515), rimg)
            except Exception:
                pass

        font = fit_font(draw, weapon_name, canvas.width - 40, max_size=28, min_size=14)
        bbox = draw.textbbox((0, 0), weapon_name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_y = 500 + (100 - text_h) // 2 + 14
        draw.text(((canvas.width - text_w) // 2, text_y), weapon_name, font=font, fill="white")

        if SHOW_PERCENT and list_percent_text:
            draw_percent_badge(canvas, list_percent_text)

        border_color = RARITY_BORDER_COLORS.get(rarity, "#ffffff")
        draw.rectangle([(0, 0), (canvas.width - 1, canvas.height - 1)], outline=border_color, width=2)

        safe_weapon_name = re.sub(r'[\\/:"*?<>|]', "_", weapon_name)

        rarity_ja = RARITY_JP_MAP.get(rarity.lower(), rarity)
        tier = RARITY_TO_TIER.get(rarity_ja, "ティア?")

        filename = f"{safe_weapon_name} - {tier}.png"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        if os.path.exists(out_path):
            return
        canvas.save(out_path)
        print(f"[✔] 生成: {out_path}")
    except Exception as e:
        print(f"[×] カード生成失敗: {e}")
