"""Unofficial Corvus GUI - a small tkinter front end for CTRE's `corvus` CLI.

This is an unofficial community project. It is not maintained, endorsed, or
supported by CTR Electronics. It does NOT include corvus: download corvus
yourself from https://docs.ctr-electronics.com/cli-tools

Flow:
1. Pick a mechanism type (dropdown, filled from corvus itself).
2. The form is built from the JSON template that `corvus json <type>` produces.
3. Click Generate -> choose where to save the .java file -> corvus writes it.

corvus is looked up in this order: the path you last chose (saved in
corvus_gui_config.json), the folder next to this script / the .exe, then PATH.
"""

import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Unofficial Corvus GUI"
DISCLAIMER = (
    "Unofficial community tool. Not maintained, endorsed, or supported by "
    "CTR Electronics. corvus is not included; get it from CTRE."
)
CORVUS_DOWNLOAD_URL = "https://docs.ctr-electronics.com/cli-tools"

LANGUAGE = "java"  # fixed for now
DEFAULT_OUT_DIR = os.path.join("src", "main", "java", "frc", "robot", "subsystems")
FALLBACK_TYPES = ["elevator", "arm", "flywheel", "led", "configs"]  # only if parsing --help fails

# Never shown in the dropdown (swerve is too different; swerve-proj is the swerve project generator)
EXCLUDED_TYPES = {"json", "swerve", "swerve-proj"}

CORVUS_NAME = "corvus.exe" if os.name == "nt" else "corvus"

# Fields that should be a dropdown instead of a free-text box.
# Key = text that appears in the field name (lowercase, no underscores/spaces),
# value = the choices to offer. Add your own lines here.
FIELD_CHOICES = {
    "neutralmode": ["Brake", "Coast"],
    "inverted": ["CounterClockwise_Positive", "Clockwise_Positive"],
    "model": ["TalonFX", "TalonFXS"],
}

# Lists that may hold more than one item (they get a "+ Add" button).
# Every other list has a fixed set of items: no Add, no Remove.
# Key = list name from the template, lowercase, no underscores/spaces.
REPEATABLE_LISTS = {"motorcontrollers", "setpoints"}

# Fields that are never shown in the form (their template value is still sent
# to corvus unchanged). Use the exact key name from the template JSON.
HIDDEN_FIELDS = set()


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_dir(), "corvus_gui_config.json")


# --------------------------------------------------------------------------
# corvus helpers
# --------------------------------------------------------------------------

def _find_in_dir(folder):
    """Return a corvus executable inside `folder`, or None."""
    exact = os.path.join(folder, CORVUS_NAME)
    if os.path.isfile(exact):
        return exact
    pattern = "corvus*.exe" if os.name == "nt" else "corvus*"
    skip = (".py", ".json", ".java", ".md", ".txt")
    for path in sorted(glob.glob(os.path.join(folder, pattern))):
        if os.path.isfile(path) and not path.lower().endswith(skip):
            return path
    return None


def resolve_corvus_path(path):
    """Turn a user-chosen path (file or folder) into a runnable file, or None."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isdir(path):
        return _find_in_dir(path)
    return path if os.path.isfile(path) else None


def load_saved_corvus():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            saved = json.load(f).get("corvus")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return saved if saved and os.path.isfile(saved) else None


def save_corvus_choice(path):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"corvus": path}, f)
    except OSError:
        pass  # read-only location; not important


def find_corvus():
    """Saved choice, then the program's own folder, then PATH."""
    saved = load_saved_corvus()
    if saved:
        return saved
    found = _find_in_dir(app_dir())
    if found:
        return found
    return shutil.which("corvus")


def run_corvus(corvus, args, timeout=60):
    """Run corvus and return (returncode, combined output)."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [corvus, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        return -1, "corvus timed out"
    except OSError as e:
        return -1, f"Could not run '{corvus}': {e}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_mech_values(help_text):
    """Read the mechanism names from the '<MECH> ... Possible values:' block.

    The help text looks like:
        <MECH>
            Mechanism to generate
            Possible values:
            - configs: Generate a device configuration object
            - elevator: Generate an Elevator subsystem
        <LANG>
    """
    names = []
    in_mech = False
    for line in help_text.splitlines():
        if "<MECH>" in line and not line.lstrip().startswith("Usage"):
            in_mech = True
            continue
        if in_mech:
            if "<LANG>" in line or line.strip().startswith("Options:"):
                break
            m = re.match(r"\s*-\s+([a-z][a-z0-9_-]*)\s*:", line)
            if m:
                names.append(m.group(1))
    return names


def discover_mechanisms(corvus):
    """Ask corvus for its mechanism list (from `corvus --help`).

    Returns (names, diagnostics). `diagnostics` is what corvus printed, so a
    failure can be shown to the user instead of silently hidden.
    """
    notes = []
    for args in (["--help"], ["json", "--help"]):
        code, out = run_corvus(corvus, args, timeout=20)
        names = [n for n in parse_mech_values(out) if n not in EXCLUDED_TYPES]
        if names:
            return names, out
        notes.append(f"> corvus {' '.join(args)} (exit code {code})\n{out.strip()}")
    return FALLBACK_TYPES, "\n".join(notes)


# --------------------------------------------------------------------------
# Label / widget helpers
# --------------------------------------------------------------------------

def pretty(label):
    """'currentLimit' / 'supply_current_limit' -> 'Current Limit' style labels."""
    text = re.sub(r"[_\-]+", " ", str(label))
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return text[:1].upper() + text[1:]


def flat_key(key):
    return str(key).lower().replace("_", "").replace(" ", "") if key is not None else ""


def is_param(data):
    """True for {"name": ..., "type": ..., "value": ...} parameter entries."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("name"), str)
        and "value" in data
        and set(data) <= {"name", "type", "value", "unit", "units"}
    )


def choices_for(key, value):
    """Dropdown options for a string field, or None if it should be free text."""
    if not isinstance(value, str) or key is None:
        return None
    flat = str(key).lower().replace("_", "").replace(" ", "")
    for part, options in FIELD_CHOICES.items():
        if part in flat:
            options = list(options)
            if value and value not in options:
                options.insert(0, value)  # never lose the template's own value
            return options
    return None


# --------------------------------------------------------------------------
# Dynamic form built from a JSON template
# --------------------------------------------------------------------------

class JsonForm(ttk.Frame):
    """Scrollable form that mirrors the structure of a JSON object."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        # One global binding, but the handler only acts when the mouse is over this form.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_wheel, add="+")
        self._getter = None

    # -- scrolling --------------------------------------------------------

    def _pointer_in_form(self, event):
        """True when the mouse pointer is inside the form's on-screen rectangle."""
        try:
            left, top = self.winfo_rootx(), self.winfo_rooty()
            return (
                left <= event.x_root < left + self.winfo_width()
                and top <= event.y_root < top + self.winfo_height()
            )
        except (tk.TclError, AttributeError, TypeError):
            return False

    def _on_wheel(self, event):
        try:
            if not self._pointer_in_form(event):
                return
            num = getattr(event, "num", None)
            if num == 4:
                step = -1
            elif num == 5:
                step = 1
            else:
                step = -1 if int(event.delta) > 0 else 1
            self.canvas.yview_scroll(step * 3, "units")
        except Exception as e:  # never let a wheel event spam errors into the console
            print(f"mouse wheel handler error: {e!r}", file=sys.stderr)

    def _wheel_break(self, event):
        """For dropdowns: scroll the form instead of changing the selection."""
        self._on_wheel(event)
        return "break"

    # -- building ---------------------------------------------------------

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self._getter = None
        self.canvas.yview_moveto(0)

    def load(self, data):
        self.clear()
        self._root = data
        self._getter = self._build(self.inner, data)
        # Make sure the scrollable area matches the new content right away.
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def get_value(self):
        return self._getter() if self._getter else None

    # Each _build returns a zero-arg function that reads the widget's value back.
    def _build(self, parent, value, key=None, choice_key=None, unlock_name=False, label=None):
        if isinstance(value, dict):
            return self._build_dict(parent, value, key, unlock_name)
        if isinstance(value, list):
            return self._build_list(parent, value, key)

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=6, pady=2)
        name = label or (pretty(key) if key is not None else "")
        if key is not None:
            ttk.Label(row, text=name, width=28, anchor="w").pack(side="left")

        if isinstance(value, bool):
            var = tk.BooleanVar(value=value)
            ttk.Checkbutton(row, variable=var).pack(side="left")
            return var.get

        options = choices_for(choice_key or key, value)
        if options:
            var = tk.StringVar(value=value)
            box = ttk.Combobox(row, textvariable=var, values=options, state="readonly")
            box.pack(side="left", fill="x", expand=True)
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                box.bind(seq, self._wheel_break)
            return var.get

        if isinstance(value, int):
            var = tk.StringVar(value=str(value))
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            return lambda: self._to_number(var.get(), int, name)

        if isinstance(value, float):
            var = tk.StringVar(value=repr(value))
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            return lambda: self._to_number(var.get(), float, name)

        if isinstance(value, str):
            var = tk.StringVar(value=value)
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            return var.get

        # lists / null / anything else: edit as raw JSON text
        var = tk.StringVar(value=json.dumps(value))
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Label(row, text="(JSON)", foreground="gray").pack(side="left", padx=4)

        def get_json():
            try:
                return json.loads(var.get())
            except json.JSONDecodeError as e:
                raise ValueError(f"'{name}' is not valid JSON: {e}")

        return get_json

    def _build_dict(self, parent, data, key, unlock_name=False):
        if is_param(data):
            # Parameter entry: show only its value, labelled with the parameter's name.
            # "name" and "type" are passed through to corvus unchanged.
            # Units are not shown at all (they are still sent to corvus unchanged).
            value_getter = self._build(parent, data["value"], data["name"], label=pretty(data["name"]))
            return lambda: {**data, "value": value_getter()}

        if key is None:
            frame = parent
        else:
            frame = ttk.LabelFrame(parent, text=pretty(key))
            frame.pack(fill="x", padx=6, pady=4)

        getters = {}
        for child_key, child_val in data.items():
            # "name" and "type" are fixed: passed to corvus unchanged, not editable.
            # (Only the name of an item you add yourself with "+ Add" can be typed.)
            # "unit" / "units" are not shown at all, but still sent to corvus unchanged.
            locked = child_key in ("type", "unit", "units") or (
                child_key == "name" and not unlock_name
            )
            if child_key in HIDDEN_FIELDS or (locked and isinstance(child_val, str)):
                getters[child_key] = lambda v=child_val: v
                show = child_key == "name" and data is getattr(self, "_root", None)
                if show and child_key not in HIDDEN_FIELDS:
                    row = ttk.Frame(frame)
                    row.pack(fill="x", padx=6, pady=2)
                    ttk.Label(row, text=pretty(child_key), width=28, anchor="w").pack(side="left")
                    ttk.Label(row, text=child_val).pack(side="left")
                continue

            # For {"name": "NeutralMode", "value": ...} style entries, the sibling
            # "name" decides what kind of input "value" gets (e.g. Brake/Coast dropdown).
            choice_key = None
            if child_key == "value" and isinstance(data.get("name"), str):
                choice_key = data["name"]
            getters[child_key] = self._build(frame, child_val, child_key, choice_key)
        return lambda: {k: get() for k, get in getters.items()}

    def _build_list(self, parent, items, key):
        """A list becomes one group per item (own fields) with Add / Remove buttons."""
        label = pretty(key) if key is not None else "Items"
        frame = ttk.LabelFrame(parent, text=label)
        frame.pack(fill="x", padx=6, pady=4)

        if items and all(is_param(item) for item in items):
            # A list of parameters: just one value input per parameter, no add/remove.
            getters = [self._build(frame, item) for item in items]
            return lambda: [get() for get in getters]

        holder = ttk.Frame(frame)
        holder.pack(fill="x")
        entries = []  # each entry is [container, getter]
        template = copy.deepcopy(items[-1]) if items else None  # what "Add" copies
        repeatable = flat_key(key) in REPEATABLE_LISTS

        def add_item(value, title, is_new=False):
            container = ttk.LabelFrame(holder, text=title)
            container.pack(fill="x", padx=4, pady=3)
            entry = [container, None]

            def remove():
                if entry in entries:
                    entries.remove(entry)
                container.destroy()

            if is_new:  # only items you added yourself can be removed
                header = ttk.Frame(container)
                header.pack(fill="x")
                ttk.Button(header, text="Remove", width=8, command=remove).pack(side="right", padx=4)
            entry[1] = self._build(container, value, None, None, unlock_name=is_new)
            entries.append(entry)

        for index, item in enumerate(items, start=1):
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                title = item["name"]
            else:
                title = f"{label} {index}"
            add_item(item, title)

        if repeatable:
            ttk.Button(
                frame,
                text=f"+ Add to {label}",
                command=lambda: add_item(copy.deepcopy(template), f"New {label} item", True),
            ).pack(anchor="w", padx=6, pady=4)

        return lambda: [entry[1]() for entry in entries]

    @staticmethod
    def _to_number(text, kind, name):
        try:
            return kind(text.strip())
        except ValueError:
            raise ValueError(f"'{name}' must be a {kind.__name__}, got '{text}'")


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} - Phoenix 6 mechanism generator")
        self.geometry("720x740")
        self.corvus = find_corvus()
        self.template_text = ""
        self.last_dir = DEFAULT_OUT_DIR if os.path.isdir(DEFAULT_OUT_DIR) else os.getcwd()
        self._build_ui()
        if not self.corvus:
            self.log("corvus not found. This app does not include it.")
            self.log(f"Download corvus from CTRE: {CORVUS_DOWNLOAD_URL}")
            self.log("Then put it next to this program, or click 'Browse for corvus...'.")
            self.after(300, self._offer_download)
        else:
            self.log(f"Using corvus: {self.corvus}")
            self.refresh_mechanisms()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(top, text="Mechanism:").pack(side="left")
        self.type_var = tk.StringVar()
        self.type_box = ttk.Combobox(top, textvariable=self.type_var, state="readonly", width=24)
        self.type_box.pack(side="left", padx=6)
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self.load_template())
        ttk.Button(top, text="Refresh", command=self.refresh_mechanisms).pack(side="left")
        ttk.Button(top, text="Browse for corvus...", command=self.browse_corvus).pack(side="right")
        ttk.Button(top, text="Get corvus (CTRE)...", command=self.open_download_page).pack(
            side="right", padx=6
        )

        ttk.Label(
            self, text=DISCLAIMER, foreground="gray", wraplength=690, justify="left"
        ).pack(fill="x", padx=8, pady=(0, 6))

        self.form = JsonForm(self)
        self.form.pack(fill="both", expand=True, padx=8)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=6)
        ttk.Button(bottom, text="Generate Java subsystem...", command=self.generate).pack(side="left")
        ttk.Button(bottom, text="Copy template JSON", command=self.copy_template).pack(side="left", padx=8)
        ttk.Label(bottom, text="Output language: Java", foreground="gray").pack(side="left", padx=10)

        self.log_box = tk.Text(self, height=9, state="disabled", wrap="word")
        self.log_box.pack(fill="x", padx=8, pady=(0, 8))

    # -- logging ----------------------------------------------------------

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def copy_template(self):
        if not self.template_text:
            self.log("No template loaded yet.")
            return
        self.clipboard_clear()
        self.clipboard_append(self.template_text)
        self.log("Template JSON copied to the clipboard.")

    # -- corvus discovery -------------------------------------------------

    def open_download_page(self):
        try:
            webbrowser.open(CORVUS_DOWNLOAD_URL)
            self.log(f"Opened {CORVUS_DOWNLOAD_URL}")
        except Exception as e:
            self.log(f"Could not open the browser ({e}). Go to: {CORVUS_DOWNLOAD_URL}")

    def _offer_download(self):
        if messagebox.askyesno(
            APP_TITLE,
            "corvus was not found.\n\n"
            "This app does not include corvus. CTR Electronics provides it "
            "on their CLI Tools page.\n\nOpen that page now?",
        ):
            self.open_download_page()

    def browse_corvus(self):
        chosen = filedialog.askopenfilename(
            title="Select corvus executable",
            initialdir=app_dir(),
            filetypes=[("Programs", "*.exe"), ("All files", "*.*")] if os.name == "nt"
            else [("All files", "*.*")],
        )
        if not chosen:
            return
        path = resolve_corvus_path(chosen)
        if not path:
            self.log(f"Could not use '{chosen}': file does not exist or is not a file.")
            return
        # Check it actually runs before accepting it.
        code, out = run_corvus(path, ["--help"], timeout=20)
        if code == -1:
            self.log(f"That file could not be started:\n{out}")
            return
        self.corvus = path
        save_corvus_choice(path)
        self.log(f"Using corvus: {path}")
        self.refresh_mechanisms()

    def refresh_mechanisms(self):
        if not self.corvus:
            self.log("corvus not found yet. Use 'Get corvus (CTRE)...' or 'Browse for corvus...'.")
            return
        names, diag = discover_mechanisms(self.corvus)
        if names is FALLBACK_TYPES:
            self.log("Could not read the mechanism list from corvus; using a default list.")
            if diag:
                self.log(diag)
        self.type_box["values"] = names
        if self.type_var.get() not in names:
            self.type_var.set(names[0])
        self.load_template()

    def load_template(self):
        mech = self.type_var.get()
        if not (self.corvus and mech):
            return
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "template.json")
            code, out = run_corvus(self.corvus, ["json", mech, path])
            if code != 0 or not os.path.isfile(path):
                self.form.clear()
                self.template_text = ""
                self.log(f"Could not create a template for '{mech}' (exit code {code}):\n{out}")
                return
            try:
                with open(path, encoding="utf-8") as f:
                    self.template_text = f.read()
                data = json.loads(self.template_text)
            except (OSError, json.JSONDecodeError) as e:
                self.log(f"Template for '{mech}' was not valid JSON: {e}")
                return
        self.form.load(data)
        self.log(f"Loaded '{mech}' template.")

    # -- generate ---------------------------------------------------------

    def generate(self):
        mech = self.type_var.get()
        if not (self.corvus and mech):
            messagebox.showerror(APP_TITLE, "Pick a mechanism and make sure corvus is found.")
            return
        try:
            spec = self.form.get_value()
        except ValueError as e:
            messagebox.showerror("Invalid value", str(e))
            return

        out_path = filedialog.asksaveasfilename(
            title="Save generated subsystem as",
            initialdir=self.last_dir,
            initialfile=f"{mech.capitalize()}.java",
            defaultextension=".java",
            filetypes=[("Java file", "*.java"), ("All files", "*.*")],
        )
        if not out_path:
            return
        self.last_dir = os.path.dirname(out_path)

        with tempfile.TemporaryDirectory() as tmp:
            spec_path = os.path.join(tmp, f"{mech}.json")
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            code, out = run_corvus(self.corvus, [mech, LANGUAGE, "-i", spec_path, "-o", out_path])

        if out.strip():
            self.log(out)
        if code == 0:
            self.log(f"Done: {out_path}")
            messagebox.showinfo(APP_TITLE, f"Saved:\n{out_path}")
        else:
            self.log(f"corvus failed (exit code {code}).")
            messagebox.showerror(APP_TITLE, "corvus failed - see the log at the bottom.")


if __name__ == "__main__":
    App().mainloop()