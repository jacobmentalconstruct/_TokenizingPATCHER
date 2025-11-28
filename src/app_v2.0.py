# Sturdy Patcher – Tkinter Version
# Single-file hunk patcher for one target buffer.

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import os
import datetime
import json
import re

# ==============================
# Global Config
# ==============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "./")
LOG_DIR = os.path.join(SCRIPT_DIR, "./logs/")
LOG_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_OUTPUT_FILENAME = "patched_output.txt"
DEBUG_EXPANDED_BY_DEFAULT = True
# ==============================

os.makedirs(LOG_DIR, exist_ok=True)

PATCH_SCHEMA = """{
  "hunks": [
    {
      "description": "Short human description",
      "search_block": "exact text to find\\n(can span multiple lines)",
      "replace_block": "replacement text\\n(same or different length)"
    }
  ]
}"""


class PatchError(Exception):
    pass


class StructuredLine:
    """
    Represents a line of text tokenized into its structural parts.
    <indent><content><trailing>
    """
    def __init__(self, line: str):
        self.original_line = line
        match = re.match(r"(^[ \t]*)(.*?)([ \t]*$)", line)
        if match:
            self.indent = match.group(1)
            self.content = match.group(2)
            self.trailing = match.group(3)
        else:
            self.indent = ""
            self.content = line
            self.trailing = ""

    def reconstruct(self) -> str:
        return f"{self.indent}{self.content}{self.trailing}"

    def __repr__(self):
        return f"[L: '{self.indent}' | '{self.content}' | '{self.trailing}']"


def detect_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    return "\n"


def split_lines_preserve(text: str, newline: str):
    if text == "":
        return [""]
    return text.split(newline)


def locate_hunk(file_lines: list[StructuredLine], 
                search_lines: list[StructuredLine], 
                floating: bool):
    matches = []
    if not search_lines:
        return matches

    window = len(search_lines)
    max_start = len(file_lines) - window
    if max_start < 0:
        return matches

    for start in range(max_start + 1):
        ok = True
        for offset, s_line in enumerate(search_lines):
            f_line = file_lines[start + offset]
            f_content = f_line.content
            s_content = s_line.content
            
            if floating:
                f_content = f_content.strip()
                s_content = s_content.strip()

            if f_content != s_content:
                ok = False
                break
        if ok:
            matches.append(start)

    return matches


def check_overlaps(applications):
    if not applications:
        return False

    sorted_apps = sorted(applications, key=lambda a: a["start"])
    for prev, cur in zip(sorted_apps, sorted_apps[1:]):
        if prev["end"] > cur["start"]:
            return True
    return False


def apply_patch_text(file_text: str, patch_obj: dict, log_fn=None) -> str:
    def log(msg: str):
        if log_fn is not None:
            log_fn(msg)

    newline = detect_newline(file_text)
    file_lines_str = split_lines_preserve(file_text, newline)
    file_lines = [StructuredLine(line) for line in file_lines_str]

    hunks = patch_obj.get("hunks")
    if not isinstance(hunks, list):
        raise PatchError("Patch JSON must contain a 'hunks' array.")

    applications = []

    for idx, h in enumerate(hunks):
        num = idx + 1
        desc = h.get("description") or "(no description)"
        log(f"Hunk {num}: {desc}")

        search_block = h.get("search_block")
        replace_block = h.get("replace_block")

        if not isinstance(search_block, str) or not isinstance(replace_block, str):
            raise PatchError(f"Hunk {num} is missing search_block or replace_block.")

        search_lines_str = re.split(r"\r\n|\n", search_block)
        search_lines = [StructuredLine(line) for line in search_lines_str]
        
        replace_lines_str = re.split(r"\r\n|\n", replace_block)
        replace_lines = [StructuredLine(line) for line in replace_lines_str]

        strict_matches = locate_hunk(file_lines, search_lines, floating=False)
        if len(strict_matches) > 1:
            raise PatchError(f"Ambiguous strict match for hunk {num}.")
        
        start_end = None
        if len(strict_matches) == 1:
            start = strict_matches[0]
            end = start + len(search_lines)
            start_end = (start, end)
            log(f"Strict match at lines {start + 1}–{end}")
        else:
            float_matches = locate_hunk(file_lines, search_lines, floating=True)
            if len(float_matches) > 1:
                raise PatchError(f"Ambiguous floating match for hunk {num}.")
            if len(float_matches) == 0:
                raise PatchError(f"Hunk {num} not found in file.")
            
            start = float_matches[0]
            end = start + len(search_lines)
            start_end = (start, end)
            log(f"Floating match at lines {start + 1}–{end}")

        applications.append(
            {"start": start_end[0], "end": start_end[1], "replace_lines": replace_lines}
        )

    if check_overlaps(applications):
        raise PatchError("Overlapping hunks detected. Patch aborted.")

    for app in sorted(applications, key=lambda a: a["start"], reverse=True):
        start = app["start"]
        end = app["end"]
        replace_lines_tokenized = app["replace_lines"]
        
        indent_to_inherit = ""
        if start < len(file_lines):
            indent_to_inherit = file_lines[start].indent

        new_structured_lines = []
        for i, replace_line in enumerate(replace_lines_tokenized):
            if (start + i) < end:
                original_line = file_lines[start + i]
                original_line.content = replace_line.content
                new_structured_lines.append(original_line)
            else:
                replace_line.indent = indent_to_inherit
                new_structured_lines.append(replace_line)
        
        file_lines[start:end] = new_structured_lines

    final_lines_str = [line.reconstruct() for line in file_lines]
    return newline.join(final_lines_str)


class Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow is not None:
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
            font=("Segoe UI", 9),
        )
        label.pack(ipadx=4, ipady=2)

    def hide_tip(self, event=None):
        if self.tipwindow is not None:
            self.tipwindow.destroy()
            self.tipwindow = None


def create_gui():
    root = tk.Tk()
    root.title("Sturdy Patcher – Desktop Prototype")
    root.geometry("1000x750")

    root.configure(bg="#020617")
    root.option_add("*Background", "#020617")
    root.option_add("*Foreground", "#e5e7eb")

    # ---------- Header ----------
    header = tk.Label(
        root,
        text="Sturdy Patcher",
        font=("Helvetica", 18, "bold"),
        bg="#020617",
        fg="#e5e7eb",
    )
    header.pack(pady=10)

    # ---------- Loaded file path row ----------
    filename_frame = tk.Frame(root, bg="#020617")
    filename_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(
        filename_frame,
        text="Loaded file path:",
        bg="#020617",
        fg="#e5e7eb",
    ).pack(side="left")
    
    output_name_var = tk.StringVar(value="")
    output_entry = tk.Entry(
        filename_frame,
        textvariable=output_name_var,
        state="readonly",
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        readonlybackground="#020617",
    )
    output_entry.pack(side="left", padx=8, fill="x", expand=True)
    Tooltip(output_entry, "Full path of the loaded file (read-only).")

    # ---------- Toolbar ----------
    toolbar = tk.Frame(root, bg="#020617")
    toolbar.pack(fill="x", padx=10, pady=(0, 5))

    btn_load = tk.Button(toolbar, text="Load File")
    btn_load.pack(side="left", padx=5)
    Tooltip(btn_load, "Load a file from disk into the left text area.")

    btn_save = tk.Button(toolbar, text="Save Patched File")
    btn_save.pack(side="left", padx=5)
    Tooltip(btn_save, "Save patched file next to original using version fingerprint.")

    # --- Versioning controls ---
    version_enabled_var = tk.BooleanVar(value=False)
    version_check = tk.Checkbutton(
        toolbar,
        text="Save as version",
        variable=version_enabled_var,
        bg="#020617",
        fg="#e5e7eb",
        selectcolor="#020617",
    )
    version_check.pack(side="left", padx=5)
    Tooltip(version_check, "Enable saving with a version suffix (e.g., _v1.0).")
    
    version_suffix_var = tk.StringVar(value="")
    version_entry = tk.Entry(
        toolbar,
        textvariable=version_suffix_var,
        width=10,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        state="disabled",
    )
    version_entry.pack(side="left", padx=5)
    Tooltip(version_entry, "Suffix to append to the file name, starting with '_' (e.g., _v1.0).")
    
    # Toggle logic for version entry
    def _toggle_version_entry(*args):
        if version_enabled_var.get():
            version_entry.config(state="normal")
        else:
            version_entry.config(state="disabled")
    
    version_enabled_var.trace_add("write", _toggle_version_entry)

    btn_clear = tk.Button(toolbar, text="Clear All")
    btn_clear.pack(side="left", padx=5)
    Tooltip(btn_clear, "Clear all text areas.")

    # ---------- Main Paned Window ----------
    paned = tk.PanedWindow(
        root,
        orient=tk.HORIZONTAL,
        sashrelief=tk.RAISED,
        bg="#020617",
        sashwidth=4,
    )
    paned.pack(fill="both", expand=True, padx=10, pady=5)

    # Left: original file
    left_frame = tk.Frame(paned, bg="#020617")
    tk.Label(
        left_frame,
        text="Original File (Paste or Load):",
        bg="#020617",
        fg="#e5e7eb",
    ).pack(anchor="w")
    file_preview = scrolledtext.ScrolledText(
        left_frame,
        wrap=tk.NONE,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#1f2937",
    )
    file_preview.pack(fill="both", expand=True)
    Tooltip(file_preview, "Paste or load the original file content here.")
    paned.add(left_frame)

    # Right: patch JSON + schema button
    right_frame = tk.Frame(paned, bg="#020617")
    patch_header = tk.Frame(right_frame, bg="#020617")
    patch_header.pack(fill="x")

    tk.Label(
        patch_header,
        text="Patch JSON Payload:",
        bg="#020617",
        fg="#e5e7eb",
    ).pack(side="left")

    schema_btn = tk.Button(patch_header, text="Schema", font=("Helvetica", 9))
    schema_btn.pack(side="right", padx=5)
    Tooltip(schema_btn, "Insert the canonical patch JSON schema.")

    patch_entry = scrolledtext.ScrolledText(
        right_frame,
        wrap=tk.NONE,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#1f2937",
    )
    patch_entry.pack(fill="both", expand=True)
    Tooltip(patch_entry, "Paste your patch JSON here.")
    
    # --- Placeholder Logic ---
    placeholder_color = "#6b7280" # A dim gray
    default_fg_color = "#e5e7eb"

    def on_patch_focus_in(event):
        if patch_entry.get("1.0", tk.END).strip() == PATCH_SCHEMA:
            patch_entry.delete("1.0", tk.END)
            patch_entry.config(fg=default_fg_color)

    def on_patch_focus_out(event):
        if not patch_entry.get("1.0", tk.END).strip():
            patch_entry.insert("1.0", PATCH_SCHEMA)
            patch_entry.config(fg=placeholder_color)
            
    patch_entry.insert("1.0", PATCH_SCHEMA)
    patch_entry.config(fg=placeholder_color)
    patch_entry.bind("<FocusIn>", on_patch_focus_in)
    patch_entry.bind("<FocusOut>", on_patch_focus_out)
    # --- End Placeholder Logic ---

    paned.add(right_frame)

    # ---------- Apply button ----------
    apply_frame = tk.Frame(root, bg="#020617")
    apply_frame.pack(pady=10, fill="x", padx=10)

    btn_apply = tk.Button(
        apply_frame,
        text="Validate & Apply",
        font=("Helvetica", 12, "bold"),
        bg="#22c55e",
        fg="black",
        padx=20,
        pady=5,
    )
    btn_apply.pack(side="right")
    Tooltip(btn_apply, "Validate the patch JSON and apply to the loaded file.")

    # ---------- Debug + Status ----------
    debug_header = tk.Frame(root, bg="#020617")
    debug_header.pack(fill="x", padx=10, pady=(5, 0))

    tk.Label(
        debug_header,
        text="Debug Output:",
        bg="#020617",
        fg="#e5e7eb",
    ).pack(side="left")

    save_log_btn = tk.Button(debug_header, text="↓", font=("Helvetica", 10, "bold"))
    save_log_btn.pack(side="right", padx=5)
    Tooltip(save_log_btn, "Save debug output to log file.")

    debug_toggle = tk.Button(debug_header, text="▲", font=("Helvetica", 10, "bold"))
    debug_toggle.pack(side="right", padx=5)
    Tooltip(debug_toggle, "Show or hide debug panel.")

    debug_panel = tk.Frame(root, bg="#020617")
    debug_panel.pack(fill="both", expand=False, padx=10, pady=5)

    debug_output = scrolledtext.ScrolledText(
        debug_panel,
        wrap=tk.NONE,
        bg="#020617",
        fg="#e5e7eb",
        insertbackground="#e5e7eb",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground="#1f2937",
        height=10,
    )
    debug_output.pack(fill="both", expand=True)

    status_lbl = tk.Label(root, text="Ready", fg="green", bg="#020617")
    status_lbl.pack(pady=5)

    footer = tk.Label(
        root,
        text="Sturdy Patcher – Python Edition",
        fg="gray",
        bg="#020617",
    )
    footer.pack(pady=4)

    # ---------- State + helpers ----------
    debug_enabled = tk.BooleanVar(value=True)
    debug_collapsed = tk.BooleanVar(value=not DEBUG_EXPANDED_BY_DEFAULT)

    # -------------------------------------------------------
    # INTERNAL FUNCTIONS (All indented inside create_gui now)
    # -------------------------------------------------------

    def log(msg: str):
        if not debug_enabled.get():
            return
        debug_output.insert(tk.END, msg + "\n")
        debug_output.see(tk.END)

    def set_status(msg: str, is_error: bool = False):
        status_lbl.config(text=msg, fg=("red" if is_error else "green"))
        prefix = "ERROR: " if is_error else ""
        log(prefix + msg)

    def clear_all():
        file_preview.delete("1.0", tk.END)
        patch_entry.delete("1.0", tk.END)
        debug_output.delete("1.0", tk.END)
        
        # Reset the loaded file path and displayed path
        output_name_var.set("")
        # Use getattr/setattr on root to store state safely
        root.loaded_filepath = None
        
        # Reset versioning controls
        version_enabled_var.set(False)
        version_suffix_var.set("")
        
        # Restore placeholder
        on_patch_focus_out(None)
        set_status("Cleared", False)

    def toggle_debug_panel():
        if debug_collapsed.get():
            debug_panel.pack(fill="both", expand=False, padx=10, pady=5)
            debug_toggle.config(text="▲")
            debug_collapsed.set(False)
            log("Debug panel expanded")
        else:
            debug_panel.forget()
            debug_toggle.config(text="▼")
            debug_collapsed.set(True)
            log("Debug panel collapsed")

    def save_log_to_file():
        text = debug_output.get("1.0", tk.END)
        if not text.strip():
            set_status("Debug log is empty.", True)
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime(LOG_TIMESTAMP_FORMAT)
        name = f"sturdy_patcher_log_{stamp}.txt"
        path = os.path.join(LOG_DIR, name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            set_status(f"Debug log saved as {path}")
        except Exception as e:
            set_status(f"Failed to save debug log: {e}", True)

    def insert_schema():
        try:
            root.clipboard_clear()
            root.clipboard_append(PATCH_SCHEMA)
            set_status("Schema copied to clipboard")
        except Exception as e:
            set_status(f"Failed to copy schema: {e}", True)

    def _compute_default_version(path: str) -> str:
        base = os.path.splitext(os.path.basename(path))[0]
        dir_name = os.path.dirname(path) or "."
        max_major, max_minor = None, None
        
        pattern = re.compile(re.escape(base) + r"_v(\d+)\.(\d+)")
        
        try:
            for fn in os.listdir(dir_name):
                stem, _ext = os.path.splitext(fn)
                m = pattern.match(stem)
                if m:
                    major = int(m.group(1))
                    minor = int(m.group(2))
                    if (max_major is None) or (major > max_major) or (major == max_major and minor > max_minor):
                        max_major, max_minor = major, minor
        except Exception:
            return "_v0.0"

        if max_major is None:
            return "_v0.0"
        
        major, minor = max_major, max_minor + 1
        if minor >= 10:
            major += 1
            minor = 0
        
        return f"_v{major}.{minor}"

    def load_file():
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                file_preview.delete("1.0", tk.END)
                file_preview.insert(tk.END, f.read())
            
            root.loaded_filepath = filepath
            output_name_var.set(filepath)

            default_version = _compute_default_version(filepath)
            version_suffix_var.set(default_version)
            
            version_enabled_var.set(True)
        
            set_status(f"Loaded: {filepath}")
        except Exception as e:
            set_status(f"Failed to load file: {e}", True)

    def save_patched_file():
        text = file_preview.get("1.0", tk.END)
        
        out_path = None
        original_path = getattr(root, "loaded_filepath", None)
        
        if original_path:
            dir_name = os.path.dirname(original_path) or "."
            base_name, ext = os.path.splitext(os.path.basename(original_path))
            
            if version_enabled_var.get():
                suffix = version_suffix_var.get().strip()
                if suffix and not suffix.startswith("_"):
                    suffix = "_" + suffix
                new_name = f"{base_name}{suffix}{ext}"
            else:
                new_name = f"{base_name}{ext}"
            
            out_path = os.path.join(dir_name, new_name)
        
        else:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            name = output_name_var.get().strip() or DEFAULT_OUTPUT_FILENAME
            out_path = os.path.join(OUTPUT_DIR, name)

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            set_status(f"Patched file saved as: {out_path}")
        except Exception as e:
            set_status(f"Failed to save patched file: {e}", True)

    def apply_patch():
        set_status("Validating...", is_error=False)
        log("--- BEGIN PATCH ---")

        file_text = file_preview.get("1.0", tk.END)
        patch_text = patch_entry.get("1.0", tk.END)

        if not file_text.strip() or not patch_text.strip():
            set_status("Both file content and patch JSON must be provided.", True)
            return

        try:
            patch_obj = json.loads(patch_text)
        except Exception as e:
            set_status(f"Invalid JSON: {e}", True)
            return

        if "hunks" not in patch_obj or not isinstance(patch_obj["hunks"], list):
            set_status("Patch JSON must contain a 'hunks' array.", True)
            return

        try:
            patched = apply_patch_text(file_text, patch_obj, log_fn=log)
        except PatchError as e:
            set_status(str(e), True)
            return
        except Exception as e:
            set_status(f"Unexpected patch error: {e}", True)
            return

        file_preview.delete("1.0", tk.END)
        file_preview.insert(tk.END, patched)
        set_status("Patch Applied")
        log("--- PATCH COMPLETE ---")

    # ---------- Bind buttons / shortcuts ----------
    btn_clear.config(command=clear_all)
    debug_toggle.config(command=toggle_debug_panel)
    save_log_btn.config(command=save_log_to_file)
    schema_btn.config(command=insert_schema)
    btn_apply.config(command=apply_patch)
    btn_load.config(command=load_file)
    btn_save.config(command=save_patched_file)

    root.bind("<Control-o>", lambda e: load_file())
    root.bind("<Control-p>", lambda e: apply_patch())

    # Start with debug expanded or collapsed based on flag
    if DEBUG_EXPANDED_BY_DEFAULT:
        debug_collapsed.set(False)
        debug_toggle.config(text="▲")
    else:
        debug_collapsed.set(True)
        debug_panel.forget()
        debug_toggle.config(text="▼")

    # This loop is now correctly indented and will actually run!
    root.mainloop()


if __name__ == "__main__":
    create_gui()