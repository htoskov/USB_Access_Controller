# hid_guard_helper.py
import sys
import subprocess
import winreg

RESTRICTIONS = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"
REMOVABLE_STORAGE = r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices"

KEYBOARD_CLASS_GUID = "{4D36E96B-E325-11CE-BFC1-08002BE10318}"
MOUSE_CLASS_GUID    = "{4D36E96F-E325-11CE-BFC1-08002BE10318}"
HIDCLASS_GUID       = "{745A17A0-74D3-11D0-B6FE-00A0C90F57DA}"

DENY_CLASS_GUIDS = [KEYBOARD_CLASS_GUID, MOUSE_CLASS_GUID, HIDCLASS_GUID]

def _set_dword(path, name, value: int) -> None:
    k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))
    finally:
        winreg.CloseKey(k)

def _write_list_values(subkey_path: str, items) -> None:
    k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
    try:
        # clear existing
        try:
            i = 0
            while True:
                name, _, _ = winreg.EnumValue(k, i)
                winreg.DeleteValue(k, name)
        except OSError:
            pass

        for idx, item in enumerate(items, start=1):
            winreg.SetValueEx(k, str(idx), 0, winreg.REG_SZ, str(item))
    finally:
        winreg.CloseKey(k)

def gpupdate() -> None:
    subprocess.run(["gpupdate", "/force"], check=False)

def lock_all() -> None:
    # 1) Deny HID/Keyboard/Mouse installs by class GUID (no allowlists)
    _set_dword(RESTRICTIONS, "DenyDeviceClasses", 1)
    _write_list_values(RESTRICTIONS + r"\DenyDeviceClasses", DENY_CLASS_GUIDS)
    _set_dword(RESTRICTIONS, "DenyDeviceClassesRetroactive", 0)

    # keep legacy allow/deny lists off
    _set_dword(RESTRICTIONS, "DenyUnspecified", 0)
    _set_dword(RESTRICTIONS, "AllowDeviceInstanceIDs", 0)
    _set_dword(RESTRICTIONS, "AllowDeviceIDs", 0)

    # 2) Deny ALL removable storage access (flash drives)
    # Policy: "All Removable Storage classes: Deny all access" -> Deny_All=1 :contentReference[oaicite:1]{index=1}
    _set_dword(REMOVABLE_STORAGE, "Deny_All", 1)

    gpupdate()

def unlock_all() -> None:
    # Allow HID installs
    _set_dword(RESTRICTIONS, "DenyDeviceClasses", 0)
    _set_dword(RESTRICTIONS, "DenyUnspecified", 0)
    _set_dword(RESTRICTIONS, "AllowDeviceInstanceIDs", 0)
    _set_dword(RESTRICTIONS, "AllowDeviceIDs", 0)
    _set_dword(RESTRICTIONS, "DenyDeviceClassesRetroactive", 0)

    # Allow removable storage
    _set_dword(REMOVABLE_STORAGE, "Deny_All", 0)

    gpupdate()

def status() -> int:
    # 1 = locked, 0 = unlocked
    locked_hid = 0
    locked_storage = 0

    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, RESTRICTIONS, 0, winreg.KEY_READ)
        try:
            v, _ = winreg.QueryValueEx(k, "DenyDeviceClasses")
            locked_hid = 1 if int(v) == 1 else 0
        finally:
            winreg.CloseKey(k)
    except OSError:
        pass

    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REMOVABLE_STORAGE, 0, winreg.KEY_READ)
        try:
            v, _ = winreg.QueryValueEx(k, "Deny_All")
            locked_storage = 1 if int(v) == 1 else 0
        finally:
            winreg.CloseKey(k)
    except OSError:
        pass

    return 1 if (locked_hid == 1 and locked_storage == 1) else 0

def main():
    if len(sys.argv) < 2:
        print("Missing cmd: lock_all|unlock_all|status")
        sys.exit(2)

    cmd = sys.argv[1].lower()

    try:
        if cmd == "lock_all":
            lock_all()
            print("LOCKED (HID installs denied + USB storage denied).")
            return
        if cmd == "unlock_all":
            unlock_all()
            print("UNLOCKED (HID installs allowed + USB storage allowed).")
            return
        if cmd == "status":
            print(status())
            return

        print("Unknown cmd:", cmd)
        sys.exit(2)

    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
