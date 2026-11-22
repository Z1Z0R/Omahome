import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons

Button {
    id: root
    property string iconName: ""
    property bool primary: false
    property bool selected: false
    property bool compact: false
    readonly property color ink: primary ? Commons.Color.background : (selected ? Commons.Color.accent : Commons.Color.foreground)
    implicitHeight: compact ? 32 : 38
    implicitWidth: contentItem.implicitWidth + leftPadding + rightPadding
    leftPadding: text ? 13 : 10; rightPadding: leftPadding
    topPadding: 7; bottomPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.38
    font.family: Commons.Style.font.family
    font.pixelSize: 12
    font.weight: Font.DemiBold
    background: Rectangle {
        radius: root.compact ? 10 : 12
        color: root.primary ? (root.down ? Qt.darker(Commons.Color.accent, 1.15) : Commons.Color.accent)
            : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, root.down ? 0.14 : root.hovered ? 0.10 : root.selected ? 0.08 : 0.045)
        border.width: 1
        border.color: root.activeFocus ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, root.hovered ? 0.18 : 0.07)
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    contentItem: RowLayout {
        spacing: 7
        HomeIcon { visible: root.iconName !== ""; name: root.iconName; tint: root.ink; Layout.preferredWidth: 16; Layout.preferredHeight: 16; Layout.alignment: Qt.AlignVCenter }
        Text {
            visible: root.text !== ""; text: root.text; textFormat: Text.PlainText
            color: root.ink; font: root.font; elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            Layout.fillWidth: true
        }
    }
}
