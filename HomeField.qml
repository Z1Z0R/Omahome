import QtQuick
import QtQuick.Controls
import qs.Commons as Commons

TextField {
    id: root
    property string iconName: ""
    implicitHeight: 42
    leftPadding: iconName ? 39 : 13
    rightPadding: 13
    topPadding: 10; bottomPadding: 10
    color: Commons.Color.foreground
    placeholderTextColor: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.43)
    selectionColor: Commons.Color.accent
    selectedTextColor: Commons.Color.background
    font.family: Commons.Style.font.family
    font.pixelSize: 12
    selectByMouse: true
    background: Rectangle {
        color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.035)
        radius: 12
        border.width: 1
        border.color: root.activeFocus ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, root.hovered ? 0.17 : 0.09)
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
    HomeIcon { visible: root.iconName !== ""; name: root.iconName; opacity: 0.5; width: 17; height: 17; x: 13; anchors.verticalCenter: parent.verticalCenter }
}
