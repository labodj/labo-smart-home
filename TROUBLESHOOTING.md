# LSH Troubleshooting

This page is the shortest path from "something is off" to "I know which layer
to inspect next".

For the normal adoption path, read [GETTING_STARTED.md](./GETTING_STARTED.md).
For the runtime model behind these checks, read
[REFERENCE_STACK.md](./REFERENCE_STACK.md).

## First 60-Second Triage

If you only have one minute, use this shortcut:

- no MQTT at all: inspect bridge connectivity and Homie setup first
- `bridge` traffic but no `conf/state/events`: inspect the controller serial
  path first
- retained `conf/state` but device still feels offline: inspect live
  reachability, not retained data
- click request appears but no action happens: inspect the coordinator config
  and the click handshake
- commands hit `IN` but actuators do not move: inspect codec, payload shape and
  bridge diagnostics

## What Good Looks Like

In a healthy first bring-up, you should be able to observe all of these:

- `LSH/<device>/conf` appears with a valid topology snapshot
- `LSH/<device>/state` appears with a valid actuator snapshot
- `LSH/<device>/bridge` carries bridge-local runtime traffic and diagnostics
- `LSH/<device>/events` carries controller-backed runtime traffic
- the coordinator, or the Node-RED wrapper's Configuration output, exports the
  topic set it wants to subscribe to

If one of those layers is missing, the symptom usually already tells you where
to look first.

## Where To Observe The Stack

- `lsh-core`: controller serial behavior, compile-time flags, configured device
  topology
- `lsh-bridge`: MQTT `bridge` topic, runtime diagnostics, bridge compile-time
  settings
- `labo-smart-home-coordinator`: CLI/library diagnostics, startup recovery
  behavior and config alignment
- `node-red-contrib-lsh-logic`: Node-RED debug outputs, status and inline
  config alignment
- MQTT broker: retained `conf` and `state`, live `events`, inbound `IN`
  commands and service-topic traffic

## Fast Diagnosis Map

### I see no MQTT traffic from the device at all

Look at the bridge first.

Most likely causes:

- the ESP32 bridge is not connected to Wi-Fi or MQTT yet
- Homie setup is incomplete
- the bridge firmware/config was not flashed as expected
- the bridge is not reaching the controller or broker at runtime

Start with:

- `lsh-bridge` example `platformio.ini`
- Homie configuration state
- MQTT broker credentials and host settings in the embedding project

### I get `LSH/<device>/bridge` replies, but no `conf`, `state` or `events`

The bridge is alive, but the controller path is not healthy or not synchronized.

Most likely causes:

- serial baud mismatch
- serial codec mismatch
- UART pin mismatch
- missing 3.3 V / 5 V level shifting on the serial path
- controller not booting or not reaching its configured runtime

Check first:

- `CONFIG_COM_SERIAL_BAUD` in `lsh-core`
- `CONFIG_ARDCOM_SERIAL_BAUD` in `lsh-bridge`
- `CONFIG_MSG_PACK` in `lsh-core`
- `CONFIG_MSG_PACK_ARDUINO` in `lsh-bridge`
- bridge UART pin settings

This is the classic "bridge is reachable, controller is not" case.

### A service-topic `PING` works, but a device-topic `PING` does not

Treat that as a precise clue.

It means the bridge can answer bridge-local health probes, but it does not
currently trust the downstream controller path enough to answer a
controller-backed device probe.

Look for:

- controller link loss
- incomplete bootstrap
- stale or missing controller state synchronization

### `conf` appears, but `state` never appears

The bridge probably accepted controller details but never completed the
follow-up state phase.

Look for:

- controller-side startup issues after configuration
- topology or capacity mismatch between controller and bridge
- a bridge runtime that is stuck waiting for `ACTUATORS_STATE`

Check:

- bridge capacities: `CONFIG_MAX_ACTUATORS`, `CONFIG_MAX_BUTTONS`,
  `CONFIG_MAX_NAME_LENGTH`
- whether the controller example/profile you started from actually matches the
  device you flashed

### I can see retained `conf` and `state`, but the device still behaves offline

That can be completely normal.

Retained snapshots are the last known authoritative state. They are not proof
that the controller is reachable right now.

Use live signals to decide reachability:

- a current `ready` transition on the Homie side
- live `events`
- live `state`
- a successful controller-backed device `PING`

### The coordinator starts and immediately requests startup `BOOT`

This is expected only when at least one configured device is still missing an
authoritative `conf + state` snapshot.

If it keeps happening unexpectedly, check:

- device names in the coordinator config JSON
- `lshBasePath`, `homieBasePath` and `serviceTopic`
- whether the broker still retains the expected `conf` and `state` snapshots
- whether the coordinator or Node-RED wrapper is subscribing to the same topic
  layout the bridge publishes

### Network click requests appear, but the distributed action never fires

Look at the handshake, not just the first request.

The happy path is:

1. `NETWORK_CLICK_REQUEST` on `events`
2. `NETWORK_CLICK_ACK` on `IN`
3. `NETWORK_CLICK_CONFIRM` on `events`
4. only then does Node-RED execute the distributed action

Most likely causes:

- the coordinator config does not describe the button/actor mapping correctly
- the coordinator never emits the ACK
- the ACK is emitted on the wrong topic
- click timeout expires before the handshake completes

Check:

- device names
- button IDs
- target actuator IDs
- `serviceTopic` and base topic settings
- coordinator logs, or Node-RED debug outputs, for command emission

### Commands are published to `IN`, but the actuator does not change

Look for one of these:

- wrong device topic
- wrong payload codec for that hop
- malformed command payload
- bridge command rejection or queue overflow

The bridge can emit diagnostics on `LSH/<device>/bridge`, including:

- `mqtt_queue_overflow`
- `mqtt_command_rejected`
- `actuator_command_storm_dropped`

If those appear, the bridge is telling you the command path is the problem, not
the UI layer.

### MQTT payloads look like unreadable binary

That usually means MQTT MsgPack is enabled and the tool reading the topic
expects text.

Check:

- `CONFIG_MSG_PACK_MQTT` in `lsh-bridge`
- `protocol` in the coordinator or Node-RED node
- upstream Node-RED `mqtt-in` payload type

For first bring-up, prefer readable MQTT payloads unless compact MQTT payloads
are a deliberate requirement.

### Home Assistant entities are missing or oddly named

Look at discovery shaping, not the low-level serial link.

Check:

- the companion Homie-to-Home-Assistant discovery package configuration
- discovery overrides in that package
- whether Homie topics are present and stable

## First-Lab Mistakes That Waste Time

- changing topic names before the stock examples work
- changing both codec and topic layout at the same time
- assuming retained snapshots prove current liveness
- debugging the coordinator or Node-RED wrapper before verifying the
  controller/bridge serial link
- enabling richer network-click behavior before the base `conf + state` path is
  healthy

## When To Stop Customizing And Compare With The Public Examples

If you have already changed more than one of these, stop and compare against the
bundled examples:

- topic base or service topic
- serial codec
- UART pin map
- coordinator config device names
- controller environment/profile

The quickest path back to a known-good mental model is usually:

1. controller example from `lsh-core`
2. bridge example from `lsh-bridge`
3. coordinator config from `labo-smart-home-coordinator`, or example flow and
   inline config from `node-red-contrib-lsh-logic`

## Need The Underlying Details?

- Architecture and semantics: [REFERENCE_STACK.md](./REFERENCE_STACK.md)
- First bring-up path: [GETTING_STARTED.md](./GETTING_STARTED.md)
- Adoption questions: [FAQ.md](./FAQ.md)
- Shared terms: [GLOSSARY.md](./GLOSSARY.md)
- Controller docs: <https://github.com/labodj/lsh-core>
- Bridge runtime docs:
  <https://github.com/labodj/lsh-bridge/blob/main/docs/runtime-behavior.md>
- Headless coordinator docs:
  <https://github.com/labodj/labo-smart-home-coordinator>
- Node-RED wrapper docs:
  <https://github.com/labodj/node-red-contrib-lsh-logic>
