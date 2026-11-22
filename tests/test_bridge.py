import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).resolve().parents[1] / 'bin/bridge.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def entity(domain='light', **attrs):
    return {'entity_id': domain + '.desk', 'state': 'on', 'attributes': {'friendly_name': 'Desk', **attrs}}


class FakeClient:
    def __init__(self, state):
        self.state, self.calls = state, []

    def request(self, path, data=None):
        self.calls.append((path, data))
        return self.state if data is None else []


class BridgeTests(unittest.TestCase):
    def test_unknown_scene_can_activate_without_prior_history(self):
        scene = entity('scene')
        scene['state'] = 'unknown'
        self.assertTrue(b.normalize(scene)['available'])
        client = FakeClient(scene)
        b.control(client, {'entity': 'scene.desk', 'action': 'activate'})
        self.assertEqual(client.calls[-1], ('services/scene/turn_on', {'entity_id': 'scene.desk'}))

    def test_unavailable_scene_and_unknown_devices_still_reject_commands(self):
        for domain, state, action in [('scene', 'unavailable', 'activate'), ('light', 'unknown', 'turn_on'), ('switch', 'unknown', 'turn_off'), ('automation', 'unknown', 'automation_run')]:
            current = entity(domain)
            current['state'] = state
            client = FakeClient(current)
            self.assertFalse(b.normalize(current)['available'])
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': domain + '.desk', 'action': action})
            self.assertEqual(client.calls, [('states/' + domain + '.desk', None)])

    def test_child_lock_identification_and_config_visibility(self):
        for label in ('Desk plug child lock', 'Desk plug ChildLock', 'Desk plug child-lock', 'Desk plug kids lock'):
            state = entity('switch', friendly_name=label, entity_category='config')
            self.assertTrue(b.include_entity(state))
            item = b.normalize(state)
            self.assertEqual((item['kind'], item['type_label'], item['category']), ('child_lock', 'Child lock', 'Plugs'))
        state = entity('input_boolean', friendly_name='Purifier child lock')
        self.assertEqual(b.normalize(state)['kind'], 'child_lock')
        state = entity('switch', friendly_name='Power', model='Plug with child lock')
        self.assertEqual(b.normalize(state)['kind'], 'outlet')
        self.assertFalse(b.include_entity(entity('switch', friendly_name='LED indicator', entity_category='config')))

    def test_child_lock_stays_after_parent_and_uses_own_entity(self):
        power = {'entity_id': 'switch.desk_plug', 'state': 'off', 'attributes': {'friendly_name': 'Z desk plug', 'device_class': 'outlet'}}
        lock = {'entity_id': 'switch.desk_plug_child_lock', 'state': 'on', 'attributes': {'friendly_name': 'A child lock', 'entity_category': 'config'}}
        metadata = {s['entity_id']: {'device_id': 'desk', 'device_name': 'Desk plug'} for s in (power, lock)}
        items = b.normalize_entities([lock, power], {}, metadata)
        self.assertEqual([item['id'] for item in items], [power['entity_id'], lock['entity_id']])
        self.assertTrue(all(item['category'] == 'Plugs' for item in items))
        self.assertEqual(items[1]['type_label'], 'Child lock')
        client = FakeClient(lock)
        b.control(client, {'entity': lock['entity_id'], 'action': 'turn_off'})
        self.assertEqual(client.calls[-1], ('services/switch/turn_off', {'entity_id': lock['entity_id']}))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_config_private_and_token_never_in_public_settings(self):
        settings = b.save_config({'local_url': 'http://192.168.1.20:8123', 'token': 'secret-token'})
        self.assertNotIn('secret-token', json.dumps(settings))
        self.assertTrue(settings['has_token'])
        self.assertEqual(stat.S_IMODE(b.config_path().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(b.config_path().parent.stat().st_mode), 0o700)
        b.save_config({'local_url': 'http://192.168.1.20:8123', 'token': ''})
        self.assertEqual(b.load_config()['token'], 'secret-token')

    def test_config_missing_is_setup_state(self):
        self.assertFalse(b.public_config(b.load_config())['has_token'])

    def test_config_world_readable_rejected(self):
        b.save_config({'local_url': 'http://localhost:8123', 'token': 'secret'})
        b.config_path().chmod(0o644)
        with self.assertRaises(b.UserError):
            b.load_config()

    def test_config_symlink_rejected(self):
        b.config_path().parent.mkdir()
        target = Path(self.tmp.name) / 'outside'
        target.write_text('{}')
        b.config_path().symlink_to(target)
        with self.assertRaises(OSError):
            b.load_config()

    def test_bad_urls(self):
        for value in ['http://example.com', 'http://100.64.0.1', 'file:///etc/passwd', 'https://u:secret@example.com', 'https://example.com/?token=x', 'https://example.com/path', 'https://example.com/#secret', 'https://example.com:abc', 'https://exa\nmple.com']:
            with self.subTest(value=value), self.assertRaises((b.UserError, ValueError)):
                b.url(value)

    def test_local_addresses(self):
        for value in ['http://homeassistant.local:8123', 'http://10.0.0.2:8123', 'http://172.16.1.3:8123', 'http://192.168.1.3:8123', 'http://[::1]:8123', 'http://[fd00::1]:8123']:
            self.assertEqual(b.url(value), value)

    def test_remote_requires_https(self):
        with self.assertRaises(b.UserError):
            b.url('http://192.168.1.2:8123', remote=True)
        self.assertEqual(b.url('https://home.example.com', True), 'https://home.example.com')

    def test_brightness_and_zero(self):
        for value in [0, 47, 100]:
            client = FakeClient(entity(supported_color_modes=['brightness']))
            b.control(client, {'entity': 'light.desk', 'action': 'brightness', 'value': value})
            self.assertEqual(client.calls[-1], ('services/light/turn_on', {'entity_id': 'light.desk', 'brightness_pct': value}))

    def test_temperature_bounds(self):
        client = FakeClient(entity(supported_color_modes=['color_temp'], min_color_temp_kelvin=2200, max_color_temp_kelvin=5000))
        b.control(client, {'entity': 'light.desk', 'action': 'temperature', 'value': 2800})
        self.assertEqual(client.calls[-1][1]['color_temp_kelvin'], 2800)
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'light.desk', 'action': 'temperature', 'value': 6000})

    def test_rgb_and_convertible_color_modes(self):
        for mode in ['rgb', 'rgbw', 'rgbww', 'hs', 'xy']:
            client = FakeClient(entity(supported_color_modes=[mode]))
            b.control(client, {'entity': 'light.desk', 'action': 'rgb', 'value': [10, 20, 255]})
            self.assertEqual(client.calls[-1][1]['rgb_color'], [10, 20, 255])

    def test_rgb_is_only_offered_for_color_capable_lights(self):
        for mode in ['rgb', 'rgbw', 'rgbww', 'hs', 'xy']:
            state = entity(supported_color_modes=[mode], rgb_color=[25, 50, 75])
            state['state'] = 'off'
            item = b.normalize(state)
            self.assertTrue(item['caps']['rgb'])
            self.assertEqual(item['rgb'], [25, 50, 75])
        for modes in (None, [], ['onoff'], ['brightness'], ['color_temp']):
            client = FakeClient(entity(supported_color_modes=modes))
            self.assertFalse(b.normalize(client.state)['caps']['rgb'])
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': 'light.desk', 'action': 'rgb', 'value': [25, 50, 75]})
            self.assertEqual(len(client.calls), 1)

    def test_automations_have_own_category_and_explicit_service_options(self):
        state = entity('automation', friendly_name='Evening lights')
        self.assertTrue(b.include_entity(state))
        item = b.normalize_entities([state], {})[0]
        self.assertEqual((item['kind'], item['category']), ('automation', 'Automations'))
        for action, service, options in [('turn_on', 'turn_on', {}), ('turn_off', 'turn_off', {'stop_actions': False}), ('automation_run', 'trigger', {'skip_condition': False})]:
            state['state'] = 'off'
            client = FakeClient(state)
            b.control(client, {'entity': 'automation.desk', 'action': action})
            self.assertEqual(client.calls[-1], ('services/automation/' + service, {'entity_id': 'automation.desk', **options}))

    def test_automation_run_requires_available_automation(self):
        for domain, value in [('automation', 'unavailable'), ('automation', 'unknown'), ('light', 'on'), ('scene', 'on')]:
            state = entity(domain)
            state['state'] = value
            client = FakeClient(state)
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': domain + '.desk', 'action': 'automation_run'})
            self.assertEqual(len(client.calls), 1)

    def test_automations_do_not_merge_with_related_physical_devices(self):
        states = [entity('light'), entity('automation')]
        metadata = {s['entity_id']: {'device_id': 'desk', 'device_name': 'Desk'} for s in states}
        items = b.normalize_entities(states, {}, metadata)
        self.assertEqual([item['category'] for item in items], ['Lights', 'Automations'])
        self.assertNotEqual(items[0]['group_id'], items[1]['group_id'])

    def test_invalid_rgb(self):
        for value in [[0, 0, 256], [1, 2], 'red', [0, 0, True]]:
            with self.assertRaises(b.UserError):
                b.control(FakeClient(entity(supported_color_modes=['rgb'])), {'entity': 'light.desk', 'action': 'rgb', 'value': value})

    def test_volume_percentage_conversion(self):
        client = FakeClient(entity('media_player', supported_features=4))
        b.control(client, {'entity': 'media_player.desk', 'action': 'volume', 'value': 35})
        self.assertEqual(client.calls[-1], ('services/media_player/volume_set', {'entity_id': 'media_player.desk', 'volume_level': 0.35}))

    def test_mute(self):
        client = FakeClient(entity('media_player', supported_features=8))
        b.control(client, {'entity': 'media_player.desk', 'action': 'mute', 'value': True})
        self.assertEqual(client.calls[-1][1]['is_volume_muted'], True)

    def test_unsupported_control_never_posts(self):
        client = FakeClient(entity(supported_color_modes=['onoff']))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'light.desk', 'action': 'brightness', 'value': 50})
        self.assertEqual(len(client.calls), 1)

    def test_unavailable_never_posts(self):
        state = entity(supported_color_modes=['rgb'])
        state['state'] = 'unavailable'
        client = FakeClient(state)
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'light.desk', 'action': 'turn_on'})
        self.assertEqual(len(client.calls), 1)

    def test_invalid_values_and_entity_path(self):
        for value in [-1, 101, True, float('nan'), float('inf'), '50']:
            with self.assertRaises(b.UserError):
                b.number(value, 0, 100)
        with self.assertRaises(b.UserError):
            b.control(FakeClient(entity()), {'entity': '../config', 'action': 'turn_on'})

    def test_fan_cover_switch_and_scene(self):
        self.assertFalse(b.normalize(entity('fan', supported_features=1))['caps']['turn_on'])
        self.assertTrue(b.normalize(entity('fan', supported_features=32))['caps']['turn_on'])
        self.assertTrue(b.normalize(entity('fan', supported_features=16))['caps']['turn_off'])
        for domain, action, feature, service, extra in [('fan', 'fan_speed', 1, 'set_percentage', {'percentage': 25}), ('cover', 'cover_stop', 8, 'stop_cover', {}), ('switch', 'turn_off', 0, 'turn_off', {}), ('scene', 'activate', 0, 'turn_on', {})]:
            client = FakeClient(entity(domain, supported_features=feature))
            b.control(client, {'entity': domain + '.desk', 'action': action, 'value': 25})
            self.assertEqual(client.calls[-1], ('services/' + domain + '/' + service, {'entity_id': domain + '.desk', **extra}))

    def test_bearer_and_json_transport(self):
        client = b.Client({'local_url': 'http://localhost:8123', 'token': 'secret'})
        class Response(io.BytesIO):
            pass
        with patch.object(client.opener, 'open', return_value=Response(b'[]')) as transport:
            client.request('services/light/turn_on', {'entity_id': 'light.desk', 'brightness_pct': 42})
            request = transport.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer secret')
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(json.loads(request.data)['brightness_pct'], 42)
            self.assertNotIn('secret', request.full_url)

    def test_error_responses_do_not_expose_token_or_body(self):
        for code in [400, 401, 403, 404, 500]:
            client = b.Client({'local_url': 'http://localhost:8123', 'token': 'secret'})
            error = urllib.error.HTTPError('http://localhost', code, 'secret', {}, io.BytesIO(b'secret'))
            with patch.object(client.opener, 'open', side_effect=error), self.assertRaises(b.UserError) as caught:
                client.request('states')
            self.assertNotIn('secret', str(caught.exception))

    def test_explicit_user_agent_on_reads_and_writes(self):
        client = b.Client({'local_url': 'http://localhost:8123', 'token': 'secret'})
        for path, data in [('states', None), ('services/light/turn_on', {'entity_id': 'light.desk'})]:
            with patch.object(client.opener, 'open', return_value=io.BytesIO(b'[]')) as transport:
                client.request(path, data)
                request = transport.call_args.args[0]
                self.assertEqual(request.get_header('User-agent'), 'Omahome/1.0.0')
                self.assertEqual(request.get_header('Accept'), 'application/json')
                self.assertEqual(request.get_header('Authorization'), 'Bearer secret')

    def test_redirects_never_forward_bearer(self):
        with self.assertRaises(b.UserError):
            b.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.example')

    def test_timeout_does_not_retry(self):
        client = b.Client({'local_url': 'http://localhost:8123', 'token': 'secret'})
        with patch.object(client.opener, 'open', side_effect=TimeoutError) as transport, self.assertRaises(b.UserError):
            client.request('services/light/turn_on', {'entity_id': 'light.desk'})
        self.assertEqual(transport.call_count, 1)

    def test_remote_dashboard_uses_remote_url(self):
        b.save_config({'local_url': 'http://localhost:8123', 'remote_url': 'https://ha.example.com', 'token': 'secret'})
        self.assertEqual(b.dispatch({'command': 'dashboard', 'values': {'mode': 'remote'}}), {'url': 'https://ha.example.com'})

    def test_filters_diagnostics_and_astronomy(self):
        for entity_id, attrs in [
            ('sensor.sun_elevation', {}),
            ('sensor.sun_next_rising', {'device_class': 'timestamp'}),
            ('sensor.govee_signal', {'device_class': 'signal_strength', 'unit_of_measurement': 'dBm'}),
            ('sensor.govee_battery', {'device_class': 'battery', 'unit_of_measurement': '%'}),
            ('sensor.cpu_temperature', {'device_class': 'temperature', 'entity_category': 'diagnostic'}),
            ('sensor.govee_signal_percent', {'unit_of_measurement': '%'}),
            ('binary_sensor.bluetooth_connected', {'device_class': 'connectivity'}),
        ]:
            with self.subTest(entity=entity_id):
                self.assertFalse(b.include_entity({'entity_id': entity_id, 'state': '1', 'attributes': attrs}))

    def test_govee_temperature_humidity_and_custom_integration_fallbacks(self):
        for kind, unit in [('temperature', '°C'), ('temperature', '°F'), ('humidity', '%')]:
            state = entity('sensor', device_class=kind, unit_of_measurement=unit)
            state['state'] = '22.7' if kind == 'temperature' else '48'
            self.assertTrue(b.include_entity(state))
            reading = b.normalize(state)
            self.assertEqual(reading['sensor_kind'], kind)
            self.assertEqual(reading['state'], state['state'])
            self.assertEqual(reading['unit'], unit)
        state = entity('sensor', friendly_name='Govee H5179 humidity', unit_of_measurement='%')
        self.assertEqual(b.sensor_kind(state), 'humidity')
        self.assertEqual(b.sensor_kind(entity('sensor', unit_of_measurement='°C')), 'temperature')
        self.assertTrue(b.include_entity(entity('binary_sensor', device_class='motion')))
        readings = b.normalize_entities([entity('sensor', device_class='humidity')], {})
        self.assertEqual(readings[0]['unit'], '%')

    def test_states_dispatch_filters_telemetry_and_reads_unit_system(self):
        config = {'mode': 'remote', 'remote_url': 'https://ha.example.com', 'token': 'secret'}
        sensor = entity('sensor', device_class='temperature', unit_of_measurement='°C')
        sensor['entity_id'] = 'sensor.govee_temperature'
        climate = entity('climate', supported_features=1, temperature=72)
        diagnostic = entity('sensor', device_class='signal_strength', unit_of_measurement='dBm')
        class ReadClient:
            def request(self, path, data=None):
                if path == 'template':
                    return []
                if path == 'states':
                    return [sensor, climate, diagnostic]
                if path == 'config':
                    return {'unit_system': {'temperature': '°F'}}
                raise AssertionError(path)
        with patch.object(b, 'load_config', return_value=config), patch.object(b, 'Client', return_value=ReadClient()):
            result = b.dispatch({'command': 'states'})
        self.assertEqual(len(result['devices']), 2)
        self.assertEqual(result['mode'], 'remote')
        self.assertEqual(result['devices'][0]['temperature_unit'], '°F')
        self.assertEqual(result['devices'][1]['sensor_kind'], 'temperature')

    def test_climate_uses_home_assistant_temperature_unit(self):
        state = entity('climate', supported_features=1, temperature=71.5, min_temp=45, max_temp=90)
        devices = b.normalize_entities([state], {'unit_system': {'temperature': '°F'}})
        self.assertEqual(devices[0]['temperature_unit'], '°F')
        self.assertEqual(devices[0]['target_temperature'], 71.5)
        self.assertEqual(devices[0]['min_target_temperature'], 45)

    def test_thermostat_decimal_target_and_bounds(self):
        client = FakeClient(entity('climate', supported_features=1, min_temp=10, max_temp=30, target_temp_step=0.5))
        b.control(client, {'entity': 'climate.desk', 'action': 'target_temperature', 'value': 21.5})
        self.assertEqual(client.calls[-1], ('services/climate/set_temperature', {'entity_id': 'climate.desk', 'temperature': 21.5}))
        for value in [9, 31, float('nan')]:
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': 'climate.desk', 'action': 'target_temperature', 'value': value})

    def test_hvac_modes_are_explicit_and_supported(self):
        client = FakeClient(entity('climate', hvac_modes=['off', 'heat', 'cool', 'auto']))
        for mode in ['off', 'heat', 'cool', 'auto']:
            b.control(client, {'entity': 'climate.desk', 'action': 'hvac_mode', 'value': mode})
            self.assertEqual(client.calls[-1], ('services/climate/set_hvac_mode', {'entity_id': 'climate.desk', 'hvac_mode': mode}))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'climate.desk', 'action': 'hvac_mode', 'value': 'unsupported'})

    def test_heat_cool_range_preserves_other_live_limit(self):
        state = entity('climate', supported_features=3, min_temp=10, max_temp=30, target_temp_low=19, target_temp_high=25)
        state['state'] = 'heat_cool'
        client = FakeClient(state)
        b.control(client, {'entity': 'climate.desk', 'action': 'target_low', 'value': 20.5})
        self.assertEqual(client.calls[-1], ('services/climate/set_temperature', {'entity_id': 'climate.desk', 'target_temp_low': 20.5, 'target_temp_high': 25}))
        state['attributes']['target_temp_low'] = 21
        b.control(client, {'entity': 'climate.desk', 'action': 'target_high', 'value': 24})
        self.assertEqual(client.calls[-1][1]['target_temp_low'], 21)
        for action, value in [('target_low', 26), ('target_high', 18), ('target_temperature', 22)]:
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': 'climate.desk', 'action': action, 'value': value})

    def test_range_edit_rejected_when_other_limit_is_missing(self):
        state = entity('climate', supported_features=2, target_temp_low=None, target_temp_high=25)
        state['state'] = 'heat_cool'
        client = FakeClient(state)
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'climate.desk', 'action': 'target_high', 'value': 24})
        self.assertEqual(len(client.calls), 1)

    def test_humidifiers_and_dehumidifiers(self):
        for kind in ['humidifier', 'dehumidifier']:
            client = FakeClient(entity('humidifier', device_class=kind, humidity=45, min_humidity=30, max_humidity=70, current_humidity=55))
            self.assertTrue(b.include_entity(client.state))
            b.control(client, {'entity': 'humidifier.desk', 'action': 'target_humidity', 'value': 50})
            self.assertEqual(client.calls[-1], ('services/humidifier/set_humidity', {'entity_id': 'humidifier.desk', 'humidity': 50}))
            for action in ['turn_on', 'turn_off']:
                b.control(client, {'entity': 'humidifier.desk', 'action': action})
                self.assertEqual(client.calls[-1][0], 'services/humidifier/' + action)
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': 'humidifier.desk', 'action': 'target_humidity', 'value': 20})

    def test_climate_humidity_and_supported_modes(self):
        client = FakeClient(entity('climate', supported_features=28, min_humidity=20, max_humidity=70, fan_modes=['auto', 'low'], preset_modes=['eco', 'comfort']))
        for action, value, service, field in [('target_humidity', 45, 'set_humidity', 'humidity'), ('fan_mode', 'low', 'set_fan_mode', 'fan_mode'), ('preset_mode', 'eco', 'set_preset_mode', 'preset_mode')]:
            b.control(client, {'entity': 'climate.desk', 'action': action, 'value': value})
            self.assertEqual(client.calls[-1], ('services/climate/' + service, {'entity_id': 'climate.desk', field: value}))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'climate.desk', 'action': 'fan_mode', 'value': 'turbo'})
        unsupported = FakeClient(entity('climate', supported_features=1))
        with self.assertRaises(b.UserError):
            b.control(unsupported, {'entity': 'climate.desk', 'action': 'target_humidity', 'value': 45})

    def test_dehumidifier_mode_and_smart_plug_power(self):
        client = FakeClient(entity('humidifier', supported_features=1, device_class='dehumidifier', available_modes=['auto', 'dry']))
        b.control(client, {'entity': 'humidifier.desk', 'action': 'humidity_mode', 'value': 'dry'})
        self.assertEqual(client.calls[-1], ('services/humidifier/set_mode', {'entity_id': 'humidifier.desk', 'mode': 'dry'}))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'humidifier.desk', 'action': 'humidity_mode', 'value': 'unknown'})
        plug = FakeClient(entity('switch', device_class='outlet'))
        for action in ['turn_on', 'turn_off']:
            b.control(plug, {'entity': 'switch.desk', 'action': action})
            self.assertEqual(plug.calls[-1], ('services/switch/' + action, {'entity_id': 'switch.desk'}))

    def test_climate_power_flags_do_not_guess_heating_mode(self):
        state = entity('climate', supported_features=384, hvac_modes=['off', 'heat', 'cool'])
        client = FakeClient(state)
        for action in ['turn_on', 'turn_off']:
            b.control(client, {'entity': 'climate.desk', 'action': action})
            self.assertEqual(client.calls[-1][0], 'services/climate/' + action)
        state['attributes']['supported_features'] = 0
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'climate.desk', 'action': 'turn_on'})

    def test_core_300s_and_other_purifiers_are_air_care(self):
        for name in ['Levoit CORE 300S', 'Levoit Core300S', 'core_300s', 'Core 400S', 'Vital 200S', 'EverestAir', 'LAP-C301S-WUS', 'LV-PUR131S']:
            with self.subTest(name=name):
                item = b.normalize(entity('fan', friendly_name=name, supported_features=57, preset_modes=['auto', 'sleep']))
                self.assertEqual(item['kind'], 'air_purifier')
                self.assertEqual(item['type_label'], 'Air purifier')
                self.assertEqual(item['category'], 'Air care')
        renamed = entity('fan', friendly_name='Bedroom', icon='mdi:air-purifier')
        self.assertEqual(b.normalize(renamed)['kind'], 'air_purifier')

    def test_tower_fans_are_not_misidentified_as_air_purifiers(self):
        item = b.normalize(entity('fan', friendly_name='Levoit Smart Tower Fan', model='LTF-F422S-WUS'))
        self.assertEqual(item['kind'], 'fan')
        self.assertEqual(item['category'], 'Fans')
        self.assertEqual(b.normalize(entity('humidifier', friendly_name='Levoit humidifier'))['kind'], 'humidifier')

    def test_categories_cover_each_supported_domain(self):
        cases = [('light', {}, 'Lights'), ('switch', {'device_class': 'outlet'}, 'Plugs'), ('switch', {}, 'Switches'), ('input_boolean', {}, 'Switches'), ('climate', {}, 'Climate'), ('humidifier', {}, 'Air care'), ('media_player', {}, 'Audio'), ('cover', {}, 'Covers'), ('scene', {}, 'Scenes'), ('sensor', {'device_class': 'temperature'}, 'Sensors'), ('binary_sensor', {'device_class': 'motion'}, 'Sensors')]
        for domain, attrs, category in cases:
            with self.subTest(domain=domain):
                self.assertEqual(b.normalize(entity(domain, **attrs))['category'], category)

    def test_purifier_presets_preserve_advertised_values(self):
        client = FakeClient(entity('fan', friendly_name='Levoit Core 300S', supported_features=57, preset_modes=['auto', 'sleep', 'normal'], preset_mode='auto'))
        for preset in ['auto', 'sleep', 'normal']:
            b.control(client, {'entity': 'fan.desk', 'action': 'preset_mode', 'value': preset})
            self.assertEqual(client.calls[-1], ('services/fan/set_preset_mode', {'entity_id': 'fan.desk', 'preset_mode': preset}))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'fan.desk', 'action': 'preset_mode', 'value': 'turbo'})
        client.state['attributes']['supported_features'] = 49
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'fan.desk', 'action': 'preset_mode', 'value': 'auto'})

    def test_fan_oscillation_and_direction(self):
        client = FakeClient(entity('fan', supported_features=6))
        b.control(client, {'entity': 'fan.desk', 'action': 'oscillate', 'value': True})
        self.assertEqual(client.calls[-1], ('services/fan/oscillate', {'entity_id': 'fan.desk', 'oscillating': True}))
        b.control(client, {'entity': 'fan.desk', 'action': 'direction', 'value': 'reverse'})
        self.assertEqual(client.calls[-1], ('services/fan/set_direction', {'entity_id': 'fan.desk', 'direction': 'reverse'}))
        for action, value in [('direction', 'sideways'), ('oscillate', 'yes')]:
            with self.assertRaises(b.UserError):
                b.control(client, {'entity': 'fan.desk', 'action': action, 'value': value})
        client.state['attributes']['supported_features'] = 0
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'fan.desk', 'action': 'oscillate', 'value': True})

    def test_aircare_auxiliary_controls_are_targeted(self):
        cases = [('select', {'friendly_name': 'Levoit Core 300S night light level', 'options': ['off', 'dim', 'on']}, True), ('number', {'friendly_name': 'Levoit humidifier mist level', 'min': 1, 'max': 9}, True), ('switch', {'friendly_name': 'Core 300S display', 'entity_category': 'config'}, True), ('select', {'friendly_name': 'Recorder retention mode', 'options': ['all', 'none']}, False), ('number', {'friendly_name': 'Diagnostic retry count'}, False), ('sensor', {'friendly_name': 'Core 300S signal', 'device_class': 'signal_strength'}, False)]
        for domain, attrs, included in cases:
            with self.subTest(domain=domain, attrs=attrs):
                item = entity(domain, **attrs)
                self.assertEqual(b.include_entity(item), included)
                if included:
                    self.assertEqual(b.normalize(item)['category'], 'Air care')

    def test_aircare_select_and_mist_level_payloads(self):
        client = FakeClient(entity('select', friendly_name='Levoit night light', options=['off', 'dim', 'on']))
        b.control(client, {'entity': 'select.desk', 'action': 'select_option', 'value': 'dim'})
        self.assertEqual(client.calls[-1], ('services/select/select_option', {'entity_id': 'select.desk', 'option': 'dim'}))
        with self.assertRaises(b.UserError):
            b.control(client, {'entity': 'select.desk', 'action': 'select_option', 'value': 'bright'})
        level = FakeClient(entity('number', friendly_name='Levoit mist level', min=1, max=9, step=2))
        b.control(level, {'entity': 'number.desk', 'action': 'number_value', 'value': 5})
        self.assertEqual(level.calls[-1], ('services/number/set_value', {'entity_id': 'number.desk', 'value': 5}))
        for value in [0, 10, 4, float('nan')]:
            with self.assertRaises(b.UserError):
                b.control(level, {'entity': 'number.desk', 'action': 'number_value', 'value': value})

    def test_air_quality_and_filter_life_without_signal_clutter(self):
        for kind in ['aqi', 'pm1', 'pm25', 'pm10', 'carbon_dioxide']:
            state = entity('sensor', device_class=kind, unit_of_measurement='µg/m³')
            self.assertTrue(b.include_entity(state))
            item = b.normalize(state)
            self.assertEqual(item['category'], 'Air care')
            self.assertEqual(item['sensor_kind'], kind)
        state = entity('sensor', friendly_name='Levoit Core 300S filter life', entity_category='diagnostic')
        self.assertTrue(b.include_entity(state))
        item = b.normalize_entities([state], {})[0]
        self.assertEqual(item['unit'], '%')
        self.assertEqual(item['type_label'], 'Filter life')
        self.assertFalse(b.include_entity(entity('sensor', friendly_name='Levoit Core 300S RSSI', device_class='signal_strength')))

    def test_device_groups_keep_two_purifiers_contiguous(self):
        states, metadata = [], {}
        for suffix, name in [('bedroom', 'Bedroom purifier'), ('living_room', 'Living room purifier')]:
            entries = [('fan', '', {'supported_features': 57, 'preset_modes': ['auto', 'sleep']}), ('switch', '_display', {}), ('sensor', '_filter_life', {'unit_of_measurement': '%'})]
            for domain, ending, attrs in entries:
                item = {'entity_id': domain + '.' + suffix + ending, 'state': 'on' if domain != 'sensor' else '80', 'attributes': {'friendly_name': name + ending.replace('_', ' '), **attrs}}
                states.append(item)
                metadata[item['entity_id']] = {'device_id': suffix, 'device_name': name, 'model': 'Core300S', 'manufacturer': 'Levoit'}
        result = b.normalize_entities(list(reversed(states)), {}, metadata)
        ids = [item['group_id'] for item in result]
        self.assertEqual(ids, ['device:bedroom'] * 3 + ['device:living_room'] * 3)
        for offset in (0, 3):
            self.assertEqual([item['domain'] for item in result[offset:offset + 3]], ['fan', 'switch', 'sensor'])
            self.assertTrue(all(item['group_size'] == 3 for item in result[offset:offset + 3]))
            self.assertEqual(result[offset]['kind'], 'air_purifier')

    def test_same_name_different_registry_devices_never_merge(self):
        states = [{'entity_id': 'fan.purifier_' + str(i), 'state': 'on', 'attributes': {'friendly_name': 'Core 300S'}} for i in [1, 2]]
        metadata = {s['entity_id']: {'device_id': str(i), 'device_name': 'Core 300S', 'model': 'Core300S'} for i, s in enumerate(states)}
        result = b.normalize_entities(states, {}, metadata)
        self.assertNotEqual(result[0]['group_id'], result[1]['group_id'])
        self.assertEqual([item['group_size'] for item in result], [1, 1])

    def test_fan_related_controls_stay_in_fans(self):
        states = [entity('fan', friendly_name='Levoit Tower Fan'), entity('switch', friendly_name='Levoit Tower Fan display'), entity('sensor', friendly_name='Levoit Tower Fan temperature', device_class='temperature', unit_of_measurement='°C')]
        metadata = {s['entity_id']: {'device_id': 'tower', 'device_name': 'Bedroom fan', 'model': 'LTF-F422S-WUS', 'manufacturer': 'Levoit'} for s in states}
        result = b.normalize_entities(states, {}, metadata)
        self.assertEqual([item['domain'] for item in result], ['fan', 'switch', 'sensor'])
        self.assertTrue(all(item['category'] == 'Fans' for item in result))
        self.assertEqual(result[0]['type_label'], 'Fan')
        self.assertEqual(result[1]['type_label'], 'Fan setting')
        self.assertEqual(b.normalize(entity('humidifier'))['category'], 'Air care')
        self.assertEqual(b.normalize(entity('humidifier', device_class='dehumidifier'))['category'], 'Air care')

    def test_grouping_without_registry_uses_device_prefix(self):
        states = []
        for name in ['bedroom_core_300s', 'living_room_core_300s']:
            for domain, suffix, attrs in [('fan', '', {}), ('switch', '_display', {}), ('sensor', '_pm2_5', {'device_class': 'pm25'})]:
                states.append({'entity_id': domain + '.' + name + suffix, 'state': 'on', 'attributes': {'friendly_name': name.replace('_', ' ') + suffix.replace('_', ' '), **attrs}})
        result = b.normalize_entities(states[::2] + states[1::2], {})
        self.assertEqual([item['group_id'] for item in result], ['name:bedroom_core_300s'] * 3 + ['name:living_room_core_300s'] * 3)
        self.assertEqual([item['domain'] for item in result[:3]], ['fan', 'switch', 'sensor'])

    def test_govee_temperature_and_humidity_group_together(self):
        states = [{'entity_id': 'sensor.govee_bedroom_' + kind, 'state': '42', 'attributes': {'friendly_name': 'Govee bedroom ' + kind, 'device_class': kind}} for kind in ['temperature', 'humidity']]
        result = b.normalize_entities(states, {})
        self.assertEqual(result[0]['group_id'], result[1]['group_id'])
        self.assertTrue(all(item['group_name'] == 'Govee bedroom' for item in result))
        self.assertTrue(all(item['category'] == 'Sensors' for item in result))

    def test_metadata_request_is_read_only_and_handles_permissions(self):
        class TemplateClient:
            calls = []
            def request(self, path, data):
                self.calls.append((path, data))
                return [{'entity_id': 'fan.desk', 'device_id': 'device-1', 'device_name': 'Purifier', 'model': 'Core300S'}, {'entity_id': 'fan.not_requested', 'device_id': 'other'}]
        client = TemplateClient()
        metadata = b.device_metadata(client, [entity('fan')])
        self.assertEqual(list(metadata), ['fan.desk'])
        self.assertEqual(client.calls[0][0], 'template')
        self.assertIn('device_id(e)', client.calls[0][1]['template'])
        self.assertNotIn('services/', client.calls[0][1]['template'])
        with patch.object(client, 'request', side_effect=b.UserError('denied')):
            self.assertEqual(b.device_metadata(client, [entity('fan')]), {})


if __name__ == '__main__':
    unittest.main()
