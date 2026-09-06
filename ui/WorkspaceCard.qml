import QtQuick
Rectangle {
    id: card
    required property var workspace
    required property var palette
    property bool selected: false
    property bool carried: false
    property bool capturing: true
    signal clicked()
    signal activated()
    radius: SystemStyle.cornerRadius
    color: selected ? Qt.alpha(palette.accent, .075) : Qt.alpha(palette.foreground, .035)
    border.width: SystemStyle.borderWidth
    border.color: selected || carried ? palette.accent : Qt.alpha(palette.foreground, .12)
    OLabel { palette: card.palette; x: SystemStyle.space(13); y: SystemStyle.space(12); text: card.workspace.id == 10 ? '0 / 10' : card.workspace.label; font.pixelSize: SystemStyle.font.title; color: card.selected ? card.palette.accent : card.palette.foreground }
    OLabel { palette: card.palette; anchors { right: parent.right; top: parent.top; margins: SystemStyle.space(14) } text: card.carried ? 'Moving…' : card.workspace.clients.length + (card.workspace.clients.length === 1 ? ' window' : ' windows'); font.pixelSize: SystemStyle.font.caption; opacity: .5 }
    Item {
        id: desktop
        x: SystemStyle.space(12); y: SystemStyle.space(43); width: parent.width - SystemStyle.space(24); height: parent.height - SystemStyle.space(77)
        Rectangle { anchors.fill: parent; radius: SystemStyle.cornerRadius; color: Qt.alpha(card.palette.background, .5) }
        OLabel { palette: card.palette; anchors.centerIn: parent; visible: card.workspace.clients.length === 0; text: '+  Empty workspace'; font.pixelSize: SystemStyle.font.caption; opacity: .32 }
        Repeater {
            model: card.workspace.clients
            WindowPreview {
                required property var modelData
                client: modelData; palette: card.palette; miniature: true; capturing: card.capturing
                x: Math.max(0, modelData.rect[0] * desktop.width)
                y: Math.max(0, modelData.rect[1] * desktop.height)
                width: Math.max(12, Math.min(desktop.width - x, modelData.rect[2] * desktop.width))
                height: Math.max(12, Math.min(desktop.height - y, modelData.rect[3] * desktop.height))
                onClicked: card.clicked()
                onActivated: card.activated()
            }
        }
    }
    OLabel { palette: card.palette; x: SystemStyle.space(13); anchors.bottom: parent.bottom; anchors.bottomMargin: SystemStyle.space(12); font.pixelSize: SystemStyle.font.caption; opacity: .5; text: (card.workspace.monitor || 'Unassigned') + (!card.workspace.connected ? ' · offline' : '') }
    Rectangle { visible: card.workspace.active; width: SystemStyle.space(5); height: SystemStyle.space(5); radius: width / 2; color: card.palette.accent; anchors { right: parent.right; bottom: parent.bottom; margins: SystemStyle.space(16) } }
    MouseArea { anchors.fill: parent; z: -1; onClicked: card.clicked(); onDoubleClicked: card.activated() }
    TapHandler { onTapped: card.clicked(); onDoubleTapped: card.activated() }
}
