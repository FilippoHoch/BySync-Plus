param([switch]$Silent = $true)

$ErrorActionPreference = "Continue"
$Label = "HF_OMNITOOL"
$RelativeExe = "Documents\BySync Plus\dist\BiSyncPlus.exe"
$Log = Join-Path $env:LOCALAPPDATA "BiSyncPlus\usb-detect.log"

# --- Log ---
New-Item -ItemType Directory -Path (Split-Path $Log) -Force | Out-Null
function Log([string]$msg){ Add-Content -Path $Log -Value "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg }

# --- no doppie istanze dello script ---
Add-Type -AssemblyName System.Threading
$mutex = New-Object System.Threading.Mutex($false, "Global\USBDetect_BiSyncPlus")
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
