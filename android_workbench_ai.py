#!/usr/bin/env python3
"""android_workbench_ai.py — AI-modified training version (based on android-workbench-v1.2.py)

Sully constraints:
- DO NOT modify android-workbench-v1.2.py without asking first.
- This file is a separate playground with extra options so you can diff/learn hands-on.

What’s new vs v1.2 (high level):
- Single main menu (still) but with extra ADB/Fastboot utilities you requested:
  1) Device Summary
  3) Screenrecord (pull to host)
  4) Foreground app/activity
  5) Install APK
  6) Clear app data
  7) Open URL
  8) Fastboot getvar all
  9) Fastboot reboot/recovery options
- Small UI cleanups: consistent box rendering, menu ordering, tighter output.

Notes:
- “Live follow logcat” is inherently a streaming command. This file keeps streaming for that option.
- Anything destructive (fastboot flash, wipe, unlock) is intentionally NOT included.

Suggested learning workflow:
- Run both files and compare behaviors.
- Diff the files:
    diff -u ~/scripts/android-workbench-v1.2.py ~/scripts/android_workbench_ai.py | less
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# --- Paths ---
REPORT_DIR = Path.home() / "scripts" / "android-reports"
LOG_DIR = Path.home() / "scripts" / "android_logs"
MEDIA_DIR = Path.home() / "scripts" / "android_media"

# --- ANSI ---
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
NEON_PINK = "\x1b[38;5;213m"
NEON_CYAN = "\x1b[38;5;51m"
NEON_GREEN = "\x1b[38;5;46m"
NEON_PURPLE = "\x1b[38;5;141m"
NEON_YELLOW = "\x1b[38;5;226m"
NEON_RED = "\x1b[38;5;196m"
GRAY = "\x1b[38;5;245m"


def clear() -> None:
    print("\x1b[2j\x1b[H", end="")


def box(lines: list[str], *, title: str = "") -> str:
    width = max([len(s) for s in lines] + [len(title)]) if (lines or title) else 0
    top = "+" + "-" * (width + 2) + "+"
    if title:
        t = f" {title}"
        top = "+" + t.ljust(width + 2, "-") + "+"

    out: list[str] = [top]
    for s in lines:
        out.append("| " + s.ljust(width) + " |")
    out.append("+" + "-" * (width + 2) + "+")
    return "\n".join(out)


def banner() -> str:
    lines = [
        NEON_CYAN + BOLD + "ANDROID WORKBENCH" + RESET + " " + DIM + "ai" + RESET,
        GRAY + "based on v1.2 — extra ADB/Fastboot options" + RESET,
    ]
    return box(lines, title=NEON_PURPLE + "OPENCLAW" + RESET)


def status_line(serial: str | None, dry_run: bool) -> str:
    s = serial or "(none)"
    run_state = (NEON_YELLOW + "DRY" + RESET) if dry_run else (NEON_GREEN + "LIVE" + RESET)
    now = datetime.now().strftime("%H:%M:%S")
    return f"{GRAY}serial:{RESET} {NEON_CYAN}{s}{RESET}  {GRAY}run:{RESET} {run_state}  {GRAY}{now}{RESET}"


@dataclass
class Ctx:
    serial: str | None = None
    dry_run: bool = False
    verbose: bool = True


def run_capture(cmd: list[str], *, check: bool = True, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def run(cmd: list[str], *, check: bool = True, timeout: int = 30) -> str:
    return run_capture(cmd, check=check, timeout=timeout).stdout


def run_stream(cmd: list[str]) -> int:
    # Stream output directly (no capture). Use for tail-like commands (logcat follow, screenrecord progress, etc.)
    p = subprocess.run(cmd, check=False)
    return p.returncode


def adb_base(ctx: Ctx) -> list[str]:
    return ["adb", "-s", ctx.serial] if ctx.serial else ["adb"]


def fastboot_base(ctx: Ctx) -> list[str]:
    return ["fastboot", "-s", ctx.serial] if ctx.serial else ["fastboot"]


def parse_adb_devices(output: str) -> list[str]:
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    serials: list[str] = []
    for ln in lines[1:]:
        parts = ln.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def pick_adb_serial() -> str | None:
    out = run(["adb", "devices", "-l"], timeout=10)
    serials = parse_adb_devices(out)
    if not serials:
        return None
    if len(serials) == 1:
        return serials[0]

    print("Multiple ADB devices detected:")
    for i, s in enumerate(serials, start=1):
        print(f" {i}) {s}")
    choice = input("Pick one: ").strip()
    if not choice.isdigit():
        return None
    idx = int(choice)
    return serials[idx - 1] if 1 <= idx <= len(serials) else None


# -----------------
# Actions (existing)
# -----------------

def action_status(ctx: Ctx) -> None:
    print()
    print("ADB devices:")
    print(run(["adb", "devices", "-l"], timeout=10))
    print("Fastboot devices:")
    print(run(["fastboot", "devices"], timeout=10))


def action_report(ctx: Ctx) -> None:
    if not ctx.serial:
        print("No ADB serial selected (device must be authorized and in Android).")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"report-{ctx.serial}-{ts}.txt"

    def getprop(key: str) -> str:
        cmd = adb_base(ctx) + ["shell", "getprop", key]
        return run(cmd, timeout=15).strip()

    lines: list[str] = []
    lines.append(f"serial: {ctx.serial}")
    lines.append(f"when: {datetime.now().isoformat()}")
    lines.append("")
    lines.append(f"model: {getprop('ro.product.model')}")
    lines.append(f"android: {getprop('ro.build.version.release')}")
    lines.append(f"security_patch: {getprop('ro.build.version.security_patch')}")
    lines.append(f"fingerprint: {getprop('ro.build.fingerprint')}")
    lines.append(f"abi: {getprop('ro.product.cpu.abi')}")
    lines.append("")
    lines.append("id:")
    lines.append(run(adb_base(ctx) + ["shell", "id"], timeout=10).strip())

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote: {path}")


def action_logcat_lab(ctx: Ctx) -> None:
    if not ctx.serial:
        print(NEON_RED + "No ADB serial selected." + RESET)
        input(GRAY + "Press Enter..." + RESET)
        return

    print()
    lines = [
        f"{NEON_CYAN}l1{RESET}) Dump last 200 lines (all buffers)",
        f"{NEON_CYAN}l2{RESET}) Live follow (all buffers)",
        f"{NEON_CYAN}l3{RESET}) Crashes only (AndroidRuntime)",
        f"{NEON_CYAN}l4{RESET}) SELinux denials (avc)",
        f"{NEON_CYAN}l5{RESET}) Filter by tag",
        f"{NEON_CYAN}l6{RESET}) Filter by regex (host regex)",
        f"{NEON_CYAN}l7{RESET}) Save dump to file",
        f"{NEON_CYAN}l8{RESET}) Clear logcat buffers (confirm)",
        f"{NEON_CYAN}b{RESET}) Back",
    ]
    print(box(lines, title=NEON_PINK + "LOGCAT LAB" + RESET))

    choice = input(NEON_PINK + "> " + RESET).strip().lower()
    if choice == "b":
        return

    out_path: Path | None = None
    regex_s: str | None = None

    if choice == "l1":
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-t", "200", "-v", "time"]
        out = run(cmd, timeout=60)

    elif choice == "l2":
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-v", "time"]
        if ctx.dry_run:
            print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
            input(GRAY + "Press Enter..." + RESET)
            return
        print(GRAY + "Streaming logcat. Ctrl+C to stop." + RESET)
        run_stream(cmd)
        return

    elif choice == "l3":
        cmd = adb_base(ctx) + ["logcat", "-v", "time", "AndroidRuntime:E", "*:S"]
        out = run(cmd, timeout=60)

    elif choice == "l4":
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]
        out = run(cmd, timeout=60)
        out = "\n".join([ln for ln in out.splitlines() if "avc:" in ln.lower()])

    elif choice == "l5":
        tag = input("Tag (e.g. ActivityManager): ").strip()
        if not tag:
            return
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time", f"{tag}:V", "*:S"]
        out = run(cmd, timeout=60)

    elif choice == "l6":
        regex_s = input("Regex: ").strip()
        if not regex_s:
            return
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]
        out = run(cmd, timeout=60)
        try:
            rx = re.compile(regex_s)
        except re.error as e:
            print(NEON_RED + f"Bad regex: {e}" + RESET)
            input(GRAY + "Press Enter..." + RESET)
            return
        out = "\n".join([ln for ln in out.splitlines() if rx.search(ln)])

    elif choice == "l7":
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = LOG_DIR / f"logcat-{ctx.serial}-{ts}.txt"
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]
        out = run(cmd, timeout=60)

    elif choice == "l8":
        confirm = input("This clears log buffers. Type YES to continue: ").strip()
        if confirm != "YES":
            return
        cmd = adb_base(ctx) + ["logcat", "-b", "all", "-c"]
        out = run(cmd, timeout=30)

    else:
        return

    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    if out_path is not None:
        out_path.write_text(out, encoding="utf-8")
        print(f"Wrote: {out_path}")
    else:
        print(out)

    input(GRAY + "Press Enter..." + RESET)


# -----------------
# Actions (new)
# -----------------

def require_serial(ctx: Ctx) -> bool:
    if ctx.serial:
        return True
    print(NEON_RED + "No ADB serial selected." + RESET)
    input(GRAY + "Press Enter..." + RESET)
    return False


def adb_getprop(ctx: Ctx, key: str) -> str:
    return run(adb_base(ctx) + ["shell", "getprop", key], timeout=15).strip()


def action_device_summary(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    def sh(*args: str, timeout: int = 20) -> str:
        return run(adb_base(ctx) + ["shell", *args], timeout=timeout).strip()

    model = adb_getprop(ctx, "ro.product.model")
    android = adb_getprop(ctx, "ro.build.version.release")
    patch = adb_getprop(ctx, "ro.build.version.security_patch")
    fp = adb_getprop(ctx, "ro.build.fingerprint")
    abi = adb_getprop(ctx, "ro.product.cpu.abi")
    batt = sh("dumpsys", "battery")
    uptime = sh("uptime")

    lines = [
        f"model: {model}",
        f"android: {android}",
        f"security_patch: {patch}",
        f"abi: {abi}",
        f"fingerprint: {fp}",
        "",
        "uptime:",
        uptime,
        "",
        "battery:",
        *batt.splitlines()[:40],
    ]
    print(box(lines, title=NEON_PINK + "DEVICE SUMMARY" + RESET))
    input(GRAY + "Press Enter..." + RESET)


def action_foreground_app(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    out = run(adb_base(ctx) + ["shell", "dumpsys", "activity", "activities"], timeout=30)
    hits = []
    for ln in out.splitlines():
        if "mResumedActivity" in ln or "topResumedActivity" in ln:
            hits.append(ln.strip())

    # Fallback: sometimes new Android versions change wording; also try window focus
    if not hits:
        out2 = run(adb_base(ctx) + ["shell", "dumpsys", "window"], timeout=30)
        for ln in out2.splitlines():
            if "mCurrentFocus" in ln or "mFocusedApp" in ln:
                hits.append(ln.strip())

    lines = hits if hits else ["(No foreground activity line found — dumpsys output format may differ.)"]
    print(box(lines, title=NEON_PINK + "FOREGROUND" + RESET))
    input(GRAY + "Press Enter..." + RESET)


def action_install_apk(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    apk = input("Path to APK (e.g. ~/Downloads/app.apk): ").strip()
    if not apk:
        return
    apk_path = Path(apk).expanduser()
    if not apk_path.exists():
        print(NEON_RED + f"Not found: {apk_path}" + RESET)
        input(GRAY + "Press Enter..." + RESET)
        return

    cmd = adb_base(ctx) + ["install", "-r", str(apk_path)]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    cp = run_capture(cmd, check=False, timeout=300)
    print(cp.stdout.strip())
    if cp.stderr.strip():
        print(GRAY + cp.stderr.strip() + RESET)
    input(GRAY + "Press Enter..." + RESET)


def action_clear_app_data(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    pkg = input("Package to clear (e.g. com.example.app): ").strip()
    if not pkg:
        return

    cmd = adb_base(ctx) + ["shell", "pm", "clear", pkg]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    out = run(cmd, check=False, timeout=60).strip()
    print(out or "(no output)")
    input(GRAY + "Press Enter..." + RESET)


def action_open_url(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    url = input("URL (https://...): ").strip()
    if not url:
        return

    cmd = adb_base(ctx) + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    out = run(cmd, check=False, timeout=30).strip()
    print(out or "(no output)")
    input(GRAY + "Press Enter..." + RESET)


def action_screenshot(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = MEDIA_DIR / f"screenshot-{ctx.serial}-{ts}.png"

    cmd = adb_base(ctx) + ["exec-out", "screencap", "-p"]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd), f"> {out_path}")
        input(GRAY + "Press Enter..." + RESET)
        return

    # exec-out returns PNG bytes on stdout
    p = subprocess.run(cmd, capture_output=True, check=False)
    if p.returncode != 0:
        print(NEON_RED + "screencap failed" + RESET)
        if p.stderr:
            print(p.stderr.decode(errors="ignore"))
        input(GRAY + "Press Enter..." + RESET)
        return

    out_path.write_bytes(p.stdout)
    print(f"Wrote: {out_path}")
    input(GRAY + "Press Enter..." + RESET)


def action_screenrecord(ctx: Ctx) -> None:
    if not require_serial(ctx):
        return

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    device_path = f"/sdcard/workbench-record-{ts}.mp4"
    host_path = MEDIA_DIR / f"screenrecord-{ctx.serial}-{ts}.mp4"

    dur_s = input("Duration seconds (max 180, default 15): ").strip()
    duration = 15
    if dur_s:
        try:
            duration = int(dur_s)
        except ValueError:
            duration = 15
    duration = max(1, min(duration, 180))

    cmd = adb_base(ctx) + ["shell", "screenrecord", "--time-limit", str(duration), device_path]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        print(GRAY + "Then: adb pull" + RESET, device_path, str(host_path))
        input(GRAY + "Press Enter..." + RESET)
        return

    print(GRAY + f"Recording for {duration}s..." + RESET)
    run_capture(cmd, check=False, timeout=duration + 30)

    pull_cmd = adb_base(ctx) + ["pull", device_path, str(host_path)]
    cp = run_capture(pull_cmd, check=False, timeout=300)
    if cp.returncode == 0:
        print(f"Wrote: {host_path}")
        run_capture(adb_base(ctx) + ["shell", "rm", "-f", device_path], check=False, timeout=30)
    else:
        print(NEON_RED + "pull failed" + RESET)
        print(cp.stdout.strip())
        print(cp.stderr.strip())

    input(GRAY + "Press Enter..." + RESET)


def action_fastboot_getvar_all(ctx: Ctx) -> None:
    cmd = fastboot_base(ctx) + ["getvar", "all"]
    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    cp = run_capture(cmd, check=False, timeout=60)
    out = (cp.stdout or "") + (cp.stderr or "")
    print(out.strip() or "(no output)")
    input(GRAY + "Press Enter..." + RESET)


def action_fastboot_reboot_menu(ctx: Ctx) -> None:
    print()
    lines = [
        f"{NEON_CYAN}f1{RESET}) fastboot reboot",
        f"{NEON_CYAN}f2{RESET}) fastboot reboot bootloader",
        f"{NEON_CYAN}f3{RESET}) fastboot reboot recovery",
        f"{NEON_CYAN}b{RESET}) Back",
    ]
    print(box(lines, title=NEON_PINK + "FASTBOOT REBOOT" + RESET))
    choice = input(NEON_PINK + "> " + RESET).strip().lower()
    if choice == "b":
        return

    if choice == "f1":
        cmd = fastboot_base(ctx) + ["reboot"]
    elif choice == "f2":
        cmd = fastboot_base(ctx) + ["reboot", "bootloader"]
    elif choice == "f3":
        cmd = fastboot_base(ctx) + ["reboot", "recovery"]
    else:
        return

    if ctx.dry_run:
        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
        input(GRAY + "Press Enter..." + RESET)
        return

    cp = run_capture(cmd, check=False, timeout=60)
    out = (cp.stdout or "") + (cp.stderr or "")
    print(out.strip() or "(no output)")
    input(GRAY + "Press Enter..." + RESET)


# -----------------
# Main Menu
# -----------------

def menu(serial: str | None = None) -> None:
    ctx = Ctx(serial=serial or pick_adb_serial())

    while True:
        clear()
        print(banner())
        print(status_line(ctx.serial, ctx.dry_run))
        print()

        menu_lines = [
            f"{NEON_CYAN}1{RESET} Status (adb/fastboot devices)",
            f"{NEON_CYAN}2{RESET} Write quick report",
            f"{NEON_CYAN}3{RESET} Reboot bootloader (adb)",
            f"{NEON_CYAN}4{RESET} Logcat Lab",
            "",
            f"{NEON_CYAN}5{RESET} Device Summary (props/battery/uptime)",
            f"{NEON_CYAN}6{RESET} Screenrecord (pull to host)",
            f"{NEON_CYAN}7{RESET} Foreground app/activity",
            f"{NEON_CYAN}8{RESET} Install APK",
            f"{NEON_CYAN}9{RESET} Clear app data",
            f"{NEON_CYAN}u{RESET} Open URL on device",
            f"{NEON_CYAN}s{RESET} Screenshot (pull to host)",
            "",
            f"{NEON_CYAN}fa{RESET} Fastboot getvar all",
            f"{NEON_CYAN}fr{RESET} Fastboot reboot menu",
            "",
            f"{NEON_CYAN}d{RESET} Toggle dry-run",
            f"{NEON_CYAN}q{RESET} Quit",
        ]
        print(box(menu_lines, title=NEON_PINK + "MAIN MENU" + RESET))

        choice = input(NEON_PINK + "> " + RESET).strip().lower()

        if choice == "d":
            ctx.dry_run = not ctx.dry_run
            continue
        if choice == "q":
            return

        try:
            if choice == "1":
                action_status(ctx)
            elif choice == "2":
                action_report(ctx)
            elif choice == "3":
                if not ctx.serial:
                    print("No ADB serial selected.")
                else:
                    cmd = adb_base(ctx) + ["reboot", "bootloader"]
                    if ctx.dry_run:
                        print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))
                    else:
                        print("Running:", " ".join(cmd))
                        run(cmd, timeout=30)
                    input(GRAY + "Press Enter..." + RESET)
                    continue
            elif choice == "4":
                action_logcat_lab(ctx)
                continue
            elif choice == "5":
                action_device_summary(ctx)
                continue
            elif choice == "6":
                action_screenrecord(ctx)
                continue
            elif choice == "7":
                action_foreground_app(ctx)
                continue
            elif choice == "8":
                action_install_apk(ctx)
                continue
            elif choice == "9":
                action_clear_app_data(ctx)
                continue
            elif choice == "u":
                action_open_url(ctx)
                continue
            elif choice == "s":
                action_screenshot(ctx)
                continue
            elif choice == "fa":
                action_fastboot_getvar_all(ctx)
                continue
            elif choice == "fr":
                action_fastboot_reboot_menu(ctx)
                continue
            else:
                print("Unknown choice.")

        except subprocess.TimeoutExpired:
            print(NEON_RED + "Command timed out." + RESET)
        except subprocess.CalledProcessError as e:
            print(NEON_RED + "Command failed:" + RESET)
            print(" ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd))
            if e.stdout:
                print("\nstdout:\n" + e.stdout)
            if e.stderr:
                print("\nstderr:\n" + e.stderr)

        input(GRAY + "Press Enter to continue..." + RESET)


def main() -> None:
    parser = argparse.ArgumentParser(description="Android Workbench (AI training version)")
    parser.add_argument("--serial", help="ADB/Fastboot serial to use (skip interactive selection)")
    args = parser.parse_args()
    menu(serial=args.serial)


if __name__ == "__main__":
    main()
