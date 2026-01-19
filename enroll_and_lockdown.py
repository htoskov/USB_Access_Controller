import sys
import wmi
import win32api
import win32con

import os

HELPER = os.path.join(os.path.dirname(__file__), "hid_guard_helper.py")

def run_helper_elevated(args):
    python_exe = sys.executable
    params = f"\"{HELPER}\" " + " ".join(f"\"{a}\"" for a in args)
    return win32api.ShellExecute(0, "runas", python_exe, params, None, win32con.SW_SHOWNORMAL)

def collect_present_input_like_devices():
    """
    Collect *currently present* devices that are in Keyboard/Mouse/HID-ish space.
    We whitelist by PNPDeviceID (works as a practical instance ID string for policy lists).
    """
    c = wmi.WMI()
    ids = set()
    for d in c.Win32_PnPEntity():
        pnp = (getattr(d, "PNPDeviceID", "") or "").strip()
        name = (getattr(d, "Name", "") or "").strip()

        # Heuristics: include HID\*, ACPI\* (often internal), I2C\* (touchpad),
        # and anything that looks like keyboard/mouse in name.
        if not pnp:
            continue

        if pnp.startswith(("HID\\", "ACPI\\", "I2C\\", "ROOT\\")):
            if "KEYBOARD" in name.upper() or "MOUSE" in name.upper() or "HID" in name.upper():
                ids.add(pnp)

        # Many internal/built-in input devices still show as HID\...
        if pnp.startswith("HID\\"):
            ids.add(pnp)

    return sorted(ids)

def main():
    print("This will whitelist CURRENT HID/keyboard/mouse-related devices, then apply lockdown.")
    print("You will get a UAC prompt.\n")

    ids = collect_present_input_like_devices()
    if not ids:
        print("No devices detected to whitelist. Aborting.")
        sys.exit(1)

    print("Detected devices to whitelist (PNPDeviceID strings):")
    for x in ids:
        print("  ", x)

    # Add each to whitelist via elevated helper (adds + reapplies)
    # More efficient: you can add list file; keeping simple/reliable:
    for x in ids:
        run_helper_elevated(["add", x])

    # Final apply (in case)
    run_helper_elevated(["apply"])
    print("\nDone. Lockdown should now be active.")

if __name__ == "__main__":
    main()
