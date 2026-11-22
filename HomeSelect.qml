import QtQuick
import QtQuick.Controls
import qs.Commons as Commons

ComboBox {
    id: root
    implicitHeight: 42
    leftPadding: 13; rightPadding: 37
    font.family: Commons.Style.font.family
    font.pixelSize: 12
    contentItem: Text { text: root.displayText; textFormat: Text.PlainText; color: Commons.Color.foreground; font: root.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
    indicator: HomeIcon { name: "chevron"; x: root.width - width - 12; y: (root.height - height) / 2; width: 16; height: 16; opacity: 0.6 }
    background: Rectangle {
        radius: 12
        color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.045)
        border.width: 1
        border.color: root.activeFocus ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.09)
    }
    delegate: ItemDelegate {
        id: option
        required property var modelData
        required property int index
        width: root.width - 10; height: 38
        highlighted: root.highlightedIndex === index
        contentItem: Text { text: option.modelData; textFormat: Text.PlainText; font: root.font; color: option.highlighted ? Commons.Color.accent : Commons.Color.foreground; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 9; color: option.highlighted ? Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.12) : "transparent" }
    }
    popup: Popup {
        y: root.height + 5
        width: root.width
        padding: 5
        implicitHeight: contentItem.implicitHeight + 10
        contentItem: ListView { clip: true; implicitHeight: contentHeight; model: root.popup.visible ? root.delegateModel : null; currentIndex: root.highlightedIndex }
        background: Rectangle { color: Commons.Color.background; radius: 13; border.color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.16) }
    }
}
