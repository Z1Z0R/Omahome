import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons

ColumnLayout {
    id: root
    property string label: ""
    property string iconName: ""
    property real value: 0
    property real from: 0
    property real to: 100
    property real step: 1
    property string unit: "%"
    property color accent: Commons.Color.accent
    property bool temperature: false
    property int decimals: step < 1 ? Math.min(3, (String(step).split(".")[1] || "0").length) : 0
    property bool dirty: false
    property real pendingValue: value
    signal committed(real value)
    signal interaction(bool active)
    spacing: 2
    Layout.fillWidth: true
    opacity: enabled ? 1 : 0.4
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        HomeIcon { visible: root.iconName !== ""; name: root.iconName; tint: root.accent; Layout.preferredWidth: 14; Layout.preferredHeight: 14; opacity: 0.8 }
        Label { textFormat: Text.PlainText; text: root.label; color: Commons.Color.foreground; opacity: 0.75; font.pixelSize: 12; Layout.fillWidth: true }
        Rectangle {
            implicitWidth: number.implicitWidth + 14; implicitHeight: 24; radius: 8
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.09)
            Text { id: number; anchors.centerIn: parent; text: Number(slider.value).toFixed(root.decimals) + root.unit; color: root.accent; font.pixelSize: 11; font.weight: Font.DemiBold }
        }
    }
    Slider {
        id: slider
        Layout.fillWidth: true
        implicitHeight: 30
        leftPadding: 10; rightPadding: 10
        from: root.from; to: root.to; stepSize: root.step
        value: root.value
        hoverEnabled: true
        background: Rectangle {
            x: slider.leftPadding; y: (slider.height - height) / 2
            width: slider.availableWidth; height: 7; radius: 3.5
            color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.10)
            Rectangle {
                visible: root.temperature
                anchors.fill: parent; radius: parent.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#e6b673" }
                    GradientStop { position: 0.5; color: "#e9e3d6" }
                    GradientStop { position: 1; color: "#99c4eb" }
                }
            }
            Rectangle { visible: !root.temperature; width: slider.position * parent.width; height: parent.height; radius: parent.radius; color: root.accent }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: (slider.height - height) / 2
            implicitWidth: 19; implicitHeight: 19; radius: 9.5
            color: Commons.Color.foreground
            border.width: slider.pressed || slider.activeFocus ? 3 : 2
            border.color: root.accent
            scale: slider.pressed ? 1.14 : 1
            Behavior on scale { NumberAnimation { duration: 100 } }
        }
        onMoved: {
            root.pendingValue = value
            root.dirty = true
            if (!pressed) keyboardCommit.restart()
        }
        onPressedChanged: {
            // Commit before releasing the guard: release may synchronously
            // apply a deferred server snapshot and change the live value binding.
            if (!pressed && root.dirty) {
                const chosen = value
                root.dirty = false
                root.committed(chosen)
            }
            root.interaction(pressed)
        }
        Accessible.name: root.label
    }
    Timer {
        id: keyboardCommit
        interval: 250
        onTriggered: if (root.dirty && !slider.pressed) {
            root.dirty = false
            root.committed(root.pendingValue)
        }
    }
}
