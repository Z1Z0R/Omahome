import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons as Commons

Rectangle {
    id: root
    required property var device
    property bool expanded: false
    // Only unsent custom edits override server state. Sending a color clears
    // the draft; the next refresh remains the authority for applied colors.
    property var rgbDraft: null
    readonly property var shownRgb: rgbDraft || device.rgb
    readonly property int red: shownRgb[0]
    readonly property int green: shownRgb[1]
    readonly property int blue: shownRgb[2]
    property bool customColorOpen: false
    readonly property var rgbPresets: [
        {name: "Red", rgb: [255, 0, 0]},
        {name: "Orange", rgb: [255, 128, 0]},
        {name: "Yellow", rgb: [255, 255, 0]},
        {name: "Green", rgb: [0, 255, 0]},
        {name: "Cyan", rgb: [0, 255, 255]},
        {name: "Blue", rgb: [0, 0, 255]},
        {name: "Purple", rgb: [128, 0, 255]},
        {name: "Pink", rgb: [255, 64, 160]},
        {name: "Warm white", rgb: [255, 197, 143]},
        {name: "White", rgb: [255, 255, 255]},
        {name: "Daylight", rgb: [255, 244, 229]},
        {name: "Cold white", rgb: [201, 226, 255]},
        {name: "Mint", rgb: [128, 255, 191]},
        {name: "Lavender", rgb: [192, 160, 255]},
        {name: "Peach", rgb: [255, 180, 128]}
    ]
    function setRgbChannel(channel, value) {
        const draft = shownRgb.slice()
        draft[channel] = value
        rgbDraft = draft
    }
    function applyRgb(rgb) {
        if (!device.available || !device.caps.rgb) return
        const chosen = rgb.slice()
        rgbDraft = null
        control("rgb", chosen)
    }
    function applyColorPreset(preset) { applyRgb(preset.rgb) }
    readonly property bool isAutomation: device.domain === "automation"
    readonly property string automationStatus: !device.available ? "Unavailable" : device.state === "on" ? "Enabled" : "Disabled"
    readonly property bool isChildLock: device.kind === "child_lock"
    readonly property string childLockStatus: !device.available ? "Unavailable" : device.state === "on" ? "Enabled" : "Disabled"
    readonly property bool isOn: device.available && ['off', 'closed', 'standby'].indexOf(device.state) === -1
    readonly property string iconName: {
        if (isChildLock) return device.state === "on" ? "lock" : "unlock"
        if (device.kind === "air_purifier") return "air_purifier"
        if (device.kind === "control") return "settings"
        const kind = device.sensor_kind || device.device_class || ""
        if (["aqi", "air_quality", "pm1", "pm25", "pm10", "carbon_dioxide", "volatile_organic_compounds", "volatile_organic_compounds_parts"].indexOf(kind) >= 0) return "air_purifier"
        if (kind === "filter_life") return "filter"
        if (kind === "temperature") return "temperature"
        if (kind === "humidity" || kind === "moisture") return "humidity"
        if (kind === "battery") return "battery"
        if (kind === "power" || kind === "energy" || kind === "voltage") return "power"
        if (device.domain === "humidifier") return device.device_class === "dehumidifier" ? "dehumidifier" : "humidifier"
        if (device.domain === "switch" && device.device_class === "outlet") return "outlet"
        return device.domain
    }
    signal control(string action, var value)
    signal interaction(bool active)
    implicitHeight: body.implicitHeight + 32
    color: Qt.tint(Commons.Color.background, Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.035))
    border.color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.075)
    radius: 17
    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                implicitWidth: 40; implicitHeight: 40; radius: 13
                color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, root.isOn ? 0.13 : 0.045)
                HomeIcon { anchors.centerIn: parent; width: 22; height: 22; name: root.iconName; tint: root.isOn ? Commons.Color.accent : Commons.Color.foreground; opacity: root.device.available ? 1 : 0.4 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Label { textFormat: Text.PlainText; text: root.device.name; color: Commons.Color.foreground; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                RowLayout {
                    spacing: 5
                    Rectangle { implicitWidth: 5; implicitHeight: 5; radius: 2.5; color: !root.device.available ? "#e99595" : root.isOn ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.3) }
                    Label { textFormat: Text.PlainText; text: root.isAutomation ? "Automation · " + root.automationStatus : root.isChildLock ? "Child lock · " + root.childLockStatus : root.device.domain === "sensor" ? (root.device.type_label || "Sensor") : root.device.state.replace(/_/g, " ") + " · " + (root.device.type_label || root.device.domain); color: root.isChildLock && root.isOn ? Commons.Color.accent : Commons.Color.foreground; opacity: root.isChildLock ? 1 : 0.55; font.weight: root.isChildLock ? Font.DemiBold : Font.Normal; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                }
            }
            HomeToggle {
                visible: root.device.caps.turn_on || root.device.caps.turn_off
                checked: root.device.state !== "off"
                enabled: root.device.available && (root.device.state === "off" ? root.device.caps.turn_on : root.device.caps.turn_off)
                Accessible.name: (root.isAutomation ? "Automation enabled for " : root.isChildLock ? "Child lock for " : "Power for ") + root.device.name
                ToolTip.visible: hovered
                ToolTip.text: root.isAutomation ? "Automation: " + root.automationStatus + ". Disabling stops future triggers; active runs continue." : root.isChildLock ? "Child lock: " + root.childLockStatus + ". Toggle to " + (checked ? "disable" : "enable") + " the child lock." : "Power"
                onToggled: root.control(checked ? "turn_on" : "turn_off", null)
            }
        }
        Label {
            visible: root.isChildLock
            text: "Child lock controls the device’s physical buttons."
            textFormat: Text.PlainText
            color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11
            wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        RowLayout {
            visible: root.device.domain === "sensor"
            spacing: 7
            Label { textFormat: Text.PlainText; text: root.device.available ? root.device.state : "—"; color: Commons.Color.foreground; font.pixelSize: 30; font.weight: Font.DemiBold }
            Label { textFormat: Text.PlainText; text: root.device.unit || ""; color: Commons.Color.foreground; opacity: 0.5; font.pixelSize: 16; Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 5 }
        }
        ClimateControls {
            visible: root.device.domain === "climate" || root.device.domain === "humidifier"
            device: root.device
            onControl: (action, value) => root.control(action, value)
            onInteraction: active => root.interaction(active)
        }
        Label { textFormat: Text.PlainText; visible: !!root.device.media; text: root.device.media; color: Commons.Color.foreground; opacity: 0.6; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
        ValueSlider {
            visible: root.device.caps.brightness; enabled: root.device.available
            label: "Brightness"; iconName: "light"; value: root.device.brightness
            onCommitted: value => root.control("brightness", value)
            onInteraction: active => root.interaction(active)
        }
        ValueSlider {
            visible: root.device.caps.volume; enabled: root.device.available
            label: "Volume"; iconName: root.device.muted ? "mute" : "volume"; value: root.device.volume
            onCommitted: value => root.control("volume", value)
            onInteraction: active => root.interaction(active)
        }
        HomeButton {
            visible: root.device.caps.mute; enabled: root.device.available
            text: root.device.muted ? "Unmute" : "Mute"; iconName: root.device.muted ? "mute" : "volume"; compact: true
            selected: root.device.muted
            onClicked: root.control("mute", !root.device.muted)
        }
        ValueSlider {
            visible: root.device.caps.fan_speed; enabled: root.device.available
            label: "Fan speed"; iconName: "fan"; value: root.device.fan_speed; step: root.device.fan_speed_step || 1
            onCommitted: value => root.control("fan_speed", value)
            onInteraction: active => root.interaction(active)
        }
        FanControls {
            visible: root.device.domain === "fan"
            device: root.device
            onControl: (action, value) => root.control(action, value)
        }
        HomeSelect {
            visible: !!root.device.caps.select_option
            Layout.fillWidth: true
            enabled: root.device.available
            model: root.device.options || []
            currentIndex: (root.device.options || []).indexOf(root.device.state)
            displayText: currentIndex < 0 ? "Choose setting" : currentText.replace(/_/g, " ")
            Accessible.name: root.device.name
            onActivated: root.control("select_option", currentText)
        }
        ValueSlider {
            visible: !!root.device.caps.number_value
            enabled: root.device.available && isFinite(Number(root.device.state))
            label: root.device.name; iconName: "settings"; unit: root.device.unit || ""
            from: root.device.number_min === undefined ? 0 : root.device.number_min
            to: root.device.number_max === undefined ? 100 : root.device.number_max
            step: root.device.number_step || 1
            value: isFinite(Number(root.device.state)) ? Number(root.device.state) : from
            onCommitted: value => root.control("number_value", value)
            onInteraction: active => root.interaction(active)
        }
        RowLayout {
            visible: root.device.domain === "cover"
            Layout.fillWidth: true
            spacing: 8
            HomeButton { text: "Open"; iconName: "up"; Layout.fillWidth: true; enabled: root.device.available && root.device.caps.cover_open; onClicked: root.control("cover_open", null) }
            HomeButton { text: "Stop"; iconName: "stop"; Layout.fillWidth: true; enabled: root.device.available && root.device.caps.cover_stop; onClicked: root.control("cover_stop", null) }
            HomeButton { text: "Close"; iconName: "chevron"; Layout.fillWidth: true; enabled: root.device.available && root.device.caps.cover_close; onClicked: root.control("cover_close", null) }
        }
        HomeButton {
            objectName: "runAutomation"
            visible: root.isAutomation
            text: "Run now"; iconName: "automation"; primary: true; Layout.fillWidth: true
            enabled: root.device.available
            Accessible.name: "Run automation " + root.device.name + " with conditions checked"
            ToolTip.visible: hovered
            ToolTip.text: "Run with conditions checked, even if scheduled triggers are disabled."
            onClicked: root.control("automation_run", null)
        }
        Label {
            visible: root.isAutomation
            text: "Run now checks conditions. Disabling keeps active runs going."
            textFormat: Text.PlainText; color: Commons.Color.foreground; opacity: 0.6
            font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        HomeButton { objectName: "activateScene"; visible: root.device.domain === "scene"; text: "Activate scene"; iconName: "scene"; primary: true; enabled: root.device.available; onClicked: root.control("activate", null) }
        HomeButton {
            visible: root.device.caps.temperature
            text: root.expanded ? "Hide white temperature" : "White temperature"; iconName: "color"; compact: true; selected: root.expanded
            Layout.fillWidth: true
            onClicked: root.expanded = !root.expanded
        }
        ColumnLayout {
            visible: root.expanded && root.device.caps.temperature
            Layout.fillWidth: true
            enabled: root.device.available
            spacing: 10
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.07) }
            ValueSlider {
                visible: root.device.caps.temperature
                label: "White temperature"; iconName: "temperature"; unit: " K"; step: 50; temperature: true
                from: root.device.min_temperature; to: root.device.max_temperature
                value: root.device.temperature
                onCommitted: value => root.control("temperature", value)
                onInteraction: active => root.interaction(active)
            }
        }
        ColumnLayout {
            objectName: "rgbControls"
            visible: root.device.caps.rgb
            enabled: root.device.available
            Layout.fillWidth: true
            spacing: 6
            Label { text: "RGB color"; color: Commons.Color.foreground; font.pixelSize: 12; font.weight: Font.DemiBold }
            GridLayout {
                Layout.fillWidth: true
                columns: 5; rowSpacing: 6; columnSpacing: 6
                Repeater {
                    model: root.rgbPresets
                    delegate: Button {
                        id: presetButton
                        required property var modelData
                        objectName: "rgbPreset" + modelData.name.replace(/ /g, "")
                        readonly property bool selected: root.red === modelData.rgb[0] && root.green === modelData.rgb[1] && root.blue === modelData.rgb[2]
                        Layout.fillWidth: true; Layout.preferredWidth: 1
                        implicitHeight: 56; padding: 5
                        hoverEnabled: true
                        Accessible.name: "Set " + root.device.name + " to " + modelData.name
                        ToolTip.visible: hovered
                        ToolTip.text: "Apply " + modelData.name + " immediately" + (["Warm white", "White", "Daylight", "Cold white"].indexOf(modelData.name) >= 0 ? " (RGB approximation)" : "")
                        background: Rectangle {
                            radius: 11
                            color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, presetButton.down ? 0.14 : presetButton.hovered ? 0.10 : 0.045)
                            border.width: 1
                            border.color: presetButton.activeFocus || presetButton.selected ? Commons.Color.accent : Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.07)
                        }
                        contentItem: ColumnLayout {
                            spacing: 3
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                implicitWidth: 21; implicitHeight: 21; radius: 7
                                color: Qt.rgba(presetButton.modelData.rgb[0] / 255, presetButton.modelData.rgb[1] / 255, presetButton.modelData.rgb[2] / 255, 1)
                                border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.2)
                            }
                            Label {
                                text: presetButton.modelData.name; textFormat: Text.PlainText
                                color: Commons.Color.foreground; font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        onClicked: root.applyColorPreset(modelData)
                    }
                }
            }
            HomeButton {
                objectName: "customRgb"
                text: root.customColorOpen ? "Hide custom color" : "Custom color"
                iconName: "settings"; compact: true; selected: root.customColorOpen
                Layout.fillWidth: true
                onClicked: root.customColorOpen = !root.customColorOpen
            }
            ColumnLayout {
                objectName: "customRgbControls"
                visible: root.customColorOpen
                Layout.fillWidth: true; spacing: 6
                ValueSlider { objectName: "rgbRed"; label: "Red"; unit: ""; to: 255; accent: "#e99595"; value: root.red; onCommitted: value => root.setRgbChannel(0, value); onInteraction: active => root.interaction(active) }
                ValueSlider { objectName: "rgbGreen"; label: "Green"; unit: ""; to: 255; accent: "#9bc9a0"; value: root.green; onCommitted: value => root.setRgbChannel(1, value); onInteraction: active => root.interaction(active) }
                ValueSlider { objectName: "rgbBlue"; label: "Blue"; unit: ""; to: 255; accent: "#91b8ec"; value: root.blue; onCommitted: value => root.setRgbChannel(2, value); onInteraction: active => root.interaction(active) }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Rectangle { implicitWidth: 36; implicitHeight: 36; radius: 12; color: Qt.rgba(root.red / 255, root.green / 255, root.blue / 255, 1); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18) }
                    HomeButton { objectName: "applyRgb"; text: "Apply RGB color"; iconName: "check"; primary: true; Layout.fillWidth: true; onClicked: root.applyRgb(root.shownRgb) }
                }
            }
            Label { visible: root.device.caps.temperature; textFormat: Text.PlainText; text: "White temperature and RGB use separate light modes."; color: Commons.Color.foreground; opacity: 0.4; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
    }
}
