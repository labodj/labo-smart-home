# Hardware Overview

This page describes the hardware pattern used in the current Labo Smart Home
installation.

It is not a wiring manual, and it does not replace the official Controllino
documentation, local electrical regulations, or review by a qualified professional. Its
job is narrower: it shows how the public software repositories relate to the hardware in
the reference installation.

The current public LSH reference installation is built around **six Controllino Maxi
PLCs**, each paired with an **ESP32 bridge** inside one of the house electrical panels.

## Installation Pattern

The live installation is built around multiple electrical panels, each centered on a
**Controllino Maxi PLC** and an **ESP32 bridge**.

At a high level, the controller handles field I/O and deterministic local behavior,
while the ESP32 bridge exposes controller state over Wi-Fi through MQTT and Homie.

```text
12/24 VDC power supply
        |
        +-------------------------------> Controllino Maxi
        |
        +--> 5 V buck converter -------> ESP32 bridge

Controllino front TTL interface
        |
        +--> 5 V / 3.3 V logic level shifter --> ESP32 UART

Common ground shared by:
  - Controllino
  - buck converter
  - logic level shifter
  - ESP32 bridge
```

## Representative Hardware Stack

The recurring panel pattern uses a small set of building blocks:

- a **Controllino Maxi** handling the field inputs and outputs
- an **ESP32** acting as the Wi-Fi and MQTT bridge
- a **12 VDC or 24 VDC power supply** feeding the controller side
- a **5 V buck converter** that derives the ESP32 supply from the same DC source
- a **3.3 V / 5 V logic level shifter** on the UART path between controller and bridge
- **external USB extension leads** for bridge maintenance once the panel is closed

Early prototypes used temporary jumper-style wiring on the controller-to-bridge path.
Current revisions use more robust connector-based links.

## Current Panel Snapshot

The image below shows a current panel from the live installation.

<p>
  <img
    src="./assets/photos/current-panel-overview.jpg"
    alt="Current panel with Controllino Maxi and ESP32 bridge"
    width="48%"
  >
</p>

It is useful as a hardware reference because it shows three practical details from the
real build:

- the Controllino and ESP32 bridge live together inside the panel
- the controller-to-bridge connection is no longer loose prototyping wiring
- short external USB leads are kept available for bridge maintenance and firmware
  flashing

## Power Topology

- A 12 VDC or 24 VDC power supply feeds the Controllino.
- The same supply also feeds a buck converter that generates 5 V for the ESP32 bridge.
- Ground is common across the controller and bridge sides.

This keeps the controller power domain simple while allowing the ESP32 to run from a
dedicated low-voltage rail derived from the same source.

## Controller-to-Bridge Interface

The ESP32 bridge is connected to the **front serial / TTL interface** of the
Controllino.

Because the controller and bridge sides do not operate at the same logic level, the UART
path is routed through a **3.3 V to 5 V logic level shifter**.

Practical notes:

- The level shifter sits between the Controllino TTL pins and the ESP32 UART pins.
- The bridge and controller share a common reference ground.
- Current hardware revisions use connector-based wiring rather than temporary jumper-pin
  style connections.

## Panel Serviceability

In the current build, the ESP32 boards live inside the panel, but firmware maintenance
is still practical.

- USB extension cables are routed out of the panel.
- This allows flashing or recovering the bridge firmware without reworking the internal
  wiring.
- The goal is to keep routine bridge maintenance possible even after the panel is closed
  and in regular use.

## Field I/O Model

The Controllino side drives and reads the field wiring.

- Loads can be switched at **12 V / 24 V / 115 V / 230 V**, within the limits documented
  by the official Controllino datasheet and the rest of the installation.
- Wall buttons are powered from the controller power supply, so they stay on the
  low-voltage side of the installation, typically **12 VDC or 24 VDC**.
- Indicator lights are also driven at the controller supply voltage.
- Standard button indicator LEDs do not present special integration issues in this
  setup.

This separation was an important design choice: user-facing button circuits stay at low
voltage, while the controller still manages higher-voltage loads where appropriate.

## Controller and Network Responsibilities

The physical design mirrors the software boundary.

- The **Controllino** remains responsible for the real inputs, relays, indicators, and
  local click behavior.
- The **ESP32 bridge** is responsible for serial transport, Wi-Fi connectivity, MQTT
  exposure, and Homie integration.
- The central **coordinator** manages distributed behavior across panels. It can run as
  a headless service through `labo-smart-home-coordinator` or inside Node-RED with
  `node-red-contrib-lsh-logic`, but it does not replace the controller-side local model.

This matters operationally: local device behavior should remain coherent even when
Wi-Fi, MQTT, or the central logic node are unavailable. The network augments the
installation; it does not define the basic electrical behavior of the panel.

## Why This Hardware Layout

This hardware layout came from practical constraints rather than an idealized bus
architecture.

- The house was renovated incrementally.
- The controllers were distributed across multiple electrical panels.
- A single wired field bus between all panels was not practical in this installation.
- A local Wi-Fi bridge in each panel was the most realistic path to connect the
  distributed controller fleet.

That decision pushed the software architecture toward:

- compact serial payloads between controller and bridge
- MQTT as the transport layer between bridges and the central coordinator
- Homie as the device model exposed by the bridge
- stronger validation and test coverage in the higher-level orchestration logic

For the software map and repository links, use [DOCS.md](./DOCS.md).
