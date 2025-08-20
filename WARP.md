# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

BiSync+ is a portable, automatic **bidirectional synchronization** tool designed to work directly from a USB drive with a configurable label (default "HF_OMNITOOL"). It maintains folder alignment, manages conflicts, saves previous versions, and offers a clear graphical interface.

## Tech Stack & Dependencies

- **Python 3.9+** with Tkinter (GUI)
- **Key dependencies:** `pystray`, `plyer`, `Pillow`
- **Build tool:** PyInstaller for creating portable executables
- **Auto-launcher:** PowerShell script + Python USB detection utilities

## Development Commands

### Setup and Dependencies
```powershell
# Install Python dependencies
pip install pystray plyer Pillow

# For development builds
pip install pyinstaller
```

### Running the Application
```powershell
# Run directly from source (development mode)
python bisync_plus.py

# Run with system tray startup (production mode)
python bisync_plus.py --tray
```

### Building Executables
```powershell
# Create standalone executable using PyInstaller
pyinstaller --noconsole --onefile --name BiSyncPlus bisync_plus.py

# Alternative using the spec file
pyinstaller BiSyncPlus.spec

# The executable will be in dist/BiSyncPlus.exe
```

### USB Auto-Launcher Setup
```powershell
# Build the USB detection utility
# (These would need to be built separately with PyInstaller)
pyinstaller --onefile --name USBDetect usb_detect.py
pyinstaller --onefile --name USBDetectInstaller usb_detect_installer.py

# Run the installer to setup auto-start
.\USBDetectInstaller.exe
```

### Testing and Configuration
```powershell
# Test individual components
python usb_detect.py          # Test USB detection
python usb_detect_installer.py # Test installer GUI

# Check configuration files
type bisync_config.json        # Main app configuration
type usb_detect_config.json    # USB detection configuration
type bisync_log.txt           # Application logs
```

## Architecture

### Core Components

1. **SyncEngine** (`bisync_plus.py:154-485`)
   - Handles bidirectional synchronization logic
   - Manages file comparison, conflict resolution, and action planning
   - Supports conservative mode (restore missing files) vs propagation mode (sync deletions)
   - Implements rename detection via file hashing
   - Manages `.sync_archive` and `.sync_trash` folders for safety

2. **Snapshot System** (`bisync_plus.py:93-153`)
   - Tracks file states in `.bisync_state_*.json` files
   - Distinguishes between new files and deleted files
   - Stores file metadata (mtime, size, hash) for change detection

3. **GUI Application** (`bisync_plus.py:627-1051`)
   - Tkinter-based interface with pair management
   - Real-time logging, progress bars, and status updates
   - Tray icon support for background operation
   - Configuration editor for sync pairs

4. **USB Auto-Launch System**
   - `usb_detect.py`: Core USB detection and app launching
   - `usb_detect_installer.py`: GUI installer for Windows scheduled tasks
   - `USB-Detect.ps1`: PowerShell fallback script with WMI events

### Key Data Structures

- **Pair** (`bisync_plus.py:70-92`): Configuration for a sync pair with policies, filters, and scheduling
- **Snapshot** data format: JSON files tracking file states across syncs
- **Configuration**: JSON-based settings in `bisync_config.json` and `usb_detect_config.json`

### File Organization

```
bisync_plus.py          # Main application (GUI + sync engine)
usb_detect.py           # USB detection utility  
usb_detect_installer.py # Auto-start installer
USB-Detect.ps1          # PowerShell fallback
BiSyncPlus.spec         # PyInstaller spec file
*.json                  # Configuration files
.sync_archive/          # Backup of overwritten files
.sync_trash/            # Deleted files (when use_trash=True)
.bisync_state_*.json    # State snapshots per sync pair
```

### Sync Behavior

- **Conservative mode**: Restores missing files (assumes accidental deletion)
- **Propagation mode**: Syncs deletions (uses snapshot to detect actual deletions vs new files)
- **Conflict resolution**: Newest wins, prefer left, or prefer right
- **File safety**: All overwrites go to `.sync_archive/`, deletions to `.sync_trash/`
- **Rename detection**: Uses MD5 hashing to track file moves/renames

## Configuration

### Main App Settings (`bisync_config.json`)
- `pairs`: Array of sync pair configurations
- `monitor`: Enable continuous monitoring
- `interval`: Default sync interval in seconds  
- `retention_days`: Archive/trash cleanup period

### USB Detection (`usb_detect_config.json`)
- `label`: USB drive label to detect (default "HF_OMNITOOL")
- `relative_exe`: Path to BiSyncPlus.exe relative to drive root

### Sync Pair Configuration
Each pair supports:
- Source/destination paths
- Conservative vs propagation deletion mode
- Conflict resolution policy
- Include/exclude glob patterns
- Individual sync intervals and silent hours
- Custom notes

## USB Auto-Start Architecture

The auto-start system works in layers:
1. **Windows Scheduled Task**: Runs `USBDetect.exe` at login
2. **USB Detection Loop**: Monitors for drives with specific label
3. **App Launch**: Starts BiSyncPlus in tray mode when drive detected
4. **Configuration**: Customizable via `usb_detect_config.json`

This replaces the legacy `autorun.inf` approach which modern Windows blocks for security.
