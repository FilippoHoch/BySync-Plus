# 🔁 BiSync+ – HF_OMNITOOL

![screenshot principale](docs/img/screenshot_main.png)

## 📖 Descrizione
**BiSync+** è uno strumento portabile e automatico per la **sincronizzazione bidirezionale** di cartelle, progettato per funzionare direttamente dalla chiavetta USB **HF_OMNITOOL**. Mantiene cartelle allineate, gestisce conflitti, salva versioni precedenti e offre un’interfaccia grafica semplice e chiara.

## Indice
- [Funzionalità principali](#-funzionalità-principali)
- [Screenshot](#-screenshot)
- [Installazione](#-installazione)
  - [Opzione A — Esegui da Python](#opzione-a--esegui-da-python)
  - [Opzione B — Eseguibile portabile](#opzione-b--eseguibile-portabile)
- [Avvio automatico](#-avvio-automatico)
- [Architettura](#-architettura)
- [Sicurezza](#-sicurezza)
- [Casi d’uso](#-casi-duso)
- [Licenza](#-licenza)
- [Contributi](#-contributi)
- [TODO / Idee future](#-todo--idee-future)

## ✨ Funzionalità principali

- 🔄 **Sync bidirezionale** (PC ↔ USB o qualsiasi altra coppia di cartelle)
- 🛡️ **Modalità eliminazioni** configurabile per *singola coppia*:
  - Conservativa: ripristina i file mancanti
  - Propagazione: elimina ovunque i file rimossi (con opzione cestino)
- 🔁 **Propagazione rinomini** basata su hash dei file
- 📦 **Archivio versioni** (`.sync_archive`) per i file sovrascritti
- 🗑️ **Cestino sicuro** (`.sync_trash`) per file eliminati
- 🕒 **Retention automatica** (es. 30 giorni, configurabile)
- 👁️ **Anteprima (dry-run)** delle azioni prima di eseguire la sincronizzazione
- 📊 **Interfaccia grafica** con:
  - log in tempo reale
  - barra di avanzamento
  - velocità media ed ETA
  - pulsanti Avvia, Pausa, Stop
- ⏱️ **Monitoraggio continuo** (ripete la sync ogni N secondi)
- ⚡ **Portabilità totale**:
  - Nessuna dipendenza esterna (solo Python + Tkinter)
  - Pacchettizzabile in un singolo eseguibile con **PyInstaller**
- 🔌 **Avvio automatico all’inserimento** della chiavetta **HF_OMNITOOL**
- 🖥️ **Icona tray con notifiche desktop**

## 📷 Screenshot

| Gestione coppie | Finestra di configurazione | Anteprima azioni |
|-----------------|----------------------------|-----------------|
| ![coppie](docs/img/screenshot_pairs.png) | ![editor](docs/img/screenshot_editor.png) | ![anteprima](docs/img/screenshot_preview.png) |

## 🚀 Installazione

### Opzione A — Esegui da Python
1. Installa [Python 3.9+](https://www.python.org/downloads/)
2. Clona il repository:
   ```bash
   git clone https://github.com/tuo-utente/bisync-plus.git
   cd bisync-plus
   ```
3. Avvia:
   ```bash
   pip install pystray plyer Pillow
   python bisync_plus.py
   ```

### Opzione B — Eseguibile portabile

Crea un eseguibile singolo con [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name BiSyncPlus bisync_plus.py
```

Troverai `BiSyncPlus.exe` (Windows) o `BiSyncPlus` (macOS/Linux) in `dist/`.

Copia l’eseguibile nella **radice della chiavetta** **HF_OMNITOOL**.

## ⚡ Avvio automatico

Per motivi di sicurezza, i sistemi operativi non permettono più l’`autorun.inf`.
Questi sono i metodi supportati:

* **Windows**: script PowerShell + Attività Pianificata (detect etichetta `HF_OMNITOOL`)
* **macOS**: regola `launchd`
* **Linux**: regola `udev`

👉 Vedi [docs/autostart.md](docs/autostart.md) per i dettagli.

## 📐 Architettura

```
bisync_plus.py
 ├─ GUI (Tkinter)
 │   ├─ gestione coppie cartelle
 │   ├─ log, progress bar, controlli
 │   └─ anteprima sync
 ├─ Core (SyncEngine)
 │   ├─ confronto cartelle
 │   ├─ generazione piano azioni
 │   └─ esecuzione (copy / delete / archive / trash)
 ├─ Snapshot
 │   └─ .bisync_state_xxx.json (rileva eliminazioni)
 └─ Config & Log
     ├─ bisync_config.json
     ├─ bisync_log.txt
     ├─ .sync_archive/
     └─ .sync_trash/
```

## 🛡️ Sicurezza

* Mai eliminazioni **dirette** senza conferma: tutto passa per archivio o cestino.
* Ogni file sovrascritto viene salvato con timestamp in `.sync_archive`.
* Retention automatica elimina versioni/cestini vecchi oltre N giorni.
* Snapshots garantiscono che i file nuovi non vengano confusi con file eliminati.

## 📊 Casi d’uso

* Backup bidirezionale tra **PC e USB**
* Trasporto progetti tra più PC
* Sincronizzazione cartelle documenti/foto
* Storico versioni automatico

## 📜 Licenza

MIT License © 2025 — \[Tuo Nome / Organizzazione]

## 🙌 Contributi

Pull request e suggerimenti benvenuti!
Aggiungi screenshot, icone, traduzioni o nuove funzionalità.

## 📌 TODO / Idee future

* 📅 Pianificazione avanzata per singola coppia
* 🌐 Integrazione con cloud (Dropbox/Google Drive/OneDrive)

> **BiSync+ – HF_OMNITOOL**: il tuo **coltellino svizzero** per sincronizzazione e backup sicuri, automatici e portabili.

