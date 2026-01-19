# hid_guard_tray.py
import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import messagebox

import pystray
from PIL import Image, ImageDraw

import pywintypes
import win32con, win32event, win32process, winerror
import win32com.shell.shell as shell
import win32com.shell.shellcon as shellcon

BASE_DIR = os.path.dirname(__file__)
HELPER = os.path.join(BASE_DIR, "hid_guard_helper.py")
LOG_PATH = os.path.join(BASE_DIR, "data", "tray.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

SCRIPT_PATH = os.path.abspath(sys.argv[0])

def log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass

PASSWORD = "12345"  # keep your guard


# ------------------ Elevated helper runner ------------------
def run_helper_elevated_wait(args, timeout_ms=60000):
    python_exe = sys.executable
    params = f"\"{HELPER}\" " + " ".join(f"\"{a}\"" for a in args)

    try:
        proc_info = shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="runas",
            lpFile=python_exe,
            lpParameters=params,
            nShow=win32con.SW_SHOWNORMAL,
        )

        hproc = proc_info["hProcess"]
        rc = win32event.WaitForSingleObject(hproc, timeout_ms)
        if rc == win32con.WAIT_TIMEOUT:
            return False, "timeout"

        exit_code = win32process.GetExitCodeProcess(hproc)
        return (exit_code == 0), f"exit_code={exit_code}"

    except pywintypes.error as e:
        code = getattr(e, "winerror", None)
        if code in (winerror.ERROR_CANCELLED, 1223):
            return False, "UAC canceled"
        return False, f"ShellExecuteEx error {code}: {e}"

    except Exception as e:
        return False, str(e)


def helper_status_locked():
    # helper prints 1 if locked else 0
    try:
        p = subprocess.run([sys.executable, HELPER, "status"], capture_output=True, text=True, timeout=5)
        return (p.stdout or "").strip() == "1"
    except Exception:
        return False


# ------------------ UI process (Tk) ------------------
class PasswordDialog:
    def __init__(self, parent, title, current_locked: bool, target_lock: bool):
        self.parent = parent
        self.value = None

        # --- Theme ---
        BG = "#121212"
        CARD = "#1E1E1E"
        FG = "#EAEAEA"
        MUTED = "#B0B0B0"
        ENTRY_BG = "#2A2A2A"
        BTN_BG = "#2D2D2D"
        BTN_ACTIVE = "#3A3A3A"
        BORDER = "#333333"
        ERROR = "#7CFC9A"
        OK = "#FF5A5A"

        status_text = "LOCKED" if current_locked else "UNLOCKED"
        status_color = OK if current_locked else ERROR  # Locked=green (safe), Unlocked=red (open)

        action_text = (
            "You are about to LOCK: HID installs will be denied and USB storage will be denied."
            if target_lock
            else "You are about to UNLOCK: HID installs allowed and USB storage allowed."
        )

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.resizable(False, False)
        self.win.configure(bg=BG)

        # Modal
        self.win.grab_set()
        self.win.attributes("-topmost", True)

        outer = tk.Frame(self.win, bg=BG, padx=18, pady=18)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=CARD, padx=18, pady=16, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="USB Access Control", bg=CARD, fg=FG, font=("Segoe UI", 13, "bold")).pack(anchor="w")

        # Status row
        row = tk.Frame(card, bg=CARD)
        row.pack(anchor="w", pady=(10, 6), fill="x")

        tk.Label(row, text="Current status:", bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(row, text=f" {status_text}", bg=CARD, fg=status_color, font=("Segoe UI", 10, "bold")).pack(side="left")

        # Action text
        tk.Label(
            card,
            text=action_text,
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=520,
        ).pack(anchor="w", pady=(4, 12))

        tk.Label(card, text="Password", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        self.var = tk.StringVar()
        self.entry = tk.Entry(
            card,
            textvariable=self.var,
            show="•",
            width=36,
            bg=ENTRY_BG,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            font=("Segoe UI", 10),
        )
        self.entry.pack(anchor="w", pady=(6, 6))

        self.status_lbl = tk.Label(card, text="", bg=CARD, fg=ERROR, font=("Segoe UI", 9))
        self.status_lbl.pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(card, bg=CARD, pady=14)
        btns.pack(fill="x")

        def style_button(btn: tk.Button):
            btn.configure(
                bg=BTN_BG,
                fg=FG,
                activebackground=BTN_ACTIVE,
                activeforeground=FG,
                relief="flat",
                bd=0,
                padx=16,
                pady=10,
                cursor="hand2",
                font=("Segoe UI", 10, "bold"),
            )

        cancel_btn = tk.Button(btns, text="Cancel", command=self.on_cancel)
        style_button(cancel_btn)
        cancel_btn.pack(side="right")

        ok_btn = tk.Button(btns, text="OK", command=self.on_ok)
        style_button(ok_btn)
        ok_btn.pack(side="right", padx=(0, 10))

        # Bindings
        self.win.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.entry.bind("<Return>", lambda _e: self.on_ok())
        self.entry.bind("<Escape>", lambda _e: self.on_cancel())

        # Clear error when typing
        def clear_error(*_):
            if self.status_lbl.cget("text"):
                self.status_lbl.config(text="")
        self.var.trace_add("write", clear_error)

        # Bigger window (consistent size)
        self.win.update_idletasks()
        self.win.minsize(580, 260)

        # Center + focus
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        x = (self.win.winfo_screenwidth() // 2) - (w // 2)
        y = (self.win.winfo_screenheight() // 2) - (h // 2)
        self.win.geometry(f"+{x}+{y}")

        self.win.lift()
        self.win.focus_force()
        self.entry.focus_set()

    def on_ok(self):
        self.value = self.var.get()
        self.win.destroy()

    def on_cancel(self):
        self.value = None
        self.win.destroy()

    def show(self):
        self.parent.wait_window(self.win)
        return self.value

def run_ui_toggle():
    try:
        log("UI process started: entering run_ui_toggle()")
        root = tk.Tk()
        root.withdraw()  # fully hide the root (no top-left ghost window)
        root.update_idletasks()

        current_locked = helper_status_locked()
        target_lock = not current_locked

        dlg = PasswordDialog(root, "USB Access Control", current_locked=current_locked, target_lock=target_lock)
        pw = dlg.show()

        if pw is None:
            root.destroy()
            return

        if pw != PASSWORD:
            messagebox.showerror("USB Access Control", "Wrong password.")
            root.destroy()
            return

        ok, err = run_helper_elevated_wait(["lock_all" if target_lock else "unlock_all"])
        if not ok:
            messagebox.showerror("USB Access Control", f"Failed: {err}")
        else:
            # After success, show new status in the success message
            new_status = "LOCKED" if target_lock else "UNLOCKED"
            messagebox.showinfo("USB Access Control", f"Done.\nNew status: {new_status}")

        root.destroy()
    except Exception as e:
        # If UI crashes instantly, you’ll see why in a messagebox + log
        try:
            log(f"UI crash: {e!r}")
        except Exception:
            pass
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("USB Access Control", f"UI error:\n{e}")
            r.destroy()
        except Exception:
            pass

# ------------------ Tray process (pystray) ------------------
def make_icon_image(locked: bool):
    """
    Locked  = RED
    Unlocked = GREEN
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Colors
    if locked:
        fill = (220, 60, 60, 255)      # red
        outline = (130, 20, 20, 255)
        letter = "L"
    else:
        fill = (70, 200, 120, 255)     # green
        outline = (20, 90, 45, 255)
        letter = "U"

    # Main circle
    d.ellipse((8, 8, 56, 56), fill=fill, outline=outline, width=3)

    # Inner highlight ring
    d.ellipse((14, 14, 50, 50), outline=(255, 255, 255, 60), width=2)

    # Big letter
    # (We keep it simple without font loading to avoid extra deps)
    d.text((26, 18), letter, fill=(255, 255, 255, 255))

    return img



def run_tray():
    locked = helper_status_locked()

    icon = pystray.Icon("hid_usb_guard")
    icon.icon = make_icon_image(locked)
    icon.title = "HID+USB Guard (LOCKED)" if locked else "HID+USB Guard (UNLOCKED)"

    def refresh():
        nonlocal locked
        locked = helper_status_locked()
        icon.icon = make_icon_image(locked)
        icon.title = "HID+USB Guard (LOCKED)" if locked else "HID+USB Guard (UNLOCKED)"

    def on_toggle(_icon, _item):
        try:
            log(f"Launching UI: {sys.executable} {SCRIPT_PATH} --ui-toggle")
            subprocess.Popen(
                [sys.executable, SCRIPT_PATH, "--ui-toggle"],
                cwd=BASE_DIR,
                close_fds=True,
            )
        except Exception as e:
            log(f"Failed to launch UI: {e!r}")

    def on_refresh(_icon, _item):
        refresh()

    def on_exit(_icon, _item):
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("Lock/Unlock (HID + USB storage)", on_toggle),
        pystray.MenuItem("Refresh status", on_refresh),
        pystray.MenuItem("Exit", on_exit),
    )

    # Optional: refresh every few seconds
    def poll():
        while True:
            time.sleep(5)
            try:
                refresh()
            except Exception:
                pass

    import threading
    threading.Thread(target=poll, daemon=True).start()

    icon.run()


def main():
    if "--ui-toggle" in sys.argv:
        run_ui_toggle()
    else:
        run_tray()


if __name__ == "__main__":
    main()
