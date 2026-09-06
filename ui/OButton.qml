import QtQuick
Rectangle {
    id: button
    required property var palette
    property string text: ''
    property bool primary: false
    property bool checked: false
    signal clicked()
    implicitWidth: caption.implicitWidth + SystemStyle.spacing.controlPaddingX * 2
    implicitHeight: Math.max(SystemStyle.spacing.controlHeight, caption.implicitHeight + SystemStyle.spacing.controlPaddingY * 2)
    radius: SystemStyle.cornerRadius
    color: primary ? palette.accent : Qt.alpha(palette.foreground, mouse.containsMouse || checked ? .13 : .055)
    border.width: checked ? SystemStyle.borderWidth : 0
    border.color: Qt.alpha(palette.accent, .65)
    opacity: enabled ? 1 : .35
    OLabel {
        id: caption
        palette: button.palette
        anchors.centerIn: parent
        text: button.text
        color: button.primary ? button.palette.background : button.palette.foreground
        font.pixelSize: SystemStyle.font.body
        font.weight: Font.Normal
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: button.clicked() }
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: button.clicked()
}
