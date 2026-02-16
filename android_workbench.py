#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import Menu

REPORT_DIR = Path.home() / "scripts" / "android-reports"
LOG_DIR = Path.home() / "scripts" / "android_logs"

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

# 25-color ANSI (Konsole supports this). If it looks weird, we can turn it off.
NEON_PINK = "\x1b[38;5;213m"
NEON_CYAN = "\x1b[38;5;51m"
NEON_GREEN = "\x1b[38;5;46m"
NEON_PURPLE = "\x1b[38;5;141m"
NEON_YELLOW = "\x1b[38;5;226m"
NEON_RED = "\x1b[38;5;196m"
GRAY = "\x1b[38;5;245m"

def clear() -> None:
    # ANSI clear screen + cursor home
    print("\x1b[2j\x1b[H", end="")

def tw() -> int:
    return shutil.get_terminal_size((80, 20)).columns

def box(lines: list[str], *, title: str = "") -> str:
    width = max([len(s) for s in lines] + [len(title)]) if lines or title else 0
    top = "+" + "-" * (width + 2) + "+"
    if title:
        t = f" {title}"
        top = "+" + t.ljust(width + 2, "-") + "+"

    out = [top]
    for s in lines:
        out.append("| " + s.ljust(width) + " |")
    out.append("+" + "-" * (width + 2) + "+")
    return "\n".join(out)

def banner() -> str:
    lines = [
        NEON_CYAN + BOLD + "ANDROID WORKBENCH" + RESET + " " + DIM + "v0.1" + RESET,
        GRAY + "adb / fastboot operator console" + RESET,
    ]
    return box(lines, title=NEON_PURPLE + "" + RESET)

def status_line(serial: str | None, mode: str, dry_run: bool) -> str:
    s = serial or "(none)"
    run_state = (NEON_YELLOW + "DRY" + RESET) if dry_run else (NEON_GREEN + "LIVE" + RESET)
    now = datetime.now().strftime("%H:%M:%S")
    return (
        f"{GRAY}serial:{RESET} {NEON_CYAN}{s}{RESET} "
        f"{GRAY}mode:{RESET} {NEON_PINK}{mode}{RESET} "
        f"{GRAY}run:{RESET} {run_state}  {GRAY}{now}{RESET}"
    )

@dataclass
class Ctx:
    serial: str | None = None
    dry_run: bool = False
    verbose: bool = True


def run(cmd: list[str], *, check: bool = True, timeout: int = 30) -> str:
    """
    Run a command and return stdout (text).
    Raises CalledProcessError on failure when check=True.
    """
    p = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )
    return p.stdout

def adb_base(ctx: Ctx) -> list[str]:
    if ctx.serial:
        return ["adb", "-s", ctx.serial]
    return ["adb"]


def fastboot_base(ctx: Ctx) -> list[str]:
    if ctx.serial:
        return ["fastboot", "-s", ctx.serial]
    return ["fastboot"]

def pick_adb_serial() -> str | None:
    out = run(["adb", "devices", "-l"], timeout=10)
    serials = parse_adb_devices(out)

    # decide after collecting all serials
    if not serials:
        return None
    if len(serials) == 1:
        return serials[0]

    print("Multiple ADB devices detected:")
    for i, s in enumerate(serials, start=1):
        print(f"  {i}) {s}")
    choice = input("Pick one: ").strip()
    if not choice.isdigit():
        return None
    idx = int(choice)
    if 1 <= idx <= len(serials):
        return serials[idx - 1]
    return None


def parse_adb_devices(output: str) -> list[str]:
    """Parse the output of `adb devices -l` and return serials in state 'device'.

    Returns a list of serial strings in the same order they appear.
    """
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    serials: list[str] = []
    for ln in lines[1:]:  # skip header line
        parts = ln.split()
        if not parts:
            continue
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else ""
        if state == "device":
            serials.append(serial)
    return serials
        
        
def action_status(ctx: Ctx) -> None:
    print()
    print("ADB devices:")
    print(run(["adb", "devices", "-l"], timeout=10))

    print("Fastboot devices:")
    print(run(["fastboot", "devices"], timeout=10))


def action_report(ctx: Ctx) -> None:
    if not ctx.serial:
        print("No ADB serial selected (device must not be authorized and in Android).")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"report-{ctx.serial}-{ts}.txt"

    def getprop(key: str) -> str:
        cmd = adb_base(ctx) + ["shell", "getprop", key]
        return run(cmd, timeout=15).strip()

    lines: list[str] = []
    lines.append(f"serial: {ctx.serial}")
    lines.append(f"when:   {datetime.now().isoformat()}")
    lines.append("")
    lines.append(f"model: {getprop('ro.product.model')}")
    lines.append(f"android: {getprop('ro.build.version.release')}")
    lines.append(f"fingerprint: {getprop('ro.build.fingerprint')}")
    lines.append(f"verifiedbootstate: {getprop('ro.boot.verifiedbootstate')}")
    lines.append(f"flash.locked: {getprop('ro.boot.flash.locked')}")
    lines.append(f"vbmeta.device_state: {getprop('ro.boot.vbmeta.device_state')}")
    lines.append("")
    lines.append("id:")
    lines.append(run(adb_base(ctx) + ["shell", "id"], timeout=10).strip())

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote: {path}")


def menu(serial: str | None = None) -> None:
    ctx = Ctx()
    ctx.serial = serial or pick_adb_serial()

    while True:
        clear()
        print(banner())
        print(status_line(ctx.serial, mode="adb", dry_run=ctx.dry_run))
        print()

        menu_lines = [
            f"{NEON_CYAN}1{RESET} Status (adb/fastboot devices)",
            f"{NEON_CYAN}2{RESET} Write quick report",
            f"{NEON_CYAN}3{RESET} Reboot bootloader",
            f"{NEON_CYAN}q{RESET} Quit",
            f"{NEON_CYAN}4{RESET} Logcat Lab",
            f"{NEON_CYAN}d{RESET} Toggle dry-run",
        ]
        print(box(menu_lines, title=NEON_PINK + "MAIN MENU" + RESET))
        choice = input(NEON_PINK + "> " + RESET).strip().lower()

        if choice == "d":
            ctx.dry_run = not ctx.dry_run
            continue
        if choice == "q":
            return
        if choice == "1":
            action_status(ctx)
        elif choice == "2":
            action_report(ctx)
        elif choice == "3":
            if not ctx.serial:
                print("No ADB serial selected.")
                continue
            cmd = adb_base(ctx) + ["reboot", "bootloader"]
            print("Running:", " ".join(cmd))
            run(cmd, timeout=30)
        elif choice == "4":
            action_logcat_lab(ctx)
        else:
            print("Unknown choice.")
            input(GRAY + "Press Enter to continue..." + RESET)

def adb_shell(ctx: Ctx, *args: str, timeout: int = 30) -> str:
    return run(adb_base(ctx) + ["shell", *args], timeout=timeout)

def action_logcat_lab(ctx: Ctx) -> None:                                                                        
       if not ctx.serial:                                                                                          
           print(NEON_RED + "No ADB serial selected." + RESET)                                                     
           input(GRAY + "Press Enter..." + RESET)                                                                  
           return                                                                                                  
                                                                                                                   
       print()                                                                                                     
       lines = [                                                                                                   
           f"{NEON_CYAN}1{RESET}) Dump last 200 lines (all buffers)",                                              
           f"{NEON_CYAN}2{RESET}) Live follow (all buffers)",                                                      
           f"{NEON_CYAN}3{RESET}) Crashes only (AndroidRuntime)",                                                  
           f"{NEON_CYAN}4{RESET}) SELinux denials (avc) [host grep]",                                              
           f"{NEON_CYAN}5{RESET}) Filter by tag",                                                                  
           f"{NEON_CYAN}6{RESET}) Filter by regex (grep -E on host)",                                              
           f"{NEON_CYAN}7{RESET}) Save dump to file",                                                              
           f"{NEON_CYAN}8{RESET}) Clear logcat buffers (confirm)",                                                 
           f"{NEON_CYAN}b{RESET}) Back",                                                                           
       ]                                                                                                           
       print(box(lines, title=NEON_PINK + "LOGCAT LAB" + RESET))                                                   
                                                                                                                   
       choice = input(NEON_PINK + "> " + RESET).strip().lower()                                                    
       if choice == "b":                                                                                           
           return                                                                                                  
                                                                                                                   
       # Build the logcat command.                                                                                 
       if choice == "1":                                                                                           
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-t", "200", "-v", "time"]                          
                                                                                                                   
       elif choice == "2":                                                                                         
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-v", "time"]                                             
                                                                                                                   
       elif choice == "3":                                                                                         
           # Focused crash view                                                                                    
           cmd = adb_base(ctx) + ["logcat", "-v", "time", "AndroidRuntime:E", "*:S"]                               
                                                                                                                   
       elif choice == "4":                                                                                         
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]                                       
                                                                                                                   
       elif choice == "5":                                                                                         
           tag = input("Tag (e.g. ActivityManager): ").strip()                                                     
           if not tag:                                                                                             
               return                                                                                              
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time", f"{tag}:V", "*:S"]                    
                                                                                                                   
       elif choice == "6":                                                                                         
           regex = input("Regex (grep -E): ").strip()                                                              
           if not regex:                                                                                           
               return                                                                                              
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]                                       
                                                                                                                   
       elif choice == "7":                                                                                         
           LOG_DIR.mkdir(parents=True, exist_ok=True)                                                              
           ts = datetime.now().strftime("%Y%m%d-%H%M%S")                                                           
           out_path = LOG_DIR / f"logcat-{ctx.serial}-{ts}.txt"                                                    
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-d", "-v", "time"]                                       
                                                                                                                   
       elif choice == "8":                                                                                         
           confirm = input("This clears log buffers. Type YES to continue: ").strip()                              
           if confirm != "YES":                                                                                    
               return                                                                                              
           cmd = adb_base(ctx) + ["logcat", "-b", "all", "-c"]                                                     
       else:                                                                                                       
           return                                                                                                  
                                                                                                                   
       if ctx.dry_run:                                                                                             
           print(GRAY + "Dry-run. Would run:" + RESET, " ".join(cmd))                                              
           input(GRAY + "Press Enter..." + RESET)                                                                  
           return                                                                                                  
                                                                                                                   
       out = run(cmd, timeout=60)                                                                                  
                                                                                                                   
       # host-side filters                                                                                         
       if choice == "4":                                                                                           
           out = "\n".join([ln for ln in out.splitlines() if "avc:" in ln.lower()])                                
                                                                                                                   
       if choice == "6":                                                                                           
           import re                                                                                               
           try:                                                                                                    
               rx = re.compile(regex)                                                                              
               out = "\n".join([ln for ln in out.splitlines() if rx.search(ln)])                                   
           except re.error as e:                                                                                   
               print(NEON_RED + f"Bad regex: {e}" + RESET)                                                         
               input(GRAY + "Press Enter..." + RESET)                                                              
               return                                                                                              
                                                                                                                   
       if choice == "7":                                                                                           
           out_path.write_text(out, encoding="utf-8")                                                              
           print(f"Wrote: {out_path}")                                                                             
       else:                                                                                                       
           print(out)                                                                                              
                                                                                                                   
       input(GRAY + "Press Enter..." + RESET)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Android Workbench")
    parser.add_argument("--serial", help="ADB device serial to use (skip interactive selection)")
    args = parser.parse_args()

    menu(serial=args.serial)