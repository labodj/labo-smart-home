# LSH Documentation Map

This page helps you decide where to go next in the Labo Smart Home documentation.

Use it when you know what you want to do, but not which file or component repository to
open first. The individual pages stay focused; this page keeps the navigation in one
place.

## Start Here

- **New to LSH**: start with the [README](./README.md), then come back here.
- **Deciding whether LSH fits your project**: read [FAQ.md](./FAQ.md).
- **Understanding the runtime model**: open [REFERENCE_STACK.md](./REFERENCE_STACK.md).
- **Ready to run a first lab**: follow [GETTING_STARTED.md](./GETTING_STARTED.md).
- **Generating a finished deployment config**: use [STACK_CONFIG.md](./STACK_CONFIG.md).
- **Debugging live behavior**: use [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).
- **Planning the hardware layer**: read [HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).
- **Unfamiliar terms**: skim [GLOSSARY.md](./GLOSSARY.md).

## Public Repositories

| Repository                                                                             | Use it for                                                                  |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`lsh-core`](https://github.com/labodj/lsh-core)                                       | Arduino/Controllino runtime for wired I/O, local logic, and topology        |
| [`lsh-bridge`](https://github.com/labodj/lsh-bridge)                                   | ESP32 bridge for serial LSH protocol, MQTT/Homie exposure, and diagnostics  |
| [`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator) | Headless orchestration, startup recovery, watchdogs, and CLI/library use    |
| [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)   | Node-RED wrapper around the coordinator runtime                             |
| [`lsh-protocol`](https://github.com/labodj/lsh-protocol)                               | Shared command IDs, compact payload keys, generators, and protocol fixtures |

## Optional External Homie Discovery

| Repository                                                                                                                     | Use it for                                                        |
| ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| [`homie-home-assistant-discovery`](https://github.com/labodj/homie-home-assistant-discovery)                                   | Standalone Homie-to-Home-Assistant discovery daemon and core API  |
| [`node-red-contrib-homie-home-assistant-discovery`](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery) | Node-RED node for Homie-to-Home-Assistant MQTT discovery messages |

These are generic Homie projects, not LSH components. Add them only when you want Home
Assistant MQTT discovery from Homie metadata.

Maintained infrastructure forks are available when needed, but they are supporting code
rather than starting points: [`homie-esp8266`](https://github.com/labodj/homie-esp8266)
and [`async-mqtt-client`](https://github.com/labodj/async-mqtt-client).

## First Lab Path

For a first end-to-end evaluation, keep the public examples close to the stock
configuration and change one layer at a time.

1. Skim the [README](./README.md) for the project overview and adoption notes.
2. Read [REFERENCE_STACK.md](./REFERENCE_STACK.md) for the MQTT, Homie, and runtime
   model.
3. Follow [GETTING_STARTED.md](./GETTING_STARTED.md) for the bring-up sequence.
4. Use the controller example in
   [`lsh-core`](https://github.com/labodj/lsh-core/tree/main/examples/multi-device-project).
5. Use the bridge example in
   [`lsh-bridge`](https://github.com/labodj/lsh-bridge/tree/main/examples/basic-homie-bridge).
6. Add the headless coordinator or the Node-RED wrapper.
7. Generate deployment artifacts with [STACK_CONFIG.md](./STACK_CONFIG.md) once the
   controller profile is stable.
8. Optionally add a generic Homie discovery package if you want Home Assistant MQTT
   discovery.
9. Keep [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) nearby once real traffic starts.

## Detailed References

- Topic layout, bootstrap, `PING`, `BOOT`, and network-click semantics:
  [REFERENCE_STACK.md](./REFERENCE_STACK.md)
- End-to-end stack TOML, generated bridge flags, coordinator config and Node-RED config:
  [STACK_CONFIG.md](./STACK_CONFIG.md)
- Shared quality-gate policy for public repositories:
  [QUALITY_GATE.md](./QUALITY_GATE.md)
- Repository quality gate for docs and the stack composer:
  [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
- Controller feature flags and firmware integration:
  [`lsh-core` README](https://github.com/labodj/lsh-core)
- Bridge runtime policy:
  [`lsh-bridge/docs/runtime-behavior.md`](https://github.com/labodj/lsh-bridge/blob/main/docs/runtime-behavior.md)
- Bridge compile-time settings:
  [`lsh-bridge/docs/compile-time-configuration.md`](https://github.com/labodj/lsh-bridge/blob/main/docs/compile-time-configuration.md)
- Headless coordinator setup:
  [`labo-smart-home-coordinator` README](https://github.com/labodj/labo-smart-home-coordinator)
- Node-RED wrapper setup and examples:
  [`node-red-contrib-lsh-logic` README](https://github.com/labodj/node-red-contrib-lsh-logic)
- Optional standalone Homie-to-Home-Assistant discovery:
  [`homie-home-assistant-discovery` README](https://github.com/labodj/homie-home-assistant-discovery)
- Optional Node-RED Homie-to-Home-Assistant discovery:
  [`node-red-contrib-homie-home-assistant-discovery` README](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery)
- Canonical wire contract:
  [`lsh-protocol/shared/lsh_protocol.md`](https://github.com/labodj/lsh-protocol/blob/main/shared/lsh_protocol.md)
- Role semantics for profiles and immediate peers:
  [`lsh-protocol/docs/profiles-and-roles.md`](https://github.com/labodj/lsh-protocol/blob/main/docs/profiles-and-roles.md)
