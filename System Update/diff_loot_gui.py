import tkinter as tk
from tkinter import messagebox, ttk

from diff_loot_auto import run_latest_diff


MODE_LABEL_TO_KEY = {
    "BR": "BR",
    "BR_Comp": "BR_Comp",
    "Reload_Ranked": "Reload_Ranked",
    "Reload_NoBuild_Ranked": "Reload_NoBuild_Ranked",
    "ORIGIN (Figment)": "Figment",
    "Figment_NoBuild": "Figment_NoBuild",
    "Blitz (ForbiddenFruit)": "ForbiddenFruit",
    "NoBuild": "NoBuild",
    "NoBuild_Comp": "NoBuild_Comp",
}


def on_run(mode_var: tk.StringVar, status_var: tk.StringVar) -> None:
    try:
        label = mode_var.get()
        mode_key = MODE_LABEL_TO_KEY[label]
        result = run_latest_diff(mode_key)
        if result is None:
            status_var.set(f"OK: {label} no changes")
            messagebox.showinfo("Diff Skipped", "No changes detected. Output not created.")
            return
        out_path, diff = result
        status_var.set(
            f"OK: {label} added={len(diff['added'])} removed={len(diff['removed'])} "
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
    mode_box["values"] = list(MODE_LABEL_TO_KEY.keys())
    mode_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    run_button = ttk.Button(frame, text="Run Diff", command=lambda: on_run(mode_var, status_var))
    run_button.grid(row=1, column=0, columnspan=2, pady=(12, 0), sticky="ew")

    ttk.Label(frame, textvariable=status_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    frame.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    main()


