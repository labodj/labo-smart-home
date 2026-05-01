# Labo Smart Home

Labo Smart Home, or `LSH`, is a wired, local-first home automation stack for people who
want wall buttons, relays and indicator LEDs to feel instant, predictable and fully
under their control.

It grew inside a real house installation during and after a renovation. The goal stayed
the same from the first build: keep the physical layer dependable, then expose it
cleanly to MQTT, Node-RED and Home Assistant instead of hiding everything inside one
opaque box.

The current reference installation uses **six Controllino Maxi PLCs**, each paired with
an **ESP32 Wi-Fi bridge**. The controllers own the physical I/O and local behavior. The
bridges publish that runtime over **MQTT** with a **Homie** device model. Distributed
logic can run either in **Node-RED** or as a headless **Node.js coordinator**.

This repository is the public front door for the LSH ecosystem. It explains the shape of
the stack and points to the reusable repositories without making you reconstruct the
whole system from separate codebases.

## What LSH Is

LSH is for installations where wired field control matters: real buttons, real relays,
visible indicators, local fallback behavior and explicit integration with the network
layer.

The public stack is split into clear responsibilities:

- controllers keep physical inputs and outputs usable even when the network is
  unavailable
- ESP32 bridges expose controller state and commands over MQTT/Homie
- a coordinator handles distributed behavior that needs a system-wide view
- Node-RED can host that coordinator when you want a visual automation surface
- the protocol repository keeps the wire contract explicit and generated

LSH is not a generic plug-and-play smart-home product. It is also not the shortest path
for a few Wi-Fi bulbs. It is a documented, reusable automation stack for people who are
comfortable owning their electrical design, firmware builds and runtime services.

## Why People Study It

- **Local-first behavior**: buttons, relays and indicators keep making sense even when
  Wi-Fi or the broker is unavailable.
- **Clear boundaries**: controller, bridge, orchestration and protocol each have one
  job.
- **Explicit contracts**: command IDs, compact keys and payload shapes live in one
  shared protocol source.
- **Familiar tools**: PlatformIO, MQTT, Homie, Node.js, Node-RED and Home Assistant are
  used where they fit naturally.
- **Real installation pressure**: the public repositories reflect a system that has
  lived with real panels, timing constraints and maintenance needs.

## Current Installation

The photo below shows the current panel pattern: a Controllino Maxi paired with an
internal ESP32 bridge, a solid controller-to-bridge link and external USB service leads
kept available for bridge firmware maintenance.

<p>
  <img
    src="./assets/photos/current-panel-overview.jpg"
    alt="Current panel with Controllino Maxi and ESP32 bridge"
    width="58%"
  >
</p>

Early photos are less polished, but useful. They show the project as it really started:
cable runs, controller bring-up and panel work during the house renovation.

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
    <td>Early wiring while bringing multiple cable runs into the automation stack.</td>
    <td>One of the first Controllino-based installs during integration.</td>
  </tr>
</table>

For the power, UART, level-shifting and panel serviceability details, read
[HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).

## Public Repositories

| Repository                                                                             | Role                                                          | Latest public release                                                                                                                                                                               |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`lsh-core`](https://github.com/labodj/lsh-core)                                       | Arduino / Controllino runtime for the wired controller side   | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-core?display_name=tag&sort=semver)](https://github.com/labodj/lsh-core/releases/latest)                                       |
| [`lsh-bridge`](https://github.com/labodj/lsh-bridge)                                   | ESP32 bridge between serial LSH, MQTT and Homie               | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-bridge?display_name=tag&sort=semver)](https://github.com/labodj/lsh-bridge/releases/latest)                                   |
| [`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator) | Standalone orchestration runtime for CLI and Node.js services | [![GitHub Release](https://img.shields.io/github/v/release/labodj/labo-smart-home-coordinator?display_name=tag&sort=semver)](https://github.com/labodj/labo-smart-home-coordinator/releases/latest) |
| [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)   | Node-RED wrapper around the coordinator runtime               | [![GitHub Release](https://img.shields.io/github/v/release/labodj/node-red-contrib-lsh-logic?display_name=tag&sort=semver)](https://github.com/labodj/node-red-contrib-lsh-logic/releases/latest)   |
| [`lsh-protocol`](https://github.com/labodj/lsh-protocol)                               | Shared protocol spec, generators and golden payloads          | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-protocol?display_name=tag&sort=semver)](https://github.com/labodj/lsh-protocol/releases/latest)                               |

Maintained infrastructure forks exist as support repositories, but they are not the main
entry point: [`homie-esp8266`](https://github.com/labodj/homie-esp8266) and
[`async-mqtt-client`](https://github.com/labodj/async-mqtt-client).

## Runtime Shape

```text
+------------------+     +------------------+     +-------------+     +-----------------------------+     +----------------+
| lsh-core         |<--->| lsh-bridge       |<--->| MQTT broker |<--->| coordinator / Node-RED node |---->| Home Assistant |
| Controllino side |     | ESP32 bridge     |     | transport   |     | orchestration               |     | UI / entities  |
+------------------+     +------------------+     +-------------+     +-----------------------------+     +----------------+
```

Practical boundary summary:

- `lsh-core` owns wired I/O, device topology, local click handling and compact payload
  encoding.
- `lsh-bridge` owns the serial handshake, MQTT transport, Homie exposure, cached
  snapshot replay and bridge-side synchronization.
- `labo-smart-home-coordinator` owns registry state, watchdog logic, startup recovery
  and distributed click orchestration.
- `node-red-contrib-lsh-logic` hosts that coordinator inside Node-RED.
- `lsh-protocol` keeps command IDs, compact keys, compatibility metadata and generated
  artifacts aligned across the stack.

For the exact MQTT topics, bootstrap rules, `PING`, `BOOT` and network-click semantics,
read [REFERENCE_STACK.md](./REFERENCE_STACK.md).

## Start Reading

- Use [DOCS.md](./DOCS.md) as the central map of the public documentation.
- Follow [GETTING_STARTED.md](./GETTING_STARTED.md) when you want a first end-to-end lab
  path.
- Keep [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) nearby once real MQTT traffic and
  hardware are involved.

If you are evaluating LSH for adoption, keep the public examples close to stock for the
first successful run. Avoid changing topics, codecs, device names and hardware
assumptions all at once. Get one clean controller, bridge and orchestrator path working
first, then customize one layer at a time.

## Technical Direction

A few design choices stayed constant through the years:

- wired controllers first, network second
- local logic must keep working when Wi-Fi or the broker misbehaves
- explicit protocol contracts beat copy-pasted constants
- resource usage matters on both AVR and ESP32 targets
- topology is treated as static between controller boots

Since `lsh-core` `v3.0.0`, controller topology is configured from TOML and compiled into
optimized static profiles. A new adopter edits `lsh_devices.toml`; a typical device
profile no longer needs hand-written C++ topology code or hand-maintained actuator ID
lookup tables.

## Public History

LSH did not begin as a clean public multi-repo design. Early versions were much more
monolithic, and a lot of automation logic lived in large Node-RED flows. Over time, the
stack was split into reusable pieces: controller runtime, ESP32 bridge runtime, protocol
source of truth, standalone coordinator and a thin Node-RED wrapper.

The repositories were opened publicly only after years of real-world use, refactoring
and cleanup. This landing repository is not a separately versioned software artifact;
component release history lives in the repositories listed above.
