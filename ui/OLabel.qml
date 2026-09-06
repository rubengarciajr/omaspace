import QtQuick
Text {
    required property var palette
    color: palette.foreground
    font.family: SystemStyle.fontFamily
    font.pixelSize: SystemStyle.font.subtitle
    elide: Text.ElideRight
}
