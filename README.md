# 📂 Progetto **BiSync+ – HF\_OMNITOOL**

## 🎯 Obiettivo

Realizzare uno strumento portabile, automatico e facile da usare che permetta di **sincronizzare bidirezionalmente** cartelle tra la chiavetta USB **HF\_OMNITOOL** e uno o più percorsi locali/remoti, garantendo:

* sicurezza (nessuna perdita dati, archiviazione versioni e cestino);
* flessibilità (scelta di modalità diverse per ciascuna coppia di cartelle);
* immediatezza (partenza automatica all’inserimento della chiavetta, interfaccia grafica semplice, anteprima delle operazioni).

---

## ⚙️ Funzionalità principali

### 🔁 Sincronizzazione bidirezionale

* Mantiene **allineate due cartelle** (lato A e lato B).
* Le modifiche su un lato vengono replicate nell’altro.
* In caso di conflitto (file modificato in entrambe le parti), si applica la politica configurata:

  * **Più recente vince** (default).
  * **Preferisci A**.
  * **Preferisci B**.

### 🛡️ Modalità eliminazioni (per singola coppia)

* **Conservativa (default)**: se un file manca su un lato, viene **ripristinato** dall’altro (evita perdite accidentali).
* **Propagazione eliminazioni**: se un file viene eliminato su un lato, viene eliminato anche sull’altro.

  * Opzione di sicurezza: spostamento nel **cestino interno** (`.sync_trash`) invece della cancellazione diretta.

### 🗄️ Gestione versioni e sicurezza

* I file sovrascritti vengono spostati in un **archivio versioni** (`.sync_archive`).
* **Retention configurabile** (es. elimina automaticamente archivi/cestini più vecchi di 30 giorni).
* Snapshot di stato interno (file nascosto `.bisync_state_xxx.json`) per rilevare correttamente file eliminati vs file nuovi.

### 👁️ Anteprima operazioni (Dry-run)

* Prima di avviare la sincronizzazione, l’utente può vedere:

  * quali file saranno copiati e dove;
  * quali file verranno eliminati o archiviati;
  * il volume totale di dati e il numero di azioni.

### 📊 Interfaccia grafica

* **Gestione coppie cartelle** tramite finestra dedicata:

  * percorso A e B con selezione tramite “Sfoglia”;
  * filtri `include`/`exclude` (pattern glob tipo `*.docx, *.pdf`);
  * note descrittive per l’utente;
  * selezione politica conflitti;
  * scelta modalità conservativa o propagazione eliminazioni.
* **Monitoraggio sincronizzazione**:

  * barra di avanzamento azioni e byte;
  * log in tempo reale;
  * indicazione velocità media e tempo stimato (ETA).
* **Controlli**:

  * Avvio sincronizzazione manuale.
  * Anteprima completa.
  * Pausa/Riprendi/Stop.
  * Esportazione log.

### ⏱️ Modalità monitoraggio continuo

* Opzione per mantenere la sincronizzazione attiva ogni *N* secondi.
* Intervallo configurabile (es. ogni 10 secondi, ogni 5 minuti, ecc.).

### 📦 Portabilità

* Progetto scritto in **Python 3** con GUI **Tkinter** (nessuna dipendenza esterna).
* Pacchettizzabile in eseguibile singolo (`BiSyncPlus.exe` / `BiSyncPlus`) con **PyInstaller**.
* Tutti i dati di configurazione e log sono salvati accanto all’eseguibile sulla chiavetta:

  * `bisync_config.json` → configurazioni coppie.
  * `bisync_log.txt` → log storico.
  * `.sync_archive` e `.sync_trash` → sicurezza file.
  * `.bisync_state_xxx.json` → snapshot interno per ogni coppia.

### ⚡ Avvio automatico all’inserimento

* L’eseguibile viene avviato automaticamente quando si inserisce la chiavetta **HF\_OMNITOOL**:

  * **Windows**: script PowerShell + attività pianificata.
  * **macOS**: regola `launchd`.
  * **Linux**: regola `udev`.

---

## 📐 Architettura tecnica

1. **Core di sincronizzazione (SyncEngine)**:

   * Scansiona entrambe le cartelle (A, B).
   * Applica filtri di include/exclude.
   * Confronta lo stato attuale con lo snapshot precedente.
   * Genera un **piano di azioni** (copy A→B, copy B→A, delete A, delete B).
   * Esegue le operazioni rispettando le opzioni (archivio/cestino).
   * Aggiorna snapshot per la successiva esecuzione.

2. **GUI (Tkinter)**:

   * Gestione coppie cartelle e configurazioni.
   * Monitoraggio avanzamento e log.
   * Anteprima azioni.

3. **Automazione avvio**:

   * Rilevamento etichetta chiavetta (**HF\_OMNITOOL**).
   * Avvio trasparente dell’eseguibile.

---

## 🔒 Sicurezza & Robustezza

* **Nessuna eliminazione diretta** se non esplicitamente richiesto dall’utente.
* File sovrascritti/eliminati sempre salvati in area sicura con timestamp.
* File speciali e link simbolici ignorati per evitare cicli e inconsistenze.
* Compatibile con filesystem Windows, macOS, Linux.
* Gestione crash/stop → ripartenza senza corruzione dati (grazie a snapshot).

---

## 🚀 Casi d’uso tipici

* Tenere allineata una cartella di lavoro tra **PC e chiavetta**.
* Backup bidirezionale di documenti, progetti o foto.
* Condivisione sicura di cartelle tra **PC diversi** usando la chiavetta come ponte.
* Archiviazione storica automatica delle versioni modificate.

---

## 📊 Vantaggi

* Portabile (gira ovunque senza installazione).
* Sicuro (archivio, cestino, snapshot).
* Personalizzabile (filtri, politiche, retention, modalità).
* Automatizzato (parte da solo con la chiavetta).
* Trasparente (log dettagliato, anteprima, interfaccia chiara).

---

👉 In sintesi: **BiSync+ (HF\_OMNITOOL)** è un **gestore di sincronizzazione intelligente e sicuro**, progettato per chi vuole un backup bidirezionale automatizzato con controllo totale e interfaccia intuitiva.
