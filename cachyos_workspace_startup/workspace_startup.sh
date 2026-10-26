#!/usr/bin/env bash
# ==============================================================================
# Workspace Startup Script for CachyOS / KDE Plasma (Wayland & X11)
# ==============================================================================
# Assigns applications to dedicated virtual desktops upon login or on demand:
#   - Desktop 1: Antigravity IDE
#   - Desktop 2: Google Chrome
#   - Desktop 3: Spotify
#   - Desktop 4: KWrite
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/$(basename "${BASH_SOURCE[0]}")"
AUTOSTART_DIR="${HOME}/.config/autostart"
AUTOSTART_FILE="${AUTOSTART_DIR}/workspace-startup.desktop"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_err() {
    echo -e "${RED}[ERROR]${NC} $*"
}

install_autostart() {
    log_info "Configuring autostart entry..."
    mkdir -p "${AUTOSTART_DIR}"
    cat <<EOF > "${AUTOSTART_FILE}"
[Desktop Entry]
Type=Application
Name=CachyOS Workspace Startup
Comment=Launch Antigravity on D1, Chrome on D2, Spotify on D3, KWrite on D4
Exec=${SCRIPT_PATH}
Terminal=false
StartupNotify=false
X-KDE-autostart-phase=2
Categories=Utility;
EOF
    chmod +x "${AUTOSTART_FILE}"
    log_success "Autostart installed to: ${AUTOSTART_FILE}"
    log_info "This script will now run automatically each time you log into CachyOS."
}

uninstall_autostart() {
    if [[ -f "${AUTOSTART_FILE}" ]]; then
        rm -f "${AUTOSTART_FILE}"
        log_success "Removed autostart file: ${AUTOSTART_FILE}"
    else
        log_warn "Autostart file was not installed."
    fi
}

# Parse CLI options
case "$1" in
    --install|--install-autostart)
        install_autostart
        exit 0
        ;;
    --uninstall|--uninstall-autostart)
        uninstall_autostart
        exit 0
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (no args)             Launch and position apps across Desktops 1-4"
        echo "  --install-autostart   Register script to run automatically at KDE login"
        echo "  --uninstall-autostart Remove script from KDE login autostart"
        echo "  --help, -h            Show this help message"
        exit 0
        ;;
esac

# 1. Wait for KWin / DBus to be available (crucial on initial system boot)
log_info "Checking KWin window manager status..."
MAX_WAIT=20
WAIT_COUNT=0
until qdbus6 org.kde.KWin /KWin org.kde.KWin.currentDesktop >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [[ $WAIT_COUNT -ge $MAX_WAIT ]]; then
        log_err "Timeout waiting for KWin DBus service. Exiting."
        exit 1
    fi
done
log_success "KWin is ready."

# 2. Ensure at least 4 virtual desktops exist
CURRENT_COUNT=$(qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.count 2>/dev/null || echo 0)
if [[ $CURRENT_COUNT -lt 4 ]]; then
    log_warn "Detected only $CURRENT_COUNT virtual desktops. Creating required desktops..."
    for i in $(seq $((CURRENT_COUNT + 1)) 4); do
        qdbus6 org.kde.KWin /VirtualDesktopManager org.kde.KWin.VirtualDesktopManager.createDesktop "$i" "Desktop $i" >/dev/null 2>&1 || true
    done
fi

# 3. Create temporary KWin Script to route windows to designated virtual desktops
TMP_JS=$(mktemp /tmp/kwin_startup_XXXXXX.js)
KWIN_SCRIPT_ID=""

cleanup() {
    if [[ -n "$KWIN_SCRIPT_ID" ]]; then
        qdbus6 org.kde.KWin /Scripting/Script"$KWIN_SCRIPT_ID" org.kde.kwin.Script.stop >/dev/null 2>&1 || true
    fi
    if [[ -f "$TMP_JS" ]]; then
        rm -f "$TMP_JS"
    fi
}
trap cleanup EXIT INT TERM

cat << 'EOF' > "$TMP_JS"
const rules = [
    { match: "antigravity", desktop: 0 }, // Desktop 1
    { match: "chrome",      desktop: 1 }, // Desktop 2
    { match: "spotify",     desktop: 2 }, // Desktop 3
    { match: "kwrite",      desktop: 3 }  // Desktop 4
];

function assignDesktop(w) {
    if (!w || !w.normalWindow) return;
    const identifier = ((w.resourceClass || "") + " " + (w.desktopFileName || "")).toLowerCase();
    for (const rule of rules) {
        if (identifier.indexOf(rule.match) !== -1) {
            if (workspace.desktops.length > rule.desktop: 0) {
                w.desktops = [workspace.desktops[rule.desktop]];
                console.log("[KWin AutoPlace] Assigned " + w.resourceClass + " to " + workspace.desktops[rule.desktop].name);
            }
            break;
        }
    }
}

// Reposition any matching windows that are already open
workspace.windowList().forEach(assignDesktop);

// Intercept new windows as they are created
workspace.windowAdded.connect(assignDesktop);
EOF

# Fix typo in the js template if any
sed -i 's/rule.desktop: 0/rule.desktop/g' "$TMP_JS"

log_info "Attaching KWin window router..."
KWIN_SCRIPT_ID=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$TMP_JS" 2>/dev/null || echo "")

if [[ -n "$KWIN_SCRIPT_ID" ]]; then
    qdbus6 org.kde.KWin /Scripting/Script"$KWIN_SCRIPT_ID" org.kde.kwin.Script.run >/dev/null 2>&1 || true
    log_success "KWin router active (ID: $KWIN_SCRIPT_ID)"
else
    log_warn "Could not load KWin DBus script. Continuing with standard launch..."
fi

# 4. Helper function to launch applications
launch_app() {
    local name="$1"
    local check_proc="$2"
    local desktop_entry="$3"
    local fallback_cmd="$4"

    if pgrep -f "$check_proc" >/dev/null 2>&1; then
        log_info "$name is already running."
    else
        log_info "Launching $name..."
        if command -v gtk-launch >/dev/null 2>&1 && [[ -n "$desktop_entry" ]]; then
            gtk-launch "$desktop_entry" >/dev/null 2>&1 &
        else
            nohup $fallback_cmd >/dev/null 2>&1 &
        fi
        disown
    fi
}

# 5. Launch applications
# Desktop 1: Antigravity IDE
launch_app "Antigravity IDE" "antigravity-ide" "antigravity-ide" "/usr/bin/antigravity-ide"

# Desktop 2: Google Chrome
launch_app "Google Chrome" "chrome" "google-chrome" "/usr/bin/google-chrome-stable"

# Desktop 3: Spotify
launch_app "Spotify" "spotify" "spotify-launcher" "spotify-launcher"

# Desktop 4: KWrite
launch_app "KWrite" "kwrite" "org.kde.kwrite" "/usr/bin/kwrite"

# 6. Keep router active for a grace period so opening windows are captured
GRACE_PERIOD=12
log_info "Waiting ${GRACE_PERIOD}s for applications to initialize..."
sleep "$GRACE_PERIOD"

# 7. Set initial focus back to Desktop 1
log_info "Switching active view to Desktop 1 (Antigravity)..."
qdbus6 org.kde.KWin /KWin org.kde.KWin.setCurrentDesktop 1 >/dev/null 2>&1 || true

log_success "Workspace initialization complete!"
