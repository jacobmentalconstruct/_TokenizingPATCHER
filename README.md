# _TokenizingPATCHER
A semantic, formatting-aware GUI patcher for applying robust code changes.

---

## 🎯 The Problem: "Formatting Hell"

Applying patches to source code is often fragile. Traditional `diff` and `patch` tools are **literal**—they demand that line numbers, indentation (tabs vs. spaces), newlines (`\n` vs. `\r\n`), and trailing whitespace all match *perfectly*. If anything is off, the patch fails.

This is a massive problem when:
* Refactoring code, which changes line numbers.
* Collaborating with others who have different editor settings.
* Generating patches from AI/LLMs, which are **semantic** (they understand *ideas*) but often fail at being **literal** (they make tiny formatting errors).

## 💡 The Solution: Semantic Tokenization

`_TokenizingPATCHER` solves this by treating code as a structure, not just literal text.

Instead of matching exact lines, it **tokenizes** each line into three distinct parts:
`[indentation] [content] [trailing_whitespace]`

It then performs its search **only on the `[content]` part.**

This means the patcher can find the correct *semantic* location for a change, even if the file's indentation, whitespace, or line endings are different from the patch file.

When applying the change, it intelligently **preserves the original file's indentation and newlines**, creating a robust, non-destructive patch that *just works*.

---

## ✨ Features

* **Formatting-Immune Patching:** Uses a `StructuredLine` model to separate content from formatting.
* **Dual-Mode Matching:** Supports **Strict** (content-only) and **Floating** (content-stripped) matching logic.
* **Indentation Preservation:** Automatically preserves the target file's indentation for replaced lines and intelligently inherits it for new lines.
* **Simple JSON Schema:** Uses a clear, human-readable JSON format for defining patch hunks.
* **Self-Contained GUI:** A single-file Python/Tkinter app with no external dependencies (beyond the standard library).
* **Helper Utilities:** Load File, Save Patched File, Clear All, and a "Schema" button that copies the JSON format to your clipboard.

---

## 🚀 How to Use

1.  **Run the App:** `python app_vTEST-5.py`
2.  **Load File:** Click `Load File` and select your target source code file (e.g., `my_script.py`).
3.  **Get Schema:** The patch schema will appear as placeholder text. Click the `Schema` button to copy the raw schema to your clipboard.
4.  **Write Patch:** Write your patch in the "Patch JSON Payload" window.
5.  **Apply:** Click `Validate & Apply`.
6.  **Save:** If the patch is successful (see "Debug Output"), click `Save Patched File` to save the modified code.

---

## 📜 The Patch Schema

The patcher expects a JSON object with a single `hunks` key. A "hunk" is a single set of changes.

```json
{
  "hunks": [
    {
      "description": "A human-readable note about what this hunk does.",
      "search_block": "The exact text to find.\nNewlines are required for multi-line blocks.\nFormatting (spaces, tabs) doesn't need to be perfect.",
      "replace_block": "The new text to replace the search block with.\nThis text's indentation will be auto-formatted\nto match the original file."
    }
  ]
}