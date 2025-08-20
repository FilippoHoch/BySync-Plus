from __future__ import annotations

"""Utility to detect a USB drive and launch the sync application."""

import json
import logging
import os
import subprocess
import time
from pathlib import Path

CONFIG_FILE = Path(__file__).with_name("usb_detect_config.json")
DEFAULT_CFG = {
    "label": "HF_OMNITOOL",
    "relative_exe": r"Documents\\BySync Plus\\dist\\BiSyncPlus.exe",
}


def load_config() -> dict[str, str]:
    """Read configuration file if present, otherwise create a default one."""
    cfg = DEFAULT_CFG.copy()
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if isinstance(v, str)})
        else:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cfg


CONFIG = load_config()
USB_LABEL = CONFIG["label"]
RELATIVE_EXE_PATH = CONFIG["relative_exe"]
LOG = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "BiSyncPlus" / "usb-detect.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(LOG), level=logging.INFO,
                    format="%(asctime)s %(message)s")


def find_labeled_drive() -> str | None:
    """Return drive letter (e.g. ``'E:'``) if the labelled USB is present."""
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Volume -FileSystemLabel '{USB_LABEL}' -ErrorAction SilentlyContinue).DriveLetter",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return f"{out}:"
    except Exception:
        pass
    return None


def is_application_running(full_path: str) -> bool:
    """Check if the application at ``full_path`` is already running."""
    name = Path(full_path).stem
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-Process -Name '{name}' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.Path -ieq '{full_path}' } | Select-Object -First 1"
            ).format(name=name, full_path=full_path),
        ]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return bool(out.strip())
    except Exception:
        return False


def launch_app(drive: str) -> None:
    """Launch the configured application from ``drive`` if possible."""
    exe = os.path.join(drive, RELATIVE_EXE_PATH)
    logging.info("Check EXE: %s", exe)
    if not os.path.exists(exe):
        logging.info("EXE non trovato: %s", exe)
        return
    if is_application_running(exe):
        logging.info("Già in esecuzione: %s", exe)
        return
    try:
        subprocess.Popen(
            [exe, "--tray"], cwd=os.path.dirname(exe), creationflags=0x08000000
        )
        logging.info("Avviato: %s", exe)
    except Exception as e:
        logging.error("Errore avvio: %s", e)


def main() -> None:
    """Main loop that waits for the USB drive and launches the app."""
    while True:
        drive = find_labeled_drive()
        if drive:
            logging.info("Volume presente: %s", drive)
            launch_app(drive)
            while find_labeled_drive():
                time.sleep(1)
            logging.info("Volume scollegato")
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
