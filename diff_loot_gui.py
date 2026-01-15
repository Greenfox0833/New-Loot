import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from diff_loot import diff_items, load_json, normalize_items


JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(r"E:\フォートナイト\Web\assets\data\Loot\diff")

MODE_DIRS = {
    "BR": BASE_DIR / "戦利品データ" / "BR" / "LootPercent",
    "Reload": BASE_DIR / "戦利品データ" / "Reload" / "LootPercent",
    "ORIGIN (Figment)": BASE_DIR / "戦利品データ" / "Figment" / "LootPercent",
    "Blitz (ForbiddenFruit)": BASE_DIR / "戦利品データ" / "ForbiddenFruit" / "LootPercent",
}
MODE_OUTPUT_NAMES = {
    "BR": "BR",
    "Reload": "Reload",
    "ORIGIN (Figment)": "ORIGIN",
    "Blitz (ForbiddenFruit)": "Blitz",
}


def latest_two_files(folder: Path) -> tuple[Path, Path]:
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) < 2:
        raise FileNotFoundError("JSON files are less than 2 in the selected folder.")
    return files[1], files[0]


def build_output_path(mode_key: str) -> Path:
    mode_name = MODE_OUTPUT_NAMES.get(mode_key, mode_key)
    timestamp = datetime.now(JST).strftime("%Y-%m-%d_%H-%M-%S")
    name = f"{mode_name}_{timestamp}.json"
    return OUTPUT_DIR / name


def run_diff(mode_key: str) -> tuple[Path, dict]:
    folder = MODE_DIRS[mode_key]
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")
    old_file, new_file = latest_two_files(folder)

    old_data = load_json(old_file)
    new_data = load_json(new_file)
    old_items = normalize_items(old_data)
    new_items = normalize_items(new_data)

    diff = diff_items(old_items, new_items)
    diff["generatedAt"] = datetime.now(JST).isoformat(timespec="seconds")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = build_output_path(mode_key)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    return out_path, diff


def on_run(mode_var: tk.StringVar, status_var: tk.StringVar) -> None:
    try:
        mode = mode_var.get()
        out_path, diff = run_diff(mode)
        status_var.set(
            f"OK: {mode} added={len(diff['added'])} removed={len(diff['removed'])} "
            f"change={len(diff['change'])}"
        )
        messagebox.showinfo("Diff Completed", f"Saved: {out_path}")
    except Exception as exc:
        status_var.set("ERROR")
        messagebox.showerror("Diff Failed", str(exc))


def main() -> None:
    root = tk.Tk()
    root.title("Loot Diff")
    root.geometry("520x180")

    mode_var = tk.StringVar(value="BR")
    status_var = tk.StringVar(value="Ready")

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Mode").grid(row=0, column=0, sticky="w")
    mode_box = ttk.Combobox(frame, textvariable=mode_var, state="readonly")
    mode_box["values"] = list(MODE_DIRS.keys())
    mode_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    run_button = ttk.Button(frame, text="Run Diff", command=lambda: on_run(mode_var, status_var))
    run_button.grid(row=1, column=0, columnspan=2, pady=(12, 0), sticky="ew")

    ttk.Label(frame, textvariable=status_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    frame.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    main()
