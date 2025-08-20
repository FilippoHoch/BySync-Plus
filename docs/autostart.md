# ⚡ Avvio automatico di BiSync+ (HF_OMNITOOL)

Per motivi di sicurezza, i sistemi operativi moderni **non supportano più autorun diretto** da chiavetta USB.  
Per questo BiSync+ utilizza un avvio automatico tramite regole di sistema, basate sull’etichetta del volume: **HF_OMNITOOL**.

---

## 🪟 Windows

1. **Rinomina la chiavetta**:
   - Nome etichetta: `HF_OMNITOOL`

2. **Salva questo script** come `USB-Detect.ps1` sul PC:

```powershell
   $Label = "HF_OMNITOOL"
   $ExeName = "BiSyncPlus.exe"

   while ($true) {
     $vol = Get-CimInstance -ClassName Win32_Volume -Filter "Label='$Label' AND DriveType=2" -ErrorAction SilentlyContinue
     if ($vol) {
       $path = Join-Path $vol.DriveLetter $ExeName
       if (Test-Path $path) { Start-Process -FilePath $path }
       do { Start-Sleep -Seconds 2 } while (Get-CimInstance -ClassName Win32_Volume -Filter "Label='$Label' AND DriveType=2" -ErrorAction SilentlyContinue)
     }
     Start-Sleep -Seconds 2
   }
```

3. **Crea un’attività pianificata** che lanci lo script ad ogni login:

```powershell
   $Script = "C:\Percorso\USB-Detect.ps1"
   $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""
   $Trigger = New-ScheduledTaskTrigger -AtLogOn
   Register-ScheduledTask -TaskName "BiSyncPlus USB AutoStart" -Action $Action -Trigger $Trigger -Description "Lancia BiSyncPlus all'inserimento HF_OMNITOOL" -User "$env:UserName"
```

---

## 🍎 macOS

1. **Rinomina la chiavetta**: `HF_OMNITOOL`

2. **Crea un file LaunchAgent** in `~/Library/LaunchAgents/com.bisyncplus.autorun.plist`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.bisyncplus.autorun</string>
     <key>StartOnMount</key><true/>
     <key>ProgramArguments</key>
     <array>
       <string>/Volumes/HF_OMNITOOL/BiSyncPlus</string>
     </array>
     <key>RunAtLoad</key><true/>
   </dict>
   </plist>
   ```

3. **Carica la regola**:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.bisyncplus.autorun.plist
   ```

Da ora in poi, all’inserimento della chiavetta, l’app parte automaticamente.

---

## 🐧 Linux (udev)

1. **Rinomina la chiavetta**: `HF_OMNITOOL`

2. **Crea una regola udev** in `/etc/udev/rules.d/99-bisyncplus.rules`:

   ```
   ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="HF_OMNITOOL", RUN+="/usr/local/bin/bisyncplus_autorun.sh"
   ```

3. **Crea lo script `/usr/local/bin/bisyncplus_autorun.sh`**:

   ```bash
   #!/usr/bin/env bash
   sleep 2
   MOUNTPOINT=$(lsblk -o LABEL,MOUNTPOINT -nr | awk '$1=="HF_OMNITOOL"{print $2}')
   [ -z "$MOUNTPOINT" ] && exit 0
   "$MOUNTPOINT/BiSyncPlus" &
   ```

   Rendi eseguibile:

   ```bash
   sudo chmod +x /usr/local/bin/bisyncplus_autorun.sh
   ```

4. **Ricarica udev**:

   ```bash
   sudo udevadm control --reload
   sudo udevadm trigger
   ```

---

## ✅ Risultato

Su tutti i sistemi, quando colleghi la chiavetta **HF\_OMNITOOL**, l’app **BiSyncPlus** viene avviata in automatico e inizia a sincronizzare.


---

# 📂 `docs/img/`

Dentro la cartella `docs/img/` aggiungi dei file segnaposto (anche PNG vuoti o screenshot veri in seguito).  
Esempi:

- `screenshot_main.png` → schermata principale dell’app  
- `screenshot_pairs.png` → lista coppie configurate  
- `screenshot_editor.png` → finestra editor per singola coppia  
- `screenshot_preview.png` → anteprima azioni di sincronizzazione  

Se non hai ancora screenshot reali, puoi creare placeholder con scritte tipo *"Screenshot in arrivo"*.

---

👉 Con questo hai la struttura completa **README + docs + immagini**, pronta per GitHub.  

Vuoi che ti generi anche dei **mockup grafici** (immagini illustrative in stile wireframe o finti screenshot) da usare come segnaposto subito, così il repo appare subito curato anche senza testare l’app?
```
