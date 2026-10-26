# CachyOS / KDE Plasma Workspace Startup Automation

A bash script designed specifically for **CachyOS** running **KDE Plasma 6 (Wayland & X11)** to automatically launch applications and route them to dedicated virtual desktops upon login or on demand.

---

## Workspace Layout

| Virtual Desktop | Application | Executable / Desktop Entry |
| :--- | :--- | :--- |
| **Desktop 1** | **Antigravity IDE** | `antigravity-ide` |
| **Desktop 2** | **Google Chrome** | `google-chrome-stable` |
| **Desktop 3** | **Spotify** | `spotify-launcher` |
| **Desktop 4** | **KWrite** | `org.kde.kwrite` |

---

## How It Works

1. **Window Manager Readiness**: Verifies that `kwin_wayland` and its DBus endpoints (`qdbus6`) are initialized before launching anything (essential during boot).
2. **Virtual Desktop Assurance**: Confirms that at least 4 virtual desktops are available in KDE, creating them automatically if fewer exist.
3. **Native KWin Wayland Routing**: Dynamically connects a lightweight KWin script that listens to `workspace.windowAdded` events. When any of the target applications create their windows, KWin immediately routes them to their designated desktop without screen flickering or race conditions.
4. **App Initialization & Grace Period**: Starts each application (skipping any that are already running) and maintains the router for a 12-second grace period.
5. **Clean Teardown**: Stops and unloads the KWin listener, returning focus to Desktop 1 (Antigravity).

---

## Usage

### 1. Manual Execution
Run the script anytime to launch any missing applications and place them on their respective desktops:

```bash
./workspace_startup.sh
```

### 2. Enable Automatic Startup on Login (Recommended)
To run the script automatically when you log into CachyOS:

```bash
./workspace_startup.sh --install-autostart
```

This generates `~/.config/autostart/workspace-startup.desktop` with `X-KDE-autostart-phase=2`, ensuring KDE Plasma is fully ready before launching.

### 3. Disable Automatic Startup
To remove the script from your login autostart:

```bash
./workspace_startup.sh --uninstall-autostart
```
