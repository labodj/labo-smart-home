# Labo Smart Home

Labo Smart Home, or `LSH`, is a wired, local-first home automation stack for
people who want buttons, relays and indicator LEDs to feel instant,
deterministic and fully under their control.

It was refined over years in a real house installation during and after a
renovation. The core goal stayed the same from day one: keep the physical layer
fast and dependable, while exposing the system cleanly to MQTT, Node-RED and
Home Assistant instead of trapping everything inside one opaque box.

The current reference installation is built around **six Controllino Maxi PLCs**
connected to **ESP32 Wi-Fi bridges**. The controllers handle the physical I/O
and local logic, the bridges expose the runtime over **MQTT** with a **Homie**
device model, and a central **Node-RED** component orchestrates discovery,
health monitoring and distributed automation logic.

This repository is the public entry point for the LSH ecosystem. Its goal is
simple: explain the overall architecture, link the public repositories, and
make the project understandable without forcing visitors to reconstruct the
whole system from four separate codebases.

## Public Scope

The public side of LSH is intentionally split into reusable building blocks.

| Repository                                                                           | Role                                                        | Latest public release                                                                                                                                                                             |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`lsh-core`](https://github.com/labodj/lsh-core)                                     | Arduino / Controllino runtime for the wired controller side | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-core?display_name=tag&sort=semver)](https://github.com/labodj/lsh-core/releases/latest)                                     |
| [`lsh-bridge`](https://github.com/labodj/lsh-bridge)                                 | ESP32 bridge runtime between serial LSH, MQTT and Homie     | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-bridge?display_name=tag&sort=semver)](https://github.com/labodj/lsh-bridge/releases/latest)                                 |
| [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic) | Central orchestration node for Node-RED                     | [![GitHub Release](https://img.shields.io/github/v/release/labodj/node-red-contrib-lsh-logic?display_name=tag&sort=semver)](https://github.com/labodj/node-red-contrib-lsh-logic/releases/latest) |
| [`lsh-protocol`](https://github.com/labodj/lsh-protocol)                             | Shared wire protocol spec, generators and golden payloads   | [![GitHub Release](https://img.shields.io/github/v/release/labodj/lsh-protocol?display_name=tag&sort=semver)](https://github.com/labodj/lsh-protocol/releases/latest)                             |

The release links above always follow each repository's GitHub `releases/latest`
target, and the badges resolve the current published tag dynamically.

Maintained infrastructure forks exist as support repositories, but they are not the main public entry point of the project:

- [`homie-esp8266`](https://github.com/labodj/homie-esp8266)
- [`async-mqtt-client`](https://github.com/labodj/async-mqtt-client)

## Why Builders Pick LSH

LSH is designed to be attractive for both hands-on adopters and detail-driven
developers:

- **Local-first behavior**: buttons, relays and indicators keep making sense even when Wi-Fi or the broker is having a bad day.
- **Clear boundaries**: controller, bridge, orchestration and protocol are separate on purpose, so each part stays understandable and reusable.
- **No mystery contract**: the payload model is explicit, versioned and generated from one shared source of truth.
- **Familiar building blocks**: PlatformIO, MQTT, Homie, Node-RED and Home Assistant make the stack approachable instead of exotic.
- **Real-world shape**: this is not a toy demo; the public repos reflect a system that has already been forced to survive real electrical panels, real timing constraints and real maintenance needs.

## Choose Your Entry Point

Different readers usually need different starting points:

- If you want the whole public stack explained in one place, start with [`REFERENCE_STACK.md`](./REFERENCE_STACK.md).
- If you want the hardware pattern and panel wiring model, read [`HARDWARE_OVERVIEW.md`](./HARDWARE_OVERVIEW.md).
- If you want the shared terminology first, skim [`GLOSSARY.md`](./GLOSSARY.md).
- If you want the shortest answers to evaluation questions, read [`FAQ.md`](./FAQ.md).
- If you want the fastest honest bring-up path, read [`GETTING_STARTED.md`](./GETTING_STARTED.md).
- If you want symptom-based help during bring-up, read [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).
- If you want to build the controller-side firmware, jump to [`lsh-core`](https://github.com/labodj/lsh-core).
- If you want the ESP32 serial-to-MQTT bridge, jump to [`lsh-bridge`](https://github.com/labodj/lsh-bridge).
- If you want the central orchestration layer, jump to [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic).
- If you want the exact wire contract, jump to [`lsh-protocol`](https://github.com/labodj/lsh-protocol).

## Evaluate LSH In 15 Minutes

If you want a fast, honest evaluation before going deep:

1. Read [`REFERENCE_STACK.md`](./REFERENCE_STACK.md) to understand the runtime shape and topic model.
2. Skim [`HARDWARE_OVERVIEW.md`](./HARDWARE_OVERVIEW.md) to see the real controller + bridge pattern.
3. Open the [`lsh-core` multi-device example](https://github.com/labodj/lsh-core/tree/main/examples/multi-device-project) to see how a controller is composed.
4. Open the [`lsh-bridge` basic example](https://github.com/labodj/lsh-bridge/tree/main/examples/basic-homie-bridge) to see how the bridge is embedded.
5. Open the [`node-red-contrib-lsh-logic` examples](https://github.com/labodj/node-red-contrib-lsh-logic/tree/main/examples) to see the expected `system-config.json` and flow shape.

That path is usually enough to decide whether LSH matches your mental model,
your hardware constraints and your preferred tooling.

If you want the operational version of that path, with the alignment checklist
for codecs, topics, baud rates and example assets, read
[`GETTING_STARTED.md`](./GETTING_STARTED.md).
If you want the short decision-oriented answers first, read [`FAQ.md`](./FAQ.md).
If your first lab is partially alive but inconsistent, jump straight to
[`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

## Hardware Notes

The hardware side is now documented separately in [`HARDWARE_OVERVIEW.md`](./HARDWARE_OVERVIEW.md).
The public runtime profile is documented separately in [`REFERENCE_STACK.md`](./REFERENCE_STACK.md).
Shared terminology is documented separately in [`GLOSSARY.md`](./GLOSSARY.md).
The first real bring-up path is documented separately in [`GETTING_STARTED.md`](./GETTING_STARTED.md).
Common evaluation questions and first-lab failure modes are documented in
[`FAQ.md`](./FAQ.md) and [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

That page covers:

- the Controllino Maxi + ESP32 panel pattern used in the live installation
- the 12/24 V supply and 5 V buck conversion path for the bridge
- the TTL serial connection with 3.3 V / 5 V level shifting
- the low-voltage button and indicator wiring model
- the controller-local versus bridge/network responsibility split
- practical maintenance choices such as connectorized controller-to-bridge links and external USB extensions for ESP32 flashing

## Early Build

These WIP photos are from 2019, during the original house renovation and early electrical panel work. They are not polished beauty shots, but they make the project history much more concrete than a clean architecture diagram alone.

<table>
  <tr>
    <td width="50%"><img src="./assets/photos/early-build-cable-bundle.jpg" alt="Early 2019 wiring stage with cable bundle and controller boards"></td>
    <td width="50%"><img src="./assets/photos/early-build-controllino-closeup.jpg" alt="Early Controllino installation close-up inside wall box"></td>
  </tr>
  <tr>
    <td>Early wiring stage while bringing multiple cable runs into the automation stack.</td>
    <td>One of the early Controllino-based installs during integration and bring-up.</td>
  </tr>
</table>

<p>
  <img src="./assets/photos/early-build-panel-progress.jpg" alt="Electrical panel work in progress with breakers and controller hardware" width="48%">
</p>

Panel progress during one of the early integration phases.

## Current Installation Snapshot

This is a current closed-panel snapshot from the live installation. It shows the public hardware pattern more clearly than the early build photos: a Controllino Maxi paired with an internal ESP32 bridge, solid controller-to-bridge wiring, and external USB extensions kept available for bridge firmware maintenance.

<p>
  <img src="./assets/photos/current-panel-overview.jpg" alt="Current electrical panel snapshot with Controllino Maxi, internal ESP32 bridge and external USB service leads" width="48%">
</p>

## Runtime Architecture

```text
+------------------+     +------------------+     +-------------+     +---------------------------+     +----------------+
| lsh-core         |<--->| lsh-bridge       |<--->| MQTT broker |<--->| node-red-contrib-lsh-logic|---->| Home Assistant |
| Controllino side |     | ESP32 bridge     |     | transport   |     | orchestration             |     | UI / entities  |
+------------------+     +------------------+     +-------------+     +---------------------------+     +----------------+
```

| Repository                   | Runtime responsibility                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------- |
| `lsh-core`                   | Wired controller runtime: physical I/O, local logic, compact payloads                       |
| `lsh-bridge`                 | ESP32 bridge runtime: serial handshake, MQTT transport, Homie model, cached snapshot replay |
| `node-red-contrib-lsh-logic` | Central orchestration: registry, watchdog, startup recovery, distributed logic              |
| `lsh-protocol`               | Shared wire contract: command IDs, compact keys, generators, golden payloads                |

For the concrete public MQTT/Homie/Node-RED profile that ties those roles
together, read [`REFERENCE_STACK.md`](./REFERENCE_STACK.md).

Practical boundary summary:

- `lsh-core` owns wired I/O, device topology, local click handling and compact payload encoding.
- `lsh-bridge` owns the serial handshake, MQTT transport, Homie exposure, cached snapshot replay and bridge-side state synchronization.
- `node-red-contrib-lsh-logic` owns registry state, watchdog logic, startup recovery, discovery and distributed click orchestration.
- `lsh-protocol` keeps command IDs, compact keys, compatibility metadata and generated artifacts aligned across the stack.

## Why The Split Exists

LSH did not begin as a clean public multi-repo design.

The earliest versions were much more monolithic, and a lot of the automation logic lived in large Node-RED flows. Over time, the stack was progressively refactored into clearer boundaries:

- a reusable controller runtime instead of a one-off firmware tree
- a reusable ESP32 bridge runtime instead of a tightly coupled bridge project
- a standalone protocol source of truth instead of implicit duplicated constants
- a tested TypeScript Node-RED node instead of increasingly fragile visual flow logic

That split is intentional. Each public repository has one clear job, one clear
audience and one clear documentation surface. The result is easier adoption,
easier maintenance and fewer hidden assumptions.

## Technical Direction

A few design choices stayed constant through the years:

- wired controllers first, network second
- local logic must keep working even when Wi-Fi or the broker misbehaves
- explicit protocol contracts beat copy-pasted constants
- resource usage matters on both AVR and ESP32 targets
- topology is treated as static between controller boots

## Start Here

If you want to understand the project quickly, this is the shortest path:

1. Read [`REFERENCE_STACK.md`](./REFERENCE_STACK.md) for the public reference profile and topic model.
2. Skim [`GLOSSARY.md`](./GLOSSARY.md) if the terminology is still unfamiliar.
3. Read [`FAQ.md`](./FAQ.md) if you want the shortest path through the common adoption questions.
4. Read [`GETTING_STARTED.md`](./GETTING_STARTED.md) if your next step is a real lab bring-up.
5. Keep [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) nearby once you start wiring or exchanging real traffic.
6. Read [`lsh-core`](https://github.com/labodj/lsh-core) to understand the controller-side runtime model.
7. Read [`lsh-bridge`](https://github.com/labodj/lsh-bridge) to see how the serial side is exposed over MQTT and Homie.
8. Read [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic) for the orchestration layer.
9. Read [`lsh-protocol`](https://github.com/labodj/lsh-protocol) if you want the exact shared payload contract.

## Public History

The repositories were opened publicly only after years of real-world use,
refactoring and cleanup. The public release therefore reflects the current
reusable architecture, not the original historical monoliths.

This landing repository is maintained as the live documentation hub for the
public LSH ecosystem. It is not a separately versioned software artifact; the
actual component release history lives in the repositories linked above.
