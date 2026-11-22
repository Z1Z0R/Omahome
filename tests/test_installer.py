import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='omahome-install-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        shutil.copytree(Path(__file__).resolve().parents[1], self.source, ignore=shutil.ignore_patterns('__pycache__'))
        self.config = self.root / 'config'
        self.installed = self.config / 'omarchy/plugins/zizor.omahome'
        self.installed.parent.mkdir(parents=True)
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        self.script('omarchy', '''#!/usr/bin/env python3
import json, os, pathlib, sys
if sys.argv[1:3] == ['plugin', 'validate']:
    directory = pathlib.Path(sys.argv[3])
    if os.environ.get('TEST_FAIL_VALIDATE') and directory.name.startswith('.omahome-install.'):
        sys.exit(75)
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['id'] == 'zizor.omahome'
    assert all((directory / path).is_file() for path in manifest['entryPoints'].values())
    assert (directory / 'HomeAssistantIcon.qml').is_file()
    assert (directory / 'assets/NOTICE-home-assistant.md').is_file()
''')
        self.script('omarchy-shell', '#!/bin/bash\nexit 0\n')
        self.script('cp', '''#!/bin/bash
for arg in "$@"; do
  if [[ ${TEST_FAIL_COPY:-} == 1 && $arg == "$TEST_SOURCE/bin/bridge.py" ]]; then exit 73; fi
done
exec /usr/bin/cp "$@"
''')
        self.script('mv', '''#!/bin/bash
for arg in "$@"; do
  if [[ $arg == *"/.omahome-install."* ]]; then
    if [[ ${TEST_SIGNAL_ACTIVATE:-} == 1 ]]; then kill -TERM "$PPID"; exit 143; fi
    if [[ ${TEST_FAIL_ACTIVATE:-} == 1 ]]; then exit 74; fi
  fi
  if [[ $arg == *"/plugin-backups/omahome-"* && ${TEST_FAIL_RESTORE:-} == 1 && ${TEST_FAIL_ACTIVATE:-} == 1 ]]; then
    # This also matches the first rename's destination: allow the initial
    # backup move, and fail only when the destination is the live plugin.
    if [[ ${!#} == "$TEST_INSTALLED" ]]; then exit 76; fi
  fi
done
exec /usr/bin/mv "$@"
''')
        self.env = dict(os.environ, PATH=str(self.commands) + ':' + os.environ['PATH'], XDG_CONFIG_HOME=str(self.config), TEST_SOURCE=str(self.source), TEST_INSTALLED=str(self.installed))
        connection = self.config / 'omahome/connection.json'
        connection.parent.mkdir()
        connection.write_text('private-test-marker')

    def script(self, name, text):
        path = self.commands / name
        path.write_text(text)
        path.chmod(0o755)

    def old_install(self):
        shutil.copytree(self.source, self.installed)
        (self.installed / 'old-version.txt').write_text('old')
        # Give the proposed package a distinguishable but valid source change.
        for path in self.source.glob('*.qml'):
            path.write_bytes(path.read_bytes() + b'\n// NEW UPDATE VERSION\n')
        return self.snapshot(self.installed)

    def snapshot(self, directory):
        return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}

    def run_install(self, update=True, **flags):
        command = ['bash', str(self.source / 'install.sh')] + (['--update'] if update else [])
        return subprocess.run(command, env=dict(self.env, **flags), capture_output=True, text=True, timeout=15)

    def assert_connection_untouched(self):
        self.assertEqual((self.config / 'omahome/connection.json').read_text(), 'private-test-marker')
        self.assertEqual(list((self.config / 'omarchy').glob('.omahome-install.*')), [])

    def test_fresh_install_includes_logo_and_all_components(self):
        result = self.run_install(update=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in self.source.glob('*.qml'):
            self.assertEqual((self.installed / path.name).read_bytes(), path.read_bytes())
        self.assertTrue((self.installed / 'assets/NOTICE-home-assistant.md').exists())
        self.assertEqual((self.installed / 'docs/images/panel-example-clean-logo.png').read_bytes(), (self.source / 'docs/images/panel-example-clean-logo.png').read_bytes())
        self.assert_connection_untouched()

    def test_successful_update_keeps_complete_old_backup(self):
        before = self.old_install()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.config / 'omarchy/plugin-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.snapshot(backups[0]), before)
        self.assertFalse((self.installed / 'old-version.txt').exists())
        for path in self.source.glob('*.qml'):
            self.assertEqual((self.installed / path.name).read_bytes(), path.read_bytes())
        self.assert_connection_untouched()

    def test_copy_failure_leaves_live_install_identical(self):
        before = self.old_install()
        result = self.run_install(TEST_FAIL_COPY='1')
        self.assertEqual(result.returncode, 73)
        self.assertEqual(self.snapshot(self.installed), before)
        self.assert_connection_untouched()

    def test_validation_failure_leaves_live_install_identical(self):
        before = self.old_install()
        result = self.run_install(TEST_FAIL_VALIDATE='1')
        self.assertEqual(result.returncode, 75)
        self.assertEqual(self.snapshot(self.installed), before)
        self.assert_connection_untouched()

    def test_activation_failure_restores_complete_old_version(self):
        before = self.old_install()
        result = self.run_install(TEST_FAIL_ACTIVATE='1')
        self.assertEqual(result.returncode, 74)
        self.assertIn('restored automatically', result.stderr)
        self.assertEqual(self.snapshot(self.installed), before)
        self.assert_connection_untouched()

    def test_termination_during_activation_restores_old_version(self):
        before = self.old_install()
        result = self.run_install(TEST_SIGNAL_ACTIVATE='1')
        self.assertEqual(result.returncode, 143)
        self.assertEqual(self.snapshot(self.installed), before)
        self.assert_connection_untouched()

    def test_restore_failure_preserves_backup_and_reports_recovery_path(self):
        before = self.old_install()
        result = self.run_install(TEST_FAIL_ACTIVATE='1', TEST_FAIL_RESTORE='1')
        self.assertEqual(result.returncode, 74)
        self.assertIn('Automatic restore failed', result.stderr)
        backups = list((self.config / 'omarchy/plugin-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.snapshot(backups[0]), before)
        self.assert_connection_untouched()


if __name__ == '__main__':
    unittest.main()
