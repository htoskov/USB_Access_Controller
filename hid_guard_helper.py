import sys
import json
import os
import subprocess
import winreg
from typing import List

RESTRICTIONS = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"
APPDATA_DIR = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "UsbAccessControl")
WHITELIST_PATH = os.path.join(APPDATA_DIR, "whitelist_instance_ids.json")

# Setup Class GUIDs
KEYBOARD_CLASS_GUID = "{4D36E96B-E325-11CE-BFC1-08002BE10318}"
MOUSE_CLASS_GUID    = "{4D36E96F-E325-11CE-BFC1-08002BE10318}"
HIDCLASS_GUID       = "{745A17A0-74D3-11D0-B6FE-00A0C90F57DA}"  # includes USB + non-USB HID :contentReference[oaicite:1]{index=1}

DENY_CLASS_GUIDS = [KEYBOARD_CLASS_GUID, MOUSE_CLASS_GUID, HIDCLASS_GUID]

def _ensure_dir() -> None:
    os.makedirs(APPDATA_DIR, exist_ok=True)

def load_whitelist() -> List[str]:
    _ensure_dir()
    if not os.path.exists(WHITELIST_PATH):
        return []
    with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return sorted(set(str(x) for x in data if x))

def save_whitelist(items: List[str]) -> None:
    _ensure_dir()
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(set(items)), f, indent=2)

def _set_dword(root, path, name, value: int) -> None:
    k = winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))
    finally:
        winreg.CloseKey(k)

def _write_list_values(root, subkey_path: str, items: List[str]) -> None:
    """
    Writes list entries as REG_SZ values "1","2","3"... under the given subkey.
    """
    k = winreg.CreateKeyEx(root, subkey_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
    try:
        # Clear existing values
        try:
            i = 0
            while True:
                name, _, _ = winreg.EnumValue(k, i)
                winreg.DeleteValue(k, name)
        except OSError:
            pass

        for idx, item in enumerate(items, start=1):
            winreg.SetValueEx(k, str(idx), 0, winreg.REG_SZ, item)
    finally:
        winreg.CloseKey(k)

def enable_layered_eval() -> None:
    # "Apply layered order of evaluation..." -> AllowDenyLayered = 1 :contentReference[oaicite:2]{index=2}
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "AllowDenyLayered", 1)

def apply_lockdown() -> None:
    """
    Deny Keyboard + Mouse + HIDClass installs, but allow devices in AllowDeviceInstanceIDs.
    NOTE: This does NOT set retroactive blocking.
    """
    wl = load_whitelist()
    if not wl:
        raise RuntimeError("Whitelist is empty. Enroll devices first to avoid lockout.")

    enable_layered_eval()

    # Allow list by instance ID (highest specificity) :contentReference[oaicite:3]{index=3}
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "DenyUnspecified", 1)
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "AllowDeviceInstanceIDs", 1)
    _write_list_values(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS + r"\AllowDeviceInstanceIDs", wl)

    # Deny by class GUIDs :contentReference[oaicite:4]{index=4}
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "DenyDeviceClasses", 1)
    _write_list_values(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS + r"\DenyDeviceClasses", DENY_CLASS_GUIDS)

    # Do NOT apply retroactive deny (safer)
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "DenyDeviceClassesRetroactive", 0)

def clear_lockdown() -> None:
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "DenyUnspecified", 0)
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "DenyDeviceClasses", 0)
    _set_dword(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, "AllowDeviceInstanceIDs", 0)

def add_to_whitelist(instance_id: str) -> None:
    wl = load_whitelist()
    if instance_id and instance_id not in wl:
        wl.append(instance_id)
        save_whitelist(wl)

def gpupdate() -> None:
    subprocess.run(["gpupdate", "/force"], check=False)

def main() -> None:
    """
    Usage (must be run elevated):
      py hid_guard_helper.py apply
      py hid_guard_helper.py clear
      py hid_guard_helper.py add "<DEVICE_INSTANCE_ID>"
    """
    if len(sys.argv) < 2:
        print("Missing cmd: apply|clear|add")
        sys.exit(2)

    cmd = sys.argv[1].lower()
    try:
        if cmd == "apply":
            apply_lockdown()
            gpupdate()
            print("Lockdown applied.")
        elif cmd == "clear":
            clear_lockdown()
            gpupdate()
            print("Lockdown cleared.")
        elif cmd == "add":
            if len(sys.argv) < 3:
                print("Missing instance ID")
                sys.exit(2)
            add_to_whitelist(sys.argv[2])
            apply_lockdown()
            gpupdate()
            print("Added + reapplied.")
        else:
            print("Unknown cmd:", cmd)
            sys.exit(2)
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
