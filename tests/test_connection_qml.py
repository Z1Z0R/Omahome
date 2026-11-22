"""Exercise real Panel request flow using a helper that only logs local JSON."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ConnectionQmlTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('quickshell') and Path('/usr/share/omarchy/shell/Commons').is_dir(), 'Requires Omarchy and Quickshell')
    def test_saved_http_connection_needs_explicit_visible_session(self):
        with tempfile.TemporaryDirectory(prefix='omahome-connection-') as temporary:
            root = Path(temporary)
            plugin = root / 'Omahome'
            plugin.mkdir()
            for path in Path(__file__).resolve().parents[1].glob('*.qml'):
                shutil.copy2(path, plugin)
            (plugin / 'bin').mkdir()
            (plugin / 'bin/bridge.py').write_text('''import json,sys
from pathlib import Path
request=json.loads(sys.stdin.readline())
with (Path(__file__).parents[2]/'requests.jsonl').open('a') as log:
    log.write(json.dumps(request)+'\\n')
settings={'local_url':'http://homeassistant.local:8123','remote_url':'','mode':'local','has_token':True}
data=settings if request['command'] in ('config','save') else {'devices':[],'mode':'local'}
print(json.dumps({'ok':True,'data':data}),flush=True)
''')
            (root / 'Commons').symlink_to('/usr/share/omarchy/shell/Commons', target_is_directory=True)
            ui = root / 'Ui'
            ui.mkdir()
            names = ['BarWidget', 'BarIconButton', 'WidgetButton', 'OpticalGlyph', 'BarIconContent', 'IconContentBounds']
            for name in names:
                shutil.copy2(Path('/usr/share/omarchy/shell/Ui') / (name + '.qml'), ui)
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
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Omahome"
ShellRoot {
    id: suite
    property int stage: 0
    property int ticks: 0
    property var poll: null
    property int oldGeneration: -1
    Panel { id: widget; width: implicitWidth; height: implicitHeight }
    function check(ok, message) { if (!ok) console.error("ASSERTION FAILED:", message) }
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            suite.ticks++
            if (suite.ticks > 100) { console.error("ASSERTION FAILED: timeout at stage", suite.stage); Qt.quit(); return }
            if (widget.inFlight || widget.queue.length) return
            if (suite.stage === 0 && widget.connection.has_token) {
                suite.check(!widget.opened && !widget.connected && !widget.sessionApproved, "startup must stay disconnected")
                suite.poll = Array.from(widget.data).find(item => "interval" in item && item.interval === 10000)
                suite.check(!!suite.poll, "poll timer missing")
                suite.poll.interval = 50
                widget.open()
                suite.stage = 1; suite.ticks = 0
            } else if (suite.stage === 1 && suite.ticks > 5) {
                suite.check(widget.opened && !widget.connected && !widget.sessionApproved, "opening panel must not connect")
                suite.poll.interval = 10000
                widget.connectSaved()
                suite.stage = 2; suite.ticks = 0
            } else if (suite.stage === 2 && widget.connected) {
                // Simulate a delayed post-control refresh, then dismiss the popup
                // through its native open property rather than the Close button.
                widget.activeRequest = {command: "control", generation: widget.sessionGeneration}
                widget.receive(JSON.stringify({ok:true,data:{}}))
                widget.activeRequest = null
                const popup = widget.children.find(item => "anchorItem" in item && "open" in item)
                widget.inFlight = true
                widget.request("states")
                widget.request("control", {entity:"light.test",action:"turn_off"})
                suite.oldGeneration = widget.sessionGeneration
                popup.open = false
                widget.inFlight = false
                suite.check(!widget.sessionApproved && !widget.connected && widget.queue.length === 0, "dismissal must cancel approval and queued API calls")
                widget.refresh()
                widget.request("control", {entity:"light.test",action:"turn_on"})
                widget.activeRequest = {command:"states",generation:suite.oldGeneration}
                widget.receive(JSON.stringify({ok:true,data:{devices:[],mode:"local"}}))
                widget.activeRequest = {command:"save",generation:suite.oldGeneration}
                widget.receive(JSON.stringify({ok:true,data:widget.connection}))
                widget.activeRequest = null
                suite.check(!widget.connected && !widget.sessionApproved && widget.queue.length === 0, "late replies must not reconnect closed panel")
                suite.stage = 3; suite.ticks = 0
            } else if (suite.stage === 3 && suite.ticks > 12) {
                suite.check(!widget.connected && !widget.sessionApproved, "delayed refresh must stay cancelled")
                widget.open()
                suite.stage = 4; suite.ticks = 0
            } else if (suite.stage === 4 && suite.ticks > 5) {
                suite.check(!widget.connected && !widget.sessionApproved, "reopening must require fresh approval")
                widget.activeRequest = {command:"save",generation:suite.oldGeneration}
                widget.receive(JSON.stringify({ok:true,data:widget.connection}))
                widget.activeRequest = null
                suite.check(!widget.sessionApproved && widget.queue.length === 0, "late previous-session save must not approve reopened panel")
                widget.connectSaved()
                suite.stage = 5
            } else if (suite.stage === 5 && widget.connected) {
                widget.close()
                widget.open()
                suite.stage = 6; suite.ticks = 0
            } else if (suite.stage === 6 && suite.ticks > 5) {
                suite.check(!widget.sessionApproved, "save workflow must start unapproved")
                widget.settingsOpen = true
                widget.request("save", {local_url:widget.connection.local_url,mode:"local",token:"dummy-test-token"})
                suite.stage = 7
            } else if (suite.stage === 7 && widget.connected) {
                widget.close()
                console.log("CONNECTION CHECKS PASSED")
                Qt.quit()
            }
        }
    }
}
''')
            for name in ('runtime', 'config', 'cache'):
                (root / name).mkdir(mode=0o700)
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic', XDG_RUNTIME_DIR=str(root / 'runtime'), XDG_CONFIG_HOME=str(root / 'config'), XDG_CACHE_HOME=str(root / 'cache'))
            environment.pop('WAYLAND_DISPLAY', None)
            result = subprocess.run(['quickshell', '-p', str(root), '--no-color'], env=environment, text=True, capture_output=True, timeout=20)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn('CONNECTION CHECKS PASSED', output)
            for marker in ('ASSERTION FAILED', 'ReferenceError', 'TypeError', 'ERROR scene:'):
                self.assertNotIn(marker, output)
            requests = [json.loads(line)['command'] for line in (root / 'requests.jsonl').read_text().splitlines()]
            self.assertEqual(requests, ['config', 'config', 'states', 'config', 'states', 'config', 'save', 'states'])
