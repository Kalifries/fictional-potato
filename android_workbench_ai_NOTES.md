# android_workbench_ai — notes (what changed and why)

This file is intentionally separate from `android-workbench-v1.2.py` so you can learn by diffing.

## Run it

```bash
python3 ~/scripts/android_workbench_ai.py
```

(Optionally make executable)

```bash
chmod +x ~/scripts/android_workbench_ai.py
```

## Diff it against v1.2

```bash
diff -u ~/scripts/android-workbench-v1.2.py ~/scripts/android_workbench_ai.py | less
```

## New menu options added

- **Device Summary**: quick getprop + battery + uptime.
- **Screenrecord**: records for N seconds and pulls MP4 to `~/scripts/android_media/`.
- **Foreground**: shows the resumed/top activity from `dumpsys`.
- **Install APK**: prompts for an APK path and runs `adb install -r`.
- **Clear app data**: prompts for a package name and runs `pm clear`.
- **Open URL**: launches a browser intent via `am start`.
- **Screenshot**: uses `adb exec-out screencap -p` and writes a PNG to `~/scripts/android_media/`.
- **Fastboot getvar all**: prints variables (fastboot often uses stderr).
- **Fastboot reboot menu**: reboot/reboot bootloader/reboot recovery.

## Design choices

- **Streaming** is used only when it makes sense (logcat follow).
  - If you capture output (`capture_output=True`), you won’t see live updates.

- Avoided dangerous fastboot actions.
  - No flash / erase / format / unlock / oem commands.

## Next improvements you can do

- Add a mini "help" screen (show example package names, how to find them, etc.).
- Add "pick package" helper: `adb shell pm list packages | fzf` (if you want dependencies).
- Add better detection for ADB vs Fastboot connected devices.
- Add consistent output paging (pipe long output through `less`).
