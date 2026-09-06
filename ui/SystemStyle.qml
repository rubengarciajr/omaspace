pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "file:/usr/share/omarchy/shell/Commons" as Omarchy

// Use the installed shell's tokens, including ~/.config/omarchy/shell.toml.
// Do not copy theme defaults here: Omarchy remains the source of truth.
QtObject {
    id: root
    readonly property var font: Omarchy.Style.font
    readonly property string fontFamily: Omarchy.Style.font.menuFamily === Omarchy.Style.font.family
        ? Omarchy.Style.font.resolvedFamily : Omarchy.Style.font.menuFamily
    readonly property var spacing: Omarchy.Style.spacing
    readonly property real cornerRadius: Omarchy.Style.cornerRadius
    readonly property var colors: Omarchy.Color
    property real borderWidth: Omarchy.Style.normalBorderWidth

    function space(value) { return Omarchy.Style.space(value) }
    function refresh() {
        Omarchy.Style.refresh()
        Omarchy.Style.resolveFontFamily()
        // The main shell receives theme IPC; our separate process reads the
        // same files on open and while visible instead of keeping startup values.
        colors.colorsFile.reload()
        colors.shellFile.reload()
        colors.userShellFile.reload()
        if (!borderQuery.running) borderQuery.running = true
    }
    property Process borderQuery: Process {
        command: ['hyprctl', '-j', 'getoption', 'general:border_size']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const value = JSON.parse(text).int
                    if (typeof value === 'number' && value >= 0) root.borderWidth = value
                } catch (e) { console.warn('OmaSpace could not refresh system border width:', e) }
            }
        }
    }
    Component.onCompleted: refresh()
}
