import os
import sys
import json
import time
import tkinter as tk
from tkinter import messagebox

import wmi
import win32api
import win32event
import win32con
import winerror

# ---------- Paths ----------
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
APPDATA_DIR = os.path.join(DESKTOP_DIR, "USB_Access_Controller")
WHITELIST_PATH = os.path.join(APPDATA_DIR, "whitelist_instance_ids.json")
os.makedirs(APPDATA_DIR, exist_ok=True)
LOG_PATH = os.path.join(APPDATA_DIR, "tray.log")
HELPER = os.path.join(os.path.dirname(__file__), "hid_guard_helper.py")

def log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass

# ---------- Single instance (named mutex) ----------
try:
    mutex = win32event.CreateMutex(None, False, "Global\\USB_Access_Control_Tray")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        sys.exit(0)
except Exception as e:
    log(f"Mutex exception: {e!r}")

log("Tray started (instance OK).")

def load_whitelist():
    if not os.path.exists(WHITELIST_PATH):
        return set()
    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(x) for x in data if x)
    except Exception as e:
        log(f"Whitelist load error: {e!r}")
        return set()

def run_helper_elevated(args):
    python_exe = sys.executable
    params = f"\"{HELPER}\" " + " ".join(f"\"{a}\"" for a in args)
    log(f"Running helper elevated: {params}")
    return win32api.ShellExecute(0, "runas", python_exe, params, None, win32con.SW_HIDE)

def snapshot_hid_like():
    """
    Return a set of PNPDeviceIDs that look like HID input devices.
    """
    c = wmi.WMI()
    s = set()
    for d in c.Win32_PnPEntity():
        pnp = (getattr(d, "PNPDeviceID", "") or "").strip()
        name = (getattr(d, "Name", "") or "").strip().upper()
        if not pnp:
            continue
        if pnp.startswith(("HID\\", "USB\\")) and ("KEYBOARD" in name or "MOUSE" in name or "HID" in name):
            s.add(pnp)
    return s

def prompt_whitelist(pnp_id: str):
    log(f"Prompting for: {pnp_id}")

    PASSWORD = "12345"

    root = tk.Tk()
    root.title("USB Access Control")
    root.resizable(False, False)

    # Modal-ish behavior
    root.attributes("-topmost", True)
    root.grab_set()

    # --- Dark theme colors ---
    BG = "#121212"
    CARD = "#1E1E1E"
    FG = "#EAEAEA"
    MUTED = "#B0B0B0"
    ENTRY_BG = "#2A2A2A"
    BTN_BG = "#2D2D2D"
    BTN_ACTIVE = "#3A3A3A"
    BORDER = "#333333"
    ERROR = "#FF5A5A"

    root.configure(bg=BG)

    # Use ttk where it helps, but keep it simple with classic widgets
    # (ttk theming is inconsistent on some Windows setups without extra libs)
    result = {"ok": False}

    outer = tk.Frame(root, bg=BG, padx=14, pady=14)
    outer.pack(fill="both", expand=True)

    card = tk.Frame(outer, bg=CARD, padx=16, pady=14, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True)

    title = tk.Label(card, text="Blocked input device detected", bg=CARD, fg=FG, font=("Segoe UI", 12, "bold"))
    title.pack(anchor="w")

    subtitle = tk.Label(
        card,
        text="A new HID/keyboard/mouse device was detected.\nEnter password to whitelist (always allow).",
        bg=CARD,
        fg=MUTED,
        font=("Segoe UI", 9),
        justify="left",
    )
    subtitle.pack(anchor="w", pady=(6, 10))

    pnp_box = tk.Text(card, height=3, width=72, bg=ENTRY_BG, fg=FG, relief="flat", wrap="word")
    pnp_box.insert("1.0", pnp_id)
    pnp_box.configure(state="disabled")
    pnp_box.pack(fill="x", pady=(0, 12))

    tk.Label(card, text="Password", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")

    pw_var = tk.StringVar()
    entry = tk.Entry(
        card,
        textvariable=pw_var,
        show="•",
        width=28,
        bg=ENTRY_BG,
        fg=FG,
        insertbackground=FG,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=BORDER,
    )
    entry.pack(anchor="w", pady=(6, 6))
    entry.focus_set()

    status = tk.Label(card, text="", bg=CARD, fg=ERROR, font=("Segoe UI", 9))
    status.pack(anchor="w", pady=(2, 0))

    hint = tk.Label(
        card,
        text="This will trigger a Windows admin (UAC) prompt if accepted.",
        bg=CARD,
        fg=MUTED,
        font=("Segoe UI", 8),
    )
    hint.pack(anchor="w", pady=(10, 0))

    btn_row = tk.Frame(card, bg=CARD, pady=12)
    btn_row.pack(fill="x")

    def style_button(btn: tk.Button):
        btn.configure(
            bg=BTN_BG,
            fg=FG,
            activebackground=BTN_ACTIVE,
            activeforeground=FG,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def on_ok():
        if pw_var.get() != PASSWORD:
            status.config(text="Wrong password.")
            root.bell()
            return
        result["ok"] = True
        root.destroy()

    def on_cancel():
        result["ok"] = False
        root.destroy()

    cancel_btn = tk.Button(btn_row, text="Cancel", command=on_cancel)
    style_button(cancel_btn)
    cancel_btn.pack(side="right")

    ok_btn = tk.Button(btn_row, text="OK / Whitelist", command=on_ok)
    style_button(ok_btn)
    ok_btn.pack(side="right", padx=(0, 10))

    # Enter submits (same as OK)
    entry.bind("<Return>", lambda _e: on_ok())

    # Clear error as user types
    def clear_error(*_):
        if status.cget("text"):
            status.config(text="")

    pw_var.trace_add("write", clear_error)

    # Close button behaves like cancel
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    # Center window
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()

    log(f"Prompt result for {pnp_id}: {'YES' if result['ok'] else 'NO'}")
    return result["ok"]

def main():
    log("Entering main loop.")
    last = snapshot_hid_like()
    log(f"Initial snapshot: {len(last)} devices")

    while True:
        time.sleep(1.2)
        wl = load_whitelist()
        cur = snapshot_hid_like()
        added = cur - last

        if added:
            log(f"Detected added: {len(added)}")

        for dev in added:
            if dev in wl:
                log(f"Already whitelisted: {dev}")
                continue
            if prompt_whitelist(dev):
                run_helper_elevated(["add", dev])

        last = cur

if __name__ == "__main__":
    main()
