# _TokenizingPATCHER v3.1 – AI Enhanced (Interactive Window)
# Single-file hunk patcher with Local Ollama Inference.
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
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

# Default System Prompts
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
        "Answer the user's question concisely based on the code provided. "
        "If the user asks for code, provide it in a clean format."
    )
}

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
# AI / Ollama Client
# ==============================
class OllamaClient:
    @staticmethod
    def get_models():
        try:
            url = f"{OLLAMA_URL}/api/tags"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                return [model['name'] for model in data.get('models', [])]
        except Exception:
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
# Patching Logic (Standard)
# ==============================
class PatchError(Exception): pass

class StructuredLine:
    def __init__(self, line: str):
        self.original_line = line
        match = re.match(r"(^[ \t]*)(.*?)([ \t]*$)", line)
        if match:
            self.indent, self.content, self.trailing = match.group(1), match.group(2), match.group(3)
        else:
            self.indent, self.content, self.trailing = "", line, ""
    def reconstruct(self) -> str:
        return f"{self.indent}{self.content}{self.trailing}"

def detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"

def split_lines_preserve(text: str, newline: str):
    return [""] if text == "" else text.split(newline)

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
            f_cont, s_cont = f_line.content, s_line.content
            if floating:
                f_cont, s_cont = f_cont.strip(), s_cont.strip()
            if f_cont != s_cont:
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
        s_blk, r_blk = h.get("search_block"), h.get("replace_block")
        if not isinstance(s_blk, str) or not isinstance(r_blk, str): raise PatchError(f"Hunk {num} incomplete.")
        s_lines = [StructuredLine(l) for l in re.split(r"\r\n|\n", s_blk)]
        r_lines = [StructuredLine(l) for l in re.split(r"\r\n|\n", r_blk)]
        
        matches = locate_hunk(file_lines, s_lines, False)
        if len(matches) > 1: raise PatchError(f"Ambiguous strict match hunk {num}.")
        start_end = None
        if len(matches) == 1:
            start_end = (matches[0], matches[0] + len(s_lines))
            log(f"Hunk {num}: Strict match.")
        else:
            matches = locate_hunk(file_lines, s_lines, True)
            if len(matches) > 1: raise PatchError(f"Ambiguous floating match hunk {num}.")
            if len(matches) == 0: raise PatchError(f"Hunk {num} not found.")
            start_end = (matches[0], matches[0] + len(s_lines))
            log(f"Hunk {num}: Floating match.")
        applications.append({"start": start_end[0], "end": start_end[1], "replace_lines": r_lines})

    if check_overlaps(applications): raise PatchError("Overlapping hunks.")
    
    for app in sorted(applications, key=lambda a: a["start"], reverse=True):
        start, end = app["start"], app["end"]
        r_lines = app["replace_lines"]
        indent = file_lines[start].indent if start < len(file_lines) else ""
        new_l = []
        for i, rl in enumerate(r_lines):
            if (start + i) < end:
                orig = file_lines[start + i]
                orig.content = rl.content
                new_l.append(orig)
            else:
                rl.indent = indent
                new_l.append(rl)
        file_lines[start:end] = new_l
        
    return newline.join([line.reconstruct() for line in file_lines])

# ==============================
# GUI
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
        x, y = self.widget.winfo_rootx() + 20, self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, bg="#3b4252", fg="#eee", relief="solid", borderwidth=1).pack(ipadx=4, ipady=2)
    def hide_tip(self, event=None):
        if self.tipwindow: self.tipwindow.destroy(); self.tipwindow = None

def create_gui():
    root = tk.Tk()
    root.title("_TokenizingPATCHER – AI Enhanced")
    root.geometry("1100x800")
    root.configure(bg="#020617")
    root.option_add("*Background", "#020617")
    root.option_add("*Foreground", "#e5e7eb")

    # State for the Ask AI window so we don't open duplicates
    ai_window = None 

    # --- Header ---
    tk.Label(root, text="_TokenizingPATCHER", font=("Helvetica", 18, "bold"), bg="#020617", fg="#e5e7eb").pack(pady=10)

    # --- Filename Row ---
    fn_frame = tk.Frame(root, bg="#020617")
    fn_frame.pack(fill="x", padx=10, pady=5)
    tk.Label(fn_frame, text="Loaded path:", bg="#020617", fg="#e5e7eb").pack(side="left")
    output_name_var = tk.StringVar(value="")
    tk.Entry(fn_frame, textvariable=output_name_var, state="readonly", bg="#020617", fg="#e5e7eb", readonlybackground="#020617").pack(side="left", padx=8, fill="x", expand=True)

    # --- Toolbar ---
    toolbar = tk.Frame(root, bg="#020617")
    toolbar.pack(fill="x", padx=10, pady=(0, 5))

    btn_load = tk.Button(toolbar, text="Load File")
    btn_load.pack(side="left", padx=5)
    btn_save = tk.Button(toolbar, text="Save Patched")
    btn_save.pack(side="left", padx=5)
    
    version_enabled_var = tk.BooleanVar(value=False)
    tk.Checkbutton(toolbar, text="Version", variable=version_enabled_var, bg="#020617", fg="#e5e7eb", selectcolor="#020617").pack(side="left", padx=5)
    version_suffix_var = tk.StringVar(value="")
    v_entry = tk.Entry(toolbar, textvariable=version_suffix_var, width=8, bg="#020617", fg="#e5e7eb", state="disabled")
    v_entry.pack(side="left", padx=5)
    version_enabled_var.trace_add("write", lambda *a: v_entry.config(state="normal" if version_enabled_var.get() else "disabled"))

    btn_clear = tk.Button(toolbar, text="Clear All")
    btn_clear.pack(side="left", padx=5)

    # --- AI Toolbar ---
    ai_toolbar = tk.Frame(toolbar, bg="#020617")
    ai_toolbar.pack(side="right", padx=5)
    tk.Label(ai_toolbar, text="Model:", bg="#020617", fg="#9ca3af", font=("Segoe UI", 8)).pack(side="left", padx=2)
    
    selected_model_var = tk.StringVar()
    model_combo = ttk.Combobox(ai_toolbar, textvariable=selected_model_var, state="readonly", width=15)
    model_combo.pack(side="left", padx=2)
    Tooltip(model_combo, "Select local Ollama model")

    btn_settings = tk.Button(ai_toolbar, text="⚙️", width=3, bg="#1f2937", fg="white", borderwidth=0)
    btn_settings.pack(side="left", padx=2)
    
    btn_ask_ai = tk.Button(ai_toolbar, text="Ask AI", bg="#4f46e5", fg="white")
    btn_ask_ai.pack(side="left", padx=5)

    # --- Main Area ---
    paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg="#020617", sashwidth=4)
    paned.pack(fill="both", expand=True, padx=10, pady=5)

    left_frame = tk.Frame(paned, bg="#020617")
    left_hdr = tk.Frame(left_frame, bg="#020617")
    left_hdr.pack(fill="x")
    tk.Label(left_hdr, text="Original File:", bg="#020617", fg="#e5e7eb").pack(side="left")
    btn_fix_indent = tk.Button(left_hdr, text="AI Fix Indent", font=("Segoe UI", 8), bg="#374151", fg="white")
    btn_fix_indent.pack(side="right")
    
    file_preview = scrolledtext.ScrolledText(left_frame, wrap=tk.NONE, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    file_preview.pack(fill="both", expand=True)
    paned.add(left_frame)

    right_frame = tk.Frame(paned, bg="#020617")
    patch_hdr = tk.Frame(right_frame, bg="#020617")
    patch_hdr.pack(fill="x")
    tk.Label(patch_hdr, text="Patch JSON:", bg="#020617", fg="#e5e7eb").pack(side="left")
    schema_btn = tk.Button(patch_hdr, text="Schema", font=("Helvetica", 9))
    schema_btn.pack(side="right", padx=5)

    patch_entry = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    patch_entry.pack(fill="both", expand=True)
    
    # Placeholder logic
    def on_focus_in(e):
        if patch_entry.get("1.0", tk.END).strip() == PATCH_SCHEMA:
            patch_entry.delete("1.0", tk.END)
            patch_entry.config(fg="#e5e7eb")
    def on_focus_out(e):
        if not patch_entry.get("1.0", tk.END).strip():
            patch_entry.insert("1.0", PATCH_SCHEMA)
            patch_entry.config(fg="#6b7280")
    patch_entry.insert("1.0", PATCH_SCHEMA)
    patch_entry.config(fg="#6b7280")
    patch_entry.bind("<FocusIn>", on_focus_in)
    patch_entry.bind("<FocusOut>", on_focus_out)
    paned.add(right_frame)

    # --- Footer ---
    apply_frame = tk.Frame(root, bg="#020617")
    apply_frame.pack(pady=10, fill="x", padx=10)
    btn_ai_fix = tk.Button(apply_frame, text="✨ AI Fix Patch", font=("Helvetica", 10), bg="#9333ea", fg="white", padx=10, pady=5)
    btn_ai_fix.pack(side="right", padx=(5, 0))
    btn_apply = tk.Button(apply_frame, text="Validate & Apply", font=("Helvetica", 12, "bold"), bg="#22c55e", fg="black", padx=20, pady=5)
    btn_apply.pack(side="right")

    debug_out = scrolledtext.ScrolledText(root, height=8, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", borderwidth=0, highlightthickness=1, highlightbackground="#1f2937")
    debug_out.pack(fill="both", expand=False, padx=10, pady=5)
    status_lbl = tk.Label(root, text="Ready (AI Online)", fg="green", bg="#020617")
    status_lbl.pack(pady=5)

    # ==============================
    # Logic
    # ==============================
    def log(msg: str):
        debug_out.insert(tk.END, msg + "\n")
        debug_out.see(tk.END)

    def set_status(msg: str, is_error: bool = False):
        status_lbl.config(text=msg, fg=("red" if is_error else "green"))
        if is_error: log("ERROR: " + msg)
        else: log(msg)

    def load_file():
        path = filedialog.askopenfilename()
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                file_preview.delete("1.0", tk.END)
                file_preview.insert(tk.END, f.read())
            root.loaded_filepath = path
            output_name_var.set(path)
            version_enabled_var.set(True)
            base = os.path.splitext(os.path.basename(path))[0]
            version_suffix_var.set("_v1.0")
            set_status(f"Loaded: {path}")
        except Exception as e: set_status(f"Load failed: {e}", True)

    def save_patched():
        text = file_preview.get("1.0", tk.END)
        orig = getattr(root, "loaded_filepath", None)
        if orig:
            d, f = os.path.split(orig)
            base, ext = os.path.splitext(f)
            suffix = version_suffix_var.get() if version_enabled_var.get() else ""
            if suffix and not suffix.startswith("_"): suffix = "_" + suffix
            path = os.path.join(d, base + suffix + ext)
        else:
            path = os.path.join(OUTPUT_DIR, "patched_output.txt")
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(text)
            set_status(f"Saved: {path}")
        except Exception as e: set_status(f"Save failed: {e}", True)

    def apply_patch():
        try:
            p_obj = json.loads(patch_entry.get("1.0", tk.END))
            patched = apply_patch_text(file_preview.get("1.0", tk.END), p_obj, log_fn=log)
            file_preview.delete("1.0", tk.END)
            file_preview.insert(tk.END, patched)
            set_status("Patch Applied")
        except Exception as e: set_status(f"Patch Error: {e}", True)

    def refresh_models():
        models = OllamaClient.get_models()
        if models:
            model_combo['values'] = models
            if not selected_model_var.get(): model_combo.current(0)
            log(f"Ollama: Found {len(models)} models.")
        else: log("Ollama not found at localhost:11434")

    # --- AI Task Runner ---
    def run_ai_task(task_type, input_text, target_widget=None):
        model = selected_model_var.get()
        if not model: set_status("No model selected", True); return
        set_status(f"AI ({task_type}) running...", False)
        
        def on_success(result):
            root.after(0, lambda: _handle_success(result))
        
        def _handle_success(result):
            set_status(f"AI ({task_type}) done.")
            clean = result
            # Strip markdown blocks if present
            if "```" in clean:
                m = re.search(r"```(?:\w+)?\s(.*?)```", clean, re.DOTALL)
                if m: clean = m.group(1).strip()

            if target_widget:
                # Handle ReadOnly widgets by temporarily unlocking them
                prev_state = target_widget.cget("state")
                if prev_state == "disabled":
                    target_widget.config(state="normal")
                
                target_widget.delete("1.0", tk.END)
                target_widget.insert(tk.END, clean)
                
                if prev_state == "disabled":
                    target_widget.config(state="disabled")
                
                # Restore placeholder color if needed
                if task_type == "fix_patch":
                    target_widget.config(fg="#e5e7eb")

        def on_error(err):
            root.after(0, lambda: set_status(f"AI Error: {err}", True))

        sys = AI_PROMPTS.get(task_type, "")
        OllamaClient.generate(model, input_text, sys, on_success, on_error)

    # --- AI Window Logic ---
    def open_ask_ai_window():
        nonlocal ai_window
        if ai_window is not None and tk.Toplevel.winfo_exists(ai_window):
            ai_window.lift()
            return

        ai_window = tk.Toplevel(root)
        ai_window.title("Ask AI")
        ai_window.geometry("700x600")
        ai_window.configure(bg="#1f2937")

        # Top: Response Area
        tk.Label(ai_window, text="AI Response:", bg="#1f2937", fg="#9ca3af").pack(anchor="w", padx=10, pady=(10, 0))
        
        # Read-only text area allows selection and copy (Ctrl+C)
        out_text = scrolledtext.ScrolledText(ai_window, height=20, bg="#020617", fg="#e5e7eb", 
                                             insertbackground="#e5e7eb", borderwidth=0)
        out_text.pack(fill="both", expand=True, padx=10, pady=5)
        out_text.insert("1.0", "Ask a question below to get started.")
        out_text.config(state="disabled")

        # Bottom: Input Area
        tk.Label(ai_window, text="Your Question:", bg="#1f2937", fg="#9ca3af").pack(anchor="w", padx=10, pady=(5, 0))
        
        in_entry = tk.Entry(ai_window, bg="#374151", fg="white", insertbackground="white")
        in_entry.pack(fill="x", padx=10, pady=5)
        in_entry.focus_set()

        def submit_question(event=None):
            question = in_entry.get().strip()
            if not question: return
            
            # Show "Thinking..."
            out_text.config(state="normal")
            out_text.delete("1.0", tk.END)
            out_text.insert("1.0", "Thinking...")
            out_text.config(state="disabled")
            
            # Grab context and run
            code_context = file_preview.get("1.0", tk.END)
            full_prompt = f"CODE CONTEXT:\n{code_context}\n\nUSER QUESTION: {question}"
            
            run_ai_task("ask_ai", full_prompt, target_widget=out_text)

        in_entry.bind("<Return>", submit_question)
        
        btn_frame = tk.Frame(ai_window, bg="#1f2937")
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="Ask", command=submit_question, bg="#4f46e5", fg="white", width=10).pack(side="right")

    # --- Config Window ---
    def open_settings():
        top = tk.Toplevel(root)
        top.title("AI System Prompts")
        top.geometry("600x450")
        top.configure(bg="#1f2937")
        
        def add_field(k, lbl):
            tk.Label(top, text=lbl, bg="#1f2937", fg="#9ca3af", anchor="w").pack(fill="x", padx=10, pady=(10,0))
            t = tk.Text(top, height=4, bg="#374151", fg="white", borderwidth=0)
            t.insert("1.0", AI_PROMPTS[k])
            t.pack(fill="x", padx=10, pady=5)
            return t
            
        tf, ti, ta = add_field("fix_patch", "Fix Patch Prompt:"), add_field("fix_indent", "Fix Indent Prompt:"), add_field("ask_ai", "Ask AI Prompt:")
        
        def save():
            AI_PROMPTS["fix_patch"] = tf.get("1.0", tk.END).strip()
            AI_PROMPTS["fix_indent"] = ti.get("1.0", tk.END).strip()
            AI_PROMPTS["ask_ai"] = ta.get("1.0", tk.END).strip()
            top.destroy()
            set_status("Prompts updated")
        tk.Button(top, text="Save", command=save, bg="#22c55e", fg="black").pack(pady=10)

    # Wiring
    btn_load.config(command=load_file)
    btn_save.config(command=save_patched)
    btn_clear.config(command=lambda: (file_preview.delete("1.0", tk.END), patch_entry.delete("1.0", tk.END), debug_out.delete("1.0", tk.END), set_status("Cleared")))
    schema_btn.config(command=lambda: (root.clipboard_clear(), root.clipboard_append(PATCH_SCHEMA), set_status("Copied Schema")))
    btn_apply.config(command=apply_patch)
    
    btn_settings.config(command=open_settings)
    btn_ai_fix.config(command=lambda: run_ai_task("fix_patch", patch_entry.get("1.0", tk.END), patch_entry))
    btn_fix_indent.config(command=lambda: run_ai_task("fix_indent", file_preview.get("1.0", tk.END), file_preview))
    btn_ask_ai.config(command=open_ask_ai_window)

    refresh_models()
    root.mainloop()

if __name__ == "__main__":
    create_gui()

