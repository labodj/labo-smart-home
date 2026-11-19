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
- **Maintaining the stack generator**: read
  [GENERATOR_ARCHITECTURE.md](./GENERATOR_ARCHITECTURE.md).
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

Supporting infrastructure includes the maintained
[`homie-esp8266`](https://github.com/labodj/homie-esp8266) fork, published as
`labodj/homie-v5`, and its upstream
[`bertmelis/espMqttClient`](https://github.com/bertmelis/espMqttClient) backend. The old
[`async-mqtt-client`](https://github.com/labodj/async-mqtt-client) fork remains
available only for historical-release compatibility.

## First Lab Path

1. [Compile a starter without hardware](./README.md#quick-start).
2. [Match the wiring and observe one live controller](./GETTING_STARTED.md#match-the-example-to-your-wiring).
3. [Choose the headless coordinator or Node-RED](./GETTING_STARTED.md#choose-one-orchestration-runtime).
4. [Trace an unexpected result](./TROUBLESHOOTING.md#first-60-second-triage).

## Detailed References

- Topic layout, bootstrap, `PING`, `BOOT`, and network-click semantics:
  [REFERENCE_STACK.md](./REFERENCE_STACK.md)
- End-to-end stack TOML, generated bridge flags, coordinator config and Node-RED config:
  [STACK_CONFIG.md](./STACK_CONFIG.md)
- Stack generator module boundaries and maintenance rules:
  [GENERATOR_ARCHITECTURE.md](./GENERATOR_ARCHITECTURE.md)
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
