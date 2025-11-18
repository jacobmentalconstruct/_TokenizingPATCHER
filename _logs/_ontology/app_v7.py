# This ia a placeholder test application.
# It currently contains nothing.

import tkinter as tk
import os, datetime
from tkinter import ttk

# ==============================
# Global Config
# ==============================
OUTPUT_DIR = "./"
LOG_DIR = "./logs/"
LOG_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_OUTPUT_FILENAME = "patched_output.txt"
DEBUG_EXPANDED_BY_DEFAULT = True
# ==============================

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Tooltip helper class
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#3b4252",
            foreground="#eee",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=4, ipady=2)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
from tkinter import filedialog, scrolledtext

def create_gui():
    root = tk.Tk()
    root.title("Sturdy Patcher - Tkinter Prototype v2")
    root.geometry("900x700")

    # Dark theme to match the Sturdy Patcher web app
    root.configure(bg="#020617")  # near Tailwind slate-950
    root.option_add("*Background", "#020617")
    root.option_add("*Foreground", "#e5e7eb")
    root.option_add("*Button.Background", "#4f46e5")
    root.option_add("*Button.Foreground", "#f9fafb")
    root.option_add("*Entry.Background", "#020617")
    root.option_add("*Entry.Foreground", "#e5e7eb")

# --- HEADER ---
    header = tk.Label(root, text="Sturdy Patcher – Desktop Prototype", font=("Helvetica", 18, "bold"), bg="#020617", fg="#e5e7eb")
    header.pack(pady=10)

    # Output filename row
    filename_frame = tk.Frame(root, bg="#020617")
    filename_frame.pack(fill='x', padx=10, pady=5)

    tk.Label(filename_frame, text="Output File Name:", bg="#020617", fg="#e5e7eb").pack(side='left')
    output_name_var = tk.StringVar(value=DEFAULT_OUTPUT_FILENAME)
    output_name_entry = tk.Entry(filename_frame, textvariable=output_name_var, width=40)
    output_name_entry.pack(side='left', padx=10)
    Tooltip(output_name_entry, "Name of the patched output file.")

    # Toolbar buttons row
    toolbar = tk.Frame(root, bg="#020617")
    toolbar.pack(fill='x', padx=10, pady=5)

    btn_load = tk.Button(toolbar, text="Load File")
    btn_load.pack(side='left', padx=5)
    Tooltip(btn_load, "Load a file into the left editor.")

    btn_save = tk.Button(toolbar, text="Save Patched File")
    btn_save.pack(side='left', padx=5)
    Tooltip(btn_save, "Save patched file next to original using version fingerprint.")

    btn_clear = tk.Button(toolbar, text="Clear All")
    btn_clear.pack(side='left', padx=5)
    Tooltip(btn_clear, "Clear all text areas.")

    debug_toggle_btn = tk.Button(toolbar, text="Debug: ON")
    debug_toggle_btn.pack(side='left', padx=5)
    Tooltip(debug_toggle_btn, "Toggle debug mode.")
    header = tk.Label(
        root,
        text="Sturdy Patcher Prototype",
        font=("Helvetica", 18, "bold"),
        bg="#020617",
        fg="#e5e7eb"
    )
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

# Paned window for left/right layout
    paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RIDGE, bg="#020617")
    paned.pack(fill='both', expand=True, padx=10, pady=10)

    # Left panel
    left_frame = tk.Frame(paned, bg="#020617")
    tk.Label(left_frame, text="Original File (Paste or Upload):", bg="#020617", fg="#e5e7eb").pack(anchor='w')
    file_preview = scrolledtext.ScrolledText(left_frame, wrap=tk.NONE, height=20, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    file_preview.pack(fill='both', expand=True)
    Tooltip(file_preview, "This shows the full contents of the loaded file.")
    paned.add(left_frame)

    # Right panel
    right_frame = tk.Frame(paned, bg="#020617")
    tk.Label(right_frame, text="Patch JSON Payload:", bg="#020617", fg="#e5e7eb").pack(anchor='w')
    patch_entry = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, height=20, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    patch_entry.pack(fill='both', expand=True)
    Tooltip(patch_entry, "Paste your patch JSON here.")
    paned.add(right_frame)
    file_preview = scrolledtext.ScrolledText(
        root,
        wrap=tk.NONE,
        height=20,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#1f2937"
    )
    file_preview.pack(fill="both", expand=True, padx=10, pady=10)

    # --- PATCH INPUT AREA ---
    patch_lbl = tk.Label(root, text="Patch JSON:")
    patch_lbl.pack(pady=(0, 5))

    patch_entry = scrolledtext.ScrolledText(
        root,
        wrap=tk.NONE,
        height=10,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#1f2937"
    )
    patch_entry.pack(fill="both", expand=False, padx=10)

# --- APPLY BUTTON (centered) ---
    apply_frame = tk.Frame(root, bg="#020617")
    apply_frame.pack(pady=10)

    btn_apply = tk.Button(apply_frame, text="Validate and Apply Patch", font=("Helvetica", 12, "bold"), bg="#22c55e", fg="black", padx=20, pady=5)
    btn_apply.pack()
    Tooltip(btn_apply, "Validate and apply the patch to the loaded file.")
    def apply_patch_stub():
        status_lbl.config(text="Patch Applied (Stub)", fg="yellow")

    btn_apply = tk.Button(root, text="Apply Patch", command=apply_patch_stub)
    btn_apply.pack(pady=10)

# Debug Output Header
    debug_header = tk.Frame(root, bg="#020617")
    debug_header.pack(fill='x', padx=10, pady=(5,0))

    tk.Label(debug_header, text="Debug Output:", bg="#020617", fg="#e5e7eb").pack(side='left')

    # Collapse/Expand button
    debug_toggle = tk.Button(debug_header, text="▲", font=("Helvetica", 10, "bold"))
    debug_toggle.pack(side='right', padx=5)
    Tooltip(debug_toggle, "Show or hide debug panel.")

    # Save Log button
    save_log_btn = tk.Button(debug_header, text="↓", font=("Helvetica", 10, "bold"))
    save_log_btn.pack(side='right', padx=5)
    Tooltip(save_log_btn, "Save debug output to log file.")

    # Debug content panel
    debug_panel = tk.Frame(root, bg="#020617")
    debug_panel.pack(fill='both', expand=False, padx=10, pady=5)

    debug_output = scrolledtext.ScrolledText(debug_panel, wrap=tk.NONE, height=10, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    debug_output.pack(fill='both', expand=True)
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