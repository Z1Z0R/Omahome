import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons

ColumnLayout {
    id: root
    required property var device
    signal control(string action, var value)
    Layout.fillWidth: true
    spacing: 9
    enabled: device.available
    ColumnLayout {
        visible: !!root.device.caps.preset_mode
        Layout.fillWidth: true
        spacing: 5
        Label { text: root.device.kind === "air_purifier" ? "Purifier mode" : "Fan mode"; color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11 }
        HomeSelect {
            Layout.fillWidth: true
            model: root.device.preset_modes || []
            currentIndex: (root.device.preset_modes || []).indexOf(root.device.preset_mode)
            displayText: currentIndex < 0 ? (root.device.operating_mode || "Manual / speed control") : currentText.replace(/_/g, " ")
            Accessible.name: "Operating mode for " + root.device.name
            onActivated: root.control("preset_mode", currentText)
        }
    }
    RowLayout {
        visible: !!root.device.caps.oscillate
        Layout.fillWidth: true
        Label { text: "Oscillation"; color: Commons.Color.foreground; opacity: 0.7; font.pixelSize: 12; Layout.fillWidth: true }
        HomeToggle { checked: !!root.device.oscillating; Accessible.name: "Oscillation for " + root.device.name; onToggled: root.control("oscillate", checked) }
    }
    ColumnLayout {
        visible: !!root.device.caps.direction
        Layout.fillWidth: true
        spacing: 5
        Label { text: "Direction"; color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11 }
        HomeSelect {
            Layout.fillWidth: true
            model: ["forward", "reverse"]
            currentIndex: ["forward", "reverse"].indexOf(root.device.direction)
            displayText: currentIndex < 0 ? "Choose direction" : currentText
            Accessible.name: "Direction for " + root.device.name
            onActivated: root.control("direction", currentText)
        }
    }
}
