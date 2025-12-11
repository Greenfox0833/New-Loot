import json
import os
import sys
import math
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# Paths
DEFAULT_JSON_PATH = os.path.join("戦利品データ", "BR", "LootPercent", "BR_LootData_2025-12-06_05-30.json")
DEFAULT_ICON_DIR = r"E:\フォートナイト\Picture\Loot Pool\TEST4\アイテム画像\BR\IconOnly"
DEFAULT_SAVE_DIR = r"E:\フォートナイト\Picture\Loot Pool\TEST4\アイテム画像"
DEFAULT_TITLE = "チャプター7 シーズン1 : 戦利品データ"
DEFAULT_SUBTITLE = ""
DATASET_CHOICES = ["BR", "BRComp", "ZB", "ZBComp", "Reload", "OG", "Delulu"]

RARITY_TIER = {
    "コモン": 1,
    "アンコモン": 2,
    "レア": 3,
    "エピック": 4,
    "レジェンド": 5,
    "エキゾチック": 6,
    "ミシック": 7,
}

RARITY_ORDER = ["コモン", "アンコモン", "レア", "エピック", "レジェンド", "エキゾチック", "ミシック"]
RARITY_COLOR = {
    "コモン": (104, 111, 122),
    "アンコモン": (45, 157, 45),
    "レア": (42, 123, 214),
    "エピック": (161, 42, 214),
    "レジェンド": (214, 123, 42),
    "エキゾチック": (42, 186, 186),
    "ミシック": (214, 191, 42),
}


def collect_items(node, seen, source_label, category_label=None):
    """Recursively walk dict/list to find ListItems entries and collect (name, rarity, source, category)."""
    results = []
    if isinstance(node, dict):
        if "ListItems" in node and isinstance(node["ListItems"], list):
            for item in node["ListItems"]:
                name = item.get("LocalizedName")
                rarity = item.get("rarity")
                if name and rarity:
                    key = (name, rarity, source_label, category_label)
                    if key not in seen:
                        seen.add(key)
                        results.append(key)
        for k, v in node.items():
            next_category = category_label
            if isinstance(k, str) and k.startswith("LootNumber_"):
                try:
                    num = int(k.split("_")[1])
                    next_category = f"カテゴリー{num + 1}"
                except Exception:
                    next_category = k
            results.extend(collect_items(v, seen, source_label, next_category))
    elif isinstance(node, list):
        for v in node:
            results.extend(collect_items(v, seen, source_label, category_label))
    return results


def load_items(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    pairs = []
    if isinstance(data, dict):
        for source_label, node in data.items():
            pairs.extend(collect_items(node, seen, source_label, None))
    rarities = sorted({r for _, r, _, _ in pairs}, key=lambda r: RARITY_ORDER.index(r) if r in RARITY_ORDER else 99)
    sources = sorted({s for _, _, s, _ in pairs})
    categories = sorted({c for *_ , c in pairs if c})
    # 初期表示はレアリティ優先で並べ、同名ならソースで安定化
    items = sorted(pairs, key=lambda x: (RARITY_ORDER.index(x[1]) if x[1] in RARITY_ORDER else 99, x[0], x[2]))
    return items, rarities, sources, categories


def find_icon_path(name, rarity, icon_dir):
    tier = RARITY_TIER.get(rarity)
    if not tier:
        return None
    filename = f"{name} - ティア{tier}.png"
    path = os.path.join(icon_dir, filename)
    if os.path.exists(path):
        return path
    return None


def _load_font(candidates, size):
    for fc in candidates:
        try:
            return ImageFont.truetype(fc, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def generate_image(selected_items, icon_dir, save_dir, dataset_name, title_text, subtitle_text, show_category_label=False, cols=13, cell_size=112, padding=18, title_height=120):
    if Image is None:
        messagebox.showerror("Pillow missing", "Pillow (PIL) がインストールされていません。pip install pillow を実行してください。")
        return False, None, ["Pillow not installed"]

    def draw_vertical_gradient(w, h, top_color, bottom_color):
        base = Image.new("RGBA", (w, h), top_color + (255,))
        top_r, top_g, top_b = top_color
        bot_r, bot_g, bot_b = bottom_color
        for y in range(h):
            t = y / max(h - 1, 1)
            r = int(top_r + (bot_r - top_r) * t)
            g = int(top_g + (bot_g - top_g) * t)
            b = int(top_b + (bot_b - top_b) * t)
            ImageDraw.Draw(base).line([(0, y), (w, y)], fill=(r, g, b, 255))
        return base

    # keep incoming order (respecting user drag order)
    selected_items = list(selected_items)

    icons = []
    missing = []
    for name, rarity, source, category in selected_items:
        icon_path = find_icon_path(name, rarity, icon_dir)
        if not icon_path:
            missing.append(f"{name} ({rarity}) [{source}] -> not found")
            continue
        try:
            img = Image.open(icon_path).convert("RGBA")
        except Exception as e:
            missing.append(f"{name} ({rarity}) [{source}] -> error: {e}")
            continue
        bg_color = RARITY_COLOR.get(rarity, (80, 80, 80))
        icons.append((img, bg_color, name, rarity, source, category))

    if not icons:
        return False, None, ["No icons found to draw."] + missing

    cols = max(1, cols)
    cell = cell_size
    pad = padding

    font_candidates = [
        r"C:\\Windows\\Fonts\\Noto Sans JP\\NotoSansJP-VariableFont_wght_0.ttf",
        r"c:/USERS/FN_GREENFOX/APPDATA/LOCAL/MICROSOFT/WINDOWS/FONTS/NOTOSANSJP-BOLD.OTF",
        "NotoSansJP-Regular.otf",
        "NotoSansJP-Regular.ttf",
        "NotoSans-Regular.ttf",
        "NotoSans-Regular.otf",
    ]
    label_font = _load_font(font_candidates, 12)
    if hasattr(label_font, "getsize"):
        label_h = label_font.getsize("Ag")[1]
    else:
        label_h = 14

    if show_category_label:
        grouped = {}
        for entry in icons:
            group_key = entry[5] if entry[5] else entry[4]
            grouped.setdefault(group_key, []).append(entry)
        group_keys = sorted(grouped.keys())
        total_h = title_height + pad
        for key in group_keys:
            items_len = len(grouped[key])
            rows_needed = math.ceil(items_len / cols)
            total_h += label_h + pad
            total_h += rows_needed * (cell + pad)
        canvas_w = cols * cell + (cols + 1) * pad
        canvas_h = total_h + pad
    else:
        rows = math.ceil(len(icons) / cols)
        canvas_w = cols * cell + (cols + 1) * pad
        canvas_h = title_height + rows * cell + (rows + 1) * pad

    # modern, deeper navy gradient
    canvas = draw_vertical_gradient(canvas_w, canvas_h, (12, 18, 36), (6, 10, 20))
    draw = ImageDraw.Draw(canvas)

    title_font = None
    subtitle_font = None

    def _measure_with_font(txt, fnt):
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), txt, font=fnt)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        return draw.textsize(txt, font=fnt)

    if title_text:
        title_font = _load_font(font_candidates, 28)
        tw, th = _measure_with_font(title_text, title_font)
        if subtitle_text:
            tx = canvas_w // 2 - tw // 2
            ty = 12
        else:
            tx = canvas_w // 2 - tw // 2
            ty = max(10, (title_height - th) // 2)
        draw.text((tx + 2, ty + 2), title_text, font=title_font, fill=(0, 0, 0))
        draw.text((tx, ty), title_text, font=title_font, fill=(255, 255, 255))
        if subtitle_text:
            subtitle_font = _load_font(font_candidates, 16)
            stw, sth = _measure_with_font(subtitle_text, subtitle_font)
            sx = canvas_w // 2 - stw // 2
            sy = ty + th + 8
            draw.text((sx + 1, sy + 1), subtitle_text, font=subtitle_font, fill=(0, 0, 0, 180))
            draw.text((sx, sy), subtitle_text, font=subtitle_font, fill=(230, 230, 230, 230))

    def draw_card_at(x0, y0, img, bg_color, category_label):
        icon_img = img.copy()
        target_w = cell - 12
        target_h = cell - 12
        icon_img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        ix, iy = icon_img.size
        px = x0 + (cell - ix) // 2
        py = y0 + (cell - iy) // 2
        canvas.paste(icon_img, (px, py), icon_img)

        if show_category_label and label_font is not None:
            label = category_label or ""
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), label, font=label_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            else:
                tw, th = draw.textsize(label, font=label_font)
            lx = x0 + (cell - tw) // 2
            ly = y0 + cell - th - 2
            draw.text((lx + 1, ly + 1), label, font=label_font, fill=(0, 0, 0))
            draw.text((lx, ly), label, font=label_font, fill=(255, 255, 255))

    if show_category_label:
        grouped = {}
        for entry in icons:
            group_key = entry[5] if entry[5] else entry[4]
            grouped.setdefault(group_key, []).append(entry)
        y_cursor = title_height + pad
        for src in sorted(grouped.keys()):
            label = src
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), label, font=label_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            else:
                tw, th = draw.textsize(label, font=label_font)

            # subtle divider + pill
            divider_y = y_cursor
            draw.line((pad, divider_y, canvas_w - pad, divider_y), fill=(255, 255, 255, 60), width=1)
            pill_padding_x = 10
            pill_padding_y = 4
            pill_w = tw + pill_padding_x * 2
            pill_h = th + pill_padding_y * 2
            pill_x = pad
            pill_y = divider_y + 6
            try:
                draw.rounded_rectangle(
                    [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                    radius=10,
                    fill=(255, 255, 255, 40),
                    outline=(255, 255, 255, 80),
                    width=1,
                )
            except Exception:
                draw.rectangle(
                    [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                    fill=(255, 255, 255, 40),
                    outline=(255, 255, 255, 80),
                    width=1,
                )
            text_x = pill_x + pill_padding_x
            text_y = pill_y + pill_padding_y
            draw.text((text_x + 1, text_y + 1), label, font=label_font, fill=(0, 0, 0, 160))
            draw.text((text_x, text_y), label, font=label_font, fill=(255, 255, 255, 230))
            y_cursor = pill_y + pill_h + pad

            cat_items = grouped[src]
            for idx, entry in enumerate(cat_items):
                r = idx // cols
                c = idx % cols
                x0 = pad + c * (cell + pad)
                y0 = y_cursor + r * (cell + pad)
                draw_card_at(x0, y0, entry[0], entry[1], entry[5] if entry[5] else entry[4])
            rows_used = math.ceil(len(cat_items) / cols)
            y_cursor += rows_used * (cell + pad)
            y_cursor += pad
    else:
        for idx, (img, bg_color, name, rarity, source, category) in enumerate(icons):
            r = idx // cols
            c = idx % cols
            x0 = pad + c * (cell + pad)
            y0 = title_height + pad + r * (cell + pad)
            draw_card_at(x0, y0, img, bg_color, category or source)

    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{dataset_name}_{timestamp}.png"
    output_path = os.path.join(save_dir, filename)
    canvas.convert("RGB").save(output_path)
    return True, output_path, missing


def build_ui(root, items, all_rarities, sources, icon_dir, save_dir, dataset_default, title_default, subtitle_default):
    root.title("Loot Selector")
    root.geometry("1150x820")

    top_controls = ttk.Frame(root, padding=(6, 4))
    top_controls.pack(fill=tk.X)

    rarity_label = ttk.Label(top_controls, text="レアリティ:")
    rarity_label.pack(side=tk.LEFT)

    rarity_vars = {}

    source_label = ttk.Label(top_controls, text="  ソース:")
    source_label.pack(side=tk.LEFT, padx=(8, 0))

    source_var = tk.StringVar(value="すべて")
    source_combo = ttk.Combobox(
        top_controls,
        textvariable=source_var,
        state="readonly",
        values=["すべて"] + sources,
        width=24,
    )
    source_combo.pack(side=tk.LEFT, padx=(2, 8))

    ttk.Button(top_controls, text="全選択", command=lambda: select_all(True)).pack(
        side=tk.LEFT, padx=(4, 4)
    )
    ttk.Button(top_controls, text="全解除", command=lambda: select_all(False)).pack(
        side=tk.LEFT, padx=(2, 8)
    )

    search_var = tk.StringVar()
    ttk.Label(top_controls, text="検索:").pack(side=tk.LEFT, padx=(6, 2))
    search_entry = ttk.Entry(top_controls, textvariable=search_var, width=24)
    search_entry.pack(side=tk.LEFT, padx=(2, 4))
    ttk.Button(top_controls, text="クリア", command=lambda: clear_search()).pack(
        side=tk.LEFT, padx=(2, 4)
    )

    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Left: scrollable checkbox list
    left_frame = ttk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(left_frame, borderwidth=0)
    scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)

    def on_frame_configure(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    scroll_frame.bind("<Configure>", on_frame_configure)
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_mousewheel(event):
        delta = 0
        if event.delta:
            delta = -1 * int(event.delta / 120)
        elif event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        if delta:
            canvas.yview_scroll(delta * 3, "units")

    # Scroll only when pointer is over the list, to avoid combobox operations scrolling the list unintentionally.
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    canvas.bind("<Button-4>", _on_mousewheel)
    canvas.bind("<Button-5>", _on_mousewheel)

    # Right: controls + selected display
    right_frame = ttk.Frame(main_frame, padding=4)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    paths_frame = ttk.LabelFrame(right_frame, text="パス・出力設定")
    paths_frame.pack(fill=tk.X, padx=4, pady=4)

    tk.Label(paths_frame, text="アイコンフォルダ").grid(row=0, column=0, sticky="w")
    icon_dir_var = tk.StringVar(value=icon_dir)
    tk.Entry(paths_frame, textvariable=icon_dir_var, width=60).grid(
        row=0, column=1, sticky="we", padx=4, pady=2
    )

    tk.Label(paths_frame, text="保存フォルダ").grid(row=1, column=0, sticky="w")
    save_dir_var = tk.StringVar(value=save_dir)
    tk.Entry(paths_frame, textvariable=save_dir_var, width=60, state="disabled").grid(
        row=1, column=1, sticky="we", padx=4, pady=2
    )

    show_category_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        paths_frame,
        text="カテゴリ名 (LootNumber_x) を画像に表示",
        variable=show_category_var,
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=2, pady=2)

    tk.Label(paths_frame, text="データセット").grid(row=3, column=0, sticky="w")
    dataset_var = tk.StringVar(value=dataset_default)
    ttk.Combobox(
        paths_frame,
        textvariable=dataset_var,
        state="readonly",
        values=DATASET_CHOICES,
        width=20,
    ).grid(row=3, column=1, sticky="w", padx=4, pady=2)

    tk.Label(paths_frame, text="タイトル").grid(row=4, column=0, sticky="w")
    title_var = tk.StringVar(value=title_default)
    tk.Entry(paths_frame, textvariable=title_var, width=60).grid(
        row=4, column=1, sticky="we", padx=4, pady=2
    )

    tk.Label(paths_frame, text="サブタイトル").grid(row=5, column=0, sticky="w")
    subtitle_var = tk.StringVar(value=subtitle_default)
    tk.Entry(paths_frame, textvariable=subtitle_var, width=60).grid(
        row=5, column=1, sticky="we", padx=4, pady=2
    )

    filename_hint = ttk.Label(paths_frame, text="保存名: <データセット>_YYYY-MM-DD_HH-MM.png")
    filename_hint.grid(row=6, column=0, columnspan=2, sticky="w", padx=2, pady=(6, 2))

    paths_frame.columnconfigure(1, weight=1)

    gen_button = ttk.Button(
        right_frame,
        text="画像出力 (表示中かつ選択のみ)",
        command=lambda: do_generate(
            icon_dir_var.get(),
            save_dir_var.get(),
            dataset_var.get(),
            title_var.get(),
            subtitle_var.get(),
            show_category_var.get(),
        ),
    )
    gen_button.pack(fill=tk.X, padx=4, pady=(4, 0))

    result_label = ttk.Label(right_frame, text="選択結果")
    result_label.pack(anchor="w", padx=4, pady=(8, 0))

    result_list_frame = ttk.Frame(right_frame)
    result_list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    result_scroll = ttk.Scrollbar(result_list_frame, orient="vertical")
    result_list = tk.Listbox(result_list_frame, yscrollcommand=result_scroll.set, selectmode="extended")
    result_scroll.config(command=result_list.yview)
    result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    result_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Drag-and-drop reorder for result list
    result_drag = {"sel_indices": None}

    def result_start_drag(event):
        if result_list.size() == 0:
            return
        selection = list(result_list.curselection())
        if not selection:
            selection = [result_list.nearest(event.y)]
        result_drag["sel_indices"] = selection

    def result_end_drag(event):
        sel_indices = result_drag.get("sel_indices")
        result_drag["sel_indices"] = None
        if not sel_indices or result_list.size() == 0:
            return

        dst_idx = result_list.nearest(event.y)
        if dst_idx < 0:
            dst_idx = 0
        if dst_idx >= result_list.size():
            dst_idx = result_list.size() - 1

        # Map listbox indices -> item_widgets indices (only selected & visible)
        visible_selected = [
            idx for idx, (_n, _r, _s, _c, var, frame) in enumerate(item_widgets)
            if frame.winfo_ismapped() and var.get()
        ]
        if not visible_selected:
            return
        sel_indices_sorted = sorted(set(sel_indices))
        try:
            moving_widget_indices = [visible_selected[i] for i in sel_indices_sorted]
            dest_widget_idx = visible_selected[dst_idx]
        except IndexError:
            return

        # Extract moving entries preserving order
        moving_entries = [item_widgets[i] for i in moving_widget_indices]
        # Remove from item_widgets (descending to keep indices valid)
        for i in sorted(moving_widget_indices, reverse=True):
            item_widgets.pop(i)

        # Adjust destination after removals
        shift = sum(1 for i in moving_widget_indices if i < dest_widget_idx)
        dest_widget_idx -= shift

        # Insert block
        for offset, entry in enumerate(moving_entries):
            item_widgets.insert(dest_widget_idx + offset, entry)

        apply_filter()

    result_list.bind("<Button-1>", result_start_drag)
    result_list.bind("<ButtonRelease-1>", result_end_drag)

    item_widgets = []  # (name, rarity, source, category, var, frame)

    def update_result():
        result_list.delete(0, tk.END)
        for name, rarity, source, category, var, frame in item_widgets:
            if frame.winfo_ismapped() and var.get():
                result_list.insert(tk.END, f"{name} ({rarity})")

    def select_all(state):
        for _, _, _, _, var, frame in item_widgets:
            if frame.winfo_ismapped():
                var.set(state)
        update_result()

    def apply_filter(*_args):
        active_rarities = {r for r, var in rarity_vars.items() if var.get()}
        active_source = source_var.get()
        keyword = search_var.get().strip().lower()
        show_all_rarity = bool(active_rarities)
        seen_pairs = set()  # (name, rarity) to avoid duplicates when source == "すべて"
        for name, rarity, source, category, _, frame in item_widgets:
            show_rarity = rarity in active_rarities if show_all_rarity else False
            show_source = active_source == "すべて" or source == active_source
            show_keyword = keyword in name.lower()
            show = show_rarity and show_source and show_keyword
            if show and active_source == "すべて":
                key = (name, rarity)
                if key in seen_pairs:
                    show = False
                else:
                    seen_pairs.add(key)
            if show:
                if not frame.winfo_ismapped():
                    frame.pack(anchor="w", padx=4, pady=2, fill=tk.X)
            else:
                if frame.winfo_ismapped():
                    frame.pack_forget()
        on_frame_configure()
        update_result()

    # Drag & drop reorder (visible items only)
    drag_state = {"frame": None}

    def start_drag(event, frame):
        drag_state["frame"] = frame

    def end_drag(event):
        frame = drag_state.get("frame")
        if frame is None:
            return
        drag_state["frame"] = None
        # Build visible list with indices
        visible = []
        for idx, entry in enumerate(item_widgets):
            if entry[-1].winfo_ismapped():
                visible.append((idx, entry[-1]))
        if not visible:
            return
        # Find target index by comparing cursor y to frame centers
        y_root = event.y_root
        target_idx = None
        min_dist = None
        for idx, f in visible:
            cy = f.winfo_rooty() + f.winfo_height() / 2
            dist = abs(y_root - cy)
            if min_dist is None or dist < min_dist:
                min_dist = dist
                target_idx = idx
        # Source index
        src_idx = next((i for i, entry in enumerate(item_widgets) if entry[-1] is frame), None)
        if src_idx is None or target_idx is None or src_idx == target_idx:
            return
        entry = item_widgets.pop(src_idx)
        # Adjust target if popping before
        if src_idx < target_idx:
            target_idx -= 1
        item_widgets.insert(target_idx, entry)
        apply_filter()

    def clear_search():
        search_var.set("")
        apply_filter()

    def do_generate(icon_dir_path, save_dir_path, dataset_name, title_text, subtitle_text, show_category):
        selected = [
            (name, rarity, source, category)
            for name, rarity, source, category, var, frame in item_widgets
            if frame.winfo_ismapped() and var.get()
        ]
        if not selected:
            messagebox.showinfo("なし", "出力対象の選択がありません。")
            return
        ok, output_path, missing = generate_image(
            selected, icon_dir_path, save_dir_path, dataset_name, title_text, subtitle_text, show_category
        )
        if ok:
            msg = "画像を出力しました: " + output_path
            if missing:
                msg += "\n\n見つからなかったアイコン:\n" + "\n".join(missing)
            messagebox.showinfo("完了", msg)
        else:
            messagebox.showerror("失敗", "画像生成に失敗しました:\n" + "\n".join(missing))

    for rarity in all_rarities:
        var = tk.BooleanVar(value=True)
        rarity_vars[rarity] = var
        cb = ttk.Checkbutton(
            top_controls, text=rarity, variable=var, command=apply_filter
        )
        cb.pack(side=tk.LEFT, padx=(2, 2))

    source_combo.bind("<<ComboboxSelected>>", apply_filter)
    search_entry.bind("<KeyRelease>", apply_filter)

    for name, rarity, source, category in items:
        var = tk.BooleanVar()
        frame = ttk.Frame(scroll_frame)
        cb = ttk.Checkbutton(
            frame,
            text=f"{name} ({rarity})",
            variable=var,
            command=update_result,
        )
        cb.pack(anchor="w", fill=tk.X)
        frame.pack(anchor="w", padx=4, pady=2, fill=tk.X)
        frame.bind("<Button-1>", lambda e, f=frame: start_drag(e, f))
        frame.bind("<ButtonRelease-1>", lambda e: end_drag(e))
        cb.bind("<Button-1>", lambda e, f=frame: start_drag(e, f))
        cb.bind("<ButtonRelease-1>", lambda e: end_drag(e))
        item_widgets.append((name, rarity, source, category, var, frame))

    apply_filter()


if __name__ == "__main__":
    json_path = DEFAULT_JSON_PATH
    icon_dir = DEFAULT_ICON_DIR
    save_dir = DEFAULT_SAVE_DIR
    dataset_name = DATASET_CHOICES[0]
    title_text = DEFAULT_TITLE
    subtitle_text = DEFAULT_SUBTITLE
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    if len(sys.argv) > 2:
        icon_dir = sys.argv[2]
    if len(sys.argv) > 3:
        save_dir = sys.argv[3]
    if len(sys.argv) > 4:
        dataset_name = sys.argv[4]
    if len(sys.argv) > 5:
        title_text = sys.argv[5]
    if len(sys.argv) > 6:
        subtitle_text = sys.argv[6]
    if not os.path.exists(json_path):
        print(f"JSON file not found: {json_path}")
        sys.exit(1)
    items, rarities, sources, _categories = load_items(json_path)
    root = tk.Tk()
    build_ui(root, items, rarities, sources, icon_dir, save_dir, dataset_name, title_text, subtitle_text)
    root.mainloop()

