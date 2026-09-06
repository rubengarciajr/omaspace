import QtQuick
import Quickshell.Io
import Quickshell.Hyprland

// Hyprland's native change_id retains the layout but Quickshell 0.3.1 does
// not consume changeworkspaceid. Run in each shell process that caches it.
Item {
    property var shell: null // Omarchy service loader injection

    function refresh() {
        Hyprland.refreshWorkspaces()
        Hyprland.refreshMonitors()
    }
    function scheduleRefresh() { coalesce.restart() }

    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (['changeworkspaceid', 'openwindow', 'closewindow', 'movewindowv2'].includes(event.name)) scheduleRefresh()
        }
    }
    // Coalesce all IDs in a swap. A second pass also replaces any query
    // already in flight when the event arrived; no focus changes are needed.
    Timer {
        id: coalesce
        interval: 25
        onTriggered: { refresh(); settled.restart() }
    }
    Timer { id: settled; interval: 100; onTriggered: refresh() }
    Component.onCompleted: scheduleRefresh()

    IpcHandler {
        target: 'omaspace-sync'
        function inspect(): string {
            return JSON.stringify({
                focused: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : null,
                monitors: Hyprland.monitors.values.map(m => ({name: m.name, workspace: m.activeWorkspace ? m.activeWorkspace.id : null})),
                workspaces: Hyprland.workspaces.values.map(w => ({id: w.id, windows: w.lastIpcObject.windows}))
            })
        }
    }
}
