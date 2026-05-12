# Stack Config

`lsh_stack.toml` is the deployment layer for Labo Smart Home. It keeps the controller
profile clean while still giving users one command that generates bridge firmware
fragments, coordinator configuration and exact Node-RED node settings.

The split is intentional:

- `lsh_devices.toml` belongs to `lsh-core` and describes the controller firmware;
- `lsh_stack.toml` belongs to the installation and describes how the controllers are
  wired into MQTT, `lsh-bridge`, the coordinator and Node-RED.

## Choose Your Path

Use the configurator path when you want one source of truth for the whole stack:

1. edit `core/lsh_devices.toml` for the controller topology;
2. edit `lsh_stack.toml` for MQTT, bridge deployment, coordinator and Node-RED choices;
3. run `lsh-stack generate`;
4. include the generated PlatformIO fragments and copy the generated coordinator or
   Node-RED values.

Use the manual path when you only need one library, or when an existing installation
already owns its build files. In that case you configure each project directly:
`lsh-core` gets its own `lsh_devices.toml`, `lsh-bridge` gets matching build flags and
MQTT/Homie values, and the coordinator or Node-RED node receives matching device names
and topics. This gives maximum control, but you must keep repeated values aligned by
hand.

The configurator does not keep hidden state. Files under `generated/` are disposable,
and generated commands show the config files they use, including OTA JSON files.

## Quick Start

After installing the package, use `lsh-stack` directly. From a checkout of this
repository, use the standard Python launcher script. On Windows, use `py` instead of
`python` if that is how Python is installed.

Create one personal installation project:

```bash
python /path/to/labo-smart-home/lsh-stack.py new my-lsh-installation
cd my-lsh-installation
```

The starter project has two normal PlatformIO projects, disposable generated files in
`generated/` and persistent local notes or manual extensions in `overrides/`. When you
already have an existing `lsh_stack.toml` plus `lsh_devices.toml`, `lsh-stack setup` can
create the missing core/bridge PlatformIO shells from those paths.

```text
my-lsh-installation/
  lsh_stack.toml
  core/
    lsh_devices.toml
    platformio.ini
    src/main.cpp
  bridge/
    platformio.ini
    src/main.cpp
  generated/
  overrides/
    README.md
```

The TOML files include `#:schema` hints. Editors with TOML schema support can use
[`schemas/lsh_stack.schema.json`](./schemas/lsh_stack.schema.json) for completions and
early validation.

`generated/platformio-core.ini` and `generated/platformio-bridge.ini` start as bootstrap
files so PlatformIO can install packages in a fresh project. The first `generate` run
replaces them with controller-derived environments.

Build the starter controller once so PlatformIO installs `lsh-core` and the bootstrap
pre-build hook can generate `core/include/lsh_user_config.hpp`:

- IDE path: open `core/` in VSCode with the PlatformIO extension and run `core_panel` ->
  Build.
- CLI path, when `platformio` is available:

  ```bash
  platformio run -d core -e core_panel
  ```

Generate all stack artifacts:

```bash
python /path/to/labo-smart-home/lsh-stack.py generate
```

If `generate` cannot find the `lsh-core` generator yet, build `core_panel` once from the
IDE or CLI so dependencies are installed, or set `[core].tool` to a local `lsh-core`
checkout.

The output directory contains:

- `lsh-stack-config.json`: complete machine-readable export;
- `system-config.json`: coordinator `systemConfig`;
- `node-red-setup.md`: guided Node-RED GUI setup with the exact values to copy;
- `node-red-lsh-logic.json`: raw fields for scripts that need only the `lsh-logic` node
  configuration;
- `bridge-platformio-flags/bridge.txt`: raw build flags for the wide bridge firmware;
- `platformio-core.ini`: generated controller environments;
- `platformio-bridge.ini`: generated bridge build, USB upload and OTA upload
  environments;
- `bridge-ota.py`: generated wrapper around the Homie/MQTT OTA updater from
  `homie-esp8266`, when `[deploy.bridge.ota]` is set;
- `bridge-ota.json`: generated broker, TLS and Homie defaults consumed by
  `bridge-ota.py`, when `[deploy.bridge.ota]` is set;
- `deploy-plan.json`: exact PlatformIO commands for tools and scripts;
- `README.generated.md`: short generated guide for the current stack.

Use `python /path/to/labo-smart-home/lsh-stack.py check` in CI or before a firmware
build. It validates the TOML, asks `lsh-core` for the controller contract, verifies
names and prints a compact bring-up report.

Use `python /path/to/labo-smart-home/lsh-stack.py doctor` when something fails and you
want the likely fix in plain language. Use
`python /path/to/labo-smart-home/lsh-stack.py explain <device>` to inspect the
controller environment, bridge environments, MQTT topics, build flags and coordinator
entry for one controller.

## File Shape

```toml
schema_version = 1

[core]
devices = "lsh_devices.toml"

[transport]
mode = "serial_bridge"

[mqtt]
codec = "json"
lsh_base_path = "LSH/"
homie_base_path = "homie/5/"
service_topic = "LSH/Node-RED/SRV"
```

`core.devices` points to the controller TOML. If the `lsh-core` generator is not next to
your project, set `core.tool` or the `LSH_CORE_TOOL` environment variable.

`transport.mode = "serial_bridge"` is the supported public stack today. The schema
reserves `onboard_ethernet` for a future bridgeless controller profile, but the composer
fails clearly until that firmware path exists.

`mqtt.codec` controls the MQTT-facing payload codec. This is where heterogeneous mode
lives: the controller can use serial MsgPack while MQTT, the coordinator and Node-RED
stay on JSON.

`mqtt.codec = "auto"` follows the protocol exported by the selected controller profile.
With the current public serial bridge presets that resolves to `msgpack`. Set `json` or
`msgpack` explicitly when you want the generated coordinator, Node-RED and bridge MQTT
configuration to stay obvious during bring-up.

## Examples

Use the smallest file that matches where you are in the bring-up:

- [`examples/lsh_stack.minimal.toml`](./examples/lsh_stack.minimal.toml) only points to
  the controller profile and chooses MQTT JSON. It is enough to generate bridge flags,
  coordinator devices and Node-RED basics.
- [`examples/lsh_stack.network-clicks.toml`](./examples/lsh_stack.network-clicks.toml)
  adds one distributed long-click action and one external actor.
- [`examples/lsh_stack.complete.toml`](./examples/lsh_stack.complete.toml) shows the
  full shape: selected devices, MQTT paths, coordinator timing, Node-RED context
  exports, an external actor topic and multiple network-click mappings.

## Network Clicks

Network-click actions are declared with readable names:

```toml
[[network_clicks]]
source = "j2.salaTavolo"
type = "long"
actors = [
  { device = "j1", actuators = "all" },
  { device = "garage", actuators = ["ceiling"] },
]
other_actors = ["zigbee_table_lamp"]
```

The composer checks that `source` is a `network = true` click in `lsh_devices.toml`. It
also resolves actuator names to the numeric ids required by the coordinator JSON. If a
name is wrong, generation fails before the configuration reaches Node-RED.

`other_actors` stay protocol-neutral. LSH emits the intended boolean state and your
Node-RED flow, CLI adapter or custom integration decides how to route it to Zigbee,
Tasmota, Home Assistant or another system.

Declare optional `[external_actors.<name>]` entries when you want inventory metadata for
those non-LSH targets:

```toml
[external_actors.zigbee_table_lamp]
state_key = "other_devices.zigbee_table_lamp.state"
```

These entries are metadata. They are included in `lsh-stack-config.json` for generated
guides, audits and custom flows, but `node-red-lsh-logic.json` only needs the
`otherActors` names inside `systemConfigJson`. The Node-RED node reads external state
through `other_devices_prefix` plus the actor name, while your surrounding flow owns the
actual Zigbee, Tasmota, Home Assistant or other integration mapping.

## Coordinator and Node-RED

Coordinator timing and Node-RED context exports live in the stack file:

```toml
[coordinator]
click_timeout = "2s"
watchdog_interval = "60s"
other_devices_prefix = "other_devices"

[node_red]
export_topics = "flow"
export_topics_key = "lsh_topics"
other_actors_context = "global"
```

Durations accept seconds as numbers or strings such as `250ms`, `2s`, `1m` and `1h`.
Topic bases must end with `/`; concrete publish topics such as `service_topic` must not.

For normal Node-RED GUI usage, keep the flow in Node-RED and use the generated guide for
the exact `lsh-logic` values:

1. Install `node-red-contrib-lsh-logic` from the Node-RED palette.
2. Restart Node-RED if requested.
3. Add one `lsh-logic` node to a flow.
4. Add standard MQTT input and output nodes and wire them like the
   `node-red-contrib-lsh-logic` example flow.
5. Open `generated/node-red-setup.md`, paste the generated `System Config JSON` into the
   node editor and set the listed fields.
6. Configure the MQTT broker node manually for your host, credentials and TLS.
7. Deploy.

This is deliberately a small human step. The generator does not mirror Node-RED editor
internals or emit a full flow, so changes in the Node-RED node do not force a large
Python flow renderer rewrite. The raw `node-red-lsh-logic.json` file remains available
for scripts and advanced tooling.

## PlatformIO Without Copy-Paste

The generated PlatformIO fragments are the recommended user path, but they are an
overlay, not a hard dependency. Keep useful standalone environments in each PlatformIO
project so `lsh-core` and `lsh-bridge` remain normal library consumers even if the stack
configurator is removed. Controller firmware still has one environment per controller;
bridge firmware is deliberately wider and shared by every bridge device in the stack.

In the controller project:

```ini
[platformio]
extra_configs = ../generated/platformio-core.ini
```

In the bridge project:

```ini
[platformio]
extra_configs = ../generated/platformio-bridge.ini
```

Use the generated environments from VSCode PlatformIO Project Tasks or from the
PlatformIO CLI when the stack overlay is present. IDE users do not need a system-wide
PlatformIO installation; CLI users can run the same environments directly when
`platformio` is available in `PATH`.

Command-line examples:

```bash
platformio run -d core -e core_j1
platformio run -d bridge -e bridge_littlefs
```

The bridge config uses the maximum required stack limits for `CONFIG_MAX_*` defines,
such as actuators, buttons, indicators when present and name length. That means
`bridge_littlefs` is one binary that can run on `c1`, `j1`, `j2` and the other bridge
devices. Device names are upload targets, not firmware variants.

Use bridge profiles for firmware variants:

```toml
[[platformio.bridge_profiles]]
name = "release"
extends = "lsh_bridge_release"

[[platformio.bridge_profiles]]
name = "debug"
extends = "lsh_bridge_debug"

[[platformio.bridge_profiles]]
name = "littlefs"
extends = "lsh_bridge_littlefs"
default = true

[[platformio.bridge_profiles]]
name = "littlefs_migration"
extends = "lsh_bridge_littlefs_migration"

[[platformio.bridge_profiles]]
name = "littlefs_debug"
extends = "lsh_bridge_littlefs_debug"

[[platformio.bridge_profiles]]
name = "littlefs_migration_debug"
extends = "lsh_bridge_littlefs_migration_debug"
```

If you do not define `platformio.bridge_profiles`, the generator creates exactly one
bridge profile from `platformio.bridge_base_env`. It is reported as `default` in
`deploy-plan.json` and rendered as the normal `bridge` PlatformIO environment.

With profiles enabled, `bridge` is the friendly alias for the default profile. Explicit
profile environments are also generated, for example `bridge_release`, `bridge_debug`,
`bridge_littlefs`, `bridge_littlefs_migration`, `bridge_littlefs_debug` and
`bridge_littlefs_migration_debug`.

Advanced PlatformIO users still have room to extend. Create your own environment that
extends a generated one, then add local flags, upload ports or extra scripts:

```ini
[env:bridge_j1_lab]
extends = env:bridge_littlefs
build_flags =
    ${env:bridge_littlefs.build_flags}
    -D LSH_DEBUG
```

## Bridge Uploads

For the first flash, use PlatformIO Upload on the selected firmware profile:

- Project Tasks -> `bridge_littlefs` -> Upload

The same action can be scripted:

```bash
platformio run -d bridge -e bridge_littlefs -t upload
```

After the bridge has Wi-Fi/Homie configuration, use the generated custom OTA targets:

- Project Tasks -> `bridge_littlefs` -> Custom -> `LSH OTA j1`
- Project Tasks -> `bridge_littlefs` -> Custom -> `LSH OTA All`

Bridge firmware OTA is MQTT-only. For the standard Homie OTA helper, keep broker and
topic settings in the stack file:

```toml
[deploy.bridge]
default_method = "ota"

[deploy.bridge.ota]
broker_host = "mqtt.local"
broker_port = 1883
broker_username = "homie"
broker_password_env = "LSH_OTA_PASSWORD"
# base_topic defaults to [mqtt].homie_base_path.
homie_version = "5"
timeout = 300
```

When this section is present, `generate` writes `generated/bridge-ota.py` and
`generated/bridge-ota.json`. The Python file is only a wrapper: it finds and executes
the stable `homie-esp8266/scripts/homie_ota.py` entry point from a sibling checkout,
from PlatformIO `libdeps` when the package exports it, or from `LSH_HOMIE_OTA_UPDATER`.
The JSON file holds the broker host, TLS options, Homie base topic and timeout, so
PlatformIO targets stay readable.

The generated JSON stores `base_topic` from `[deploy.bridge.ota].base_topic` when set,
otherwise from `[mqtt].homie_base_path`. Use `broker_password_env` or
`broker_username_env` when secrets should stay outside `lsh_stack.toml`; the Homie OTA
helper reads the environment variable at execution time, so secrets do not appear in
generated PlatformIO commands.

Build-all stays a direct PlatformIO CLI command to avoid nested PlatformIO runs from
inside a custom target:

```bash
platformio run -d bridge \
  -e bridge_release \
  -e bridge_debug \
  -e bridge_littlefs \
  -e bridge_littlefs_migration \
  -e bridge_littlefs_debug \
  -e bridge_littlefs_migration_debug
```

OTA-all is still generated as a PlatformIO custom target on the selected profile
environment because one selected firmware is uploaded to one or more devices:

- Project Tasks -> `bridge_littlefs` -> Custom -> `LSH OTA All`

From the bridge project directory, the equivalent subset OTA form is the OTA helper with
the generated config file and the desired device:

```bash
python ../generated/bridge-ota.py \
  --config ../generated/bridge-ota.json \
  --device-id j1 \
  .pio/build/bridge_littlefs/firmware.bin
```

There is no implicit config lookup: generated PlatformIO targets pass the same
`--config ../generated/bridge-ota.json` argument explicitly. To override any setting for
one run, pass normal Homie OTA arguments after `bridge-ota.py`; CLI arguments override
values from the JSON config.

Configure friendly USB upload environments in TOML:

```toml
[platformio]
core_project = "../core"
bridge_project = "../bridge"
core_base_env = "env:release"
bridge_base_env = "env:release"

[deploy.bridge.devices.j1]
usb_port = "/dev/ttyUSB0"
```

With a `usb_port` or `usb_port_template`, the generator adds explicit USB upload
environments such as `bridge_littlefs_usb_j1` and records the exact commands in
`deploy-plan.json`.

If your project uses a custom base section, point the generated environments at it:

```toml
[platformio]
core_base_env = "common_release"
bridge_base_env = "bridge_base"
```

For controller builds, `platformio-core.ini` adds the `lsh-core` pre-build generator as
an `extra_scripts` entry. The default path targets a normal PlatformIO package install:

```ini
pre:.pio/libdeps/core_j1/lsh-core/tools/platformio_lsh_static_config.py
```

If `[core].tool` points at a local `lsh-core` checkout, the generated fragment derives
the sibling `platformio_lsh_static_config.py` path instead, relative to `core_project`.
Set `platformio.core_extra_script` only when you need to override that derived path
explicitly:

```toml
[core]
tool = "../lsh-core/tools/generate_lsh_static_config.py"

[platformio]
core_project = "../lsh-core-personal"
core_extra_script = "../lsh-core/tools/platformio_lsh_static_config.py"
```

When the core base environment already defines `extra_scripts`, the generated env keeps
those inherited scripts and appends the LSH pre-build generator.

## Persistent Overrides

Use the override layers in this order:

1. Put common user-facing choices in typed TOML fields.
2. Put stack-wide bridge build choices in `[bridge.defaults]`.
3. Put per-device upload endpoints in `[deploy.bridge.devices.<device>]`.
4. Extend generated PlatformIO environments manually only for expert escape hatches.

Typed bridge `defines` replace generated `-D` flags with the same name, so the generated
environment does not contain duplicate conflicting values. A boolean `true` emits a bare
`-DNAME`; a boolean `false` removes the generated define without re-emitting it. Raw
appended flags are added last and are intentionally treated as an expert escape hatch.

```toml
[bridge.defaults.defines]
CONFIG_ARDCOM_SERIAL_RX_PIN = "16U"
CONFIG_ARDCOM_SERIAL_TX_PIN = "17U"
LSH_DEBUG = true

[bridge.defaults.build_flags]
append = ["-Wall"]
```

Precedence is:

1. generated bridge flags from `lsh_devices.toml`;
2. `[bridge.defaults.defines]`;
3. stack-wide max merge for `CONFIG_MAX_*` bridge capacity defines;
4. `[bridge.defaults.build_flags].append`.

There is no `[bridge.devices.<device>]` build override section. Device-specific bridge
build flags would create different bridge binaries, which is exactly what the wide
firmware model avoids.

Keep manual files out of `generated/`. A normal project should place persistent notes,
local scripts and hand-written PlatformIO extensions in `overrides/`,
`core/platformio.ini` or `bridge/platformio.ini`.

`CONFIG_HOMIE_FIRMWARE_VERSION` is not a stack option; it follows the bridge firmware.
`HOMIE_CONVENTION_VERSION` must stay `5`.

## Option Ownership

The stack composer owns options that must stay aligned across repositories. It should
not absorb every low-level firmware or service-manager knob.

| Area                      | Owned by stack TOML                                                                                                                                   | Owned elsewhere                                                                                                                                                  |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Controller profile        | `core.devices`, optional `core.tool`, selected devices and generated PlatformIO environments.                                                         | `lsh_devices.toml`: hardware include, serial objects, controller timing, serial codec, resources, local clicks, indicators, scenes, IDs and advanced core flags. |
| MQTT contract             | MQTT payload codec, LSH base path, Homie base path, service topic, generated bridge topics, coordinator subscriptions and Node-RED protocol fields.   | Broker URL, credentials, TLS files, MQTT client id and service-manager details.                                                                                  |
| Bridge firmware           | Per-device capacity flags, topic flags, QoS policy, serial baud/timeout values mirrored from the controller, serial/MQTT codec flags and upload envs. | ESP32 board selection, Wi-Fi/Homie provisioning, UART RX/TX pins, Homie firmware identity, debug/reset flags, ETL overrides and deep queue/runtime tuning.       |
| Coordinator system config | Device list, network-click actor targets, external actor names, generated `system-config.json` and coordinator timing used by LSH logic.              | Standalone process wiring such as broker connection, TLS, log level, alert publication topic and systemd/container supervision.                                  |
| Node-RED wrapper          | `lsh-logic` fields for protocol, topics, inline system config, context exports, external-actor context and LSH timing.                                | The surrounding flow: MQTT broker node credentials, Home Assistant/Zigbee/Tasmota routing, dashboards and presentation.                                          |

Current coverage is intentionally complete for the LSH contract: one stack TOML can
generate a valid controller build matrix, tailored bridge build matrix, coordinator
system config and Node-RED node config. Advanced firmware tuning remains available in
the consumer PlatformIO projects by extending the generated environments.

If an option affects more than one component, promote it into `lsh_stack.toml`. Good
candidates are future user-facing MQTT QoS policy, bridge UART pin selection and a
standalone coordinator launch/env file. If an option affects only one board, one broker
credential set or one integration flow, keep it in that component's own project.

## Design Rule

The stack composer only owns LSH integration. It produces a complete LSH configuration,
but it does not become a universal automation language or a clone of GUI-owned
configuration formats.

Generate stable contracts, PlatformIO fragments, machine-readable JSON and short
operator checklists. Do not generate full artifacts whose shape is owned by an external
editor unless that format is stable, documented and worth maintaining.

Home Assistant entities, Zigbee2MQTT topics, dashboards and presentation details remain
in their own integration layer.
