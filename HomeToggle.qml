import QtQuick
import QtQuick.Controls
import qs.Commons as Commons

Switch {
    id: root
    implicitWidth: 40; implicitHeight: 30
    padding: 0
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    contentItem: Item { }
    indicator: Rectangle {
        implicitWidth: 40; implicitHeight: 24
        x: 0; y: (root.height - height) / 2
        radius: 12
        color: root.checked ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, root.hovered ? 0.20 : 0.12)
        border.width: 1
        border.color: root.activeFocus ? Commons.Color.accent : "transparent"
        Behavior on color { ColorAnimation { duration: 140 } }
        Rectangle {
            width: 18; height: 18; radius: 9
            x: root.checked ? 19 : 3; y: 3
            color: root.checked ? Commons.Color.background : Commons.Color.foreground
            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
    }
}
