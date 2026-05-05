# Getting Started With LSH

This guide gives you a practical path from "I want to evaluate LSH" to "I know how to
bring up the reference stack without guessing".

It keeps the first run intentionally narrow. Start from the public examples, make one
controller-to-bridge-to-orchestrator path healthy, then customize one layer at a time.
For the broader documentation map, use [DOCS.md](./DOCS.md).

## Before You Start

- If the runtime model is still unclear, read
  [REFERENCE_STACK.md](./REFERENCE_STACK.md).
- If you are already debugging symptoms, use [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).
- If you are still deciding whether LSH fits your project, skim [FAQ.md](./FAQ.md).

## The Public Stack at a Glance

```mermaid
graph LR
  Core["lsh-core<br/>Controller runtime"] <--> Bridge["lsh-bridge<br/>ESP32 bridge"]
  Bridge <--> Broker["MQTT broker"]
  Broker <--> Logic["labo-smart-home-coordinator<br/>Headless orchestration"]
  Broker <--> NodeRed["node-red-contrib-lsh-logic<br/>Node-RED wrapper"]
  Protocol["lsh-protocol<br/>Shared contract"] -. aligns .-> Core
  Protocol -. aligns .-> Bridge
  Protocol -. aligns .-> Logic
  Protocol -. aligns .-> NodeRed
```

## What You Need for a First Full-Stack Lab

For the public reference path you need:

- one controller target supported by `lsh-core`
- one ESP32 target for `lsh-bridge`
- one MQTT broker
- one orchestration runtime:
  [`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator)
  for CLI/library deployments, or
  [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)
  when you want Node-RED

For the reference electrical pattern used by the current examples:

- a Controllino Maxi on the controller side
- an ESP32 on the bridge side
- a UART path between them
- a 3.3 V / 5 V level shifter when the controller side is 5 V logic

For the exact panel pattern, read [HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).

For the controller firmware, start from `lsh-core` v3.0.0 or newer. The documented
configuration path is TOML-based: device topology lives in `lsh_devices.toml`, and
PlatformIO runs a pre-build generator before compiling.

For a finished bridge, coordinator and Node-RED configuration, add `lsh_stack.toml`
after the controller profile is valid. The stack composer reads the controller contract
and generates deployment artifacts without mixing MQTT or Node-RED settings into the
firmware TOML.

If you also want entities in Home Assistant, add an external generic Homie discovery
tool after the LSH path is healthy:
[`homie-home-assistant-discovery`](https://github.com/labodj/homie-home-assistant-discovery)
or
[`node-red-contrib-homie-home-assistant-discovery`](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery).

## First Bring-Up Checks

Most first bring-up problems come from one of these mismatches:

### 1. Serial codec must match

- If `lsh-core` uses `CONFIG_MSG_PACK`, `lsh-bridge` must use `CONFIG_MSG_PACK_ARDUINO`.
- If the bridge also uses `CONFIG_MSG_PACK_MQTT`, the Node-RED node must be set to
  `MsgPack`, and the upstream `mqtt-in` node must emit a `Buffer`.

### 2. Serial baud must match

- `lsh-core`: `CONFIG_COM_SERIAL_BAUD`
- `lsh-bridge`: `CONFIG_ARDCOM_SERIAL_BAUD`

### 3. Topic layout must match

These values must align between the bridge and the coordinator runtime, whether it runs
directly or through Node-RED:

- `CONFIG_MQTT_TOPIC_BASE` ↔ `lshBasePath`
- `CONFIG_MQTT_TOPIC_SERVICE` ↔ `serviceTopic`
- Homie base path ↔ `homieBasePath`

The reference examples use:

- LSH base: `LSH/`
- service topic: `LSH/Node-RED/SRV`
- Homie base: `homie/`

### 4. Bridge capacities must fit the controller

The bridge rejects controller topology that exceeds its compiled limits:

- `CONFIG_MAX_ACTUATORS`
- `CONFIG_MAX_BUTTONS`
- `CONFIG_MAX_NAME_LENGTH`

These limits must be large enough for the `DEVICE_DETAILS` emitted by the controller.

### 5. Orchestrator config must match the actual device topology

In the coordinator config, these must match what the controller really exposes:

- device names
- button IDs
- target device names
- target actuator IDs when `allActuators` is `false`

## First Lab Path

### Step 1. Align on the reference profile

Read [REFERENCE_STACK.md](./REFERENCE_STACK.md) before wiring pieces together. It
defines the topic layout, bootstrap behavior, and role boundaries used by the public
examples.

If a term feels overloaded, skim [GLOSSARY.md](./GLOSSARY.md). If you are still deciding
whether to adopt the stack at all, read [FAQ.md](./FAQ.md) before moving on.

### Step 2. Start from the controller example

Open:

- [`lsh-core/examples/multi-device-project/platformio.ini`](https://github.com/labodj/lsh-core/blob/main/examples/multi-device-project/platformio.ini)
- [`lsh-core/examples/multi-device-project/lsh_devices.toml`](https://github.com/labodj/lsh-core/blob/main/examples/multi-device-project/lsh_devices.toml)
- [`lsh-core/examples/multi-device-project/README.md`](https://github.com/labodj/lsh-core/blob/main/examples/multi-device-project/README.md)

Use that example as the baseline for your controller bring-up.

Important example profiles:

- `J1_release`: lean profile with MsgPack enabled and network-click behavior disabled
- `J2_release`: richer profile with network-click behavior enabled

If you want the simplest first controller test, start from the leaner profile and only
add distributed click logic after the base controller/bridge link is healthy.

A useful controller-only build command is:

```bash
platformio run -d examples/multi-device-project -e J1_release
```

When adapting the example, edit `lsh_devices.toml` first. Keep the generated headers and
`platformio.ini` layout close to the public example until the first device builds,
publishes details, and reports actuator state.

Then create the stack file:

```bash
uv run lsh-stack init
uv run lsh-stack generate lsh_stack.toml --output-dir generated
```

The generated files give you bridge PlatformIO flags, coordinator `systemConfig` and
Node-RED `lsh-logic` settings derived from the same controller profile.

### Step 3. Start from the bridge example

Open:

- [`lsh-bridge/examples/basic-homie-bridge/platformio.ini`](https://github.com/labodj/lsh-bridge/blob/main/examples/basic-homie-bridge/platformio.ini)

This example already reflects the public topic profile:

- `LSH/<device>/conf`
- `LSH/<device>/state`
- `LSH/<device>/events`
- `LSH/<device>/bridge`
- `LSH/<device>/IN`
- `LSH/Node-RED/SRV`

For the first pass, keep topic names, service topic, and codec choices unchanged unless
your hardware or deployment requires a change.

### Step 4. Bring up MQTT and orchestration

Pick the orchestration surface that matches how you want to operate the stack.

Use the standalone package when you want a headless service, CLI process, or custom
Node.js integration:

- [`labo-smart-home-coordinator` README](https://github.com/labodj/labo-smart-home-coordinator)

Use the Node-RED wrapper when you want a visual flow, debug sidebar, and
Node-RED-managed MQTT nodes:

- [`node-red-contrib-lsh-logic` README](https://github.com/labodj/node-red-contrib-lsh-logic)
- [`examples/lsh-logic-example.json`](https://github.com/labodj/node-red-contrib-lsh-logic/blob/main/examples/lsh-logic-example.json)

For Node-RED `v3.0.0+`, paste the system config JSON directly into the node editor. The
reusable examples are:

- [`examples/inline-config.minimal.json`](https://github.com/labodj/node-red-contrib-lsh-logic/blob/main/examples/inline-config.minimal.json)
- [`examples/inline-config.multi-device.json`](https://github.com/labodj/node-red-contrib-lsh-logic/blob/main/examples/inline-config.multi-device.json)

The example flow already shows the intended shape:

- dynamic `mqtt-in` subscription management
- `lsh-logic` as central orchestrator
- MQTT-out for LSH commands
- debug outputs for commands, alerts, topics, and raw traffic

### Step 5. Verify the first healthy signs

When the stack is lined up, the first useful things to look for are:

- a valid `conf` publish for the controller device
- a valid `state` publish for the same device
- bridge-local traffic on `LSH/<device>/bridge`
- controller-backed traffic on `LSH/<device>/events`
- topic subscription updates emitted by the coordinator, or by the Node-RED wrapper's
  Configuration output

If one of those signals is missing, use [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
before changing more variables.

### Step 6. Add richer behavior after the base path works

Once the base stack is healthy, expand in this order:

1. more controller devices
2. network click logic
3. optional external Homie-to-Home-Assistant discovery, after the LSH path is stable
4. MsgPack over MQTT
5. custom topic naming or deployment-specific tuning

## Questions to Ask Before Customizing

Before you customize anything, decide:

- Do you want the public reference topic layout unchanged?
- Do you want JSON first for observability, or MsgPack first for compactness?
- Do you need only local controller logic, or distributed click orchestration too?
- Are you evaluating the stack, or already shaping a deployment?
- Are you changing one variable at a time, or changing hardware, topics, codecs, and
  device names in the same pass?

Those answers tell you how much of the stack to adopt immediately.

For repository links, protocol details, and alternate reading paths, use
[DOCS.md](./DOCS.md).
