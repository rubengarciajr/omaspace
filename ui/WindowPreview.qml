import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
Rectangle {
    id: preview
    required property var client
    required property var palette
    property bool selected: false
    property bool miniature: false
    property bool capturing: true
    property int number: 0
    signal clicked()
    signal activated()
    radius: SystemStyle.cornerRadius
    color: Qt.alpha(palette.foreground, .07)
    border.color: selected ? palette.accent : Qt.alpha(palette.foreground, .18)
    border.width: SystemStyle.borderWidth
    clip: true
    property var handle: {
        const entries = Hyprland.toplevels.values
        for (let i = 0; i < entries.length; i++) {
            if (('0x' + entries[i].address.replace(/^0x/, '')) === client.address) return entries[i].wayland
        }
        return null
    }
    Item {
        anchors { fill: parent; margins: SystemStyle.borderWidth; bottomMargin: preview.miniature ? SystemStyle.borderWidth : SystemStyle.space(47) }
        OLabel {
            palette: preview.palette; anchors.centerIn: parent
            text: (preview.client.launcher ? preview.client.launcher.label : preview.client.class).substring(0, preview.miniature ? 14 : 24)
            font.pixelSize: preview.miniature ? SystemStyle.font.caption : SystemStyle.font.heading
            opacity: .6
            visible: !capture.hasContent
        }
        ScreencopyView {
            id: capture
            anchors.centerIn: parent
            width: Math.min(parent.width, sourceSize.height > 0 ? parent.height * sourceSize.width / sourceSize.height : parent.width)
            height: Math.min(parent.height, sourceSize.width > 0 ? parent.width * sourceSize.height / sourceSize.width : parent.height)
            captureSource: preview.capturing ? preview.handle : null
            live: false
            paintCursor: false
        }
        Timer { interval: 1500; running: preview.capturing && !!preview.handle; repeat: true; onTriggered: capture.captureFrame() }
    }
    Rectangle {
        visible: !preview.miniature
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: SystemStyle.borderWidth }
        height: SystemStyle.space(43); radius: SystemStyle.cornerRadius; color: Qt.alpha(preview.palette.background, .93)
        OLabel { palette: preview.palette; x: SystemStyle.space(12); y: SystemStyle.space(5); width: parent.width - SystemStyle.space(24); font.pixelSize: SystemStyle.font.bodySmall; text: preview.client.title }
        OLabel { palette: preview.palette; x: SystemStyle.space(12); y: SystemStyle.space(23); width: parent.width - SystemStyle.space(24); font.pixelSize: SystemStyle.font.caption; opacity: .55; text: preview.client.class + (preview.client.floating ? ' · floating' : '') }
    }
    Rectangle {
        visible: !preview.miniature
        x: SystemStyle.space(10); y: SystemStyle.space(10); width: SystemStyle.space(25); height: SystemStyle.space(25); radius: SystemStyle.cornerRadius
        color: preview.selected ? preview.palette.accent : Qt.alpha(preview.palette.background, .9)
        OLabel { palette: preview.palette; anchors.centerIn: parent; text: preview.number; color: preview.selected ? preview.palette.background : preview.palette.foreground; font.pixelSize: SystemStyle.font.body }
    }
    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: preview.clicked(); onDoubleClicked: preview.activated() }
}
