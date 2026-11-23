#!/usr/bin/env python3
"""Load real plugin QML offscreen with only the compositor popup stubbed."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

plugin = Path(__file__).resolve().parents[1]
omarchy = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))
if not (omarchy / 'shell/Commons').is_dir() or not shutil.which('quickshell'):
    raise SystemExit('Requires an installed Omarchy shell and quickshell.')

spec = importlib.util.spec_from_file_location('bridge', plugin / 'bin/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
samples = []

def sample(domain, state='on', **attrs):
    item = bridge.normalize({'entity_id': domain + '.test_' + str(len(samples)), 'state': state, 'attributes': {'friendly_name': 'Test ' + domain, **attrs}})
    if domain == 'climate':
        item['temperature_unit'] = '°C'
    item['group_id'] = 'test-group-' + str(len(samples) // 2)
    item['group_name'] = 'Test physical device ' + str(len(samples) // 2)
    item['group_size'] = 2
    samples.append(item)

sample('light', supported_color_modes=['rgb', 'color_temp'], brightness=128)
sample('media_player', supported_features=396, volume_level=0.35)
sample('fan', friendly_name='Levoit CORE 300S', supported_features=57, percentage=50, percentage_step=25, preset_modes=['auto', 'sleep', 'normal'], preset_mode='auto')
sample('fan', friendly_name='Levoit Tower Fan', supported_features=63, percentage=50, oscillating=True, direction='forward', preset_modes=['auto', 'sleep'], preset_mode='sleep')
sample('select', state='dim', friendly_name='Levoit Core 300S night light', options=['off', 'dim', 'on'])
sample('number', state='3', friendly_name='Levoit humidifier mist level', min=1, max=9, step=1)
sample('sensor', state='8', friendly_name='Levoit Core 300S PM2.5', device_class='pm25', unit_of_measurement='µg/m³')
sample('cover', supported_features=11)
sample('scene', state='unknown')
sample('climate', state='heat', supported_features=413, hvac_modes=['off', 'heat', 'cool'], temperature=21.5, current_temperature=20.2, current_humidity=44, min_temp=7, max_temp=35, target_temp_step=0.5, humidity=45, fan_modes=['auto', 'low'], fan_mode='auto', preset_modes=['eco', 'comfort'], preset_mode='eco')
sample('climate', state='heat_cool', supported_features=3, hvac_modes=['off', 'heat_cool'], target_temp_low=20, target_temp_high=25, current_temperature=22, min_temp=7, max_temp=35)
sample('humidifier', device_class='humidifier', humidity=45, current_humidity=38, min_humidity=30, max_humidity=80, supported_features=1, available_modes=['auto', 'normal'], mode='auto')
sample('humidifier', device_class='dehumidifier', humidity=50, current_humidity=62, min_humidity=35, max_humidity=70)
sample('sensor', state='22.6', device_class='temperature', unit_of_measurement='°C')
sample('sensor', state='48', device_class='humidity', unit_of_measurement='%')
sample('switch', device_class='outlet')
sample('switch', friendly_name='Desk plug child lock', entity_category='config')
sample('automation', friendly_name='Evening lights')

room_states = [
    {'entity_id': 'fan.office_purifier', 'state': 'on', 'attributes': {'friendly_name': 'Purifier'}},
    {'entity_id': 'switch.office_purifier_child_lock', 'state': 'on', 'attributes': {'friendly_name': 'Child lock'}},
    {'entity_id': 'light.bedroom_lamp', 'state': 'on', 'attributes': {'friendly_name': 'Lamp'}},
]
room_metadata = {
    room_states[0]['entity_id']: {'device_id': 'purifier', 'device_name': 'Desk air care', 'area_id': 'office', 'area_name': 'Office'},
    room_states[1]['entity_id']: {'device_id': 'purifier', 'device_name': 'Desk air care', 'area_id': 'office', 'area_name': 'Office'},
    room_states[2]['entity_id']: {'device_id': 'lamp', 'device_name': 'Bedside lamp', 'area_id': 'bedroom', 'area_name': 'Bedroom'},
}
room_samples = bridge.normalize_entities(room_states, {}, room_metadata)

with tempfile.TemporaryDirectory(prefix='omahome-qml-') as temporary:
    directory = Path(temporary)
    (directory / 'Commons').symlink_to(omarchy / 'shell/Commons', target_is_directory=True)
    (directory / 'Omahome').symlink_to(plugin, target_is_directory=True)
    ui = directory / 'Ui'
    ui.mkdir()
    names = ['BarWidget', 'BarIconButton', 'WidgetButton', 'OpticalGlyph', 'BarIconContent', 'IconContentBounds']
    for name in names:
        shutil.copy2(omarchy / 'shell/Ui' / (name + '.qml'), ui)
    (ui / 'qmldir').write_text('module qs.Ui\n' + '\n'.join(name + ' 1.0 ' + name + '.qml' for name in names + ['KeyboardPanel']) + '\n')
    (ui / 'KeyboardPanel.qml').write_text('''import QtQuick
Item {
    property Item anchorItem
    property var owner
    property var bar
    property int contentWidth
    property int contentHeight
    property bool open: false
    property var screen: null
    width: contentWidth; height: contentHeight
}
''')
    (directory / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Omahome"
ShellRoot {
    id: suite
    property bool rgbPassed: false
    property int rgbCommandCount: 0
    property var lastRgb: []
    property bool automationPassed: false
    property bool scenePassed: false
    function rows(item) {
        const model = Array.from(item.data).find(child => "count" in child && "get" in child && "append" in child)
        if (!model) { console.error("SMOKE ASSERTION FAILED: device model missing"); return [] }
        const found = []
        for (let index = 0; index < model.count; index++) found.push(model.get(index).payload)
        return found
    }
    function findItem(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children || []) {
            const result = findItem(child, name)
            if (result) return result
        }
        return null
    }
    property bool dragPassed: false
    property bool keyboardPassed: false
    property bool roomsPassed: false
    // Match the bar host: derive the slot from the widget's preferred size.
    Panel { id: widget; width: implicitWidth; height: implicitHeight }
    DeviceCard { id: colorCard; width: 420; expanded: false; onControl: (action, value) => { suite.rgbPassed = action === "rgb" && JSON.stringify(value) === "[12,34,56]"; if (action === "rgb") { suite.rgbCommandCount++; suite.lastRgb = value } }; device: ''' + json.dumps(samples[0]) + ''' }
    DeviceCard { id: lockCard; width: 420; device: ''' + json.dumps(samples[16]) + ''' }
    DeviceCard { id: automationCard; width: 420; onControl: (action, value) => { suite.automationPassed = action === "automation_run" }; device: ''' + json.dumps(samples[-1]) + ''' }
    DeviceCard { id: sceneCard; width: 420; onControl: (action, value) => { suite.scenePassed = action === "activate" }; device: ''' + json.dumps(samples[8]) + ''' }
    FloatingWindow {
        visible: true; implicitWidth: 300; implicitHeight: 180
        ValueSlider {
            id: dragged; width: 280
            property real modelValue: 20
            value: modelValue
            onInteraction: active => { if (!active) dragged.modelValue = 21 }
            onCommitted: value => {
                suite.dragPassed = value === 80
                if (!suite.dragPassed) console.error("SMOKE ASSERTION FAILED: drag committed", value, "instead of 80")
            }
        }
        ValueSlider {
            id: keyboard; y: 80; width: 280
            property real modelValue: 20
            value: modelValue
            onCommitted: value => {
                suite.keyboardPassed = value === 40
                if (!suite.keyboardPassed) console.error("SMOKE ASSERTION FAILED: keyboard committed", value, "instead of 40")
            }
        }
    }
    Timer { interval: 250; running: true; onTriggered: {
        const slider = dragged.children.find(item => "stepSize" in item && "pressed" in item)
        slider.pressed = true
        slider.stepSize = 60
        slider.increase()
        slider.moved()
        slider.pressed = false
    } }
    Timer { interval: 450; running: true; onTriggered: {
        const slider = keyboard.children.find(item => "stepSize" in item && "pressed" in item)
        slider.stepSize = 20
        slider.increase()
        slider.moved()
        keyboard.modelValue = 21
    } }
    Timer { interval: 200; running: true; onTriggered: {
        if (widget.implicitWidth <= 0 || widget.implicitHeight <= 0 || widget.width <= 0 || widget.height <= 0) {
            console.error("SMOKE ASSERTION FAILED: bar widget has no visible size")
        }
        if (!lockCard.isChildLock || lockCard.iconName !== "lock" || lockCard.childLockStatus !== "Enabled") console.error("SMOKE ASSERTION FAILED: child lock enabled")
        lockCard.device = Object.assign({}, lockCard.device, {state: "off"})
        if (lockCard.iconName !== "unlock" || lockCard.childLockStatus !== "Disabled") console.error("SMOKE ASSERTION FAILED: child lock disabled")
        lockCard.device = Object.assign({}, lockCard.device, {state: "unavailable", available: false})
        if (lockCard.childLockStatus !== "Unavailable") console.error("SMOKE ASSERTION FAILED: child lock unavailable")
        const rgb = suite.findItem(colorCard, "rgbControls")
        if (!rgb || !rgb.visible) console.error("SMOKE ASSERTION FAILED: RGB controls hidden on compatible lamp")
        if (suite.findItem(colorCard, "customRgbControls").visible) console.error("SMOKE ASSERTION FAILED: custom RGB should start collapsed")
        for (const preset of colorCard.rgbPresets) {
            const count = suite.rgbCommandCount
            suite.findItem(colorCard, "rgbPreset" + preset.name.replace(/ /g, "")).clicked()
            if (suite.rgbCommandCount !== count + 1 || JSON.stringify(suite.lastRgb) !== JSON.stringify(preset.rgb)) console.error("SMOKE ASSERTION FAILED: preset did not apply immediately", preset.name)
            if (colorCard.rgbDraft !== null) console.error("SMOKE ASSERTION FAILED: preset left an unsent draft")
            colorCard.device = Object.assign({}, colorCard.device, {rgb: preset.rgb})
            if (JSON.stringify(colorCard.shownRgb) !== JSON.stringify(preset.rgb)) console.error("SMOKE ASSERTION FAILED: applied preset did not follow refresh")
        }
        const beforeUnavailable = suite.rgbCommandCount
        colorCard.device = Object.assign({}, colorCard.device, {available: false})
        suite.findItem(colorCard, "rgbPresetRed").clicked()
        if (suite.rgbCommandCount !== beforeUnavailable) console.error("SMOKE ASSERTION FAILED: unavailable preset sent a command")
        colorCard.device = Object.assign({}, colorCard.device, {available: true})
        suite.findItem(colorCard, "customRgb").clicked()
        if (!suite.findItem(colorCard, "customRgbControls").visible) console.error("SMOKE ASSERTION FAILED: custom RGB did not open")
        colorCard.device = Object.assign({}, colorCard.device, {rgb: [0,255,0]})
        if (JSON.stringify(colorCard.shownRgb) !== "[0,255,0]") console.error("SMOKE ASSERTION FAILED: external RGB refresh remained stale")
        suite.findItem(colorCard, "rgbRed").committed(12)
        suite.findItem(colorCard, "rgbGreen").committed(34)
        suite.findItem(colorCard, "rgbBlue").committed(56)
        const beforeDraftRefresh = suite.rgbCommandCount
        colorCard.device = Object.assign({}, colorCard.device, {rgb: [0,0,255]})
        if (JSON.stringify(colorCard.shownRgb) !== "[12,34,56]" || suite.rgbCommandCount !== beforeDraftRefresh) console.error("SMOKE ASSERTION FAILED: refresh overwrote or sent unsaved RGB draft")
        suite.findItem(colorCard, "applyRgb").clicked()
        if (!suite.rgbPassed) console.error("SMOKE ASSERTION FAILED: RGB apply payload")
        if (colorCard.rgbDraft !== null || JSON.stringify(colorCard.shownRgb) !== "[0,0,255]") console.error("SMOKE ASSERTION FAILED: submitted RGB did not return to confirmed state")
        colorCard.device = Object.assign({}, colorCard.device, {rgb: [12,34,56]})
        if (JSON.stringify(colorCard.shownRgb) !== "[12,34,56]") console.error("SMOKE ASSERTION FAILED: custom RGB acknowledgement did not synchronize")
        colorCard.device = Object.assign({}, colorCard.device, {rgb: [99,88,77]})
        if (JSON.stringify(colorCard.shownRgb) !== "[99,88,77]") console.error("SMOKE ASSERTION FAILED: later custom RGB refresh remained stale")
        suite.findItem(colorCard, "rgbRed").committed(222)
        suite.findItem(colorCard, "rgbPresetBlue").clicked()
        if (colorCard.rgbDraft !== null) console.error("SMOKE ASSERTION FAILED: preset did not discard old custom draft")
        const sceneButton = suite.findItem(sceneCard, "activateScene")
        if (!sceneButton.enabled) console.error("SMOKE ASSERTION FAILED: unknown-state scene activation disabled")
        sceneButton.clicked()
        if (!suite.scenePassed) console.error("SMOKE ASSERTION FAILED: scene activation not emitted")
        sceneCard.device = Object.assign({}, sceneCard.device, {state: "unavailable", available: false})
        if (sceneButton.enabled) console.error("SMOKE ASSERTION FAILED: unavailable scene activation enabled")
        colorCard.device = Object.assign({}, colorCard.device, {caps: Object.assign({}, colorCard.device.caps, {rgb: false})})
        if (rgb.visible) console.error("SMOKE ASSERTION FAILED: RGB controls visible on incompatible lamp")
        const beforeUnsupported = suite.rgbCommandCount
        suite.findItem(colorCard, "rgbPresetBlue").clicked()
        if (suite.rgbCommandCount !== beforeUnsupported) console.error("SMOKE ASSERTION FAILED: incompatible preset sent a command")
        suite.findItem(automationCard, "runAutomation").clicked()
        if (!suite.automationPassed || automationCard.automationStatus !== "Enabled") console.error("SMOKE ASSERTION FAILED: automation action")
        automationCard.device = Object.assign({}, automationCard.device, {state: "off"})
        if (automationCard.automationStatus !== "Disabled") console.error("SMOKE ASSERTION FAILED: automation disabled status")
        automationCard.device = Object.assign({}, automationCard.device, {state: "unavailable", available: false})
        if (suite.findItem(automationCard, "runAutomation").enabled) console.error("SMOKE ASSERTION FAILED: unavailable automation enabled")
        widget.connected = true
        widget.applyDevices(''' + json.dumps(samples) + ''')
    } }
    Timer { interval: 600; running: true; onTriggered: {
        widget.applyDevices(''' + json.dumps(samples) + ''')
        widget.category = "Air care"; widget.filterDevices()
        widget.category = "Fans"; widget.filterDevices()
        widget.category = "Plugs"; widget.filterDevices()
        widget.category = "Audio"; widget.filterDevices()
        widget.category = "Climate"; widget.filterDevices()
        widget.category = "Sensors"; widget.filterDevices()
        widget.category = "Lights"; widget.filterDevices()
        if (widget.categories.indexOf("Automations") < 0) console.error("SMOKE ASSERTION FAILED: automations category missing")
        widget.category = "Automations"; widget.filterDevices()
        widget.category = "All"; widget.filterDevices()
        if (widget.allDevices.length !== 18) console.error("SMOKE ASSERTION FAILED")
    } }
    Timer { interval: 950; running: true; onTriggered: {
        widget.applyDevices(''' + json.dumps(room_samples) + ''')
        const rows = suite.rows(widget)
        if (rows.length !== 3 || rows.filter(row => row.room_start).length !== 2 || rows.filter(row => row.group_start).length !== 2) console.error("SMOKE ASSERTION FAILED: room/device heading counts")
        widget.search = "office"; widget.filterDevices()
        const office = suite.rows(widget)
        if (office.length !== 2 || office.filter(row => row.room_start).length !== 1 || office.some(row => row.room_id !== "office")) console.error("SMOKE ASSERTION FAILED: room search")
        widget.search = "child lock"; widget.filterDevices()
        const child = suite.rows(widget)
        if (child.length !== 1 || !child[0].room_start || !child[0].group_start || child[0].group_name !== "Desk air care") console.error("SMOKE ASSERTION FAILED: filtered auxiliary lost room/device context")
        widget.search = "desk air care"; widget.filterDevices()
        if (suite.rows(widget).length !== 2) console.error("SMOKE ASSERTION FAILED: physical device search")
        widget.search = ""; widget.category = "Lights"; widget.filterDevices()
        const lights = suite.rows(widget)
        if (lights.length !== 1 || !lights[0].room_start || lights[0].room_name !== "Bedroom") console.error("SMOKE ASSERTION FAILED: category room header")
        widget.category = "All"; widget.applyDevices(''' + json.dumps(room_samples) + ''')
        if (suite.rows(widget).length !== 3) console.error("SMOKE ASSERTION FAILED: room refresh duplicates")
        widget.category = "Lights"
        widget.applyDevices(''' + json.dumps([item for item in room_samples if item['domain'] != 'light']) + ''')
        if (widget.category !== "All" || suite.rows(widget).length !== 2) console.error("SMOKE ASSERTION FAILED: removed category left hidden empty filter")
        suite.roomsPassed = true
    } }
    Timer { interval: 200; repeat: true; running: true; onTriggered: {
        if (suite.roomsPassed && suite.dragPassed && suite.keyboardPassed) Qt.quit()
    } }
    Timer { interval: 5000; running: true; onTriggered: {
        console.error("SMOKE ASSERTION FAILED: regression checks timed out", suite.roomsPassed, suite.dragPassed, suite.keyboardPassed)
        Qt.quit()
    } }
}
''')
    for name in ('runtime', 'config', 'cache'):
        (directory / name).mkdir(mode=0o700)
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic', XDG_RUNTIME_DIR=str(directory / 'runtime'), XDG_CONFIG_HOME=str(directory / 'config'), XDG_CACHE_HOME=str(directory / 'cache'))
    environment.pop('WAYLAND_DISPLAY', None)
    result = subprocess.run(['quickshell', '-p', str(directory), '--no-color'], env=environment, text=True, capture_output=True, timeout=15)
    output = result.stdout + result.stderr
    if result.returncode or 'Configuration Loaded' not in output or any(marker in output for marker in ('WARN scene:', 'ERROR scene:', 'Failed to load configuration', 'SMOKE ASSERTION FAILED', 'ReferenceError', 'TypeError')):
        print(output)
        raise SystemExit('QML smoke test failed.')
    print('QML smoke test passed: setup form, purifier presets, fan controls, air-care settings, climate and humidity controls, readings, room/device headings, room/device search, polling updates, category filters, child-lock icons/status, RGB presets/draft preservation/refresh synchronization, unknown-scene activation, automation controls/category, and drag/keyboard slider regression checks.')
    print('Popup compositor wrapper was stubbed; live Wayland placement and hardware were not tested.')
