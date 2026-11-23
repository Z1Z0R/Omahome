pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "zizor.omahome"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property bool opened: panel.open
    readonly property string bridgePath: decodeURIComponent(Qt.resolvedUrl("bin/bridge.py").toString().replace(/^file:\/\//, ""))
    property var connection: ({local_url: "", remote_url: "", mode: "local", has_token: false})
    property var queue: []
    property var activeRequest: null
    property bool inFlight: false
    property bool settingsOpen: false
    property bool connected: false
    property bool sessionApproved: false
    property int sessionGeneration: 0
    readonly property bool canUseApi: panel.open && sessionApproved && !settingsOpen
    readonly property bool usesLocalHttp: connection.mode !== "remote" && connection.local_url.indexOf("http://") === 0
    property string message: "Add your Home Assistant connection to get started."
    property string errorText: ""
    property string search: ""
    property string category: "All"
    readonly property var categories: {
        const order = ["All", "Lights", "Air care", "Fans", "Climate", "Plugs", "Switches", "Audio", "Sensors", "Covers", "Scenes", "Automations"]
        return order.filter(name => name === "All" || allDevices.some(d => d.category === name))
    }
    property int interactions: 0
    property var deferredDevices: null
    property var allDevices: []
    property string lastUpdate: ""
    ListModel { id: devices }

    function open() { panel.open = true; request("config") }
    function endSession() {
        sessionGeneration++
        sessionApproved = false; connected = false
        queue = queue.filter(item => item.command !== "states" && item.command !== "control")
        refreshLater.stop()
        deferredDevices = null; interactions = 0
    }
    function close() { panel.open = false; token.text = ""; endSession() }
    function connectSaved() {
        if (!panel.open || settingsOpen || !connection.has_token) return
        sessionApproved = true
        refresh()
    }
    function togglePanel() { if (panel.open) close(); else open() }
    function closeForPopoutSwitch() { close() }
    function request(command, values) {
        if ((command === "states" || command === "control") && !canUseApi) return
        // Coalesce pending slider changes, never repeat a command after a failure.
        const item = {command: command, values: values || {}, generation: sessionGeneration}
        let next = queue.slice()
        if (command === "states" && (next.some(x => x.command === "states") || (activeRequest && activeRequest.command === "states"))) return
        if (command === "control") next = next.filter(x => !(x.command === command && x.values.entity === item.values.entity && x.values.action === item.values.action))
        if (next.length >= 50) { errorText = "Too many pending requests. Wait for the connection to finish."; return }
        next.push(item); queue = next
        pump()
    }
    function pump() {
        if (inFlight || !queue.length) return
        queue = queue.filter(item => (item.command !== "states" && item.command !== "control") || (canUseApi && item.generation === sessionGeneration))
        if (!queue.length) return
        activeRequest = queue[0]; queue = queue.slice(1)
        inFlight = true
        worker.running = true
    }
    function refresh() { if (canUseApi && connection.has_token) request("states") }
    function filterDevices() {
        if (category !== "All" && !allDevices.some(d => d.category === category)) category = "All"
        const needle = search.toLowerCase()
        const matches = allDevices.filter(d => {
            const group = category === "All" || d.category === category
            return group && (!needle || (d.name + " " + d.id + " " + (d.group_name || "") + " " + (d.room_name || "")).toLowerCase().indexOf(needle) >= 0)
        })
        // Keep delegates stable so open color editors and keyboard focus survive polling.
        let index = 0
        let previousGroup = ""
        let previousRoom = null
        for (let original of matches) {
            const roomId = original.room_id || ""
            const d = Object.assign({}, original, {group_start: original.group_id !== previousGroup, room_start: roomId !== previousRoom})
            previousGroup = original.group_id
            previousRoom = roomId
            if (index < devices.count && devices.get(index).payload.id === d.id) devices.setProperty(index, "payload", d)
            else { while (index < devices.count) devices.remove(index); devices.append({payload: d}) }
            index++
        }
        while (devices.count > index) devices.remove(index)
    }
    function applyDevices(items) {
        if (interactions > 0) { deferredDevices = items; return }
        allDevices = items; filterDevices()
    }
    function interaction(active) {
        interactions = Math.max(0, interactions + (active ? 1 : -1))
        if (interactions === 0 && deferredDevices) { const pending = deferredDevices; deferredDevices = null; applyDevices(pending) }
    }
    function receive(raw) {
        // A completed request cannot reconnect a panel dismissed in the meantime.
        if ((activeRequest.command === "states" || activeRequest.command === "control") && (!canUseApi || activeRequest.generation !== sessionGeneration)) return
        let result
        try { result = JSON.parse(raw) } catch (e) { errorText = "The Home Assistant helper did not return a valid response."; return }
        if (!result.ok) {
            errorText = result.error
            if (activeRequest.command === "states" || activeRequest.command === "control") connected = false
            if (activeRequest.command === "save") token.text = ""
            return
        }
        errorText = ""
        const data = result.data
        switch (activeRequest.command) {
        case "config":
        case "save":
            connection = data
            localUrl.text = data.local_url; remoteUrl.text = data.remote_url; mode.currentIndex = data.mode === "remote" ? 1 : 0
            token.text = ""
            if (activeRequest.command === "save") {
                settingsOpen = false; connected = false; allDevices = []; devices.clear()
                // Save and connect is explicit authorization, only while visible.
                sessionApproved = panel.open && activeRequest.generation === sessionGeneration
                refresh()
            }
            else if (!data.has_token) settingsOpen = true
            else if (!sessionApproved) message = "Saved connection. Click Connect to load devices."
            break
        case "states":
            connected = true; applyDevices(data.devices)
            lastUpdate = new Date().toLocaleTimeString()
            message = (data.mode === "remote" ? "Remote" : "Local") + " · " + data.devices.length + " entities · " + lastUpdate
            break
        case "control": message = "Command sent. Refreshing device state…"; refreshLater.restart(); break
        case "dashboard": Qt.openUrlExternally(data.url); break
        }
    }
    Component.onCompleted: request("config")
    Process {
        id: worker
        command: ["python3", root.bridgePath]
        stdinEnabled: true
        onStarted: {
            write(JSON.stringify(root.activeRequest) + "\n")
            // Remove the token from the queued request as soon as it is sent.
            if (root.activeRequest.command === "save") root.activeRequest.values.token = ""
        }
        stdout: StdioCollector { onStreamFinished: root.receive(text) }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) root.errorText = "Home Assistant helper stopped unexpectedly. Check that Python 3 is installed."
            root.inFlight = false; root.activeRequest = null
            Qt.callLater(root.pump)
        }
    }
    Timer { id: refreshLater; interval: 900; onTriggered: root.refresh() }
    Timer { interval: 10000; running: root.canUseApi && root.connected && root.connection.has_token && root.interactions === 0; repeat: true; onTriggered: root.refresh() }
    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        iconComponent: Component { HomeAssistantIcon { tint: button.foreground } }
        tooltipText: "Omahome · Home Assistant"
        onPressed: root.togglePanel()
    }
    Ui.KeyboardPanel {
        id: panel
        anchorItem: button; owner: root; bar: root.bar
        contentWidth: Commons.Style.space(480)
        contentHeight: Math.min(Commons.Style.space(710), screen ? screen.height - Commons.Style.space(110) : Commons.Style.space(710))
        open: false
        onOpenChanged: if (!open) { token.text = ""; root.endSession() }
        Control {
            anchors.fill: parent
            palette.window: Commons.Color.background
            palette.windowText: Commons.Color.foreground
            palette.text: Commons.Color.foreground
            palette.button: Qt.lighter(Commons.Color.background, 1.6)
            palette.buttonText: Commons.Color.foreground
            palette.base: Commons.Color.background
            palette.highlight: Commons.Color.accent
            palette.highlightedText: Commons.Color.background
            contentItem: ColumnLayout {
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 11
                Rectangle {
                    implicitWidth: 42; implicitHeight: 42; radius: 14
                    color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, 0.13)
                    HomeAssistantIcon { anchors.centerIn: parent; width: 25; height: 25 }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    Label { textFormat: Text.PlainText; text: "Omahome"; color: Commons.Color.foreground; font.pixelSize: 22; font.weight: Font.DemiBold }
                    Label { textFormat: Text.PlainText; text: root.settingsOpen ? "Connection settings" : "Your home, at a glance"; color: Commons.Color.foreground; opacity: 0.45; font.pixelSize: 11 }
                }
                HomeButton { text: root.settingsOpen ? "Devices" : ""; iconName: root.settingsOpen ? "dashboard" : "settings"; Accessible.name: root.settingsOpen ? "Show devices" : "Connection settings"; onClicked: root.settingsOpen = !root.settingsOpen }
                HomeButton { iconName: "close"; Accessible.name: "Close panel"; onClicked: root.close() }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: statusRow.implicitHeight + 18
                radius: 12
                color: Qt.rgba(Commons.Color.foreground.r, Commons.Color.foreground.g, Commons.Color.foreground.b, 0.035)
                RowLayout {
                    id: statusRow
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                    spacing: 8
                    Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: root.connected ? Commons.Color.accent : Commons.Color.foreground; opacity: root.connected ? 1 : 0.35 }
                    Label { textFormat: Text.PlainText; text: root.inFlight ? "Updating your home…" : root.message; color: Commons.Color.foreground; opacity: 0.65; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
            Rectangle {
                visible: !!root.errorText
                Layout.fillWidth: true
                implicitHeight: errorRow.implicitHeight + 22
                radius: 12
                color: Qt.rgba(0.91, 0.58, 0.58, 0.08)
                RowLayout {
                    id: errorRow
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 11 }
                    spacing: 9
                    HomeIcon { name: "warning"; tint: "#e99595"; Layout.preferredWidth: 17; Layout.preferredHeight: 17 }
                    Label { textFormat: Text.PlainText; text: root.errorText; color: "#e99595"; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                HomeButton { text: "Dashboard"; iconName: "dashboard"; Layout.fillWidth: true; enabled: root.connection.has_token; onClicked: root.request("dashboard") }
                HomeButton { text: "Remote"; iconName: "external"; Layout.fillWidth: true; enabled: !!root.connection.remote_url; onClicked: root.request("dashboard", {mode: "remote"}) }
                HomeButton { iconName: "refresh"; Accessible.name: "Refresh devices"; enabled: !root.inFlight && root.canUseApi && root.connection.has_token; onClicked: root.refresh() }
            }
            HomeButton {
                objectName: "connectSaved"
                visible: !root.settingsOpen && !root.sessionApproved && root.connection.has_token
                text: "Connect to Home Assistant"; iconName: "power"; primary: true
                Layout.fillWidth: true; enabled: !root.inFlight
                onClicked: root.connectSaved()
            }
            Label {
                visible: !root.settingsOpen && !root.sessionApproved && root.usesLocalHttp && root.connection.has_token
                text: "Local HTTP cannot verify the server’s identity. Connect only on your trusted home network, or use an HTTPS address."
                textFormat: Text.PlainText; color: Commons.Color.foreground; opacity: 0.7
                font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            ScrollView {
                visible: root.settingsOpen
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent.width
                    spacing: 9
                    Label { textFormat: Text.PlainText; text: "Connection"; color: Commons.Color.foreground; font.bold: true }
                    Label { textFormat: Text.PlainText; text: "Local server URL"; color: Commons.Color.foreground }
                    HomeField { id: localUrl; Layout.fillWidth: true; placeholderText: "http://homeassistant.local:8123"; selectByMouse: true }
                    Label { textFormat: Text.PlainText; text: "Remote server URL (HTTPS)"; color: Commons.Color.foreground }
                    HomeField { id: remoteUrl; Layout.fillWidth: true; placeholderText: "https://your-instance.ui.nabu.casa"; selectByMouse: true }
                    Label { textFormat: Text.PlainText; text: "Use this connection for device controls"; color: Commons.Color.foreground }
                    HomeSelect { id: mode; model: ["Local", "Remote"]; Layout.fillWidth: true }
                    Label { textFormat: Text.PlainText; text: "Home Assistant access token"; color: Commons.Color.foreground }
                    HomeField {
                        id: token; Layout.fillWidth: true; echoMode: TextInput.Password; selectByMouse: true
                        placeholderText: root.connection.has_token ? "Saved · leave blank to keep" : "Paste a long-lived access token"
                        onVisibleChanged: if (!visible) text = ""
                    }
                    Label { textFormat: Text.PlainText;
                        text: "Create a long-lived access token in your Home Assistant profile → Security. It stays on this computer in a private file."
                        color: Commons.Color.foreground; opacity: 0.7; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                    Label {
                        text: "Save and connect sends your token to the selected server. Local HTTP cannot verify its identity; use it only on a trusted network. HTTPS verifies the server certificate."
                        textFormat: Text.PlainText; color: Commons.Color.foreground; opacity: 0.7
                        wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                    HomeButton {
                        text: "Save and connect"; iconName: "check"; primary: true; Layout.fillWidth: true; enabled: !root.inFlight
                        onClicked: {
                            root.request("save", {local_url: localUrl.text, remote_url: remoteUrl.text, mode: mode.currentIndex === 1 ? "remote" : "local", token: token.text})
                            token.text = ""
                        }
                    }
                    Label { textFormat: Text.PlainText; text: "Access from outside home"; color: Commons.Color.foreground; font.bold: true; Layout.topMargin: 12 }
                    Label { textFormat: Text.PlainText;
                        text: "Enable remote access in Home Assistant Cloud, then paste its HTTPS address above. An existing HTTPS tunnel or VPN address also works. Opening a remote dashboard does not expose your server or create a tunnel."
                        color: Commons.Color.foreground; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                    HomeButton {
                        text: "Set up Home Assistant Cloud"; iconName: "cloud"; Layout.fillWidth: true
                        enabled: !!root.connection.local_url
                        onClicked: Qt.openUrlExternally(root.connection.local_url + "/config/cloud")
                    }
                    HomeButton { text: "Remote access guide"; iconName: "external"; Layout.fillWidth: true; onClicked: Qt.openUrlExternally("https://www.home-assistant.io/docs/configuration/remote/") }
                    Label { textFormat: Text.PlainText;
                        text: "For a Cloudflare tunnel, the API must also accept your Home Assistant token. A separate Cloudflare Access login page will block device controls. No router ports need to be opened for Home Assistant Cloud."
                        color: Commons.Color.foreground; opacity: 0.65; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                }
            }
            HomeField {
                visible: !root.settingsOpen; Layout.fillWidth: true
                placeholderText: "Find a device…"; iconName: "search"; selectByMouse: true
                onTextChanged: { root.search = text; root.filterDevices() }
            }
            Flow {
                visible: !root.settingsOpen
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: root.categories
                    delegate: HomeButton {
                        required property string modelData
                        text: modelData
                        compact: true; selected: root.category === modelData
                        onClicked: { root.category = modelData; root.filterDevices() }
                    }
                }
            }
            Label { textFormat: Text.PlainText;
                visible: !root.settingsOpen && devices.count === 0
                text: root.connected ? "No matching devices. Try another search or filter." : "Connect to Home Assistant in Settings."
                color: Commons.Color.foreground; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            ScrollView {
                visible: !root.settingsOpen
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                Column {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: devices
                        delegate: Column {
                            id: groupRow
                            required property var payload
                            width: parent.width
                            spacing: 8
                            Label {
                                objectName: "roomHeading"
                                visible: !!groupRow.payload.room_start
                                text: groupRow.payload.room_name || "Unassigned"
                                textFormat: Text.PlainText; color: Commons.Color.accent
                                font.pixelSize: 14; font.weight: Font.DemiBold
                                width: parent.width; elide: Text.ElideRight
                                topPadding: 10; leftPadding: 3
                            }
                            Label {
                                visible: !!groupRow.payload.group_start && groupRow.payload.group_size > 1
                                text: groupRow.payload.group_name || ""
                                textFormat: Text.PlainText
                                color: Commons.Color.foreground; opacity: 0.55
                                font.pixelSize: 11; font.weight: Font.DemiBold
                                width: parent.width; elide: Text.ElideRight
                                topPadding: 9; leftPadding: 3
                            }
                            DeviceCard {
                                width: parent.width
                                device: groupRow.payload
                                enabled: root.connected && !root.settingsOpen
                                onControl: (action, value) => root.request("control", {entity: groupRow.payload.id, action: action, value: value})
                                onInteraction: active => root.interaction(active)
                            }
                        }
                    }
                }
            }
        }
        }
    }
}
