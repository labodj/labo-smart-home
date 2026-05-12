# Labo Smart Home

Labo Smart Home (`LSH`) is a wired, local-first home automation stack for installations
where wall buttons, relays, and indicator LEDs need to remain responsive, predictable,
and under local control.

The project grew out of a home installation that began during a renovation and kept
evolving afterward. The core design goal has not changed: keep the wired controls
dependable, then expose their state and commands cleanly through MQTT/Homie and the
orchestration layer instead of hiding the system inside a single opaque box.

The current reference installation uses **six Controllino Maxi PLCs**, each paired with
an **ESP32 Wi-Fi bridge**. The PLCs handle physical I/O and local behavior. The bridges
publish controller state over **MQTT** using the **Homie** device model. The
orchestration layer can run in **Node-RED** or as a headless **Node.js coordinator**.

This repository is the public entry point for LSH. It shows how the pieces fit together,
where each component lives, which docs to read next, and now also hosts the stack
composer that turns controller contracts into bridge firmware fragments, coordinator
configuration and Node-RED node settings.

## What LSH Is

LSH is a reference stack for wired home automation. A Controllino controller keeps local
inputs and outputs usable without the network. An ESP32 bridge publishes state and
accepts commands over MQTT/Homie. A coordinator adds behavior that needs system-wide
context, while a shared protocol package keeps compact payloads aligned across the
components.

The public repositories are installable packages rather than only source snapshots: the
controller and bridge libraries are available through PlatformIO, and the orchestration
layer can be used either from Node-RED or as a standalone Node.js runtime.

You can adopt the stack in two ways. The recommended first route is the stack
configurator: edit one controller TOML file, edit one stack TOML file, then generate the
PlatformIO fragments and orchestration settings. The manual route is still available for
existing projects, but then you keep controller, bridge, MQTT, coordinator and Node-RED
values aligned yourself.

LSH is not a packaged plug-and-play smart-home product or the simplest path for a few
Wi-Fi bulbs. It fits projects whose maintainers are comfortable with electrical
planning, firmware builds, MQTT services, and gradual integration.

## When LSH Fits

- Your wired controls need to keep working when Wi-Fi or the MQTT broker is unavailable.
- You prefer small components with clear boundaries over a single all-in-one automation
  box.
- You want command IDs, compact keys, and payload shapes defined in one place.
- You already use, or can reasonably adopt, tools such as PlatformIO, MQTT, Homie,
  Node.js, or Node-RED.
- You are looking for a reference implementation shaped by real panels, timing
  constraints, and maintenance work.

## Current Installation

The photo below shows the current panel layout: a Controllino Maxi paired with an
internal ESP32 bridge, a dedicated controller-to-bridge link, and external USB service
leads kept available for firmware maintenance.

<p>
  <img
    src="./assets/photos/current-panel-overview.jpg"
    alt="Current panel with Controllino Maxi and ESP32 bridge"
    width="58%"
  >
</p>

The early photos show how the project started: cable runs, controller bring-up and panel
work during the house renovation.

<table>
  <tr>
    <td width="50%">
      <img
        src="./assets/photos/early-build-cable-bundle.jpg"
        alt="Early 2019 wiring stage with cable bundle and controller boards"
      >
    </td>
    <td width="50%">
      <img
        src="./assets/photos/early-build-controllino-closeup.jpg"
        alt="Early Controllino installation close-up inside wall box"
      >
    </td>
  </tr>
  <tr>
    <td>Early wiring while bringing multiple cable runs into the system.</td>
    <td>One of the first Controllino-based installations during integration.</td>
  </tr>
</table>

For details on power, UART, level shifting, and panel serviceability, read
[HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).

## Public Repositories

| Repository                                                                             | Role                                                          | Latest public release                                                                                                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`lsh-core`](https://github.com/labodj/lsh-core)                                       | Arduino/Controllino runtime for wired controller-side logic   | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-core?display_name=tag&sort=semver)](https://github.com/labodj/lsh-core/releases/latest) [![PlatformIO Registry](https://badges.registry.platformio.org/packages/labodj/library/lsh-core.svg)](https://registry.platformio.org/libraries/labodj/lsh-core)                |
| [`lsh-bridge`](https://github.com/labodj/lsh-bridge)                                   | ESP32 bridge for serial LSH protocol and MQTT/Homie exposure  | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-bridge?display_name=tag&sort=semver)](https://github.com/labodj/lsh-bridge/releases/latest) [![PlatformIO Registry](https://badges.registry.platformio.org/packages/labodj/library/lsh-bridge.svg)](https://registry.platformio.org/libraries/labodj/lsh-bridge)        |
| [`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator) | Standalone orchestration runtime for CLI and Node.js services | [![GitHub Release](https://img.shields.io/github/v/release/labodj/labo-smart-home-coordinator?display_name=tag&sort=semver)](https://github.com/labodj/labo-smart-home-coordinator/releases/latest) [![npm](https://img.shields.io/npm/v/labo-smart-home-coordinator.svg)](https://www.npmjs.com/package/labo-smart-home-coordinator)         |
| [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)   | Node-RED wrapper around the coordinator runtime               | [![GitHub Release](https://img.shields.io/github/v/release/labodj/node-red-contrib-lsh-logic?display_name=tag&sort=semver)](https://github.com/labodj/node-red-contrib-lsh-logic/releases/latest) [![Node-RED Library](https://img.shields.io/badge/Node--RED-Library-8f0000.svg)](https://flows.nodered.org/node/node-red-contrib-lsh-logic) |
| [`lsh-protocol`](https://github.com/labodj/lsh-protocol)                               | Shared protocol spec, generators, and golden payloads         | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-protocol?display_name=tag&sort=semver)](https://github.com/labodj/lsh-protocol/releases/latest)                                                                                                                                                                         |

Optional Home Assistant discovery is handled outside LSH by generic Homie discovery
projects, not by the LSH coordinator:

| Repository                                                                                                                     | Role                                         | Latest public release                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`homie-home-assistant-discovery`](https://github.com/labodj/homie-home-assistant-discovery)                                   | Standalone daemon or embeddable Node.js core | [![GitHub Release](https://img.shields.io/github/v/release/labodj/homie-home-assistant-discovery?display_name=tag&sort=semver)](https://github.com/labodj/homie-home-assistant-discovery/releases/latest) [![npm](https://img.shields.io/npm/v/homie-home-assistant-discovery.svg)](https://www.npmjs.com/package/homie-home-assistant-discovery)                                                            |
| [`node-red-contrib-homie-home-assistant-discovery`](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery) | Node-RED wrapper for Homie discovery         | [![GitHub Release](https://img.shields.io/github/v/release/labodj/node-red-contrib-homie-home-assistant-discovery?display_name=tag&sort=semver)](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery/releases/latest) [![Node-RED Library](https://img.shields.io/badge/Node--RED-Library-8f0000.svg)](https://flows.nodered.org/node/node-red-contrib-homie-home-assistant-discovery) |

Maintained infrastructure forks are available when needed, but they are supporting code
rather than starting points. The
[`homie-esp8266`](https://github.com/labodj/homie-esp8266) fork is published as
[`labodj/homie-v5`](https://registry.platformio.org/libraries/labodj/homie-v5) for
ESP8266/ESP32 Arduino projects that need Homie 3.0.1 compatibility plus opt-in Homie
v4/v5 discovery modes. The MQTT client fork lives at
[`async-mqtt-client`](https://github.com/labodj/async-mqtt-client).

## Runtime Shape

```text
+------------------+     +------------------+     +-------------+     +-----------------------------+
| lsh-core         |<--->| lsh-bridge       |<--->| MQTT broker |<--->| coordinator / Node-RED node |
| Controllino side |     | ESP32 bridge     |     | transport   |     | orchestration               |
+------------------+     +------------------+     +-------------+     +-----------------------------+
```

Practical boundary summary:

- `lsh-core` implements wired I/O, device topology, local click handling and compact
  payload encoding.
- `lsh-bridge` handles the serial handshake, MQTT transport, Homie exposure, cached
  snapshot replay and bridge-side synchronization.
- `labo-smart-home-coordinator` maintains registry state, watchdog logic, startup
  recovery, and distributed click orchestration.
- `node-red-contrib-lsh-logic` runs the coordinator inside Node-RED.
- `lsh-protocol` keeps command IDs, compact keys, compatibility metadata, and generated
  artifacts in sync across the components.

Home Assistant is not part of the LSH runtime path. If you want Home Assistant MQTT
discovery, attach a generic Homie discovery daemon or Node-RED discovery node to the
Homie topics published by `lsh-bridge`.

For the exact MQTT topics, bootstrap rules, `PING`, `BOOT`, and network-click semantics,
read [REFERENCE_STACK.md](./REFERENCE_STACK.md).

## Start Reading

- Use [DOCS.md](./DOCS.md) as the public documentation map.
- Follow [GETTING_STARTED.md](./GETTING_STARTED.md) for a first end-to-end lab setup.
- Use [STACK_CONFIG.md](./STACK_CONFIG.md) when you want one TOML file to generate
  bridge, coordinator and Node-RED configuration from a controller profile.
- Keep [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) nearby once real MQTT traffic and
  hardware are involved.

If you are evaluating LSH for adoption, keep the public examples close to the stock
configuration for the first successful run. Avoid changing topics, codecs, device names,
and hardware assumptions all at once. Get a clean controller-to-bridge-to-coordinator
chain working first, then customize one layer at a time.

## Technical Direction

A few design choices have stayed consistent through the years:

- wired controllers first, network second
- local logic must keep working when Wi-Fi or the broker misbehaves
- shared protocol contracts avoid copy-pasted constants
- resource usage matters on both AVR and ESP32 targets
- topology is treated as static between controller boots

Since `lsh-core` v3.0.0, controller topology is configured from TOML and compiled into
optimized static profiles. New adopters typically edit `lsh_devices.toml`; a device
profile no longer needs hand-written C++ topology code or hand-maintained actuator ID
lookup tables.

The public stack composer adds the deployment layer on top of that controller profile.
`lsh_stack.toml` keeps MQTT codec choices, Node-RED context exports and distributed
network-click actor targets outside the firmware TOML, while still generating the
bridge/coordinator contract and exact Node-RED node settings. It also emits PlatformIO
fragments for per-device controller environments and stack-wide bridge firmware
profiles, so every bridge device can run the same selected bridge binary while keeping
device-specific uploads as IDE targets.

The normal starting point is one personal installation folder with two normal PlatformIO
projects inside it:

If `lsh-stack` is already installed:

```bash
lsh-stack new my-lsh-installation
cd my-lsh-installation
lsh-stack setup
```

From a GitHub Release, you can use the single-file launcher without checking out this
repository:

```bash
python /path/to/lsh-stack.pyz new my-lsh-installation
cd my-lsh-installation
python /path/to/lsh-stack.pyz setup
```

From a checkout of this repository, use the standard Python launcher script. On Windows,
use `py` instead of `python` if that is how Python is installed:

```bash
python /path/to/labo-smart-home/lsh-stack.py new my-lsh-installation
cd my-lsh-installation
python /path/to/labo-smart-home/lsh-stack.py setup
```

If you only want to evaluate or build `lsh-core` firmware first, create a standalone
controller project instead of the whole stack:

```bash
lsh-stack new-core my-lsh-core
cd my-lsh-core
platformio run -e core_panel
```

`new` writes `core/platformio.ini` and `bridge/platformio.ini` once, then leaves those
manual files alone. If you already have only `lsh_stack.toml` and `lsh_devices.toml`,
`setup` creates the missing core/bridge PlatformIO shells beside them without
overwriting existing project files. Use either VSCode with the PlatformIO extension or
the `platformio` CLI if it is available. The `setup` command runs the normal first-use
sequence: it installs/builds the starter core once when the PlatformIO CLI is available,
regenerates `generated/`, checks the stack and prints the next build targets. The
lower-level `generate` command still replaces only the files in `generated/`.

For local or symlinked controller checkouts, set `[core].tool`; generated controller
environments then use the matching local `platformio_lsh_static_config.py` instead of a
`.pio/libdeps` path.

Edit `core/lsh_devices.toml` and `lsh_stack.toml`; treat `generated/` as disposable;
keep persistent manual extensions in `overrides/` or in the `core/` and `bridge/`
PlatformIO files.

For Node-RED, install `node-red-contrib-lsh-logic`, add the node to a flow and follow
`generated/node-red-setup.md`. The generator gives exact copy-paste values for the
`lsh-logic` node, while MQTT broker settings and the surrounding flow stay in Node-RED.

For bridge builds and uploads, use the generated PlatformIO environments from the IDE or
CLI. Profile tasks such as `bridge_littlefs` build one wide firmware shared by every
bridge device. The same profile exposes `LSH OTA j1`, `LSH OTA j2` and `LSH OTA All`
custom targets for Homie/MQTT OTA in the PlatformIO IDE. For CLI use, the stack command
can build the default bridge profile and OTA-upload one device, a subset, or every
bridge:

```bash
lsh-stack ota j1
lsh-stack ota j1 j2
lsh-stack ota
```

If a prerequisite is missing, the command exits with the install command to run.

## Public History

LSH did not begin as a clean public multi-repo design. Early versions were much more
monolithic, and a lot of automation logic lived in large Node-RED flows. Over time, the
project was split into reusable pieces: controller runtime, ESP32 bridge runtime,
protocol source of truth, standalone coordinator and a thin Node-RED wrapper.

The repositories were published after years of real-world use, refactoring and cleanup.
This repository remains the reference-stack entry point, not a runtime peer like
`lsh-core` or `lsh-bridge`. Its active software surface is intentionally small: the
`lsh-stack` composer and the quality gates around the public documentation and examples.
Component release history still lives in the runtime repositories listed above.
