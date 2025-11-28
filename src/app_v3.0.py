# _TokenizingPATCHER v3.0 – AI Enhanced
# Single-file hunk patcher with Local Ollama Inference.
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import datetime
import json
import re
import threading
import urllib.request
import urllib.error

# ==============================
# Global Config
# ==============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "./")
LOG_DIR = os.path.join(SCRIPT_DIR, "./logs/")
LOG_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_OUTPUT_FILENAME = "patched_output.txt"
DEBUG_EXPANDED_BY_DEFAULT = True
OLLAMA_URL = "http://localhost:11434"

# Default System Prompts for the AI Tools
AI_PROMPTS = {
    "fix_patch": (
        "You are a strict JSON formatting tool. "
        "The user will provide a code patch that might be malformed, contain comments, or be wrapped in markdown. "
        "Output ONLY valid JSON matching this schema:\n"
        "{ 'hunks': [ { 'description': '...', 'search_block': '...', 'replace_block': '...' } ] }\n"
        "Do not output markdown backticks. Do not output explanations. Output ONLY the raw JSON string."
    ),
    "fix_indent": (
        "You are a Python indentation repair tool. "
        "The user will provide code with broken or mixed indentation. "
        "Return the exact same code logic, but fix the indentation to use consistent 4 spaces. "
        "Do not change variable names or logic. Return ONLY the code."
    ),
    "ask_ai": (
        "You are a helpful coding assistant. "
        "Answer the user's question concisely based on the code provided."
    )
}
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

# ==============================
# AI / Ollama Client (No Dependencies)
# ==============================
class OllamaClient:
    @staticmethod
    def get_models():
        try:
            url = f"{OLLAMA_URL}/api/tags"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            return []

    @staticmethod
    def generate(model, prompt, system_prompt, callback_success, callback_error):
        def _run():
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            }
            try:
                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/generate",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode())
                    response_text = result.get('response', '')
                    callback_success(response_text)
            except Exception as e:
                callback_error(str(e))
        
        thread = threading.Thread(target=_run)
        thread.daemon = True
        thread.start()

# ==============================
# Patching Logic
# ==============================
class PatchError(Exception):
    pass

class StructuredLine:
    """ <indent><content><trailing> """
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

def detect_newline(text: str) -> str:
    if "\r\n" in text: return "\r\n"
    return "\n"

def split_lines_preserve(text: str, newline: str):
    if text == "": return [""]
    return text.split(newline)

def locate_hunk(file_lines: list, search_lines: list, floating: bool):
    matches = []
    if not search_lines: return matches
    window = len(search_lines)
    max_start = len(file_lines) - window
    if max_start < 0: return matches

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
        if ok: matches.append(start)
    return matches

def check_overlaps(applications):
    if not applications: return False
    sorted_apps = sorted(applications, key=lambda a: a["start"])
    for prev, cur in zip(sorted_apps, sorted_apps[1:]):
        if prev["end"] > cur["start"]: return True
    return False

def apply_patch_text(file_text: str, patch_obj: dict, log_fn=None) -> str:
    def log(msg: str):
        if log_fn: log_fn(msg)

    newline = detect_newline(file_text)
    file_lines = [StructuredLine(line) for line in split_lines_preserve(file_text, newline)]

    hunks = patch_obj.get("hunks")
    if not isinstance(hunks, list): raise PatchError("Patch JSON must contain a 'hunks' array.")

    applications = []
    for idx, h in enumerate(hunks):
        num = idx + 1
        search_block = h.get("search_block")
        replace_block = h.get("replace_block")

        if not isinstance(search_block, str) or not isinstance(replace_block, str):
            raise PatchError(f"Hunk {num} missing blocks.")

        search_lines = [StructuredLine(l) for l in re.split(r"\r\n|\n", search_block)]
        replace_lines = [StructuredLine(l) for l in re.split(r"\r\n|\n", replace_block)]

        matches = locate_hunk(file_lines, search_lines, floating=False)
        if len(matches) > 1: raise PatchError(f"Ambiguous strict match for hunk {num}.")
        
        start_end = None
        if len(matches) == 1:
            start = matches[0]
            start_end = (start, start + len(search_lines))
            log(f"Hunk {num}: Strict match found.")
        else:
            matches = locate_hunk(file_lines, search_lines, floating=True)
            if len(matches) > 1: raise PatchError(f"Ambiguous floating match for hunk {num}.")
            if len(matches) == 0: raise PatchError(f"Hunk {num} not found.")
            start = matches[0]
            start_end = (start, start + len(search_lines))
            log(f"Hunk {num}: Floating match found.")

        applications.append({"start": start_end[0], "end": start_end[1], "replace_lines": replace_lines})

    if check_overlaps(applications): raise PatchError("Overlapping hunks detected.")

    for app in sorted(applications, key=lambda a: a["start"], reverse=True):
        start, end = app["start"], app["end"]
        replace_lines = app["replace_lines"]
        indent_to_inherit = file_lines[start].indent if start < len(file_lines) else ""

        new_lines = []
        for i, r_line in enumerate(replace_lines):
            if (start + i) < end:
                original = file_lines[start + i]
                original.content = r_line.content
                new_lines.append(original)
            else:
                r_line.indent = indent_to_inherit
                new_lines.append(r_line)
        file_lines[start:end] = new_lines

    return newline.join([line.reconstruct() for line in file_lines])


# ==============================
# GUI Components
# ==============================
class Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, bg="#3b4252", fg="#eee", relief="solid", borderwidth=1).pack(ipadx=4, ipady=2)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

def create_gui():
    root = tk.Tk()
    root.title("_TokenizingPATCHER – AI Enhanced")
    root.geometry("1100x800")
    root.configure(bg="#020617")
    root.option_add("*Background", "#020617")
    root.option_add("*Foreground", "#e5e7eb")

    # --- Header ---
    tk.Label(root, text="_TokenizingPATCHER", font=("Helvetica", 18, "bold"), bg="#020617", fg="#e5e7eb").pack(pady=10)

    # --- Filename Row ---
    filename_frame = tk.Frame(root, bg="#020617")
    filename_frame.pack(fill="x", padx=10, pady=5)
    tk.Label(filename_frame, text="Loaded path:", bg="#020617", fg="#e5e7eb").pack(side="left")
    output_name_var = tk.StringVar(value="")
    tk.Entry(filename_frame, textvariable=output_name_var, state="readonly", bg="#020617", fg="#e5e7eb", readonlybackground="#020617").pack(side="left", padx=8, fill="x", expand=True)

    # --- Toolbar ---
    toolbar = tk.Frame(root, bg="#020617")
    toolbar.pack(fill="x", padx=10, pady=(0, 5))

    # Left Toolbar Items
    btn_load = tk.Button(toolbar, text="Load File")
    btn_load.pack(side="left", padx=5)
    
    btn_save = tk.Button(toolbar, text="Save Patched")
    btn_save.pack(side="left", padx=5)
    
    version_enabled_var = tk.BooleanVar(value=False)
    tk.Checkbutton(toolbar, text="Version", variable=version_enabled_var, bg="#020617", fg="#e5e7eb", selectcolor="#020617").pack(side="left", padx=5)
    
    version_suffix_var = tk.StringVar(value="")
    version_entry = tk.Entry(toolbar, textvariable=version_suffix_var, width=8, bg="#020617", fg="#e5e7eb", state="disabled")
    version_entry.pack(side="left", padx=5)
    
    def _toggle_version(*args):
        version_entry.config(state="normal" if version_enabled_var.get() else "disabled")
    version_enabled_var.trace_add("write", _toggle_version)

    btn_clear = tk.Button(toolbar, text="Clear All")
    btn_clear.pack(side="left", padx=5)

    # --- AI Toolbar Section (Right Aligned) ---
    ai_toolbar = tk.Frame(toolbar, bg="#020617")
    ai_toolbar.pack(side="right", padx=5)

    tk.Label(ai_toolbar, text="Model:", bg="#020617", fg="#9ca3af", font=("Segoe UI", 8)).pack(side="left", padx=2)
    
    selected_model_var = tk.StringVar()
    model_combo = ttk.Combobox(ai_toolbar, textvariable=selected_model_var, state="readonly", width=15)
    model_combo.pack(side="left", padx=2)
    Tooltip(model_combo, "Select local Ollama model")

    btn_ai_settings = tk.Button(ai_toolbar, text="⚙️", width=3, bg="#1f2937", fg="white", borderwidth=0)
    btn_ai_settings.pack(side="left", padx=2)
    Tooltip(btn_ai_settings, "Configure System Prompts")

    btn_ask_ai = tk.Button(ai_toolbar, text="Ask AI", bg="#4f46e5", fg="white")
    btn_ask_ai.pack(side="left", padx=5)
    Tooltip(btn_ask_ai, "Ask a question about the loaded file")

    # --- Main Panes ---
    paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg="#020617", sashwidth=4)
    paned.pack(fill="both", expand=True, padx=10, pady=5)

    # Left: File
    left_frame = tk.Frame(paned, bg="#020617")
    
    # Left Header with Tools
    left_header = tk.Frame(left_frame, bg="#020617")
    left_header.pack(fill="x")
    tk.Label(left_header, text="Original File:", bg="#020617", fg="#e5e7eb").pack(side="left")
    btn_fix_indent = tk.Button(left_header, text="AI Fix Indent", font=("Segoe UI", 8), bg="#374151", fg="white")
    btn_fix_indent.pack(side="right")
    Tooltip(btn_fix_indent, "Use AI to normalize indentation in this file")

    file_preview = scrolledtext.ScrolledText(left_frame, wrap=tk.NONE, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    file_preview.pack(fill="both", expand=True)
    paned.add(left_frame)

    # Right: Patch
    right_frame = tk.Frame(paned, bg="#020617")
    patch_header = tk.Frame(right_frame, bg="#020617")
    patch_header.pack(fill="x")
    tk.Label(patch_header, text="Patch JSON:", bg="#020617", fg="#e5e7eb").pack(side="left")
    schema_btn = tk.Button(patch_header, text="Schema", font=("Helvetica", 9))
    schema_btn.pack(side="right", padx=5)

    patch_entry = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    patch_entry.pack(fill="both", expand=True)
    
    # Placeholder logic
    placeholder_color, default_fg = "#6b7280", "#e5e7eb"
    def on_focus_in(e):
        if patch_entry.get("1.0", tk.END).strip() == PATCH_SCHEMA:
            patch_entry.delete("1.0", tk.END)
            patch_entry.config(fg=default_fg)
    def on_focus_out(e):
        if not patch_entry.get("1.0", tk.END).strip():
            patch_entry.insert("1.0", PATCH_SCHEMA)
            patch_entry.config(fg=placeholder_color)
    patch_entry.insert("1.0", PATCH_SCHEMA)
    patch_entry.config(fg=placeholder_color)
    patch_entry.bind("<FocusIn>", on_focus_in)
    patch_entry.bind("<FocusOut>", on_focus_out)
    
    paned.add(right_frame)

    # --- Footer / Apply Area ---
    apply_frame = tk.Frame(root, bg="#020617")
    apply_frame.pack(pady=10, fill="x", padx=10)

    # AI Fix Button (Next to Apply)
    btn_ai_fix_patch = tk.Button(apply_frame, text="✨ AI Fix Patch", font=("Helvetica", 10), bg="#9333ea", fg="white", padx=10, pady=5)
    btn_ai_fix_patch.pack(side="right", padx=(5, 0))
    Tooltip(btn_ai_fix_patch, "Use AI to repair broken/invalid JSON in the patch window")

    btn_apply = tk.Button(apply_frame, text="Validate & Apply", font=("Helvetica", 12, "bold"), bg="#22c55e", fg="black", padx=20, pady=5)
    btn_apply.pack(side="right")

    # --- Debug ---
    debug_header = tk.Frame(root, bg="#020617")
    debug_header.pack(fill="x", padx=10, pady=(5, 0))
    tk.Label(debug_header, text="Debug Output:", bg="#020617", fg="#e5e7eb").pack(side="left")
    debug_output = scrolledtext.ScrolledText(root, height=8, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    debug_output.pack(fill="both", expand=False, padx=10, pady=5)
    
    status_lbl = tk.Label(root, text="Ready", fg="green", bg="#020617")
    status_lbl.pack(pady=5)

    # ==============================
    # Logic & Event Handlers
    # ==============================
    def log(msg: str):
        debug_output.insert(tk.END, msg + "\n")
        debug_output.see(tk.END)

    def set_status(msg: str, is_error: bool = False):
        status_lbl.config(text=msg, fg=("red" if is_error else "green"))
        prefix = "ERROR: " if is_error else ""
        log(prefix + msg)

    # --- Core Functions ---
    def load_file():
        path = filedialog.askopenfilename()
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                file_preview.delete("1.0", tk.END)
                file_preview.insert(tk.END, content)
            root.loaded_filepath = path
            output_name_var.set(path)
            version_enabled_var.set(True)
            # Simple version bump logic
            base = os.path.splitext(os.path.basename(path))[0]
            version_suffix_var.set("_v1.0") # Simplified for brevity
            set_status(f"Loaded: {path}")
        except Exception as e:
            set_status(f"Load failed: {e}", True)

    def save_patched():
        text = file_preview.get("1.0", tk.END)
        if not text.strip(): return
        # Logic to determine filename
        original = getattr(root, "loaded_filepath", None)
        if original:
            d, f = os.path.split(original)
            base, ext = os.path.splitext(f)
            suffix = version_suffix_var.get() if version_enabled_var.get() else ""
            if suffix and not suffix.startswith("_"): suffix = "_" + suffix
            path = os.path.join(d, base + suffix + ext)
        else:
            path = os.path.join(OUTPUT_DIR, "patched_output.txt")
        
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(text)
            set_status(f"Saved: {path}")
        except Exception as e:
            set_status(f"Save failed: {e}", True)

    def clear_all():
        file_preview.delete("1.0", tk.END)
        patch_entry.delete("1.0", tk.END)
        debug_output.delete("1.0", tk.END)
        on_focus_out(None)
        set_status("Cleared")

    def apply_patch():
        file_text = file_preview.get("1.0", tk.END)
        patch_text = patch_entry.get("1.0", tk.END)
        try:
            patch_obj = json.loads(patch_text)
            patched = apply_patch_text(file_text, patch_obj, log_fn=log)
            file_preview.delete("1.0", tk.END)
            file_preview.insert(tk.END, patched)
            set_status("Patch Applied successfully")
        except Exception as e:
            set_status(f"Patch Failed: {e}", True)

    # --- AI Functions ---
    def refresh_models():
        models = OllamaClient.get_models()
        if models:
            model_combo['values'] = models
            if not selected_model_var.get():
                model_combo.current(0)
            log(f"Ollama connected. Found {len(models)} models.")
        else:
            log("Could not connect to Ollama (localhost:11434). Is it running?")

    def open_settings():
        top = tk.Toplevel(root)
        top.title("AI System Prompts")
        top.geometry("600x450")
        top.configure(bg="#1f2937")

        def add_field(key, label_text):
            tk.Label(top, text=label_text, bg="#1f2937", fg="#9ca3af", anchor="w").pack(fill="x", padx=10, pady=(10,0))
            txt = tk.Text(top, height=4, bg="#374151", fg="white", borderwidth=0)
            txt.insert("1.0", AI_PROMPTS[key])
            txt.pack(fill="x", padx=10, pady=5)
            return txt

        t_fix = add_field("fix_patch", "Fix Patch Prompt:")
        t_indent = add_field("fix_indent", "Fix Indent Prompt:")
        t_ask = add_field("ask_ai", "Ask AI Prompt:")

        def save_prompts():
            AI_PROMPTS["fix_patch"] = t_fix.get("1.0", tk.END).strip()
            AI_PROMPTS["fix_indent"] = t_indent.get("1.0", tk.END).strip()
            AI_PROMPTS["ask_ai"] = t_ask.get("1.0", tk.END).strip()
            top.destroy()
            set_status("AI Prompts updated.")

        tk.Button(top, text="Save", command=save_prompts, bg="#22c55e", fg="black").pack(pady=10)

    def run_ai_task(task_type, input_text, target_widget=None):
        model = selected_model_var.get()
        if not model:
            set_status("No model selected.", True)
            return
        
        set_status(f"AI ({task_type}) running...", False)
        root.config(cursor="watch")

        def on_success(result):
            root.after(0, lambda: _handle_success(result))

        def _handle_success(result):
            root.config(cursor="")
            set_status(f"AI ({task_type}) complete.")
            
            # Clean up result (remove markdown blocks if present)
            clean_result = result
            if "```" in clean_result:
                # Regex to strip code blocks
                match = re.search(r"```(?:\w+)?\s(.*?)```", clean_result, re.DOTALL)
                if match:
                    clean_result = match.group(1).strip()
            
            if target_widget:
                target_widget.delete("1.0", tk.END)
                target_widget.insert(tk.END, clean_result)
                if task_type == "fix_patch":
                    # Re-trigger color logic
                    target_widget.config(fg="#e5e7eb")
            elif task_type == "ask_ai":
                log(f"\n[AI ANSWER]:\n{result}\n{'-'*20}")
                messagebox.showinfo("AI Answer", result)

        def on_error(err):
            root.after(0, lambda: _handle_error(err))

        def _handle_error(err):
            root.config(cursor="")
            set_status(f"AI Error: {err}", True)

        sys_prompt = AI_PROMPTS.get(task_type, "")
        OllamaClient.generate(model, input_text, sys_prompt, on_success, on_error)

    # --- AI Button Callbacks ---
    def on_fix_patch():
        text = patch_entry.get("1.0", tk.END).strip()
        if not text or text == PATCH_SCHEMA: 
            set_status("Patch window is empty.", True)
            return
        run_ai_task("fix_patch", text, patch_entry)

    def on_fix_indent():
        text = file_preview.get("1.0", tk.END)
        if not text.strip(): return
        run_ai_task("fix_indent", text, file_preview)

    def on_ask_ai():
        code = file_preview.get("1.0", tk.END)
        # Ask user for query
        query = tk.simpledialog.askstring("Ask AI", "What is your question about this code?", parent=root)
        if not query: return
        prompt = f"CODE:\n{code}\n\nQUESTION: {query}"
        run_ai_task("ask_ai", prompt, None)

    # Wiring
    btn_load.config(command=load_file)
    btn_save.config(command=save_patched)
    btn_clear.config(command=clear_all)
    schema_btn.config(command=lambda: (root.clipboard_clear(), root.clipboard_append(PATCH_SCHEMA), set_status("Copied Schema")))
    btn_apply.config(command=apply_patch)
    
    # AI Wiring
    btn_ai_settings.config(command=open_settings)
    btn_ai_fix_patch.config(command=on_fix_patch)
    btn_fix_indent.config(command=on_fix_indent)
    btn_ask_ai.config(command=on_ask_ai)

    # Init
    refresh_models()
    root.mainloop()

if __name__ == "__main__":
    create_gui()
