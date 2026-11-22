import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons

ColumnLayout {
    id: root
    required property var device
    signal control(string action, var value)
    signal interaction(bool active)
    readonly property var caps: device.caps
    readonly property bool hasRange: device.target_low !== null && device.target_low !== undefined && device.target_high !== null && device.target_high !== undefined
    Layout.fillWidth: true
    spacing: 10
    enabled: device.available
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Repeater {
            model: [{value: root.device.current_temperature, unit: root.device.temperature_unit || "", label: "Room temperature", icon: "temperature"}, {value: root.device.current_humidity, unit: "%", label: "Room humidity", icon: "humidity"}]
            delegate: Rectangle {
                id: measurement
                required property var modelData
                visible: modelData.value !== null && modelData.value !== undefined
                Layout.fillWidth: true
                implicitHeight: 64
                radius: 12
                color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.035)
                ColumnLayout {
                    anchors { fill: parent; margins: 10 }
                    spacing: 3
                    RowLayout {
                        HomeIcon { name: measurement.modelData.icon; tint: Commons.Color.accent; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
                        Label { text: measurement.modelData.label; textFormat: Text.PlainText; color: Commons.Color.foreground; opacity: 0.5; font.pixelSize: 10 }
                    }
                    Label { text: measurement.modelData.value + " " + measurement.modelData.unit; textFormat: Text.PlainText; color: Commons.Color.foreground; font.pixelSize: 18; font.weight: Font.DemiBold }
                }
            }
        }
    }
    Label { visible: !!root.device.hvac_action; text: root.device.hvac_action || ""; textFormat: Text.PlainText; color: Commons.Color.accent; font.pixelSize: 11 }
    ColumnLayout {
        visible: !!root.caps.hvac_mode
        Layout.fillWidth: true
        spacing: 5
        Label { text: "Heating / cooling mode"; color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11 }
        HomeSelect {
            Layout.fillWidth: true
            model: root.device.hvac_modes || []
            currentIndex: (root.device.hvac_modes || []).indexOf(root.device.state)
            displayText: currentIndex < 0 ? "Choose mode" : currentText.replace(/_/g, " ")
            Accessible.name: "Heating or cooling mode"
            onActivated: root.control("hvac_mode", currentText)
        }
    }
    ValueSlider {
        visible: !!root.caps.target_temperature
        label: "Target temperature"; iconName: "temperature"
        unit: " " + (root.device.temperature_unit || "")
        from: root.device.min_target_temperature === undefined ? 7 : root.device.min_target_temperature
        to: root.device.max_target_temperature === undefined ? 35 : root.device.max_target_temperature
        step: root.device.temperature_step || 0.5
        value: root.device.target_temperature === null || root.device.target_temperature === undefined ? from : root.device.target_temperature
        enabled: root.device.target_temperature !== null && root.device.target_temperature !== undefined
        onCommitted: value => root.control("target_temperature", value)
        onInteraction: active => root.interaction(active)
    }
    ColumnLayout {
        visible: !!root.caps.target_range
        Layout.fillWidth: true
        spacing: 5
        Label { visible: !root.hasRange; text: "Waiting for the device's target range…"; color: Commons.Color.foreground; opacity: 0.6; font.pixelSize: 11 }
        ValueSlider {
            enabled: root.hasRange
            label: "Lower target"; iconName: "temperature"; unit: " " + (root.device.temperature_unit || "")
            from: root.device.min_target_temperature || 0
            to: root.hasRange ? root.device.target_high : root.device.max_target_temperature || 35
            step: root.device.temperature_step || 0.5
            value: root.hasRange ? root.device.target_low : from
            onCommitted: value => root.control("target_low", value)
            onInteraction: active => root.interaction(active)
        }
        ValueSlider {
            enabled: root.hasRange
            label: "Upper target"; iconName: "temperature"; unit: " " + (root.device.temperature_unit || "")
            from: root.hasRange ? root.device.target_low : root.device.min_target_temperature || 0
            to: root.device.max_target_temperature || 35
            step: root.device.temperature_step || 0.5
            value: root.hasRange ? root.device.target_high : to
            onCommitted: value => root.control("target_high", value)
            onInteraction: active => root.interaction(active)
        }
    }
    ValueSlider {
        visible: !!root.caps.target_humidity
        label: "Target humidity"; iconName: "humidity"
        from: root.device.min_humidity || 0
        to: root.device.max_humidity === undefined ? 100 : root.device.max_humidity
        step: root.device.humidity_step || 1
        value: root.device.target_humidity === null || root.device.target_humidity === undefined ? from : root.device.target_humidity
        enabled: root.device.target_humidity !== null && root.device.target_humidity !== undefined
        onCommitted: value => root.control("target_humidity", value)
        onInteraction: active => root.interaction(active)
    }
    Repeater {
        model: [{cap: "fan_mode", title: "Fan mode", list: "fan_modes"}, {cap: "preset_mode", title: "Preset", list: "preset_modes"}, {cap: "humidity_mode", title: "Operating mode", list: "humidity_modes"}]
        delegate: ColumnLayout {
            id: modeRow
            required property var modelData
            Layout.fillWidth: true
            visible: !!root.caps[modelData.cap]
            spacing: 5
            Label { text: modeRow.modelData.title; color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11 }
            HomeSelect {
                Layout.fillWidth: true
                model: root.device[modeRow.modelData.list] || []
                currentIndex: (root.device[modeRow.modelData.list] || []).indexOf(root.device[modeRow.modelData.cap])
                displayText: currentIndex < 0 ? "Choose mode" : currentText.replace(/_/g, " ")
                Accessible.name: modeRow.modelData.title
                onActivated: root.control(modeRow.modelData.cap, currentText)
            }
        }
    }
}
