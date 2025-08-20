from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

TASK_NAME = "BiSyncPlus USB AutoStart"


def select_dir() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(title="Scegli cartella di installazione")
    root.destroy()
    return Path(path) if path else None


def install() -> None:
    src = Path(__file__).with_name("USBDetect.exe")
    if not src.exists():
        messagebox.showerror("Installer", f"USBDetect.exe non trovato accanto all'installer.")
        return
    dest_dir = select_dir()
    if not dest_dir:
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "USBDetect.exe"
    try:
        shutil.copy2(src, dest)
    except Exception as e:
        messagebox.showerror("Installer", f"Copiatura fallita: {e}")
        return
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        subprocess.run([
            "schtasks", "/Create", "/SC", "ONLOGON", "/TN", TASK_NAME,
            "/TR", str(dest),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        messagebox.showerror("Installer", f"Creazione attività fallita: {e}")
        return
    messagebox.showinfo("Installer", f"Installazione completata in {dest}")


if __name__ == "__main__":
    install()
