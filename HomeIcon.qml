import QtQuick
import qs.Commons as Commons

Item {
    id: root
    property string name: "home"
    property color tint: Commons.Color.foreground
    implicitWidth: 20
    implicitHeight: 20
    // Small bundled vector symbols; no icon font or network dependency.
    readonly property var paths: ({
        home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
        light: '<path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2Z"/>',
        media_player: '<rect x="5" y="2" width="14" height="20" rx="3"/><circle cx="12" cy="15" r="4"/><path d="M10 6h4"/>',
        switch: '<rect x="4" y="2" width="16" height="20" rx="4"/><path d="M12 6v5m-4 2a5 5 0 1 0 8 0"/>',
        input_boolean: '<rect x="2" y="6" width="20" height="12" rx="6"/><circle cx="15" cy="12" r="3"/>',
        air_purifier: '<rect x="5" y="2" width="14" height="20" rx="4"/><path d="M8 6h8M8 9h8m-8 4h8m-8 3h8m-6 3h4"/>',
        filter: '<path d="M3 4h18l-7 8v7l-4 2V12Z"/>',
        fan: '<circle cx="12" cy="12" r="2"/><path d="M10 10C4 8 6 1 10 3c3 1 4 4 3 7m1 2c5-4 10 1 6 4-2 2-6 1-7-2m-2 0c1 7-6 9-7 4-1-3 2-5 5-5"/>',
        cover: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 7h16M4 11h16M4 15h16m-8 0v6"/>',
        outlet: '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="M8 9v3m8-3v3m-7 5a3 3 0 0 1 6 0"/>',
        humidifier: '<rect x="5" y="11" width="14" height="10" rx="3"/><path d="M9 7c-3-3 3-3 0-6m6 6c-3-3 3-3 0-6m-5 15h4"/>',
        dehumidifier: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M7 7h10M7 10h10m-5 3s-3 3-3 4a3 3 0 0 0 6 0c0-1-3-4-3-4Z"/>',
        climate: '<path d="M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Z"/><path d="M12 8v10m6-12h3m-3 4h2"/>',
        temperature: '<path d="M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Z"/><path d="M12 9v9"/>',
        humidity: '<path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
        battery: '<rect x="2" y="6" width="18" height="12" rx="3"/><path d="M22 10v4M6 9v6m4-6v6m4-6v6"/>',
        power: '<path d="M12 2v10m-5-7a9 9 0 1 0 10 0"/>',
        lock: '<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
        unlock: '<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0m-4 9v2"/>',
        sensor: '<circle cx="12" cy="12" r="3"/><path d="M7 7a7 7 0 0 0 0 10m10-10a7 7 0 0 1 0 10M4 4a11 11 0 0 0 0 16M20 4a11 11 0 0 1 0 16"/>',
        binary_sensor: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/>',
        scene: '<path d="m12 2 2.5 6.5L21 11l-6.5 2.5L12 20l-2.5-6.5L3 11l6.5-2.5Zm7 15 1 2 2 1-2 1-1 2-1-2-2-1 2-1Z"/>',
        automation: '<path d="m13 2-9 12h7l-1 8 10-13h-7Z"/>',
        volume: '<path d="m11 4-6 5H2v6h3l6 5Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
        mute: '<path d="m11 4-6 5H2v6h3l6 5Zm5 5 6 6m0-6-6 6"/>',
        settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
        close: '<path d="m6 6 12 12M6 18 18 6"/>',
        refresh: '<path d="M20 7v5h-5M4 17v-5h5m10-1a7 7 0 0 0-12-5L4 9m16 6-3 3a7 7 0 0 1-12-5"/>',
        external: '<path d="M14 3h7v7m0-7L10 14m0-9H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
        dashboard: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
        search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
        color: '<circle cx="12" cy="12" r="9"/><circle cx="8" cy="9" r="1"/><circle cx="15" cy="8" r="1"/><circle cx="8" cy="15" r="1"/><circle cx="15" cy="15" r="1"/>',
        chevron: '<path d="m6 9 6 6 6-6"/>',
        up: '<path d="m6 15 6-6 6 6"/>',
        stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
        check: '<path d="m5 12 4 4L19 6"/>',
        warning: '<path d="m12 3 10 18H2Zm0 6v4m0 4v.1"/>',
        cloud: '<path d="M7 18a5 5 0 1 1 0-10 7 7 0 0 1 13 2 4 4 0 0 1-1 8Z"/>',
        all: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>'
    })
    Image {
    anchors.fill: parent
    sourceSize.width: Math.max(1, root.width * 2)
    sourceSize.height: Math.max(1, root.height * 2)
    fillMode: Image.PreserveAspectFit
    source: 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="' + root.tint.toString() + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + (root.paths[root.name] || root.paths.sensor) + '</svg>')
    }
}
