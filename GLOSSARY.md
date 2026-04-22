# LSH Glossary

This page collects the core terms used across the public LSH repositories.

If you are new to the project, skim this once before diving into the individual
README files. Most cross-repo confusion comes from the same few words being used
very precisely.

If you are still deciding whether LSH fits your use case, pair this page with
[FAQ.md](./FAQ.md). If you are already wiring a first lab, keep
[GETTING_STARTED.md](./GETTING_STARTED.md) and
[TROUBLESHOOTING.md](./TROUBLESHOOTING.md) nearby too.

## Core Roles

- **Controller**: the device that owns the real field I/O. In the public
  reference stack this is `lsh-core` running on a Controllino or Arduino-class
  controller.
- **Bridge**: the adapter between the controller link and MQTT/Homie. In the
  public reference stack this is `lsh-bridge` on ESP32.
- **Orchestrator**: the higher-level automation peer that coordinates multiple
  devices over MQTT. In the public reference stack this is
  `node-red-contrib-lsh-logic`.
- **Protocol source of truth**: the repository that owns command IDs, wire keys
  and generated artifacts. In the public stack this is `lsh-protocol`.

## State And Synchronization

- **Authoritative**: the source that currently owns the truth for a specific
  piece of data. In the public stack, controller topology and actuator state are
  authoritative on the controller side.
- **Topology**: the declared device identity plus the actuator and button layout
  exposed by `DEVICE_DETAILS`.
- **Runtime state**: the current actuator snapshot exposed by `ACTUATORS_STATE`.
- **Snapshot**: a complete payload used to rebuild current knowledge of topology
  or state.
- **Retained snapshot**: the last authoritative `conf` or `state` payload kept
  by the broker. Useful for startup recovery, but not proof of current
  reachability.
- **Cached topology**: a previously validated `DEVICE_DETAILS` snapshot stored
  by the bridge for reuse across reboots.
- **Runtime synchronized**: the bridge has both validated topology and fresh
  authoritative state for the current controller session.
- **Warm-up window**: the short startup phase where the orchestrator repairs
  missing snapshots and verifies reachability before normal watchdog behavior
  becomes authoritative again.

## Topic Families

- **Device topic**: a topic scoped to one device name such as
  `LSH/<device>/state` or `LSH/<device>/events`.
- **Service topic**: the bridge-scoped control topic used independently of one
  device command stream. In the public stack this is `LSH/Node-RED/SRV`.
- **Controller-backed traffic**: MQTT payloads that represent current controller
  knowledge or controller-originated runtime events.
- **Bridge-local traffic**: MQTT payloads emitted by the bridge about its own
  runtime, diagnostics or bridge-scoped health.

## Public MQTT Profile

- **`conf`**: the published topology snapshot derived from `DEVICE_DETAILS`.
- **`state`**: the published authoritative actuator state snapshot derived from
  `ACTUATORS_STATE`.
- **`events`**: controller-backed runtime events such as `NETWORK_CLICK_*`
  payloads and device-level `PING` replies.
- **`bridge`**: bridge-local runtime events such as service-level ping replies
  and diagnostics.
- **`IN`**: the device command topic consumed by `lsh-bridge`.

## Behavioral Terms

- **Immediate peer**: the other endpoint on the current hop. The protocol is
  defined between immediate peers, not between branded products.
- **Profile**: the concrete rules a stack applies on top of the base wire
  contract, such as topic layout, cache policy and local handling of commands.
- **Reference stack**: the concrete public profile currently implemented by
  `lsh-core`, `lsh-bridge`, `node-red-contrib-lsh-logic` and `lsh-protocol`.
- **Embedding project**: the real deployment project that wraps one of the
  reusable public repos with board-specific PlatformIO settings, credentials,
  release policy or integration glue.
- **Network click**: a distributed click flow where the controller emits a
  request, the orchestrator validates it, then the controller waits for ACK and
  final confirmation before the global action executes.
- **Fallback**: the controller-local behavior used when a network click cannot
  complete in time.

## `BOOT` And `PING`

- **`BOOT`**: a re-synchronization signal. It does not carry version metadata.
  By default it is role-local, not an end-to-end command that must cross every
  hop unchanged.
- **`PING`**: a liveness probe. By default it is hop-local, so its meaning
  depends on which peer and which topic or transport answered it.
- **Device-topic `PING`**: in the public stack, answered only when the bridge
  currently has a live and synchronized controller path.
- **Service-topic `PING`**: in the public stack, answered by the bridge on the
  `bridge` topic and reports bridge-local runtime health.
- **Bridge-local `BOOT`**: a service-topic resync trigger used by the public
  stack to ask the bridge for a fresh controller synchronization cycle without
  redefining `BOOT` as a mandatory end-to-end command.

## Read Next

- For the public profile as one coherent story, read [REFERENCE_STACK.md](./REFERENCE_STACK.md).
- For short decision-oriented answers, read [FAQ.md](./FAQ.md).
- For the first practical bring-up path, read [GETTING_STARTED.md](./GETTING_STARTED.md).
- For the hardware pattern, read [HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).
- For symptom-based diagnosis, read [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).
- For the landing overview, read [README.md](./README.md).
