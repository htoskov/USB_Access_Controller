# USB Access Control (Windows)

A lightweight, open-source tray utility for Windows that **locks and unlocks USB device installation/access** with a human approval step. It’s designed to reduce the risk of opportunistic or low-skill attacks that rely on quickly plugging in new devices (HID injection devices) and to optionally block **USB storage** (flash drives) when locked.

This is **not** a kernel driver or enterprise endpoint solution. It’s a user-space control layer that toggles **Windows policy settings** to raise the bar against casual misuse.

---

## Security posture and threat model

This tool follows a **defensive, convenience-oriented threat model**, not a high-assurance one.

It is effective against:
- “Plug-and-run” HID injection attempts that rely on immediate acceptance/install
- Casual/low-skill HID attack devices
- Opportunistic use of USB flash drives when the system is set to “locked”
- Situations where you want a quick “lockdown” switch for HID installs + removable storage access

It is **not designed to stop**:
- A determined attacker with local admin access
- Malware already running on the system
- Kernel/driver-level USB attacks
- Hardware attacks that don’t rely on Windows install/access paths
- Someone willing to disable policies, tamper with the process, or reconfigure the machine

---

## How it works (high level)

The tool uses a small elevated helper to toggle Windows policy keys under:

- Device installation restrictions (deny HID/keyboard/mouse install classes)
- Removable storage access (deny removable storage access)

Because these are **system-wide policies**, Windows will require Administrator approval (UAC) unless you deploy a pre-authorized mechanism (e.g., scheduled task “run with highest privileges”).

---

## Password handling (important)

⚠️ **Current implementation uses a hardcoded password in the GUI.**

---

## Limitations

- User-space tool (not a driver)
- Policies can be changed/tampered with by an admin user or malware
- Does not provide cryptographic device identity or true attestation
- Users still need admin elevation (UAC) for policy changes unless you pre-authorize via scheduled task/service
- The tool does not “retroactively kill” already-working devices (safer default)

---

## Requirements

- Windows 10 / Windows 11
- Python 3.10+
- Required packages:

## How to run (from project directory)
```Powershell
.\install_autostart.ps1
```

```bash
pip install pywin32 pystray pillow
