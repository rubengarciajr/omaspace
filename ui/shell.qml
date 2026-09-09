import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
    id: app
    WorkspaceSync {}
    property bool opened: false
    property bool opening: false
    readonly property bool panelReady: opened && !opening
    property int openRevision: 0
    property bool refreshPending: false
    property var queuedKeys: []
    property var data: ({workspaces: [], clients: [], monitors: [], theme: {background: '#101315', foreground: '#cacccc', accent: '#7cb8a0', font: 'monospace'}})
    readonly property var palette: SystemStyle.colors
    property int selectedId: 1
    property int windowIndex: 0
    property string view: 'workspaces'
    property string screenMode: 'switcher'
    property int quickSource: 0
    property string monitorFilter: ''
    property string dialog: ''
    property int destination: 1
    property string status: 'Your desktop, in order.'
    property bool statusError: false
    property var undoAction: []
    property string actionSource: ''
    property int workspaceSource: 1
    property int swapTarget: 0
    property var displayScreen: null
    readonly property var allWorkspaces: data.workspaces.concat(data.auxiliaryWorkspaces || [])
    readonly property var selectedWorkspace: allWorkspaces.find(w => w.id === selectedId) || {id: selectedId, label: String(selectedId), name: String(selectedId), selector: String(selectedId), clients: [], monitor: ''}
    readonly property string profileName: data.profile ? data.profile.name : 'Detecting displays…'
    readonly property var windows: selectedWorkspace.clients
    readonly property var selectedWindow: windows[Math.min(windowIndex, windows.length - 1)] || null
    readonly property var shownWorkspaces: data.workspaces.filter(w => !monitorFilter || w.monitor === monitorFilter)
    readonly property var destinations: allWorkspaces.filter(w => w.id > 0 && w.connected)
    property bool pendingAction: false
    readonly property bool busy: action.running || pendingAction || opening
    readonly property bool restoring: busy && action.command.length > 1 && action.command[1].startsWith('restore')
    readonly property string executable: Quickshell.shellDir + '/../bin-omaspace'

    function acceptState(result, initial) {
        const changed = data.profile && result.profile && data.profile.id !== result.profile.id
        data = result
        if (changed) {
            quickSource = 0; dialog = ''; undoAction = []; monitorFilter = ''
            status = 'Detected ' + profileName + (result.savedAt ? ' · Saved profile available.' : ' · Save this setup to remember it.')
        }
        const monitor = result.monitors.find(m => m.focused) || result.monitors[0]
        if (initial || !allWorkspaces.some(w => w.id === selectedId)) {
            const focused = monitor ? monitor.activeWorkspace.id : 0
            selectedId = allWorkspaces.some(w => w.id === focused) ? focused : (result.workspaces[0] ? result.workspaces[0].id : 0)
            windowIndex = 0
        }
        if (monitorFilter && !result.monitors.some(m => m.name === monitorFilter)) monitorFilter = ''
        if (monitor && (initial || changed)) displayScreen = Quickshell.screens.find(s => s.name === monitor.name) || displayScreen
        if (!destinations.some(w => w.id === destination)) destination = destinations.length ? destinations[0].id : 0
    }

    function refresh() {
        SystemStyle.refresh()
        if (fetch.running) { refreshPending = true; return }
        refreshPending = false
        fetch.revision = openRevision
        fetch.running = true
    }
    function open() {
        SystemStyle.refresh()
        displayScreen = Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0]
        // Quickshell's focusedWorkspace ID can remain stale after change_id.
        // The opening query is authoritative; keep actions disabled until it arrives.
        openRevision++; opening = true; queuedKeys = []; statusError = false
        screenMode = 'switcher'; quickSource = 0
        monitorFilter = ''; view = 'workspaces'; dialog = ''; windowIndex = 0
        opened = true
        loadOpeningState()
        Qt.callLater(() => keyboard.forceActiveFocus())
    }
    function close() { opened = false; opening = false; queuedKeys = []; dialog = ''; quickSource = 0 }
    function loadOpeningState() {
        if (initialFetch.running) return
        initialFetch.revision = openRevision
        initialFetch.running = true
    }
    function showManager() { screenMode = 'manager'; quickSource = 0; dialog = ''; view = 'workspaces' }
    function pickWorkspace() {
        if (selectedId > 0 && !busy) quickSource = selectedId
    }
    function quickActivate() {
        if (busy) return
        if (quickSource) {
            if (quickSource === selectedId || selectedId <= 0) return
            execute(['move-workspace', String(quickSource), String(selectedId)])
            quickSource = 0
        } else { execute(['focus-workspace', selectedWorkspace.selector]); close() }
    }
    function quickKey(event) {
        if (event.key === Qt.Key_Escape) { if (quickSource) quickSource = 0; else close() }
        else if ((event.modifiers & Qt.MetaModifier) && event.key === Qt.Key_Up) close()
        else if (event.key === Qt.Key_Comma) showManager()
        else if (event.key === Qt.Key_Z && (event.modifiers & Qt.ControlModifier)) { if (undoAction.length) { execute(undoAction); undoAction = [] } }
        else if (event.key === Qt.Key_M || event.key === Qt.Key_W || event.key === Qt.Key_Space) pickWorkspace()
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) quickActivate()
        else if (event.key >= Qt.Key_0 && event.key <= Qt.Key_9) selectWorkspace(event.key === Qt.Key_0 ? 10 : event.key - Qt.Key_0)
        else {
            const list = allWorkspaces.filter(w => !quickSource || (w.id > 0 && w.connected))
            let step = 0
            if ([Qt.Key_Left, Qt.Key_H, Qt.Key_Backtab].includes(event.key)) step = -1
            else if ([Qt.Key_Right, Qt.Key_L, Qt.Key_Tab].includes(event.key)) step = 1
            else if ([Qt.Key_Up, Qt.Key_K].includes(event.key)) step = -5
            else if ([Qt.Key_Down, Qt.Key_J].includes(event.key)) step = 5
            if (step && list.length) selectWorkspace(list[Math.max(0, Math.min(list.length - 1, list.findIndex(w => w.id === selectedId) + step))].id)
        }
        event.accepted = true
    }
    function execute(args) {
        if (busy) return
        if (['save', 'restore', 'restore-pinned'].includes(args[0]) && data.profile) args = args.concat([data.profile.id])
        // A snapshot started before a move must not repaint the old layout.
        openRevision++
        action.command = [executable].concat(args)
        pendingAction = true
        actionDelay.restart()
        status = args[0].startsWith('restore') ? 'Reopening your apps and rebuilding the layout…' : 'Applying…'
        statusError = false
    }
    function revealSelection() {
        const entries = view === 'workspaces' ? shownWorkspaces : windows
        const index = view === 'workspaces' ? entries.findIndex(w => w.id === selectedId) : windowIndex
        const scroll = view === 'workspaces' ? workspaceScroll : windowScroll
        const height = view === 'workspaces' ? 196 : 242
        const columns = view === 'workspaces' ? 5 : 3
        const y = Math.floor(Math.max(0, index) / columns) * height
        if (scroll.contentItem && y < scroll.contentItem.contentY) scroll.contentItem.contentY = y
        else if (scroll.contentItem && y + height > scroll.contentItem.contentY + scroll.availableHeight)
            scroll.contentItem.contentY = Math.max(0, y + height - scroll.availableHeight)
    }
    onSelectedIdChanged: Qt.callLater(revealSelection)
    onWindowIndexChanged: Qt.callLater(revealSelection)
    function selectWorkspace(id) {
        if (!allWorkspaces.some(w => w.id === id)) return
        if (monitorFilter && !shownWorkspaces.some(w => w.id === id)) monitorFilter = ''
        selectedId = id; windowIndex = 0
    }
    function activate() {
        if (view === 'windows' && selectedWindow) execute(['focus-window', selectedWindow.address])
        else execute(['focus-workspace', selectedWorkspace.selector])
        close()
    }
    function beginMove(kind) {
        if (busy) return
        if (kind === 'window' && !selectedWindow) { status = 'Select a window first. Tab opens the window view.'; return }
        if (kind === 'workspace' && selectedId <= 0) { status = 'Scratchpads can move individual windows; whole moves use numbered workspaces.'; return }
        actionSource = selectedWindow ? selectedWindow.address : ''
        workspaceSource = selectedId
        const next = destinations.find(w => w.id !== selectedId)
        destination = next ? next.id : selectedId
        dialog = kind
    }
    function beginSwap() {
        if (!selectedWindow || windows.length < 2) { status = 'Open a workspace with at least two tiled windows to swap positions.'; return }
        actionSource = selectedWindow.address
        swapTarget = windowIndex === 0 ? 1 : 0
        dialog = 'swap'
    }
    function acceptDialog() {
        const current = dialog
        if ((current === 'window' || current === 'workspace') && !destinations.some(w => w.id === destination)) return
        if (current === 'window') execute(['move-window', actionSource, String(destination)])
        else if (current === 'workspace') execute(['move-workspace', String(workspaceSource), String(destination)])
        else if (current === 'swap' && windows[swapTarget]) execute(['swap-windows', actionSource, windows[swapTarget].address])
        else if (current === 'restore') execute(['restore'])
        dialog = ''
    }
    function key(event) {
        if (opening) {
            if (event.key === Qt.Key_Escape || ((event.modifiers & Qt.MetaModifier) && event.key === Qt.Key_Up)) close()
            else queuedKeys = queuedKeys.concat([{key: event.key, modifiers: event.modifiers}])
            event.accepted = true
            return
        }
        if (screenMode === 'switcher') { quickKey(event); return }
        if (event.key === Qt.Key_Escape) {
            if (dialog) dialog = ''
            else if (view === 'windows') view = 'workspaces'
            else { screenMode = 'switcher'; view = 'workspaces'; monitorFilter = '' }
        } else if ((event.modifiers & Qt.MetaModifier) && event.key === Qt.Key_Up) close()
        else if (event.key === Qt.Key_Z && (event.modifiers & Qt.ControlModifier)) { if (undoAction.length) { execute(undoAction); undoAction = [] } }
        else if (dialog) {
            if (dialog === 'restore' && event.key === Qt.Key_P && data.pinnedAt) { execute(['restore-pinned']); dialog = '' }
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) acceptDialog()
            else if (dialog === 'window' || dialog === 'workspace') {
                if (event.key >= Qt.Key_0 && event.key <= Qt.Key_9) {
                    const number = event.key === Qt.Key_0 ? 10 : event.key - Qt.Key_0
                    if (destinations.some(w => w.id === number)) destination = number
                } else if (destinations.length && [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].includes(event.key)) {
                    let i = destinations.findIndex(w => w.id === destination)
                    let step = event.key === Qt.Key_Left ? -1 : event.key === Qt.Key_Right ? 1 : event.key === Qt.Key_Up ? -5 : 5
                    destination = destinations[Math.max(0, Math.min(destinations.length - 1, i + step))].id
                }
            } else if (dialog === 'swap') {
                if (event.key >= Qt.Key_1 && event.key <= Qt.Key_9) swapTarget = Math.min(windows.length - 1, event.key - Qt.Key_1)
                else if ([Qt.Key_Left, Qt.Key_Up].includes(event.key)) swapTarget = Math.max(0, swapTarget - 1)
                else if ([Qt.Key_Right, Qt.Key_Down].includes(event.key)) swapTarget = Math.min(windows.length - 1, swapTarget + 1)
            }
        } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) { view = view === 'workspaces' ? 'windows' : 'workspaces'; windowIndex = 0 }
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) activate()
        else if (event.key === Qt.Key_A) execute(['settings', 'autoRestore', data.autoRestore ? 'false' : 'true'])
        else if (event.key === Qt.Key_S) execute(['save'])
        else if (event.key === Qt.Key_R) dialog = 'restore'
        else if (event.key === Qt.Key_M) beginMove('window')
        else if (event.key === Qt.Key_W) beginMove('workspace')
        else if (event.key === Qt.Key_X) beginSwap()
        else if (event.key === Qt.Key_Space && view === 'workspaces') view = 'windows'
        else if (event.key >= Qt.Key_0 && event.key <= Qt.Key_9) {
            const number = event.key === Qt.Key_0 ? 10 : event.key - Qt.Key_0
            if (view === 'workspaces') selectWorkspace(number)
            else windowIndex = Math.min(windows.length - 1, number - 1)
        } else if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_H, Qt.Key_J, Qt.Key_K, Qt.Key_L].includes(event.key)) {
            let left = event.key === Qt.Key_Left || event.key === Qt.Key_H
            let right = event.key === Qt.Key_Right || event.key === Qt.Key_L
            let up = event.key === Qt.Key_Up || event.key === Qt.Key_K
            const step = left ? -1 : right ? 1 : up ? -(view === 'windows' ? 3 : 5) : (view === 'windows' ? 3 : 5)
            if (view === 'workspaces') {
                const i = shownWorkspaces.findIndex(w => w.id === selectedId)
                const target = shownWorkspaces[Math.max(0, Math.min(shownWorkspaces.length - 1, i + step))]
                if (target) selectWorkspace(target.id)
            } else windowIndex = Math.max(0, Math.min(windows.length - 1, windowIndex + step))
        }
        event.accepted = true
    }

    IpcHandler {
        target: 'omaspace'
        function toggle(): void { app.opened ? app.close() : app.open() }
        function open(): void { app.open() }
        function close(): void { app.close() }
        function style(): string { return JSON.stringify({border: SystemStyle.borderWidth, radius: SystemStyle.cornerRadius, font: SystemStyle.fontFamily, body: SystemStyle.font.body, heading: SystemStyle.font.heading, spacingScale: SystemStyle.spacing.scale}) }
        function inspect(): string { return JSON.stringify({opened: app.opened, selected: app.selectedId, screen: app.screenMode, carrying: app.quickSource, view: app.view, dialog: app.dialog, workspaces: app.data.workspaces.length, workspaceIds: app.data.workspaces.map(w => w.id), auxiliaryIds: (app.data.auxiliaryWorkspaces || []).map(w => w.id), profile: app.data.profile, destination: app.destination, windows: app.windows.length, busy: app.busy, opening: app.opening, panelVisible: switcher.visible || panel.visible, status: app.status}) }
    }
    Process {
        id: initialFetch
        property int revision: 0
        command: [app.executable, 'state']
        stdout: StdioCollector {
            onStreamFinished: {
                if (!app.opened || initialFetch.revision !== app.openRevision) return
                try {
                    const result = JSON.parse(text)
                    if (result.error) throw new Error(result.error)
                    const monitor = result.monitors.find(m => m.focused) || result.monitors[0]
                    if (!monitor) throw new Error('No active display')
                    app.acceptState(result, true)
                    app.opening = false
                    const queued = app.queuedKeys
                    app.queuedKeys = []
                    // Finish queued selection changes before the first frame is painted.
                    for (const event of queued) { if (app.opened) app.key(event) }
                    Qt.callLater(() => keyboard.forceActiveFocus())
                } catch (e) {
                    app.status = 'Could not read the current workspace: ' + e
                    app.statusError = true
                    app.queuedKeys = []
                }
            }
        }
        onExited: { if (app.opening && revision !== app.openRevision) app.loadOpeningState() }
    }
    Timer { interval: 2000; running: app.opened && app.opening && !initialFetch.running; repeat: true; onTriggered: app.loadOpeningState() }
    Process {
        id: fetch
        property int revision: 0
        command: [app.executable, 'state']
        stdout: StdioCollector {
            onStreamFinished: {
                if (!app.opened || app.opening || fetch.revision !== app.openRevision) return
                try {
                    const result = JSON.parse(text)
                    if (result.error) { app.status = result.error; app.statusError = true }
                    else if (JSON.stringify(app.data) !== JSON.stringify(result)) app.acceptState(result, false)
                } catch (e) { app.status = 'Could not read the desktop: ' + e; app.statusError = true }
            }
        }
        onExited: { if (app.refreshPending && app.opened && !app.opening) app.refresh() }
    }
    Timer { id: actionDelay; interval: 100; onTriggered: { action.running = true; app.pendingAction = false } }
    Process {
        id: action
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const result = JSON.parse(text)
                    app.statusError = !!result.error
                    app.status = result.error || result.message || 'Done.'
                    if (result.undo) app.undoAction = result.undo
                    if (!result.error && result.selectedWorkspace) app.selectWorkspace(result.selectedWorkspace)
                    if (result.failed && result.failed.length) app.status += ' Could not reopen: ' + result.failed.join(', ')
                    if (result.skipped && result.skipped.length) app.status += ' No launcher: ' + result.skipped.join(', ')
                    if (result.layoutWarnings && result.layoutWarnings.length) app.status += ' ' + result.layoutWarnings.join('; ')
                } catch (e) { app.status = 'The action did not return a valid result: ' + e; app.statusError = true }
                app.refresh()
            }
        }
    }
    Timer { interval: 2000; running: app.opened && !app.busy; repeat: true; onTriggered: app.refresh() }

    PanelWindow {
        id: overlay
        visible: app.opened
        screen: app.displayScreen
        anchors { top: true; bottom: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        color: 'transparent'
        WlrLayershell.namespace: 'omaspace'
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: app.opened && !app.restoring ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
        Rectangle { anchors.fill: parent; color: Qt.alpha(app.palette.background, .64); MouseArea { anchors.fill: parent; onClicked: app.close() } }
        FocusScope {
            id: keyboard
            anchors.fill: parent; focus: true
            Keys.onPressed: event => app.key(event)
            // Keep keyboard capture during the short query, but never paint the old selection.
            QuickSwitcher { id: switcher; controller: app; anchors.centerIn: parent; visible: app.panelReady && app.screenMode === 'switcher' }
            OLabel { palette: app.palette; anchors.centerIn: parent; width: Math.min(parent.width - SystemStyle.space(80), 700); wrapMode: Text.Wrap; text: app.status + '\nEsc to close'; visible: app.opened && app.opening && app.statusError }
            Rectangle {
                id: panel
                visible: app.panelReady && app.screenMode === 'manager'
                anchors.centerIn: parent
                width: Math.min(parent.width - SystemStyle.space(64), SystemStyle.space(1480))
                height: Math.min(parent.height - SystemStyle.space(84), SystemStyle.space(920))
                radius: SystemStyle.cornerRadius
                color: Qt.alpha(app.palette.background, .94)
                border.color: Qt.alpha(app.palette.foreground, .16)
                border.width: SystemStyle.borderWidth
                MouseArea { anchors.fill: parent; onClicked: keyboard.forceActiveFocus() }
                ColumnLayout {
                    anchors { fill: parent; margins: SystemStyle.space(28) }
                    spacing: SystemStyle.space(22)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: SystemStyle.space(15)
                        Rectangle {
                            width: SystemStyle.space(42); height: SystemStyle.space(42); radius: SystemStyle.cornerRadius; color: app.palette.accent
                            Grid { anchors.centerIn: parent; columns: 2; spacing: SystemStyle.space(3); Repeater { model: 4; Rectangle { width: SystemStyle.space(9); height: SystemStyle.space(9); radius: SystemStyle.cornerRadius; color: app.palette.background; opacity: index === 3 ? .4 : 1 } } }
                        }
                        ColumnLayout {
                            spacing: SystemStyle.space(3)
                            OLabel { palette: app.palette; text: 'OmaSpace'; font.pixelSize: SystemStyle.font.display }
                            OLabel { palette: app.palette; text: 'Display profile · ' + app.profileName; font.pixelSize: SystemStyle.font.bodySmall; opacity: .5 }
                        }
                        Item { Layout.fillWidth: true }
                        OLabel { palette: app.palette; text: app.data.clients.length + ' windows   /   ' + app.data.workspaces.length + ' workspaces'; font.pixelSize: SystemStyle.font.bodySmall; opacity: .5 }
                        OButton { palette: app.palette; text: 'Save profile  S'; enabled: !app.busy; onClicked: app.execute(['save']) }
                        OButton { palette: app.palette; text: 'Restore  R'; enabled: !app.busy; onClicked: app.dialog = 'restore' }
                        OButton { palette: app.palette; text: '← Switcher'; onClicked: { app.screenMode = 'switcher'; app.view = 'workspaces'; app.dialog = '' } }
                    }
                    Rectangle { Layout.fillWidth: true; height: SystemStyle.space(1); color: Qt.alpha(app.palette.foreground, .09) }
                    RowLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true; spacing: SystemStyle.space(25)
                        ColumnLayout {
                            Layout.preferredWidth: SystemStyle.space(192); Layout.maximumWidth: SystemStyle.space(192); Layout.minimumWidth: SystemStyle.space(192); Layout.fillHeight: true; spacing: SystemStyle.space(8)
                            OLabel { palette: app.palette; text: 'DISPLAYS'; font.pixelSize: SystemStyle.font.caption; opacity: .4; Layout.bottomMargin: SystemStyle.space(8) }
                            OButton { palette: app.palette; text: 'All displays'; checked: app.monitorFilter === ''; Layout.fillWidth: true; onClicked: { app.monitorFilter = ''; app.view = 'workspaces' } }
                            Repeater {
                                model: app.data.monitors
                                OButton {
                                    required property var modelData
                                    palette: app.palette
                                    text: modelData.name.startsWith('eDP') ? 'Laptop · ' + modelData.name : modelData.name.startsWith('DP') ? 'ThinkVision · ' + modelData.name : modelData.name
                                    checked: app.monitorFilter === modelData.name
                                    Layout.fillWidth: true
                                    onClicked: { app.monitorFilter = modelData.name; app.view = 'workspaces'; const ws = app.shownWorkspaces[0]; if (ws) app.selectWorkspace(ws.id) }
                                }
                            }
                            OLabel { palette: app.palette; text: 'OTHER OPEN'; visible: (app.data.auxiliaryWorkspaces || []).length > 0; font.pixelSize: SystemStyle.font.caption; opacity: .5 }
                            Repeater {
                                model: app.data.auxiliaryWorkspaces || []
                                OButton {
                                    required property var modelData
                                    palette: app.palette; text: modelData.label + (modelData.id > 0 ? ' · ' + modelData.clients.length + (modelData.clients.length === 1 ? ' window' : ' windows') : '')
                                    checked: app.selectedId === modelData.id; Layout.fillWidth: true
                                    onClicked: { app.selectWorkspace(modelData.id); app.view = 'windows' }
                                }
                            }
                            Item { Layout.preferredHeight: SystemStyle.space(20) }
                            OLabel { palette: app.palette; text: 'SELECTED WORKSPACE'; font.pixelSize: SystemStyle.font.caption; opacity: .4 }
                            OLabel { palette: app.palette; text: app.selectedWorkspace.id > 0 ? 'Workspace ' + app.selectedWorkspace.label : app.selectedWorkspace.label; font.pixelSize: SystemStyle.font.heading; color: app.palette.accent; Layout.fillWidth: true }
                            OLabel { palette: app.palette; text: app.selectedWorkspace.monitor + ' · ' + app.windows.length + ' windows'; font.pixelSize: SystemStyle.font.caption; opacity: .5 }
                            OButton { palette: app.palette; text: 'Open workspace  ↵'; Layout.fillWidth: true; onClicked: { app.execute(['focus-workspace', app.selectedWorkspace.selector]); app.close() } }
                            OButton { palette: app.palette; text: 'Move workspace  W'; enabled: !app.busy && app.selectedId > 0; Layout.fillWidth: true; onClicked: app.beginMove('workspace') }
                            Item { Layout.fillHeight: true }
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: profileColumn.implicitHeight + SystemStyle.space(28); radius: SystemStyle.cornerRadius; color: Qt.alpha(app.palette.foreground, .035)
                                ColumnLayout {
                                    id: profileColumn
                                    anchors { fill: parent; margins: SystemStyle.space(14) } spacing: SystemStyle.space(8)
                                    OLabel { palette: app.palette; text: 'DISPLAY PROFILE'; font.pixelSize: SystemStyle.font.caption; opacity: .5 }
                                    OLabel { palette: app.palette; text: app.profileName; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    OLabel { palette: app.palette; text: app.data.savedAt ? app.data.savedCount + ' windows saved' : 'Not saved yet'; font.pixelSize: SystemStyle.font.body }
                                    OLabel { palette: app.palette; text: app.data.savePaused ? 'Autosave paused · retry restore or save' : (app.data.savedAt ? 'Saved ' + new Date(app.data.savedAt * 1000).toLocaleTimeString(Qt.locale(), 'h:mm:ss AP') : 'Save S · Restore R'); wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: SystemStyle.font.caption; opacity: .5 }
                                    OButton { palette: app.palette; text: 'Login [A]: ' + (app.data.autoRestore ? 'on' : 'off'); Layout.fillWidth: true; implicitHeight: SystemStyle.space(29); onClicked: app.execute(['settings', 'autoRestore', app.data.autoRestore ? 'false' : 'true']) }
                                    OButton { palette: app.palette; text: 'Auto-switch: ' + (app.data.autoProfileRestore ? 'on' : 'off'); Layout.fillWidth: true; implicitHeight: SystemStyle.space(29); onClicked: app.execute(['settings', 'autoProfileRestore', app.data.autoProfileRestore ? 'false' : 'true']) }
                                    OLabel { palette: app.palette; text: 'Saved setups: ' + (app.data.profiles || []).map(p => p.name).join(' · '); visible: (app.data.profiles || []).length > 0; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: SystemStyle.font.caption; opacity: .55 }

                                }
                            }
                        }
                        Rectangle { Layout.fillHeight: true; width: SystemStyle.space(1); color: Qt.alpha(app.palette.foreground, .08) }
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true; spacing: SystemStyle.space(16)
                            RowLayout {
                                Layout.fillWidth: true
                                OButton { palette: app.palette; text: 'Workspaces'; checked: app.view === 'workspaces'; onClicked: app.view = 'workspaces' }
                                OButton { palette: app.palette; text: 'Windows'; checked: app.view === 'windows'; onClicked: app.view = 'windows' }
                                OLabel { palette: app.palette; text: 'Tab to switch'; font.pixelSize: SystemStyle.font.caption; opacity: .35; Layout.leftMargin: SystemStyle.space(8) }
                                Item { Layout.fillWidth: true }
                                OLabel { palette: app.palette; text: app.view === 'workspaces' ? 'Select a card · Space to inspect' : 'Workspace ' + app.selectedWorkspace.label; font.pixelSize: SystemStyle.font.caption; opacity: .5 }
                            }
                            Item {
                                Layout.fillWidth: true; Layout.fillHeight: true
                                ScrollView {
                                    id: workspaceScroll
                                    anchors.fill: parent; visible: app.view === 'workspaces'; clip: true
                                    contentWidth: availableWidth
                                    GridLayout {
                                        width: parent.width; columns: 5; columnSpacing: 12; rowSpacing: 12
                                        Repeater {
                                            model: app.shownWorkspaces
                                            WorkspaceCard {
                                                required property var modelData
                                                Layout.fillWidth: true; Layout.preferredWidth: SystemStyle.space(160); Layout.preferredHeight: SystemStyle.space(184)
                                                workspace: modelData; palette: app.palette; selected: modelData.id === app.selectedId; capturing: app.opened && app.screenMode === 'manager' && !app.dialog && app.view === 'workspaces'
                                                onClicked: app.selectWorkspace(modelData.id)
                                                onActivated: { app.selectWorkspace(modelData.id); app.view = 'windows' }
                                            }
                                        }
                                    }
                                }
                                ScrollView {
                                    id: windowScroll
                                    anchors.fill: parent; visible: app.view === 'windows'; clip: true
                                    contentWidth: availableWidth
                                    GridLayout {
                                        width: parent.width; columns: 3; columnSpacing: 14; rowSpacing: 14
                                        Repeater {
                                            model: app.windows
                                            WindowPreview {
                                                required property var modelData
                                                required property int index
                                                Layout.fillWidth: true; Layout.preferredWidth: SystemStyle.space(230); Layout.preferredHeight: SystemStyle.space(228)
                                                client: modelData; palette: app.palette; selected: index === app.windowIndex; number: index + 1; capturing: app.opened && app.screenMode === 'manager' && !app.dialog && app.view === 'windows'
                                                onClicked: app.windowIndex = index
                                                onActivated: { app.windowIndex = index; app.activate() }
                                            }
                                        }
                                    }
                                }
                                ColumnLayout {
                                    anchors.centerIn: parent; visible: app.view === 'windows' && !app.windows.length; spacing: SystemStyle.space(14)
                                    OLabel { palette: app.palette; text: 'Room for something new.'; font.pixelSize: SystemStyle.font.display; opacity: .8 }
                                    OLabel { palette: app.palette; text: 'Move a window here from another workspace.'; font.pixelSize: SystemStyle.font.body; opacity: .4 }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                OLabel { palette: app.palette; text: app.view === 'windows' && app.selectedWindow ? app.selectedWindow.title : app.profileName + ' · Workspaces ' + app.data.workspaces.map(w => w.label).join(', '); font.pixelSize: SystemStyle.font.bodySmall; opacity: .6; Layout.fillWidth: true }
                                OButton { palette: app.palette; text: 'Swap position  X'; visible: app.view === 'windows'; enabled: !!app.selectedWindow && !app.busy; onClicked: app.beginSwap() }
                                OButton { palette: app.palette; text: 'Move window  M'; visible: app.view === 'windows'; enabled: !!app.selectedWindow && !app.busy; primary: true; onClicked: app.beginMove('window') }
                            }
                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: SystemStyle.space(1); color: Qt.alpha(app.palette.foreground, .09) }
                    RowLayout {
                        Layout.fillWidth: true
                        Rectangle { width: SystemStyle.space(6); height: SystemStyle.space(6); radius: width / 2; color: app.palette.accent; opacity: app.busy ? .4 : 1 }
                        OLabel { palette: app.palette; text: app.status; font.pixelSize: SystemStyle.font.bodySmall; Layout.fillWidth: true; maximumLineCount: 3; wrapMode: Text.Wrap; color: app.statusError ? app.palette.foreground : Qt.alpha(app.palette.foreground, .65) }
                        OButton { palette: app.palette; text: 'Undo  Ctrl Z'; visible: app.undoAction.length > 0; enabled: !app.busy; onClicked: { app.execute(app.undoAction); app.undoAction = [] } }
                        OLabel { palette: app.palette; text: '↑↓←→ navigate   ↵ focus   Esc back'; font.pixelSize: SystemStyle.font.caption; opacity: .4 }
                    }
                }
                Rectangle {
                    anchors.fill: parent; radius: parent.radius; visible: app.dialog !== ''; color: Qt.alpha(app.palette.background, .92)
                    MouseArea { anchors.fill: parent; onClicked: keyboard.forceActiveFocus() }
                    ColumnLayout {
                        anchors.centerIn: parent; width: Math.min(790, parent.width - SystemStyle.space(80)); spacing: SystemStyle.space(20)
                        OLabel { palette: app.palette; text: app.dialog === 'window' ? 'Move window to…' : app.dialog === 'workspace' ? 'Move workspace ' + app.workspaceSource + ' to…' : app.dialog === 'swap' ? 'Swap window positions' : 'Restore ' + app.profileName; font.pixelSize: SystemStyle.font.displayLarge; Layout.fillWidth: true }
                        OLabel { palette: app.palette; text: app.dialog === 'workspace' ? 'An occupied destination swaps places. Both layouts stay together.' : app.dialog === 'restore' ? 'Restore the saved layout for ' + app.profileName + '.\nExisting windows are reused; extra tiled windows move to an unused workspace.' : app.dialog === 'swap' ? 'Choose the window whose position you want.' : 'Choose a workspace. Your window moves without switching your view.'; font.pixelSize: SystemStyle.font.body; opacity: .6; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        GridLayout {
                            visible: app.dialog === 'window' || app.dialog === 'workspace'; columns: 5; columnSpacing: 10; rowSpacing: 10; Layout.fillWidth: true
                            Repeater {
                                model: app.destinations
                                Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true; Layout.preferredWidth: SystemStyle.space(140); height: SystemStyle.space(76); radius: SystemStyle.cornerRadius
                                    color: Qt.alpha(app.palette.foreground, app.destination === modelData.id ? .12 : .04)
                                    border.width: SystemStyle.borderWidth
                                    border.color: app.destination === modelData.id ? app.palette.accent : Qt.alpha(app.palette.foreground, .1)
                                    OLabel { palette: app.palette; x: SystemStyle.space(12); y: SystemStyle.space(12); text: modelData.label; font.pixelSize: SystemStyle.font.heading; color: app.destination === modelData.id ? app.palette.accent : app.palette.foreground }
                                    OLabel { palette: app.palette; x: SystemStyle.space(12); y: SystemStyle.space(46); font.pixelSize: SystemStyle.font.caption; text: modelData.monitor + ' · ' + modelData.clients.length; opacity: .5 }
                                    MouseArea { anchors.fill: parent; onClicked: app.destination = modelData.id; onDoubleClicked: { app.destination = modelData.id; app.acceptDialog() } }
                                }
                            }
                        }
                        ColumnLayout {
                            visible: app.dialog === 'swap'; Layout.fillWidth: true; spacing: SystemStyle.space(8)
                            Repeater {
                                model: app.windows
                                OButton {
                                    required property var modelData
                                    required property int index
                                    palette: app.palette; text: (index + 1) + '  ' + modelData.class; checked: app.swapTarget === index; Layout.fillWidth: true
                                    onClicked: app.swapTarget = index
                                }
                            }
                        }
                        ColumnLayout {
                            visible: app.dialog === 'restore'; Layout.fillWidth: true; spacing: SystemStyle.space(12)
                            OLabel { palette: app.palette; text: 'Latest layout · ' + app.data.savedCount + ' windows · ' + (app.data.savedAt ? new Date(app.data.savedAt * 1000).toLocaleString() : 'Save a session first'); font.pixelSize: SystemStyle.font.title; color: app.palette.accent }
                            OLabel { palette: app.palette; text: 'Window sizes save automatically after resizing settles. S saves immediately.\nThe manual checkpoint keeps the layout from the last time you pressed S.\nApps restore their own tabs and documents; terminals reopen as fresh shells.'; font.pixelSize: SystemStyle.font.bodySmall; opacity: .55; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            OButton { palette: app.palette; text: 'Manual checkpoint  P · ' + (app.data.pinnedAt ? new Date(app.data.pinnedAt * 1000).toLocaleString() : 'Not saved'); enabled: !app.busy && !!app.data.pinnedAt; onClicked: { app.dialog = ''; app.execute(['restore-pinned']) } }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            OLabel { palette: app.palette; text: app.dialog === 'restore' ? 'Placement changes apply immediately.' : 'Number keys or arrows to select'; font.pixelSize: SystemStyle.font.bodySmall; opacity: .45; Layout.fillWidth: true }
                            OButton { palette: app.palette; text: 'Cancel  Esc'; onClicked: app.dialog = '' }
                            OButton { palette: app.palette; text: app.dialog === 'restore' ? 'Restore latest  ↵' : app.dialog === 'swap' ? 'Swap positions  ↵' : 'Move / swap  ↵'; primary: true; enabled: !app.busy && (app.dialog !== 'restore' || !!app.data.savedAt); onClicked: app.acceptDialog() }
                        }
                    }
                }
            }
        }
    }
}
