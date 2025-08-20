from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

LABEL = "HF_OMNITOOL"
RELATIVE_EXE = r"Documents\\BySync Plus\\dist\\BiSyncPlus.exe"
LOG = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "BiSyncPlus" / "usb-detect.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG), level=logging.INFO,
                    format="%(asctime)s %(message)s")


def find_drive() -> str | None:
    """Return drive letter (e.g. 'E:') if the labeled USB is present."""
    try:
        out = subprocess.check_output([
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-Volume -FileSystemLabel '{LABEL}' -ErrorAction SilentlyContinue).DriveLetter"
        ], text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return f"{out}:"
    except Exception:
        pass
    return None


def is_app_running(full_path: str) -> bool:
    name = Path(full_path).stem
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-Process -Name '{name}' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.Path -ieq '{full_path}' } | Select-Object -First 1"
            ).format(name=name, full_path=full_path)
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return bool(out.strip())
    except Exception:
        return False


def start_app(drive: str) -> None:
    exe = os.path.join(drive, RELATIVE_EXE)
    logging.info("Check EXE: %s", exe)
    if not os.path.exists(exe):
        logging.info("EXE non trovato: %s", exe)
        return
    if is_app_running(exe):
        logging.info("Già in esecuzione: %s", exe)
        return
    try:
        subprocess.Popen([exe, "--tray"], cwd=os.path.dirname(exe),
                         creationflags=0x08000000)
        logging.info("Avviato: %s", exe)
    except Exception as e:
        logging.error("Errore avvio: %s", e)


def main() -> None:
    while True:
        drive = find_drive()
        if drive:
            logging.info("Volume presente: %s", drive)
            start_app(drive)
            while find_drive():
                time.sleep(1)
            logging.info("Volume scollegato")
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
