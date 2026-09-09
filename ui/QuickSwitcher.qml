import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Rectangle {
    id: quick
    required property var controller
    readonly property var palette: controller.palette
    readonly property var primary: controller.data.workspaces.filter(w => w.id >= 1 && w.id <= 10)
    readonly property var extra: controller.data.workspaces.filter(w => w.id > 10).concat(controller.data.auxiliaryWorkspaces || [])
    readonly property var groups: {
        let names = []
        for (const w of primary) if (!names.includes(w.monitor)) names.push(w.monitor)
        return names.map(name => ({name: name, workspaces: primary.filter(w => w.monitor === name)}))
    }
    width: Math.min(parent.width - SystemStyle.space(64), SystemStyle.space(1120))
    height: Math.min(parent.height - SystemStyle.space(84), content.implicitHeight + SystemStyle.space(48))
    radius: SystemStyle.cornerRadius
    color: Qt.alpha(palette.background, .95)
    border.width: SystemStyle.borderWidth
    border.color: Qt.alpha(palette.foreground, .16)
    MouseArea { anchors.fill: parent }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: SystemStyle.space(24) }
        spacing: SystemStyle.space(18)
        RowLayout {
            Layout.fillWidth: true
            OLabel { palette: quick.palette; text: 'Workspaces'; font.pixelSize: SystemStyle.font.heading }
            OLabel { palette: quick.palette; text: controller.profileName; font.pixelSize: SystemStyle.font.bodySmall; opacity: .35; Layout.leftMargin: SystemStyle.space(7) }
            Item { Layout.fillWidth: true }
            OButton { palette: quick.palette; text: 'Settings  ,'; onClicked: controller.showManager() }
            OButton { palette: quick.palette; text: 'Esc'; onClicked: controller.close() }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: SystemStyle.space(16)
            Repeater {
                model: quick.groups
                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true; spacing: SystemStyle.space(9)
                    OLabel {
                        palette: quick.palette; font.pixelSize: SystemStyle.font.caption; opacity: .5
                        text: modelData.name.startsWith('eDP') ? 'LAPTOP' : modelData.name.startsWith('DP') ? 'THINKVISION' : (modelData.name || 'WORKSPACES').toUpperCase()
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: SystemStyle.space(11)
                        Repeater {
                            model: modelData.workspaces
                            WorkspaceCard {
                                required property var modelData
                                workspace: modelData; palette: quick.palette; enabled: !controller.opening
                                Layout.fillWidth: true; Layout.preferredWidth: SystemStyle.space(180); Layout.preferredHeight: SystemStyle.space(145)
                                selected: controller.selectedId === modelData.id
                                carried: controller.quickSource === modelData.id
                                capturing: controller.opened && controller.screenMode === 'switcher'
                                onClicked: controller.selectWorkspace(modelData.id)
                                onActivated: { controller.selectWorkspace(modelData.id); controller.quickActivate() }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            visible: quick.extra.length > 0; spacing: SystemStyle.space(8); Layout.fillWidth: true
            OLabel { palette: quick.palette; text: 'Also open'; font.pixelSize: SystemStyle.font.caption; opacity: .4; Layout.rightMargin: SystemStyle.space(5) }
            Repeater {
                model: quick.extra
                OButton {
                    required property var modelData
                    palette: quick.palette; text: modelData.label + (modelData.id > 0 ? ' · ' + modelData.monitor : '')
                    checked: controller.selectedId === modelData.id
                    enabled: !controller.opening && (!controller.quickSource || modelData.id > 0)
                    onClicked: controller.selectWorkspace(modelData.id)
                }
            }
            Item { Layout.fillWidth: true }
        }
        Rectangle { Layout.fillWidth: true; height: SystemStyle.space(1); color: Qt.alpha(quick.palette.foreground, .1) }
        RowLayout {
            Layout.fillWidth: true; spacing: SystemStyle.space(10)
            ColumnLayout {
                Layout.fillWidth: true; spacing: SystemStyle.space(5)
                OLabel {
                    palette: quick.palette; Layout.fillWidth: true; font.pixelSize: SystemStyle.font.body
                    text: controller.quickSource ? 'Move workspace ' + controller.quickSource + ' → ' + (controller.selectedId === 10 ? '0 / 10' : controller.selectedWorkspace.label) : (controller.selectedId > 0 ? 'Workspace ' : '') + controller.selectedWorkspace.label
                    color: controller.quickSource ? quick.palette.accent : quick.palette.foreground
                }
                OLabel {
                    palette: quick.palette; Layout.fillWidth: true; font.pixelSize: SystemStyle.font.caption; opacity: .5
                    text: controller.quickSource ? (controller.quickSource === controller.selectedId ? 'Choose a destination with arrows or number keys.' : controller.selectedWorkspace.clients.length ? 'Occupied destination: the two workspaces will swap.' : 'The entire layout moves together.') : 'Arrows / numbers select · Enter switches · M moves'
                }
            }
            OButton { palette: quick.palette; text: 'Undo  Ctrl Z'; visible: controller.undoAction.length > 0; enabled: !controller.busy; onClicked: { controller.execute(controller.undoAction); controller.undoAction = [] } }
            OButton { palette: quick.palette; text: controller.quickSource ? 'Cancel  Esc' : 'Move  M'; enabled: !controller.busy && controller.selectedId > 0; onClicked: controller.quickSource ? controller.quickSource = 0 : controller.pickWorkspace() }
            OButton {
                palette: quick.palette; primary: true
                text: controller.quickSource ? (controller.selectedWorkspace.clients.length ? 'Swap  ↵' : 'Move here  ↵') : 'Switch  ↵'
                enabled: !controller.busy && (!controller.quickSource || (controller.quickSource !== controller.selectedId && controller.selectedId > 0))
                onClicked: controller.quickActivate()
            }
        }
        OLabel {
            palette: quick.palette; Layout.fillWidth: true; visible: controller.status !== 'Your desktop, in order.'
            text: controller.status; font.pixelSize: SystemStyle.font.caption; opacity: .65; wrapMode: Text.Wrap; maximumLineCount: 2
        }
    }
}
