#!/usr/bin/env python3
"""One JSON request on stdin, one JSON reply on stdout; no credentials in argv."""
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


class UserError(Exception):
    pass


def url(value, remote=False):
    """Validate transport/address policy; private HTTP does not prove server identity."""
    if not isinstance(value, str):
        raise UserError('Enter a Home Assistant URL.')
    value = value.strip().rstrip('/')
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise UserError('Use an HTTP(S) address without credentials, query, or fragment.')
    try:
        parsed.port
    except ValueError:
        raise UserError('Invalid URL port.') from None
    if any(ord(c) < 33 for c in value) or parsed.path:
        raise UserError('Use the server root URL, for example http://homeassistant.local:8123.')
    host = parsed.hostname.lower()
    try:
        address = ipaddress.ip_address(host)
        networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16') if address.version == 4 else ('fc00::/7', 'fe80::/10')
        private = address.is_loopback or any(address in ipaddress.ip_network(net) for net in networks)
    except ValueError:
        private = host == 'localhost' or host.endswith(('.local', '.lan', '.home.arpa'))
    if parsed.scheme != 'https' and (remote or not private):
        raise UserError('Remote/public addresses require HTTPS. HTTP is allowed only for private local addresses.')
    return value


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'omahome' / 'connection.json'


def load_config():
    path = config_path()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {'local_url': '', 'remote_url': '', 'mode': 'local', 'token': ''}
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise UserError('Connection file must be owned by you and readable only by you (chmod 600).')
        try:
            return json.load(stream)
        except (ValueError, TypeError):
            raise UserError('Connection settings are invalid. Restore or remove connection.json and configure again.') from None


def public_config(config):
    return {key: config.get(key, '') for key in ('local_url', 'remote_url', 'mode')} | {'has_token': bool(config.get('token'))}


def save_config(values):
    old = load_config()
    mode = values.get('mode', 'local')
    if mode not in ('local', 'remote'):
        raise UserError('Choose local or remote connection.')
    local = url(values['local_url']) if values.get('local_url') else ''
    remote = url(values['remote_url'], remote=True) if values.get('remote_url') else ''
    if not (remote if mode == 'remote' else local):
        raise UserError('Enter the URL for the selected connection.')
    token = values.get('token', '').strip() or old.get('token', '')
    if not token or any(c.isspace() for c in token):
        raise UserError('Enter a valid long-lived access token from your Home Assistant profile.')
    config = dict(local_url=local, remote_url=remote, mode=mode, token=token)
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_uid != os.getuid():
        raise UserError('The Omahome configuration directory must be owned by you and not a symlink.')
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix='.connection-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(config, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return public_config(config)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UserError('Home Assistant redirected the request. Enter its final server URL; credentials were not forwarded.')


class Client:
    def __init__(self, config):
        mode = config.get('mode', 'local')
        self.base = url(config.get('remote_url' if mode == 'remote' else 'local_url', ''), remote=mode == 'remote')
        self.token = config.get('token', '')
        if not self.token:
            raise UserError('Add your Home Assistant access token in Connection settings.')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.base + '/api/' + path, data=body, headers={
            'Authorization': 'Bearer ' + self.token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            # Identify this client explicitly instead of urllib's generic agent,
            # which some reverse-proxy security rules reject.
            'User-Agent': 'Omahome/1.0.0',
        })
        try:
            with self.opener.open(request, timeout=8) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise UserError('Home Assistant returned too much data.')
            return json.loads(raw)
        except urllib.error.HTTPError as error:
            error.close()
            messages = {401: 'Access denied. Replace the Home Assistant token in Connection settings.', 403: 'Home Assistant or the remote proxy denied access. Check account permissions and proxy access rules.', 404: 'Home Assistant endpoint was not found. Check the server URL and entity.', 400: 'Home Assistant rejected this command. Refresh devices and check supported features.'}
            raise UserError(messages.get(error.code, 'Home Assistant returned HTTP ' + str(error.code) + '.')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise UserError('Cannot reach Home Assistant. Check the selected connection, network, and HTTPS certificate. Commands are not retried.') from None
        except (ValueError, UnicodeError):
            raise UserError('The address did not return Home Assistant JSON. Check the URL and remote proxy login requirements.') from None


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise UserError(f'Value must be between {low} and {high}.')
    return value


def normalize(state):
    entity = state['entity_id']
    domain = entity.split('.')[0]
    a = state.get('attributes', {})
    modes = a.get('supported_color_modes') or []
    features = a.get('supported_features', 0)
    climate = domain == 'climate'
    humidifier = domain == 'humidifier'
    hvac_modes = a.get('hvac_modes') or []
    range_mode = climate and bool(features & 2) and (state['state'] == 'heat_cool' or not features & 1)
    kind, type_label, category = classify(state)
    capabilities = {
        'brightness': domain == 'light' and bool(set(modes) - {'onoff', 'unknown'}),
        'temperature': domain == 'light' and 'color_temp' in modes,
        'rgb': domain == 'light' and bool(set(modes) & {'rgb', 'rgbw', 'rgbww', 'hs', 'xy'}),
        'volume': domain == 'media_player' and bool(features & 4),
        'mute': domain == 'media_player' and bool(features & 8),
        'turn_on': domain in ('light', 'switch', 'input_boolean', 'humidifier', 'automation') or climate and bool(features & 256) or domain == 'fan' and bool(features & 32) or domain == 'media_player' and bool(features & 128),
        'turn_off': domain in ('light', 'switch', 'input_boolean', 'humidifier', 'automation') or climate and bool(features & 128) or domain == 'fan' and bool(features & 16) or domain == 'media_player' and bool(features & 256),
        'automation_run': domain == 'automation',
        'fan_speed': domain == 'fan' and bool(features & 1),
        'oscillate': domain == 'fan' and bool(features & 2),
        'direction': domain == 'fan' and bool(features & 4),
        'select_option': domain == 'select' and bool(a.get('options')),
        'number_value': domain == 'number' and a.get('min') is not None and a.get('max') is not None,
        'cover_open': domain == 'cover' and bool(features & 1),
        'cover_close': domain == 'cover' and bool(features & 2),
        'cover_stop': domain == 'cover' and bool(features & 8),
        'hvac_mode': climate and bool(hvac_modes),
        'target_temperature': climate and bool(features & 1) and not range_mode,
        'target_range': range_mode,
        'target_humidity': humidifier or climate and bool(features & 4),
        'fan_mode': climate and bool(features & 8) and bool(a.get('fan_modes')),
        'preset_mode': (climate and bool(features & 16) or domain == 'fan' and bool(features & 8)) and bool(a.get('preset_modes')),
        'humidity_mode': humidifier and bool(features & 1) and bool(a.get('available_modes')),
    }
    # A scene's state describes its activation history, not an on/off state.
    # Unknown history must not prevent its first activation.
    available = state['state'] != 'unavailable' and (state['state'] != 'unknown' or domain == 'scene')
    return dict(id=entity, domain=domain, kind=kind, type_label=type_label, category=category, device_class=a.get('device_class', ''), name=a.get('friendly_name', entity), state=state['state'], available=available, caps=capabilities,
                brightness=round((a.get('brightness') or 0) / 255 * 100), temperature=a.get('color_temp_kelvin') or 3000,
                min_temperature=a.get('min_color_temp_kelvin') or 2000, max_temperature=a.get('max_color_temp_kelvin') or 6500,
                rgb=a.get('rgb_color') or [255, 255, 255], volume=round((a.get('volume_level') or 0) * 100), muted=bool(a.get('is_volume_muted')),
                fan_speed=a.get('percentage') or 0, unit=a.get('unit_of_measurement') or '', media=a.get('media_title') or '',
                hvac_modes=hvac_modes, hvac_action=a.get('hvac_action') or '',
                current_temperature=a.get('current_temperature'), current_humidity=a.get('current_humidity'),
                target_temperature=a.get('temperature'), target_low=a.get('target_temp_low'), target_high=a.get('target_temp_high'),
                min_target_temperature=a.get('min_temp', 7), max_target_temperature=a.get('max_temp', 35),
                temperature_step=a.get('target_temp_step') or 0.5,
                target_humidity=a.get('humidity'), min_humidity=a.get('min_humidity', 0), max_humidity=a.get('max_humidity', 100),
                humidity_step=a.get('target_humidity_step') or 1,
                fan_mode=a.get('fan_mode') or '', fan_modes=a.get('fan_modes') or [],
                preset_mode=a.get('preset_mode') or '', preset_modes=a.get('preset_modes') or [],
                humidity_mode=a.get('mode') or '', humidity_modes=a.get('available_modes') or [],
                sensor_kind=sensor_kind(state), last_updated=state.get('last_updated') or '',
                temperature_unit=a.get('temperature_unit') or '',
                operating_mode=a.get('mode') or '', fan_speed_step=a.get('percentage_step') or 1, oscillating=bool(a.get('oscillating')),
                direction=a.get('direction') or '', options=a.get('options') or [],
                number_min=a.get('min', 0), number_max=a.get('max', 100), number_step=a.get('step') or 1)


def control(client, values):
    entity, action = values.get('entity', ''), values.get('action', '')
    if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+', entity):
        raise UserError('Invalid entity identifier.')
    # Re-check live capabilities before every write; never replay a failed write.
    current = normalize(client.request('states/' + entity))
    if not current['available']:
        raise UserError('This device is unavailable. Refresh and try again.')
    domain, caps = current['domain'], current['caps']
    data = {'entity_id': entity}
    value = values.get('value')
    service = action
    if action in ('turn_on', 'turn_off') and caps.get(action):
        if domain == 'automation' and action == 'turn_off':
            # Disable future triggers without cancelling an in-progress run.
            data['stop_actions'] = False
    elif action == 'automation_run' and caps['automation_run']:
        service = 'trigger'
        data['skip_condition'] = False
    elif action == 'brightness' and caps['brightness']:
        service = 'turn_on'
        data['brightness_pct'] = round(number(value, 0, 100))
    elif action == 'temperature' and caps['temperature']:
        service = 'turn_on'
        data['color_temp_kelvin'] = round(number(value, current['min_temperature'], current['max_temperature']))
    elif action == 'rgb' and caps['rgb']:
        if not isinstance(value, list) or len(value) != 3:
            raise UserError('RGB color needs red, green, and blue values.')
        service = 'turn_on'
        data['rgb_color'] = [round(number(c, 0, 255)) for c in value]
    elif action == 'volume' and caps['volume']:
        service = 'volume_set'
        data['volume_level'] = number(value, 0, 100) / 100
    elif action == 'mute' and caps['mute'] and isinstance(value, bool):
        service = 'volume_mute'
        data['is_volume_muted'] = value
    elif action == 'fan_speed' and caps['fan_speed']:
        service = 'set_percentage'
        data['percentage'] = round(number(value, 0, 100))
    elif action == 'oscillate' and caps['oscillate'] and isinstance(value, bool):
        service = 'oscillate'
        data['oscillating'] = value
    elif action == 'direction' and caps['direction']:
        if value not in ('forward', 'reverse'):
            raise UserError('Choose forward or reverse for fan direction.')
        service = 'set_direction'
        data['direction'] = value
    elif action == 'select_option' and caps['select_option']:
        if value not in current['options']:
            raise UserError('Choose an option supported by this device.')
        service = 'select_option'
        data['option'] = value
    elif action == 'number_value' and caps['number_value']:
        value = number(value, current['number_min'], current['number_max'])
        step = current['number_step']
        if not math.isclose((value - current['number_min']) / step, round((value - current['number_min']) / step), abs_tol=1e-6):
            raise UserError('Choose a value matching the device step size.')
        service = 'set_value'
        data['value'] = value
    elif action in ('cover_open', 'cover_close', 'cover_stop') and caps.get(action):
        service = {'cover_open': 'open_cover', 'cover_close': 'close_cover', 'cover_stop': 'stop_cover'}[action]
    elif action == 'hvac_mode' and caps['hvac_mode']:
        if value not in current['hvac_modes']:
            raise UserError('Choose an HVAC mode supported by this device.')
        service = 'set_hvac_mode'
        data['hvac_mode'] = value
    elif action == 'target_temperature' and caps['target_temperature']:
        service = 'set_temperature'
        data['temperature'] = number(value, current['min_target_temperature'], current['max_target_temperature'])
    elif action in ('target_low', 'target_high') and caps['target_range']:
        low = value if action == 'target_low' else current['target_low']
        high = value if action == 'target_high' else current['target_high']
        low = number(low, current['min_target_temperature'], current['max_target_temperature'])
        high = number(high, current['min_target_temperature'], current['max_target_temperature'])
        if low > high:
            raise UserError('The lower target temperature cannot exceed the upper target.')
        service = 'set_temperature'
        data.update(target_temp_low=low, target_temp_high=high)
    elif action == 'target_humidity' and caps['target_humidity']:
        service = 'set_humidity'
        data['humidity'] = round(number(value, max(0, current['min_humidity']), min(100, current['max_humidity'])))
    elif action in ('fan_mode', 'preset_mode', 'humidity_mode') and caps[action]:
        modes = current[{'fan_mode': 'fan_modes', 'preset_mode': 'preset_modes', 'humidity_mode': 'humidity_modes'}[action]]
        if value not in modes:
            raise UserError('Choose a mode supported by this device.')
        service = {'fan_mode': 'set_fan_mode', 'preset_mode': 'set_preset_mode', 'humidity_mode': 'set_mode'}[action]
        data['mode' if action == 'humidity_mode' else action] = value
    elif action == 'activate' and domain == 'scene':
        service = 'turn_on'
    else:
        raise UserError('This device does not support that control.')
    client.request('services/' + domain + '/' + service, data)
    return {'entity': entity, 'sent': True}


DOMAINS = {'light', 'switch', 'input_boolean', 'media_player', 'fan', 'cover', 'climate', 'humidifier', 'sensor', 'binary_sensor', 'scene', 'select', 'number', 'automation'}
BINARY_CLASSES = {'door', 'window', 'garage_door', 'opening', 'motion', 'occupancy', 'presence', 'moisture', 'smoke', 'gas', 'carbon_monoxide', 'safety'}


AIR_CLASSES = {'aqi', 'pm1', 'pm25', 'pm10', 'carbon_dioxide', 'volatile_organic_compounds', 'volatile_organic_compounds_parts'}
CATEGORY_ORDER = ['Lights', 'Plugs', 'Switches', 'Climate', 'Air care', 'Fans', 'Audio', 'Sensors', 'Covers', 'Scenes', 'Automations']


def identity(state):
    a = state.get('attributes') or {}
    return ' '.join(str(value or '') for value in (state.get('entity_id'), a.get('friendly_name'), a.get('device_class'), a.get('model'), a.get('device_model'), a.get('manufacturer'), a.get('icon'))).lower()


def purifier_identity(state):
    text = identity(state)
    return bool(re.search(r'air[ _-]*purif|purifier|core[ _-]*(?:mini|[2346]00s?)(?=$|[^a-z0-9])|vital[ _-]*(?:100|200)s?(?=$|[^a-z0-9])|everest[ _-]*air|lv[ _-]*pur131|lap[ _-]*[cv][0-9]', text))


def aircare_identity(state):
    return purifier_identity(state) or bool(re.search(r'levoit|vesync|humidifier|dehumidifier', identity(state)))


def aircare_auxiliary(state):
    text = identity(state)
    return aircare_identity(state) and bool(re.search(r'night[ _-]*light|mist[ _-]*(level|intensity)|purif|preset|mode|display|child[ _-]*lock', text))


def child_lock(state):
    # Use entity-level hints only: a parent device's model/name must not turn
    # its ordinary power switch into a child-lock control.
    a = state.get('attributes') or {}
    text = ' '.join(str(value or '') for value in (state.get('entity_id'), a.get('friendly_name'), a.get('translation_key')))
    return state.get('entity_id', '').split('.')[0] in ('switch', 'input_boolean') and bool(re.search(r'(?<![a-z])(?:child|kids?)[ _-]*lock(?![a-z])', text, re.I))


def classify(state):
    domain = state['entity_id'].split('.')[0]
    a = state.get('attributes') or {}
    if child_lock(state):
        category = 'Air care' if aircare_identity(state) else 'Plugs' if re.search(r'plug|outlet|socket', identity(state)) else 'Switches'
        return 'child_lock', 'Child lock', category
    if domain == 'fan':
        return ('air_purifier', 'Air purifier', 'Air care') if purifier_identity(state) else ('fan', 'Fan', 'Fans')
    if domain == 'humidifier':
        kind = 'dehumidifier' if a.get('device_class') == 'dehumidifier' else 'humidifier'
        return kind, kind.capitalize(), 'Air care'
    if domain in ('select', 'number') or domain in ('switch', 'light') and aircare_auxiliary(state):
        return ('control', 'Air-care setting', 'Air care')
    if domain == 'sensor':
        kind = sensor_kind(state)
        labels = {'temperature': 'Temperature', 'humidity': 'Humidity', 'aqi': 'Air quality index', 'air_quality': 'Air quality', 'pm1': 'PM1', 'pm25': 'PM2.5', 'pm10': 'PM10', 'filter_life': 'Filter life', 'carbon_dioxide': 'CO₂', 'volatile_organic_compounds': 'VOC', 'volatile_organic_compounds_parts': 'VOC'}
        return kind, labels.get(kind, 'Sensor'), 'Air care' if kind in AIR_CLASSES | {'air_quality', 'filter_life'} else 'Sensors'
    if domain == 'switch':
        plug = a.get('device_class') == 'outlet' or bool(re.search(r'plug|outlet|socket', identity(state)))
        return ('outlet', 'Smart plug', 'Plugs') if plug else ('switch', 'Switch', 'Switches')
    return {
        'light': ('light', 'Light', 'Lights'), 'input_boolean': ('input_boolean', 'Switch', 'Switches'),
        'climate': ('climate', 'Heating / cooling', 'Climate'), 'media_player': ('media_player', 'Speaker / media', 'Audio'),
        'binary_sensor': ('binary_sensor', 'Sensor', 'Sensors'), 'cover': ('cover', 'Cover', 'Covers'),
        'scene': ('scene', 'Scene', 'Scenes'), 'automation': ('automation', 'Automation', 'Automations')
    }.get(domain, ('sensor', 'Device', 'Sensors'))


def sensor_kind(state):
    a = state.get('attributes') or {}
    kind = a.get('device_class') or ''
    if kind in {'temperature', 'humidity'} | AIR_CLASSES:
        return kind
    text = identity(state)
    if aircare_identity(state):
        if re.search(r'filter[ _-]*(life|remaining)|remaining[ _-]*filter', text):
            return 'filter_life'
        if re.search(r'air[ _-]*quality', text):
            return 'air_quality'
        if re.search(r'pm2[_. -]?5', text):
            return 'pm25'
    # Some custom integrations omit the class but do publish a useful unit.
    if not kind:
        unit = a.get('unit_of_measurement') or ''
        if unit in ('°C', '°F', 'K'):
            return 'temperature'
        name = (state.get('entity_id', '') + ' ' + str(a.get('friendly_name', ''))).lower()
        if unit == '%' and ('humidity' in name or 'humidit' in name):
            return 'humidity'
    return ''


def include_entity(state):
    domain = state.get('entity_id', '').split('.')[0]
    a = state.get('attributes') or {}
    if domain not in DOMAINS:
        return False
    if a.get('entity_category') in ('diagnostic', 'config') and not child_lock(state) and not aircare_auxiliary(state) and sensor_kind(state) != 'filter_life':
        return False
    if domain in ('select', 'number'):
        return aircare_auxiliary(state)
    if domain == 'sensor':
        return bool(sensor_kind(state))
    if domain == 'binary_sensor':
        return a.get('device_class') in BINARY_CLASSES
    return True


def device_metadata(client, states):
    """Read device/area associations; gracefully fall back for limited tokens."""
    ids = [state['entity_id'] for state in states
           if state.get('entity_id', '').split('.')[0] in DOMAINS
           and re.fullmatch(r'[a-z_]+\.[a-z0-9_]+', state.get('entity_id', ''))]
    if not ids:
        return {}
    # Entity IDs are validated above and serialized; names never enter the template.
    template = ("{% set ns = namespace(rows=[]) %}{% for e in " + json.dumps(ids) + " %}"
                "{% set d = device_id(e) %}{% set a = area_id(e) %}"
                "{% set da = area_id(d) if d else none %}"
                "{% set ns.rows = ns.rows + [{'entity_id': e, 'device_id': d or '', "
                "'device_name': (device_attr(d, 'name_by_user') or device_attr(d, 'name') or '') if d else '', "
                "'model': (device_attr(d, 'model') or '') if d else '', "
                "'manufacturer': (device_attr(d, 'manufacturer') or '') if d else '', "
                "'area_id': a or '', 'area_name': (area_name(a) or '') if a else '', "
                "'device_area_id': da or '', 'device_area_name': (area_name(da) or '') if da else ''}] %}"
                "{% endfor %}{{ ns.rows | to_json }}")
    try:
        rows = client.request('template', {'template': template})
    except UserError:
        return {}
    if not isinstance(rows, list):
        return {}
    fields = ('device_id', 'device_name', 'model', 'manufacturer', 'area_id', 'area_name', 'device_area_id', 'device_area_name')
    requested = set(ids)
    return {row['entity_id']: {key: row.get(key) if isinstance(row.get(key), str) else '' for key in fields}
            for row in rows if isinstance(row, dict) and isinstance(row.get('entity_id'), str)
            and row['entity_id'] in requested}


ENTITY_SUFFIX = re.compile(r'(?:[ _-]+(?:child[ _-]*lock|display(?:[ _-]*status)?|filter[ _-]*(?:life|remaining)|air[ _-]*quality|night[ _-]*light(?:[ _-]*level)?|mist[ _-]*level|pm2[_. -]?5|pm1|pm10|temperature|humidity|preset(?:[ _-]*mode)?|mode|speed|power|fan|switch|sensor))$', re.I)


def base_label(value):
    label = str(value).replace('_', ' ').strip()
    while True:
        shortened = ENTITY_SUFFIX.sub('', label).strip()
        if not shortened or shortened == label:
            return label
        label = shortened


def fallback_device_key(item):
    # Preserve room suffixes and numeric identifiers, never group on model alone.
    return re.sub(r'[^a-z0-9]+', '_', base_label(item['id'].split('.', 1)[1]).lower()).strip('_')


def member_rank(item):
    if item['kind'] == 'child_lock':
        return 3
    if item['domain'] in ('fan', 'humidifier', 'climate'):
        return 0
    return 2 if item['domain'] in ('sensor', 'binary_sensor') else 1


def group_devices(items, metadata):
    known = {}
    device_rooms = {}
    for item in items:
        info = metadata.get(item['id']) or {}
        if info.get('device_id'):
            known.setdefault(fallback_device_key(item), set()).add(info['device_id'])
            known_room = info.get('device_area_id') or info.get('area_id')
            if known_room:
                device_rooms.setdefault(info['device_id'], set()).add(known_room)
    groups = {}
    for item in items:
        info = metadata.get(item['id']) or {}
        actual = info.get('device_id')
        area = info.get('area_id') or ''
        inferred = {device for device in known.get(fallback_device_key(item), set())
                    if not area or not device_rooms.get(device) or area in device_rooms[device]}
        if item['domain'] == 'automation':
            group_id = 'entity:' + item['id']
        elif actual:
            group_id = 'device:' + actual
        elif len(inferred) == 1:
            group_id = 'device:' + next(iter(inferred))
        else:
            group_id = 'name:' + fallback_device_key(item) + (':area:' + area if area else '')
        item['group_id'] = group_id
        groups.setdefault(group_id, []).append(item)
    for group_id, members in groups.items():
        ordered = sorted(members, key=lambda item: (member_rank(item), item['kind'] == 'control', item['name'].casefold(), item['id']))
        primary = ordered[0]
        info = next((metadata[m['id']] for m in ordered if (metadata.get(m['id']) or {}).get('device_name')), {})
        name = str(info.get('device_name') or (primary['name'] if member_rank(primary) == 0 else base_label(primary['name'])))
        # A physical device is one group even when an auxiliary entity overrides
        # its area. Prefer the device's area, then its main entity's area.
        room = next((metadata[m['id']] for m in ordered if (metadata.get(m['id']) or {}).get('device_area_id')), None)
        if room:
            room_id, room_name = room['device_area_id'], room.get('device_area_name') or room['device_area_id']
        else:
            room = next((metadata[m['id']] for m in ordered if (metadata.get(m['id']) or {}).get('area_id')), {})
            room_id = room.get('area_id') or ''
            room_name = room.get('area_name') or room_id or 'Unassigned'
        for item in members:
            item['group_name'] = name
            item['group_size'] = len(members)
            item['room_id'] = room_id
            item['room_name'] = room_name
            # A purifier's display/night light/readings belong with that purifier;
            # an ordinary fan's related settings belong under Fans.
            if primary['domain'] in ('fan', 'humidifier', 'climate', 'light', 'switch', 'media_player', 'cover') and (item['domain'] in ('sensor', 'binary_sensor', 'switch', 'light', 'number', 'select') or item['kind'] == 'child_lock'):
                item['category'] = primary['category']
                if item['kind'] == 'control':
                    item['type_label'] = 'Fan setting' if primary['category'] == 'Fans' else item['type_label']
    return sorted(items, key=lambda item: (not bool(item['room_id']), item['room_name'].casefold(), item['room_id'], item['group_name'].casefold(), item['group_id'], member_rank(item), item['name'].casefold(), item['id']))


def normalize_entities(states, config, metadata=None):
    metadata = metadata or {}
    unit = (config.get('unit_system') or {}).get('temperature') or '°C'
    result = []
    for state in states:
        info = metadata.get(state.get('entity_id')) or {}
        if info:
            attrs = dict(state.get('attributes') or {})
            for key, value in [('device_model', info.get('model')), ('manufacturer', info.get('manufacturer'))]:
                if value and not attrs.get(key):
                    attrs[key] = value
            state = dict(state, attributes=attrs)
        if not include_entity(state):
            continue
        item = normalize(state)
        if item['domain'] == 'climate' and not item['temperature_unit']:
            item['temperature_unit'] = unit
        if item['domain'] == 'sensor' and not item['unit']:
            item['unit'] = unit if item['sensor_kind'] == 'temperature' else '%' if item['sensor_kind'] in ('humidity', 'filter_life') else ''
        result.append(item)
    return group_devices(result, metadata)


def dispatch(request):
    command = request.get('command')
    values = request.get('values', {})
    if command == 'config':
        return public_config(load_config())
    if command == 'save':
        return save_config(values)
    config = load_config()
    if command == 'dashboard':
        mode = values.get('mode', config.get('mode', 'local'))
        if mode not in ('local', 'remote'):
            raise UserError('Choose local or remote connection.')
        return {'url': url(config.get(mode + '_url', ''), remote=mode == 'remote')}
    client = Client(config)
    if command == 'states':
        states = client.request('states')
        return {'devices': normalize_entities(states, client.request('config'), device_metadata(client, states)), 'mode': config.get('mode', 'local')}
    if command == 'control':
        return control(client, values)
    raise UserError('Unknown command.')


def main():
    try:
        request = json.loads(sys.stdin.readline(1024 * 1024))
        result = {'ok': True, 'data': dispatch(request)}
    except UserError as error:
        result = {'ok': False, 'error': str(error)}
    except Exception:
        # Never include response bodies, credentials, or exception representations.
        result = {'ok': False, 'error': 'Could not complete the request. Check the connection settings and device, then try again.'}
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
