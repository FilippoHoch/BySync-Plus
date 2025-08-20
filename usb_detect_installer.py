from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

TASK_NAME = "BiSyncPlus USB AutoStart"
DEFAULT_CFG = {
    "label": "HF_OMNITOOL",
    "relative_exe": r"Documents\\BySync Plus\\dist\\BiSyncPlus.exe",
}


def select_dir(initial: Path | None = None) -> Path | None:
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(
        title="Scegli cartella di installazione",
        initialdir=str(initial) if initial else None,
    )
    root.destroy()
    return Path(path) if path else None


def ask_config(existing: dict[str, str]) -> dict[str, str] | None:
    root = tk.Tk()
    root.withdraw()
    label = simpledialog.askstring(
        "Installer",
        "Etichetta USB",
        initialvalue=existing.get("label", DEFAULT_CFG["label"]),
        parent=root,
    )
    if not label:
        root.destroy()
        return None
    exe_path = filedialog.askopenfilename(
        title="Seleziona BiSyncPlus.exe",
        filetypes=[("Executable", "*.exe")],
    )
    root.destroy()
    if not exe_path:
        return None
    p = Path(exe_path)
    try:
        rel = p.relative_to(p.anchor)
    except Exception:
        messagebox.showerror("Installer", "Percorso non valido")
        return None
    return {"label": label, "relative_exe": str(rel).replace("/", "\\")}


def install() -> None:
    src = Path(__file__).with_name("USBDetect.exe")
    if not src.exists():
        messagebox.showerror("Installer", f"USBDetect.exe non trovato accanto all'installer.")
        return
    dest_dir = select_dir(Path.home())
    if not dest_dir:
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    config_path = dest_dir / "usb_detect_config.json"
    existing: dict[str, str] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg = ask_config(existing)
    if not cfg:
        return
    config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
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
