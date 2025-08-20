#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import json
import time
import math
import glob
import queue
import shutil
import hashlib
import threading
import platform
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import argparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as tray_item
from plyer import notification

APP_NAME = "BiSync+"
CONFIG_NAME = "bisync_config.json"
LOG_NAME = "bisync_log.txt"
STATE_PREFIX = ".bisync_state_"
MTIME_FUZZ = 1.0  # secondi di tolleranza su mtime
DEFAULT_EXCLUDES = ["*.tmp", "*.temp", "*.swp", "Thumbs.db", ".DS_Store", "desktop.ini"]
ARCHIVE_DIRNAME = ".sync_archive"
TRASH_DIRNAME = ".sync_trash"

# Script PowerShell per monitorare l'inserimento della chiavetta HF_OMNITOOL
# e avviare automaticamente BiSyncPlus.
USB_DETECT_PS1 = r'''param([switch]$Silent = $true)

$ErrorActionPreference = "Continue"
$Label = "HF_OMNITOOL"
$RelativeExe = "Documents\\BySync Plus\\dist\\BiSyncPlus.exe"
$Log = Join-Path $env:LOCALAPPDATA "BiSyncPlus\\usb-detect.log"

# --- Log ---
New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null
function Log([string]$msg){ Add-Content -Path $Log -Value "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg }

# --- no doppie istanze dello script ---
Add-Type -AssemblyName System.Threading
$mutex = New-Object System.Threading.Mutex($false, "Global\\USBDetect_BiSyncPlus")
if(-not $mutex.WaitOne(0)){ Log "Istanza già in esecuzione"; exit }

# (opzionale) notifiche
if(-not $Silent){
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $notify = New-Object System.Windows.Forms.NotifyIcon
  $notify.Icon = [System.Drawing.SystemIcons]::Information
  $notify.Visible = $true
  $notify.BalloonTipTitle = "BiSyncPlus AutoStart"
  function Tip($t){ $notify.BalloonTipText = $t; $notify.ShowBalloonTip(2500) }
}else{ function Tip($t){} }

function Get-UsbVolume(){ Get-CimInstance Win32_Volume -Filter "Label='$Label' AND DriveType=2" -ErrorAction SilentlyContinue }
function Get-ExePath([string]$drive){ Join-Path $drive $RelativeExe }

# Evita di rilanciare se il processo è già in esecuzione con LO STESSO percorso
function Is-AppRunning([string]$fullPath){
  $name = [System.IO.Path]::GetFileNameWithoutExtension($fullPath)
  try{
    Get-Process -Name $name -ErrorAction SilentlyContinue |
      Where-Object { $_.Path -and ( $_.Path -ieq $fullPath ) } | ForEach-Object { return $true }
  }catch{}
  return $false
}

function Start-BiSyncPlus([string]$drive){
  $exe = Get-ExePath $drive
  Log "Check EXE: $exe"
  if(Test-Path -LiteralPath $exe){
    if(Is-AppRunning $exe){
      Log "Già in esecuzione: $exe"
      return
    }
    try{
      Start-Process -FilePath $exe -ArgumentList "--tray" -WorkingDirectory (Split-Path $exe) -WindowStyle Hidden
      Log "Avviato: $exe"
      Tip "Avviato BiSyncPlus"
    }catch{
      Log ("Errore avvio: " + $_.Exception.Message)
      Tip "Errore avvio BiSyncPlus"
    }
  } else {
    Log "EXE non trovato: $exe"
    Tip "EXE non trovato"
  }
}

# --- AVVIO IMMEDIATO SE GIÀ COLLEGATA ---
try{
  $vol = Get-UsbVolume
  if($vol){
    Log "Volume già presente: $($vol.DriveLetter)"
    Start-BiSyncPlus $vol.DriveLetter
  } else {
    Log "Volume non presente al lancio"
  }
}catch{ Log ("Errore check iniziale: " + $_.Exception.Message) }

# --- LISTENER EVENTI WMI (plug/unplug) ---
$query = "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType=2 OR EventType=3"
$watcher = New-Object System.Management.ManagementEventWatcher $query
Log "Watcher WMI attivo per '$Label'"
Tip "Watcher attivo per $Label"

try{
  while($true){
    $ev = $watcher.WaitForNextEvent()  # blocca finché evento
    Start-Sleep -Milliseconds 400
    try{
      $vol = Get-UsbVolume
      if($vol){
        Log "Evento: collegato $($vol.DriveLetter)"
        Start-BiSyncPlus $vol.DriveLetter
        do { Start-Sleep -Seconds 1 } while (Get-UsbVolume)
        Log "Evento: scollegato"
      }
    }catch{ Log ("Errore gestione evento: " + $_.Exception.Message) }
  }
} finally {
  try{ $watcher.Stop(); $watcher.Dispose() }catch{}
  try{ $mutex.ReleaseMutex() | Out-Null }catch{}
}
'''


def ensure_windows_autostart() -> None:
    """Installa automaticamente lo script di rilevamento USB come
    attività pianificata su Windows."""
    if platform.system() != "Windows":
        return
    try:
        task_name = "BiSyncPlus USB AutoStart"
        script_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "BiSyncPlus"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / "USB-Detect.ps1"
        if not script_path.exists():
            script_path.write_text(USB_DETECT_PS1, encoding="utf-8")
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            ps_args = f'-NoProfile -ExecutionPolicy Bypass -File "{script_path}"'
            subprocess.run(
                [
                    "schtasks",
                    "/Create",
                    "/SC",
                    "ONLOGON",
                    "/TN",
                    task_name,
                    "/TR",
                    f"powershell.exe {ps_args}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

def app_dir() -> Path:
    return Path(__file__).resolve().parent

def human_bytes(n: int) -> str:
    neg = n < 0
    n = abs(n)
    for unit in ["B","KB","MB","GB","TB","PB"]:
        if n < 1024 or unit == "PB":
            s = f"{n:.1f} {unit}" if unit!="B" else f"{int(n)} {unit}"
            return f"-{s}" if neg else s
        n /= 1024
    return f"{n:.1f} PB"

def fmt_eta(seconds: float) -> str:
    if seconds <= 0 or math.isinf(seconds) or math.isnan(seconds):
        return "—"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

@dataclass
class Pair:
    left: str
    right: str
    conservative: bool = True            # True = ripristina file mancanti, False = propaga eliminazioni
    use_trash: bool = True               # Se propaga, sposta in .sync_trash invece di cancellare
    conflict_policy: str = "newest"      # "newest" | "prefer_left" | "prefer_right"
    include_globs: List[str] = field(default_factory=list)   # es: ["*.docx","*.pdf"]
    exclude_globs: List[str] = field(default_factory=lambda: DEFAULT_EXCLUDES.copy())
    notes: str = ""
    sync_interval: int = 0              # intervallo specifico (s), 0 = usa globale
    silent_hours: str = ""             # "HH:MM-HH:MM" finestra silenziosa

    def normalized(self) -> "Pair":
        # normalizza slash per consistenza
        self.left = str(Path(self.left))
        self.right = str(Path(self.right))
        return self

    def id_hash(self) -> str:
        key = (str(Path(self.left)).lower() + "|" + str(Path(self.right)).lower()).encode("utf-8")
        return hashlib.md5(key).hexdigest()[:10]

class Snapshot:
    """
    Memorizza l'ultimo stato visto per discernere:
    - file nuovi vs file eliminati
    Struttura:
    {
        "rel/path.txt": {
            "A": mtime_or_None,
            "B": mtime_or_None,
            "sizeA": int_or_0,
            "sizeB": int_or_0,
            "hashA": str,
            "hashB": str,
        }
    }
    """
    def __init__(self, pair: Pair):
        self.pair = pair
        self.data: Dict[str, dict] = {}
        self.loaded_from: List[Path] = []

    def _paths(self) -> List[Path]:
        hid = self.pair.id_hash()
        fname = f"{STATE_PREFIX}{hid}.json"
        return [Path(self.pair.left)/fname, Path(self.pair.right)/fname]

    def load(self):
        for p in self._paths():
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if isinstance(d, dict) and d:
                        self.data = d
                        self.loaded_from.append(p)
                        return
            except Exception:
                continue

    def save(self, mappingA: Dict[str, dict], mappingB: Dict[str, dict]):
        out: Dict[str, dict] = {}
        rels = set(mappingA.keys()) | set(mappingB.keys())
        for rel in rels:
            a = mappingA.get(rel)
            b = mappingB.get(rel)
            out[rel] = {
                "A": a["mtime"] if a else None,
                "B": b["mtime"] if b else None,
                "sizeA": a["size"] if a else 0,
                "sizeB": b["size"] if b else 0,
                "hashA": a.get("hash", "") if a else "",
                "hashB": b.get("hash", "") if b else "",
            }
        payload = json.dumps(out, ensure_ascii=False, indent=0)
        for p in self._paths():
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(payload)
            except Exception:
                pass

class SyncEngine:
    def __init__(self, pairs: List[Pair], log_cb, progress_cb, status_cb, stop_event, pause_event, settings):
        self.pairs = [p.normalized() for p in pairs]
        self.log = log_cb
        self.progress = progress_cb
        self.status = status_cb
        self.stop = stop_event
        self.pause = pause_event
        self.settings = settings
        self.actions_total = 0
        self.actions_done = 0
        self.bytes_total = 0
        self.bytes_done = 0
        self._t0 = time.time()

    def _matches_filters(self, rel: str, includes: List[str], excludes: List[str]) -> bool:
        # include: se presente e nessuno match -> escludi
        if includes:
            ok = any(glob.fnmatch.fnmatch(rel, pat) for pat in includes)
            if not ok: return False
        # exclude: se match -> escludi
        for pat in excludes:
            if glob.fnmatch.fnmatch(rel, pat):
                return False
        # esclude sempre i nostri metadata
        base = rel.lower()
        if base.endswith(".json") and base.startswith(STATE_PREFIX): return False
        if ARCHIVE_DIRNAME in rel.split("/") or TRASH_DIRNAME in rel.split("/"):
            return False
        return True

    def _rel_map(self, root: Path, includes: List[str], excludes: List[str]) -> Dict[str, dict]:
        result: Dict[str, dict] = {}
        for base, dirs, files in os.walk(root):
            if self.stop.is_set():
                break
            # ignora dir di sistema nostre
            parts = Path(base).parts
            if ARCHIVE_DIRNAME in parts or TRASH_DIRNAME in parts:
                continue
            for name in files:
                p = Path(base) / name
                try:
                    if p.is_symlink():
                        continue
                    rel = p.relative_to(root).as_posix()
                    if not self._matches_filters(rel, includes, excludes):
                        continue
                    st = p.stat()
                    file_hash = self._file_hash(p)
                    result[rel] = {
                        "abs": str(p),
                        "mtime": st.st_mtime,
                        "size": st.st_size,
                        "hash": file_hash,
                    }
                except Exception:
                    continue
        return result

    def _file_hash(self, path: Path) -> str:
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except Exception:
            return ""
        return h.hexdigest()

    def _archive_existing(self, pair_root: Path, dst_rel: str):
        dst = pair_root / dst_rel
        if not dst.exists(): 
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_root = pair_root / ARCHIVE_DIRNAME / ts
        archive_path = archive_root / dst_rel
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(dst), str(archive_path))
        except Exception as e:
            self.log(f"⚠️  Impossibile archiviare {dst}: {e}")

    def _to_trash(self, pair_root: Path, rel: str, use_trash: bool):
        target = pair_root / rel
        if not target.exists():
            return
        if use_trash:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            trash_root = pair_root / TRASH_DIRNAME / ts
            trash_path = trash_root / rel
            trash_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(target), str(trash_path))
                return
            except Exception as e:
                self.log(f"⚠️  Spostamento nel cestino fallito {target}: {e}; provo cancellazione.")
        try:
            target.unlink()
        except Exception as e:
            self.log(f"❌ Eliminazione fallita {target}: {e}")

    def _safe_copy(self, src_abs: Path, dst_abs: Path, dst_pair_root: Path, dst_rel: str):
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        if dst_abs.exists():
            self._archive_existing(dst_pair_root, dst_rel)
        shutil.copy2(str(src_abs), str(dst_abs))

    def _safe_move(self, src_abs: Path, dst_abs: Path, pair_root: Path, dst_rel: str):
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        if dst_abs.exists():
            self._archive_existing(pair_root, dst_rel)
        shutil.move(str(src_abs), str(dst_abs))

    def _cleanup_retention(self, root: Path, dirname: str, days: int):
        if days <= 0: 
            return
        base = root / dirname
        if not base.exists():
            return
        cutoff = datetime.now() - timedelta(days=days)
        for sub in base.iterdir():
            try:
                if sub.is_dir():
                    # directory timestamp "YYYYmmdd_HHMMSS"
                    m = re.match(r"(\d{8})_(\d{6})", sub.name)
                    if m:
                        dt = datetime.strptime(m.group(1)+"_"+m.group(2), "%Y%m%d_%H%M%S")
                    else:
                        dt = datetime.fromtimestamp(sub.stat().st_mtime)
                    if dt < cutoff:
                        shutil.rmtree(sub, ignore_errors=True)
            except Exception:
                pass

    def _plan_pair(self, pair: Pair, mappingA: Dict[str, dict], mappingB: Dict[str, dict], snap: Snapshot):
        rels = set(mappingA.keys()) | set(mappingB.keys())
        plan = []  # list of tuples: (action, src_abs, dst_abs, size, human, info)

        # rileva rinomini confrontando hash
        onlyA = {r: mappingA[r] for r in mappingA.keys() - mappingB.keys()}
        onlyB = {r: mappingB[r] for r in mappingB.keys() - mappingA.keys()}
        hashA = {info["hash"]: rel for rel, info in onlyA.items() if info.get("hash")}
        hashB = {info["hash"]: rel for rel, info in onlyB.items() if info.get("hash")}
        handled: set = set()
        for h in set(hashA.keys()) & set(hashB.keys()):
            relA = hashA[h]
            relB = hashB[h]
            prevA = snap.data.get(relA)
            prevB = snap.data.get(relB)
            if prevB and not prevA:
                # rinomina in B per allinearsi ad A
                plan.append((
                    "RENAME_B",
                    Path(pair.right) / relB,
                    Path(pair.right) / relA,
                    0,
                    relA,
                    {"from": relB},
                ))
                handled.update({relA, relB})
            elif prevA and not prevB:
                # rinomina in A per allinearsi a B
                plan.append((
                    "RENAME_A",
                    Path(pair.left) / relA,
                    Path(pair.left) / relB,
                    0,
                    relB,
                    {"from": relA},
                ))
                handled.update({relA, relB})

        # action: "COPY_A2B", "COPY_B2A", "DELETE_A", "DELETE_B", "RENAME_A", "RENAME_B"
        for rel in sorted(rels):
            if rel in handled:
                continue
            if self.stop.is_set():
                break
            a = mappingA.get(rel)
            b = mappingB.get(rel)
            prev = snap.data.get(rel, {"A": None, "B": None, "sizeA": 0, "sizeB": 0, "hashA": "", "hashB": ""})

            if a and not b:
                # Esiste solo in A
                if pair.conservative:
                    plan.append(("COPY_A2B", Path(a["abs"]), Path(pair.right)/rel, a["size"], rel, {}))
                else:
                    # Propagazione eliminazioni: capire se è nuovo file o B l'ha rimosso
                    was_in_B = prev.get("B") is not None
                    is_new_since_last = prev.get("A") is None  # non esisteva prima
                    unchanged_since_last = (abs(a["mtime"] - (prev.get("A") or a["mtime"])) <= MTIME_FUZZ)
                    # Se era presente in B prima e A non è cambiato da allora => B ha cancellato => elimina da A
                    if was_in_B and unchanged_since_last:
                        plan.append(("DELETE_A", None, Path(pair.left)/rel, a["size"], rel, {}))
                    else:
                        plan.append(("COPY_A2B", Path(a["abs"]), Path(pair.right)/rel, a["size"], rel, {}))

            elif b and not a:
                # Esiste solo in B
                if pair.conservative:
                    plan.append(("COPY_B2A", Path(b["abs"]), Path(pair.left)/rel, b["size"], rel, {}))
                else:
                    was_in_A = prev.get("A") is not None
                    is_new_since_last = prev.get("B") is None
                    unchanged_since_last = (abs(b["mtime"] - (prev.get("B") or b["mtime"])) <= MTIME_FUZZ)
                    if was_in_A and unchanged_since_last:
                        plan.append(("DELETE_B", None, Path(pair.right)/rel, b["size"], rel, {}))
                    else:
                        plan.append(("COPY_B2A", Path(b["abs"]), Path(pair.left)/rel, b["size"], rel, {}))

            else:
                # Esiste su entrambi -> conflitto/differenza?
                # Stesso mtime±fuzz e stessa size -> salta
                if abs(a["mtime"] - b["mtime"]) <= MTIME_FUZZ and a["size"] == b["size"]:
                    continue
                policy = pair.conflict_policy
                if policy == "prefer_left":
                    plan.append(("COPY_A2B", Path(a["abs"]), Path(pair.right)/rel, a["size"], rel, {"conflict": True}))
                elif policy == "prefer_right":
                    plan.append(("COPY_B2A", Path(b["abs"]), Path(pair.left)/rel, b["size"], rel, {"conflict": True}))
                else:
                    # newest-wins
                    if (a["mtime"] - b["mtime"]) > MTIME_FUZZ:
                        plan.append(("COPY_A2B", Path(a["abs"]), Path(pair.right)/rel, a["size"], rel, {"conflict": True}))
                    elif (b["mtime"] - a["mtime"]) > MTIME_FUZZ:
                        plan.append(("COPY_B2A", Path(b["abs"]), Path(pair.left)/rel, b["size"], rel, {"conflict": True}))
                    else:
                        # mtime uguali ma size diversa: scegli quello più grande
                        if a["size"] >= b["size"]:
                            plan.append(("COPY_A2B", Path(a["abs"]), Path(pair.right)/rel, a["size"], rel, {"conflict": True}))
                        else:
                            plan.append(("COPY_B2A", Path(b["abs"]), Path(pair.left)/rel, b["size"], rel, {"conflict": True}))
        return plan

    def _execute_plan(self, pair: Pair, plan: List[tuple]):
        # calcolo totali per barra/progress
        for action, src, dst, size, rel, extra in plan:
            self.bytes_total += max(0, size)
        self.actions_total += len(plan)
        self.progress(self.actions_done, self.actions_total, self.bytes_done, self.bytes_total)

        left_root = Path(pair.left)
        right_root = Path(pair.right)

        for action, src, dst, size, rel, extra in plan:
            if self.stop.is_set(): break
            # Pausa
            while self.pause.is_set() and not self.stop.is_set():
                time.sleep(0.1)

            t1 = time.time()
            try:
                if action == "COPY_A2B":
                    self._safe_copy(Path(src), Path(dst), right_root, rel)
                    self.log(f"→ A⇒B: {rel} ({human_bytes(size)})")
                elif action == "COPY_B2A":
                    self._safe_copy(Path(src), Path(dst), left_root, rel)
                    self.log(f"→ B⇒A: {rel} ({human_bytes(size)})")
                elif action == "DELETE_A":
                    self._to_trash(left_root, rel, pair.use_trash)
                    self.log(f"✖ elimina in A: {rel}")
                elif action == "DELETE_B":
                    self._to_trash(right_root, rel, pair.use_trash)
                    self.log(f"✖ elimina in B: {rel}")
                elif action == "RENAME_A":
                    self._safe_move(Path(src), Path(dst), left_root, rel)
                    self.log(f"↺ rinomina in A: {extra.get('from')} → {rel}")
                elif action == "RENAME_B":
                    self._safe_move(Path(src), Path(dst), right_root, rel)
                    self.log(f"↺ rinomina in B: {extra.get('from')} → {rel}")
            except Exception as e:
                self.log(f"❌ Errore su {rel}: {e}")
            finally:
                dt = max(1e-6, time.time()-t1)
                self.actions_done += 1
                self.bytes_done += max(0, size)
                # Aggiorna metriche
                elapsed = max(1e-3, time.time()-self._t0)
                rate = self.bytes_done / elapsed
                remain = max(0, self.bytes_total - self.bytes_done)
                eta = remain / rate if rate > 1e-3 else float("inf")
                self.progress(self.actions_done, self.actions_total, self.bytes_done, self.bytes_total)
                self.status(rate, eta)

        # retention cleanup
        days = int(self.settings.get("retention_days", 30))
        try:
            self._cleanup_retention(left_root, ARCHIVE_DIRNAME, days)
            self._cleanup_retention(right_root, ARCHIVE_DIRNAME, days)
            self._cleanup_retention(left_root, TRASH_DIRNAME, days)
            self._cleanup_retention(right_root, TRASH_DIRNAME, days)
        except Exception:
            pass

    def dry_run_pair(self, pair: Pair) -> Tuple[List[tuple], Dict[str, dict], Dict[str, dict]]:
        A, B = Path(pair.left), Path(pair.right)
        mapA = self._rel_map(A, pair.include_globs, pair.exclude_globs)
        mapB = self._rel_map(B, pair.include_globs, pair.exclude_globs)
        snap = Snapshot(pair)
        snap.load()
        plan = self._plan_pair(pair, mapA, mapB, snap)
        return plan, mapA, mapB

    def run(self):
        self._t0 = time.time()
        self.actions_total = self.actions_done = 0
        self.bytes_total = self.bytes_done = 0
        self.progress(0, 1, 0, 1)

        for pair in self.pairs:
            if self.stop.is_set(): break
            A, B = Path(pair.left), Path(pair.right)
            if not A.exists() or not B.exists():
                self.log(f"❌ Percorsi non validi: {A} / {B}. Salto.")
                continue

            self.log(f"🔁 {A} ↔ {B}  (conservativa={'sì' if pair.conservative else 'no'}, conflitti={pair.conflict_policy})")
            plan, _, _ = self.dry_run_pair(pair)

            # Esecuzione
            self._execute_plan(pair, plan)

            # ricostruisci mapping dopo le azioni (rinomini, copie, ecc.)
            mapA = self._rel_map(A, pair.include_globs, pair.exclude_globs)
            mapB = self._rel_map(B, pair.include_globs, pair.exclude_globs)

            # Aggiorna snapshot
            snap = Snapshot(pair)
            snap.save(mapA, mapB)
        self.log("✅ Sincronizzazione completata.")

# ---------------------------- GUI ---------------------------------

class PairEditor(tk.Toplevel):
    def __init__(self, master, pair: Optional[Pair], on_save):
        super().__init__(master)
        self.title("Coppia cartelle")
        self.resizable(False, False)
        self.on_save = on_save
        self.result: Optional[Pair] = None

        # Vars
        self.left_var = tk.StringVar(value=pair.left if pair else "")
        self.right_var = tk.StringVar(value=pair.right if pair else "")
        self.cons_var = tk.BooleanVar(value=pair.conservative if pair else True)
        self.trash_var = tk.BooleanVar(value=pair.use_trash if pair else True)
        self.policy_var = tk.StringVar(value=pair.conflict_policy if pair else "newest")
        self.include_var = tk.StringVar(value=",".join(pair.include_globs) if pair and pair.include_globs else "")
        self.exclude_var = tk.StringVar(value=",".join(pair.exclude_globs) if pair and pair.exclude_globs else ",".join(DEFAULT_EXCLUDES))
        self.notes_var = tk.StringVar(value=pair.notes if pair else "")
        self.interval_var = tk.IntVar(value=pair.sync_interval if pair else 0)
        self.silent_var = tk.StringVar(value=pair.silent_hours if pair else "")

        pad = {"padx": 8, "pady": 6}
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, **pad)

        # Left
        ttk.Label(frame, text="Cartella A").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.left_var, width=58).grid(row=0, column=1, sticky="w")
        ttk.Button(frame, text="Sfoglia…", command=self._browse_left).grid(row=0, column=2, sticky="e")

        # Right
        ttk.Label(frame, text="Cartella B").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.right_var, width=58).grid(row=1, column=1, sticky="w")
        ttk.Button(frame, text="Sfoglia…", command=self._browse_right).grid(row=1, column=2, sticky="e")

        # Policy
        polf = ttk.LabelFrame(frame, text="Politica conflitti")
        polf.grid(row=2, column=0, columnspan=3, sticky="we", pady=(8,4))
        for i,(lbl,val) in enumerate([("Più recente vince","newest"),("Preferisci A","prefer_left"),("Preferisci B","prefer_right")]):
            ttk.Radiobutton(polf, text=lbl, variable=self.policy_var, value=val).grid(row=0, column=i, sticky="w", padx=6)

        # Conservative / trash
        optf = ttk.LabelFrame(frame, text="Eliminazioni")
        optf.grid(row=3, column=0, columnspan=3, sticky="we", pady=(4,4))
        ttk.Checkbutton(optf, text="Modalità conservativa (ripristina file mancanti)", variable=self.cons_var).grid(row=0, column=0, sticky="w", padx=6)
        ttk.Checkbutton(optf, text="Se propaghi, usa cestino (.sync_trash)", variable=self.trash_var).grid(row=0, column=1, sticky="w", padx=6)

        # Filters
        filt = ttk.LabelFrame(frame, text="Filtri (glob separati da virgola)")
        filt.grid(row=4, column=0, columnspan=3, sticky="we", pady=(4,4))
        ttk.Label(filt, text="Include").grid(row=0, column=0, sticky="e")
        ttk.Entry(filt, textvariable=self.include_var, width=60).grid(row=0, column=1, sticky="we")
        ttk.Label(filt, text="Exclude").grid(row=1, column=0, sticky="e")
        ttk.Entry(filt, textvariable=self.exclude_var, width=60).grid(row=1, column=1, sticky="we")

        # Schedule
        sched = ttk.LabelFrame(frame, text="Pianificazione")
        sched.grid(row=5, column=0, columnspan=3, sticky="we", pady=(4,4))
        ttk.Label(sched, text="Intervallo (s, 0=default)").grid(row=0, column=0, sticky="e")
        ttk.Spinbox(sched, from_=0, to=86400, textvariable=self.interval_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(sched, text="Finestra silenziosa HH:MM-HH:MM").grid(row=1, column=0, sticky="e")
        ttk.Entry(sched, textvariable=self.silent_var, width=20).grid(row=1, column=1, sticky="w")

        # Notes
        ttk.Label(frame, text="Note").grid(row=6, column=0, sticky="ne")
        ttk.Entry(frame, textvariable=self.notes_var, width=70).grid(row=6, column=1, columnspan=2, sticky="we")

        # Buttons
        btns = ttk.Frame(frame); btns.grid(row=7, column=0, columnspan=3, sticky="e", pady=(8,0))
        ttk.Button(btns, text="Anteprima", command=self._preview).pack(side="left", padx=4)
        ttk.Button(btns, text="Salva", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="left", padx=4)

        for i in range(3): frame.columnconfigure(i, weight=0)
        self.grab_set()
        self.transient(master)

    def _browse_left(self):
        p = filedialog.askdirectory(title="Seleziona Cartella A")
        if p: self.left_var.set(p)

    def _browse_right(self):
        p = filedialog.askdirectory(title="Seleziona Cartella B")
        if p: self.right_var.set(p)

    def _collect(self) -> Optional[Pair]:
        a = self.left_var.get().strip()
        b = self.right_var.get().strip()
        if not a or not b: 
            messagebox.showwarning(APP_NAME, "Seleziona entrambe le cartelle.")
            return None
        if not Path(a).exists() or not Path(b).exists():
            messagebox.showerror(APP_NAME, "Una delle cartelle non esiste.")
            return None
        inc = [s.strip() for s in self.include_var.get().split(",") if s.strip()]
        exc = [s.strip() for s in self.exclude_var.get().split(",") if s.strip()]
        return Pair(
            left=a, right=b, conservative=self.cons_var.get(), use_trash=self.trash_var.get(),
            conflict_policy=self.policy_var.get(), include_globs=inc, exclude_globs=exc,
            notes=self.notes_var.get(), sync_interval=int(self.interval_var.get()),
            silent_hours=self.silent_var.get().strip()
        )

    def _preview(self):
        p = self._collect()
        if not p: return
        # Dry run veloce (usa engine)
        engine = SyncEngine([p], lambda m: None, lambda *a: None, lambda *a: None,
                            threading.Event(), threading.Event(), {"retention_days": 30})
        plan, _, _ = engine.dry_run_pair(p)
        dlg = tk.Toplevel(self); dlg.title("Anteprima"); dlg.geometry("800x400")
        tv = ttk.Treeview(dlg, columns=("azione","rel","size"), show="headings")
        tv.heading("azione", text="Azione")
        tv.heading("rel", text="Percorso relativo")
        tv.heading("size", text="Dimensione")
        tv.pack(fill="both", expand=True)
        for action, src, dst, size, rel, extra in plan:
            if action == "COPY_A2B":
                a = "Copia A→B"
            elif action == "COPY_B2A":
                a = "Copia B→A"
            elif action == "DELETE_A":
                a = "Elimina in A"
            elif action == "DELETE_B":
                a = "Elimina in B"
            elif action == "RENAME_A":
                a = "Rinomina in A"
            elif action == "RENAME_B":
                a = "Rinomina in B"
            else:
                a = action
            tv.insert("", "end", values=(a, rel, human_bytes(size)))
        ttk.Button(dlg, text="Chiudi", command=dlg.destroy).pack(pady=6)

    def _save(self):
        p = self._collect()
        if not p: return
        self.on_save(p)
        self.destroy()

class App(tk.Tk):
    def __init__(self, start_hidden: bool = False):
        super().__init__()
        self.title(f"{APP_NAME} – Sync bidirezionale")
        self.geometry("1040x680")
        self.minsize(900, 560)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.config_path = app_dir() / CONFIG_NAME
        self.log_path = app_dir() / LOG_NAME
        self.state = {
            "pairs": [],        # list of Pair as dict
            "monitor": False,
            "interval": 10,     # sec
            "retention_days": 30
        }

        # threads & comms
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.log_queue = queue.Queue()
        self.tray_icon = None
        self.last_run: Dict[str, float] = {}
        self._build_ui()
        self._load_config()
        if start_hidden:
            self.withdraw()
            self._create_tray_icon()
        # avvio auto-sync all'apertura
        self.after(500, self.start_sync)
        self.after(120, self._flush_log_queue)

    # ---------------- UI ----------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # Top controls
        top = ttk.Frame(self); top.pack(fill="x", **pad)
        ttk.Button(top, text="Aggiungi coppia…", command=self._add_pair).pack(side="left")
        ttk.Button(top, text="Modifica selezionata…", command=self._edit_selected).pack(side="left", padx=6)
        ttk.Button(top, text="Rimuovi selezionata", command=self._remove_selected).pack(side="left", padx=6)
        ttk.Button(top, text="Salva config", command=self._save_config).pack(side="left", padx=6)
        ttk.Button(top, text="Anteprima sync", command=self._preview_all).pack(side="left", padx=6)

        # Settings
        settings = ttk.Frame(self); settings.pack(fill="x", **pad)
        self.monitor_var = tk.BooleanVar(value=False)
        self.interval_var = tk.IntVar(value=10)
        self.retention_var = tk.IntVar(value=30)
        ttk.Checkbutton(settings, text="Monitora continuamente", variable=self.monitor_var, command=self._toggle_monitor).pack(side="left")
        ttk.Label(settings, text="Intervallo (s):").pack(side="left", padx=(10,4))
        ttk.Spinbox(settings, from_=5, to=7200, textvariable=self.interval_var, width=6).pack(side="left")
        ttk.Label(settings, text="Retention (giorni) archivio/cestino:").pack(side="left", padx=(10,4))
        ttk.Spinbox(settings, from_=0, to=3650, textvariable=self.retention_var, width=6).pack(side="left")

        # Middle: pairs + log
        mid = ttk.Panedwindow(self, orient="horizontal"); mid.pack(fill="both", expand=True, **pad)

        leftpane = ttk.Frame(mid); mid.add(leftpane, weight=1)
        ttk.Label(leftpane, text="Coppie configurate").pack(anchor="w")
        cols = ("A","B","cons","policy","filters","sched","notes")
        self.pairs_tv = ttk.Treeview(leftpane, columns=cols, show="headings", height=8)
        self.pairs_tv.heading("A", text="Cartella A")
        self.pairs_tv.heading("B", text="Cartella B")
        self.pairs_tv.heading("cons", text="Conservativa")
        self.pairs_tv.heading("policy", text="Conflitti")
        self.pairs_tv.heading("filters", text="Filtri")
        self.pairs_tv.heading("sched", text="Pianifica")
        self.pairs_tv.heading("notes", text="Note")
        self.pairs_tv.pack(fill="both", expand=True, pady=(4,6))

        btns = ttk.Frame(leftpane); btns.pack(fill="x")
        ttk.Button(btns, text="Avvia sync ora", command=self.start_sync).pack(side="left")
        ttk.Button(btns, text="Pausa/Riprendi", command=self._toggle_pause).pack(side="left", padx=6)
        ttk.Button(btns, text="Stop", command=self._stop_sync).pack(side="left", padx=6)
        ttk.Button(btns, text="Esporta log", command=self._export_log).pack(side="left", padx=6)

        rightpane = ttk.Frame(mid); mid.add(rightpane, weight=1)
        ttk.Label(rightpane, text="Log").pack(anchor="w")
        self.log_txt = tk.Text(rightpane, height=12, wrap="word")
        self.log_txt.pack(fill="both", expand=True, pady=(4,4))
        self.log_txt.configure(state="disabled")

        # Bottom: progress
        bottom = ttk.Frame(self); bottom.pack(fill="x", **pad)
        self.progress_actions = ttk.Progressbar(bottom, orient="horizontal", mode="determinate")
        self.progress_actions.pack(fill="x")
        self.progress_bytes = ttk.Progressbar(bottom, orient="horizontal", mode="determinate")
        self.progress_bytes.pack(fill="x", pady=(4,0))
        self.status_lbl = ttk.Label(bottom, text="Pronto")
        self.status_lbl.pack(anchor="w")

    # ---------- pairs CRUD ----------
    def _pairs_from_state(self) -> List[Pair]:
        out = []
        for p in self.state.get("pairs", []):
            try:
                out.append(Pair(**p))
            except Exception:
                pass
        return out

    def _refresh_pairs_list(self):
        for i in self.pairs_tv.get_children():
            self.pairs_tv.delete(i)
        for p in self._pairs_from_state():
            filters = ""
            if p.include_globs: filters += "inc:" + ";".join(p.include_globs) + " "
            if p.exclude_globs: filters += "exc:" + ";".join(p.exclude_globs)
            sched = ""
            if getattr(p, "sync_interval", 0):
                sched += f"{p.sync_interval}s"
            if getattr(p, "silent_hours", ""):
                if sched: sched += " "
                sched += f"sil:{p.silent_hours}"
            self.pairs_tv.insert("", "end", values=(p.left, p.right, "sì" if p.conservative else "no", p.conflict_policy, filters.strip(), sched.strip(), p.notes))

    def _add_pair(self):
        def on_save(pair: Pair):
            d = asdict(pair)
            self.state["pairs"].append(d)
            self._refresh_pairs_list()
            self._save_config()
        PairEditor(self, None, on_save)

    def _edit_selected(self):
        sel = self.pairs_tv.selection()
        if not sel:
            messagebox.showinfo(APP_NAME, "Seleziona una coppia da modificare.")
            return
        index = self.pairs_tv.index(sel[0])
        p = Pair(**self.state["pairs"][index])
        def on_save(pair: Pair):
            self.state["pairs"][index] = asdict(pair)
            self._refresh_pairs_list()
            self._save_config()
        PairEditor(self, p, on_save)

    def _remove_selected(self):
        sel = self.pairs_tv.selection()
        if not sel: return
        index = self.pairs_tv.index(sel[0])
        del self.state["pairs"][index]
        self._refresh_pairs_list()
        self._save_config()

    # ---------- config ----------
    def _save_config(self):
        self.state["monitor"] = bool(self.monitor_var.get())
        self.state["interval"] = int(self.interval_var.get())
        self.state["retention_days"] = int(self.retention_var.get())
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            self._log("💾 Configurazione salvata.")
        except Exception as e:
            self._log(f"❌ Errore salvataggio config: {e}")

    def _load_config(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            self.monitor_var.set(bool(self.state.get("monitor", False)))
            self.interval_var.set(int(self.state.get("interval", 10)))
            self.retention_var.set(int(self.state.get("retention_days", 30)))
            self._refresh_pairs_list()
        except Exception as e:
            self._log(f"⚠️  Impossibile leggere la config: {e}")

    # ---------- log & progress ----------
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_queue.put(line)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _flush_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_txt.configure(state="normal")
                self.log_txt.insert("end", line)
                self.log_txt.see("end")
                self.log_txt.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._flush_log_queue)

    def _tray_image(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle((8, 8, 56, 56), fill=(0, 120, 215))
        return img

    def _create_tray_icon(self):
        def _show(icon, item):
            self.deiconify()
            self.focus_force()

        def _quit(icon, item):
            icon.stop()
            self.on_close()

        menu = pystray.Menu(tray_item("Apri", _show), tray_item("Esci", _quit))
        self.tray_icon = pystray.Icon("bisyncplus", self._tray_image(), APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _notify(self, title: str, message: str):
        try:
            notification.notify(title=title, message=message, app_name=APP_NAME, timeout=5)
        except Exception:
            pass

    def _progress(self, done_actions, total_actions, done_bytes, total_bytes):
        self.progress_actions["maximum"] = max(1, total_actions)
        self.progress_actions["value"] = done_actions
        self.progress_bytes["maximum"] = max(1, total_bytes)
        self.progress_bytes["value"] = done_bytes

    def _status(self, rate_bps: float, eta_s: float):
        self.status_lbl.config(text=f"Trasferiti {human_bytes(int(self.progress_bytes['value']))} / {human_bytes(int(self.progress_bytes['maximum']))}  |  Velocità {human_bytes(int(rate_bps))}/s  |  ETA {fmt_eta(eta_s)}")

    # ---------- sync ----------
    def start_sync(self, pairs: Optional[List[Pair]] = None):
        if pairs is None:
            pairs = self._pairs_from_state()
        if not pairs:
            self._log("ℹ️  Nessuna coppia configurata.")
            return
        self._log("▶️  Avvio sincronizzazione…")
        self._notify("Sincronizzazione", "Avviata")
        self.stop_event.clear()
        self.pause_event.clear()
        t = threading.Thread(target=self._run_sync_thread, args=(pairs,), daemon=True)
        t.start()

    def _run_sync_thread(self, pairs: List[Pair]):
        engine = SyncEngine(
            pairs=pairs,
            log_cb=self._log,
            progress_cb=self._progress,
            status_cb=self._status,
            stop_event=self.stop_event,
            pause_event=self.pause_event,
            settings={"retention_days": int(self.retention_var.get())}
        )
        engine.run()
        now = time.time()
        for p in pairs:
            self.last_run[p.id_hash()] = now
        self._notify("Sincronizzazione", "Completata")

    def _is_silent(self, p: Pair) -> bool:
        sh = getattr(p, "silent_hours", "")
        if not sh:
            return False
        try:
            start_s, end_s = sh.split("-")
            now = datetime.now().time()
            t0 = datetime.strptime(start_s.strip(), "%H:%M").time()
            t1 = datetime.strptime(end_s.strip(), "%H:%M").time()
            if t0 < t1:
                return t0 <= now < t1
            else:
                return now >= t0 or now < t1
        except Exception:
            return False

    def _toggle_monitor(self):
        enable = self.monitor_var.get()
        self._save_config()
        if enable:
            self._log("🕒 Monitoraggio continuo attivo.")
            t = threading.Thread(target=self._monitor_loop, daemon=True)
            t.start()
        else:
            self._log("🕒 Monitoraggio continuo disattivato.")

    def _monitor_loop(self):
        while self.monitor_var.get():
            due: List[Pair] = []
            now = time.time()
            for p in self._pairs_from_state():
                interval = getattr(p, "sync_interval", 0) or int(self.interval_var.get())
                last = self.last_run.get(p.id_hash(), 0)
                if now - last < interval:
                    continue
                if self._is_silent(p):
                    continue
                due.append(p)
            if due:
                if self.stop_event.is_set():
                    self.stop_event.clear()
                self.start_sync(due)
            for _ in range(10):
                if not self.monitor_var.get():
                    return
                time.sleep(0.1)

    def _toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self._log("⏯️ Riprendi")
        else:
            self.pause_event.set()
            self._log("⏸️ Pausa")

    def _stop_sync(self):
        self.stop_event.set()
        self._log("⏹️ Stop richiesto")

    def _preview_all(self):
        pairs = self._pairs_from_state()
        if not pairs:
            messagebox.showinfo(APP_NAME, "Nessuna coppia configurata.")
            return
        dlg = tk.Toplevel(self); dlg.title("Anteprima totale"); dlg.geometry("900x420")
        tv = ttk.Treeview(dlg, columns=("pair","azione","rel","size"), show="headings")
        tv.heading("pair", text="Coppia")
        tv.heading("azione", text="Azione")
        tv.heading("rel", text="Percorso relativo")
        tv.heading("size", text="Dimensione")
        tv.pack(fill="both", expand=True)
        engine = SyncEngine(pairs, lambda m: None, lambda *a: None, lambda *a: None,
                            threading.Event(), threading.Event(), {"retention_days": int(self.retention_var.get())})
        total_size = 0
        total_actions = 0
        for p in pairs:
            plan, _, _ = engine.dry_run_pair(p)
            for action, src, dst, size, rel, extra in plan:
                if action == "COPY_A2B":
                    a = "A→B"
                elif action == "COPY_B2A":
                    a = "B→A"
                elif action == "DELETE_A":
                    a = "Elimina A"
                elif action == "DELETE_B":
                    a = "Elimina B"
                elif action == "RENAME_A":
                    a = "Rinomina A"
                elif action == "RENAME_B":
                    a = "Rinomina B"
                else:
                    a = action
                tv.insert("", "end", values=(f"{p.left} ↔ {p.right}", a, rel, human_bytes(size)))
                total_size += size
                total_actions += 1
        ttk.Label(dlg, text=f"Totale azioni: {total_actions} | Dati: {human_bytes(total_size)}").pack(anchor="e", padx=8, pady=6)
        ttk.Button(dlg, text="Chiudi", command=dlg.destroy).pack(pady=6)

    def _export_log(self):
        try:
            if not self.log_path.exists():
                messagebox.showinfo(APP_NAME, "Nessun log ancora disponibile.")
                return
            dest = filedialog.asksaveasfilename(title="Esporta log", defaultextension=".txt",
                                                initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
            if dest:
                shutil.copy2(self.log_path, dest)
                messagebox.showinfo(APP_NAME, "Log esportato.")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Errore esportazione log: {e}")

    def on_close(self):
        self.stop_event.set()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.destroy()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--tray", action="store_true", help="Avvia minimizzato nella tray")
    args = parser.parse_args()

    ensure_windows_autostart()

    app = App(start_hidden=args.tray)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
