# This ia a placeholder test application.
# It currently contains nothing.

import tkinter as tk
from tkinter import filedialog, scrolledtext

def create_gui():
    root = tk.Tk()
    root.title("Sturdy Patcher - Tkinter Prototype v2")
    root.geometry("900x700")

# --- HEADER ---
header = tk.Label(root, text="Sturdy Patcher Prototype – Whitespace Drift Test", font=("Helvetica", 18, "bold"))
header.pack(pady=10)

# --- FILE LOAD ---
load_frame = tk.Frame(root)
load_frame.pack(fill="x", padx=10)

def load_file():
    filepath = filedialog.askopenfilename()
    if not filepath:
        return
    with open(filepath, "r", encoding="utf-8") as f:
        file_preview.delete(1.0, tk.END)
        file_preview.insert(tk.END, f.read())
    status_lbl.config(text=f"Loaded: {filepath}")

btn_load = tk.Button(load_frame, text="Load File", command=load_file)
btn_load.pack(side="left")

# --- FILE PREVIEW ---
file_preview = scrolledtext.ScrolledText(root, wrap=tk.NONE, height=20)
file_preview.pack(fill="both", expand=True, padx=10, pady=10)

# --- PATCH INPUT AREA ---
patch_lbl = tk.Label(root, text="Patch JSON:")
patch_lbl.pack(pady=(0, 5))

patch_entry = scrolledtext.ScrolledText(root, wrap=tk.NONE, height=10)
patch_entry.pack(fill="both", expand=False, padx=10)

# --- APPLY BUTTON ---
def apply_patch_stub():
    status_lbl.config(text="Patch Applied (Stub)", fg="yellow")

btn_apply = tk.Button(root, text="Apply Patch", command=apply_patch_stub)
btn_apply.pack(pady=10)

# --- STATUS ---
status_lbl = tk.Label(root, text="Ready", fg="green")
status_lbl.pack(pady=5)

footer = tk.Label(root, text="Sturdy Patcher v2 – Multi-Hunk Test", fg="gray")
footer.pack(pady=4)

# Keyboard shortcuts
root.bind("<Control-o>", lambda e: load_file())
root.bind("<Control-p>", lambda e: apply_patch_stub())

root.mainloop()


if __name__ == "__main__":
    create_gui()