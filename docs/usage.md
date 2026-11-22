# Omahome usage guide

[Back to README](../README.md)

A native Omarchy desktop bar plugin for Home Assistant. Click the Home Assistant icon to control devices or open the full Home Assistant dashboard.

## Install

Requires Omarchy Quattro's plugin-capable shell, Python 3.9 or newer, and Qt Quick Controls (normally included with Omarchy). No pip/npm dependencies, web server, background daemon, or Home Assistant custom integration is required.

Install directly from GitHub and enable the plugin:

```bash
omarchy plugin add https://github.com/Z1Z0R/Omahome.git --enable
```

Follow Omarchy's prompts, then click the Home Assistant icon in the bar. Update a Git-managed installation with:

```bash
omarchy plugin update zizor.omahome
```

### Manual installation

Alternatively, extract the release archive or clone the repository, open a terminal in its root directory, and run:

```bash
bash install.sh
```

The installer validates and installs `zizor.omahome`, rescans plugins, and enables the Home Assistant icon on the right of the bar. It asks you to use the explicit update command for an existing installation. Your connection settings are kept separately.

### Update a manual installation

For an installation originally made with `install.sh`, run from the new checkout or extracted release:

```bash
bash install.sh --update
omarchy-restart-shell
```

The updater stages and validates the complete new plugin before touching the installed version. It then backs up the old directory outside the watched plugins directory and activates the staged version. If activation fails or is interrupted by a handled signal, it restores the old directory automatically; if restoration fails, it preserves the backup and prints its recovery path. Your saved Home Assistant connection and bar position are preserved. The bar and panel header use the official Home Assistant logo. Slider adjustments preserve the selected value across refreshes.

### Refreshed interface

Device cards show bundled vector icons for lights, speakers, outlets, fans, covers, scenes, and sensors. Temperature, humidity, battery, and power sensors use matching icons when Home Assistant reports their device class. Rounded controls include power toggles, category tabs, search and connection fields, color-coded RGB sliders, and a warm-to-cool Kelvin track. Controls retain mouse and keyboard operation, visible focus states, and device capability checks. The colors follow your Omarchy theme.

## Connect to your server

1. Click the Home Assistant icon, then **Settings**.
2. Enter the local root address, for example `http://homeassistant.local:8123` or `http://192.168.1.50:8123`. Use your server's address, not the example IP.
3. In Home Assistant, open your user profile → **Security** → **Long-lived access tokens**, and create a token for Omahome. Use an account with access to the devices you want to control.
4. Paste the token into Omahome's password field. Choose **Local** and click **Save and connect**.

The plugin lists Home Assistant entities, rather than hardware devices. One physical device may have multiple entities. Integrate devices into Home Assistant first; Omahome uses the entities your server provides. Devices must be reachable by Home Assistant or their configured integration.

## Controls

| Entity | Available controls |
| --- | --- |
| Lights | On/off, 0–100% brightness slider, white temperature slider in the device's supported Kelvin range, red/green/blue sliders with preview and Apply button |
| Speakers and other media players | 0–100% volume slider, mute/unmute, power if supported, current media title |
| Smart plugs, switches, and input booleans | On/off; outlet icons for smart plugs; distinct child-lock controls |
| Fans and air purifiers | On/off, percentage speed, supported preset modes, oscillation and direction when advertised |
| Covers | Open, stop, close when supported |
| Scenes | Activate even when previous activation history is unknown; explicitly unavailable scenes stay disabled |
| Automations | Enable/disable; Run now with conditions checked |
| Thermometers and humidity sensors | Large live reading and unit, including Govee entities supplied by Home Assistant |
| Door, motion, occupancy, and safety sensors | Current physical state |
| Heaters, thermostats, and AC (`climate`) | Supported heating/cooling/off modes, target temperature or heat/cool range, current temperature/humidity, fan modes, presets, and humidity targets when supported; power toggle when advertised |
| Humidifiers and dehumidifiers (`humidifier`) | On/off, target humidity, current humidity, and supported operating modes |

Search by entity name or ID. Categories appear only when they contain devices: Lights, Air care, Climate, Fans, Plugs, Switches, Audio, Sensors, Covers, Scenes, and Automations. Humidifiers, dehumidifiers, and air purifiers are grouped under Air care. Ordinary desk, ceiling, and tower fans have a separate Fans category; heaters and AC stay under Climate. Only supported controls appear. Unavailable devices stay visible with controls disabled. Door locks, alarms, and other unsupported domains are accessed through the full dashboard.

The list now focuses on physical controls and room measurements. Generic sensor telemetry is excluded: signal/RSSI, sun position and sunrise times, battery/uptime, timestamps, and unrelated sensor classes do not appear. Useful air-quality measurements (AQI, particulate matter, CO₂, and VOC) and recognized air-care filter-life readings are retained under Air care. Physical door, window, motion, occupancy, moisture, smoke, gas, and safety binary sensors remain; connectivity diagnostics are excluded. Temperature and humidity are recognized by Home Assistant device class, with a fallback for integrations that publish temperature units or a humidity-named percentage sensor without a class.

### RGB color

RGB-capable lamps show one-click presets directly on the card: Red, Orange, Yellow, Green, Cyan, Blue, Purple, Pink, Warm white, White, Daylight, Cold white, Mint, Lavender, and Peach. Clicking a preset applies it immediately. **Custom color** opens red, green, and blue sliders, a preview, and **Apply RGB color**. White presets are RGB approximations; use white temperature for the lamp’s dedicated white mode. Supported modes include RGB, RGBW, RGBWW, HS, and XY. Non-color lamps do not show this section. White temperature is opened separately. Unsent custom RGB edits are preserved during refreshes. After sending a color, the preview and preset selection follow the state confirmed by Home Assistant on the next refresh.

### Automations

Automation entities appear under **Automations**, separate from physical device categories and Scenes. Enable/disable uses `automation.turn_on` / `automation.turn_off`; disabling sets `stop_actions: false` so active actions can finish. **Run now** uses `automation.trigger` with `skip_condition: false`: conditions are checked even if the automation's normal triggers are disabled. Trigger-dependent conditions may block a manual run. Unavailable automations have disabled controls. Omahome does not edit automation definitions.

See Home Assistant's [trigger automation](https://www.home-assistant.io/actions/automation.trigger/) and [disable automation](https://www.home-assistant.io/actions/automation.turn_off/) documentation for these options.

### Device-first ordering

Within each category, entities are grouped by physical device rather than by control type. A Core 300S group contains its power/speed/mode controls, then its display/child-lock settings and filter/air-quality readings, before another purifier’s group begins. Devices with multiple displayed entities have a group heading. Temperature and humidity entities belonging to the same Govee device are kept together too.

A read-only Home Assistant template lookup obtains device IDs, names, and model information. Device IDs keep two identically named devices separate. If template access is unavailable or restricted, the panel still works and falls back to entity-ID prefixes after stripping known control/measurement suffixes. Room and numeric identifiers are retained; the fallback does not merge everything by model number.

Related controls and readings inherit their primary device’s category: a tower fan’s display switch stays in Fans, while a purifier’s settings stay in Air care. Search recalculates group headings so a matching setting or reading still has context even when its main card is filtered out.

### Levoit and other air purifiers

The Core 300S is shown as **Air purifier** under **Air care**, with a purifier icon. Core 200/300/400/600 variants, Vital, EverestAir, and common Levoit model codes are recognized from the entity name or exposed model/icon metadata. Ordinary tower fans remain Fan under the Fans category, rather than being labeled as purifiers merely because they are Levoit products. The optional device lookup supplies model information for renamed entities; when no model, icon, or naming hint is available, an unidentified fan stays in Fans.

The purifier mode picker uses Home Assistant's advertised `preset_modes` exactly, such as auto, sleep, or normal when available, and calls `fan.set_preset_mode`. The speed slider uses the reported percentage step. On integrations such as VeSync, adjusting speed may select manual mode. Oscillation and direction appear only on devices that advertise them.

Levoit night-light selectors and mist-level number entities are also supported when their names/model metadata identify them as air-care settings. Display/child-lock switches appear as toggles, including recognized air-care configuration entities. Entities are sorted per physical device, with that device’s main controls first, then its settings, then its readings. The next device follows only after the first device’s entries. No filter reset is performed.

All controls require the corresponding Home Assistant entities to be exposed and available. This plugin does not call VeSync directly or invent controls missing from your integration. Related entities are linked by Home Assistant device ID when the device lookup is available. Otherwise naming/model hints are used; unrelated or completely renamed identifiers may not be recognizable without metadata.

### Heaters, AC, and humidity control

Select the Climate tab. Changing an HVAC mode explicitly selects one reported by the device, including off, heat, cool, auto, or heat/cool where supported. Power controls are shown only when the climate entity advertises turn-on/turn-off; selecting an HVAC mode is also available on devices without those power actions. Omahome does not guess which heating/cooling mode you intend when a device lacks a turn-on action.

Target sliders use the device's minimum, maximum, and step. Celsius/Fahrenheit comes from Home Assistant's unit system. A heat/cool range has separate lower and upper targets; the other limit is re-read from the device before each command and the limits cannot cross. Fan modes, presets, and humidity controls appear only if supported. Climate controls do not change devices until you adjust a control.

Smart plugs use their Home Assistant switch entities. A heater connected through a plug offers power switching; temperature regulation requires a separate climate entity in Home Assistant.

### Govee and other Bluetooth thermometers

Once Home Assistant's built-in integration or your installed custom integration exposes temperature/humidity sensor entities, Omahome displays them in Sensors. This works with Bluetooth, Wi-Fi, gateway, and proxy-backed devices alike; the desktop does not scan Bluetooth itself. Unavailable/unknown readings show an em dash. Omahome cannot discover a device or obtain readings that are missing from Home Assistant. Sensor values refresh with the panel's regular polling.


Brightness, light color temperature, volume, speed, thermostat targets, and humidity targets are sent when you release a slider. Keyboard adjustments are combined after a short pause. RGB sliders prepare a color; **Apply RGB color** sends it. Home Assistant can convert RGB for HS/XY lights. Color temperature and RGB are separate light modes, so the most recently applied mode takes effect. Setting brightness to zero turns a light off; changing brightness or color can turn it on.

Startup and opening the panel only load saved settings. Click **Connect to Home Assistant** for each new panel session, or **Save and connect** after editing settings. After that explicit action, the panel refreshes every 10 seconds while open and after commands. Closing it ends approval, drops queued authenticated requests, and cancels delayed refreshes; an already-sent request cannot be recalled. Late replies cannot reconnect a closed panel. It pauses updates during dragging and preserves expanded color editors across ordinary refreshes. A command failure never triggers an automatic retry. Click Refresh to recover after a connection failure.

## Access from outside home

Omahome includes a remote HTTPS connection, an **Open remotely** dashboard button, and a shortcut into Home Assistant Cloud setup. It does not provision a public hostname or tunnel on your server.

### Home Assistant Cloud

1. Connect locally in Omahome, then choose **Set up Home Assistant Cloud** in Settings. This opens your server's Cloud setup screen.
2. Sign in or subscribe through Home Assistant and enable remote access. Any subscription is managed there; Omahome does not purchase it.
3. Copy the remote HTTPS root address shown by Home Assistant.
4. Paste it into Omahome's **Remote server URL**, choose **Remote**, and **Save and connect**. Keep the token field blank to retain the saved token.
5. Away from home, use Remote for the sliders and other controls. **Open remotely** opens the remote Home Assistant login/dashboard in your browser. Browser login is separate from the plugin's token.

Home Assistant Cloud provides remote access without router port forwarding. You can also use an existing HTTPS reverse proxy or Cloudflare tunnel. A VPN works when it makes the configured server address reachable; this release requires HTTPS in Remote mode. You may use Local mode with a private HTTP address reachable through an encrypted VPN.

A Cloudflare Access login page will block API calls unless your proxy is configured to accept the API traffic. This plugin does not implement Cloudflare service-token authentication or bypass access rules. It does not change your firewall, router, Cloudflare account, or Home Assistant configuration. Do not disable authentication on the Home Assistant server.

**Open dashboard** follows the saved Local/Remote selection. **Open remotely** always uses the saved remote address. There is no automatic network switching or command replay between addresses.

## Credentials and connections

A local HTTP address is not proof of server identity. The same private IP or `.local` name can point to a different device on another network. HTTP connections require the user to choose Connect on a trusted home network; HTTPS with a valid certificate authenticates the configured server. An approved HTTP session does not detect roaming to a different network while the panel remains open.

- Settings live in `${XDG_CONFIG_HOME:-~/.config}/omahome/connection.json`, outside the plugin, with directory permissions 700 and file permissions 600. The access token is stored as plaintext inside that private file; this is not an encrypted keyring.
- The token is passed to the Python helper through stdin, never command arguments or URLs. Public settings replies and error messages omit it; the password field clears after saving and when closing the panel.
- HTTPS certificates are verified. Redirects are rejected so bearer tokens cannot be forwarded to redirected hosts. Public URLs require HTTPS; local HTTP is restricted to private IPs and local hostname suffixes.
- Proxy environment variables are ignored for API requests. Set a direct reachable Home Assistant address.
- Requests time out after eight seconds. Device capabilities are read again before each command. Range checks and an explicit action allowlist limit writes to the controls above.
- Other unsandboxed software running as your user, including other Omarchy plugins, can still read files your user owns. Use software you trust and revoke the token in Home Assistant when you stop using it.

## Troubleshooting

- **401:** replace the Home Assistant access token.
- **403:** check the account's permissions and remote proxy access rules.
- **Ordinary curl gets 401 but Python gets 403 without a token:** the proxy is filtering the client identification. This build sends `User-Agent: Omahome/1.0.0` instead of Python's default. Update with `bash install.sh --update` from the repository root, then run `omarchy-restart-shell`. This does not change authentication or proxy policies. If the named client is also rejected, check the matching security event in your proxy dashboard.
- **Cannot reach server:** verify the selected connection, address, VPN/tunnel, and HTTPS certificate.
- **No brightness, color, or volume slider:** the entity must advertise the corresponding capability. Check its integration in Home Assistant.
- **Remote dashboard works but controls do not:** a separate proxy login page can work in the browser but block the API.
- **File permissions error:** correct the connection file to `chmod 600 ~/.config/omahome/connection.json` (adjust for a custom XDG config directory).

## Disable or remove

```bash
omarchy plugin disable zizor.omahome
omarchy plugin remove zizor.omahome
```

Removal may move a hand-installed plugin into a backup directory according to Omarchy's own rules. Connection settings are intentionally retained. To disconnect permanently, revoke the Omahome token from your Home Assistant profile and remove the dedicated Omahome connection settings directory if desired.

## Development and validation

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
python3 tests/smoke_qml.py
```

The Python suite checks REST payloads, capabilities, unavailable entities, ranges, private configuration permissions, credential handling, redirects, and errors with an isolated configuration and mocked HTTP transport. The suite also checks separate same-model device groups, device metadata lookup/fallback, physical-device ordering, fan-category inheritance, Core 300S/purifier categorization, tower-fan distinctions, fan preset/oscillation/direction commands, targeted select/number controls, telemetry filtering, thermometer/humidity recognition, thermostat units and decimal targets, heat/cool bounds, explicit HVAC modes, and humidifier/dehumidifier service payloads. Installer regression tests cover successful installs/updates, copy and validation failures, activation failure, interruption, and backup preservation when restoration fails. The QML smoke test checks that drag and keyboard input retain their chosen values across refreshes, and loads the actual Omarchy theme and widget components offscreen, replacing only the compositor-owned popup wrapper; it covers populated device cards, expanded RGB/temperature controls, filtering, and refreshes. It does not test real Wayland popup placement or physical hardware. Configure and test against your server after installation.

References: [Omarchy shell plugins](https://omarchy.org/manual/shell-plugins/), [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/), [lights](https://www.home-assistant.io/integrations/light/), [media players](https://www.home-assistant.io/integrations/media_player/), [remote access](https://www.home-assistant.io/docs/configuration/remote/).

Child-lock switches are identified from entity names or IDs (such as `child_lock`), including configuration entities. They show a lock/unlock icon, an emphasized **Child lock · Enabled/Disabled** status, an explanation, and a child-lock tooltip/accessibility label. They stay with their device after its main controls; their toggle operates the lock entity independently of the power entity. Unknown/unavailable locks show Unavailable and cannot be toggled. Renamed entities without any child-lock hint cannot be identified automatically.
