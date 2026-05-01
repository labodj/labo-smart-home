# LSH Documentation Map

This is the navigation page for the public Labo Smart Home documentation.

Use it when you know what you want to do, but not which repository or document to open
first. The individual pages stay focused on their own topic; this page does the
cross-linking.

## Start Here

- **I am new to LSH**: read the [README](./README.md), then come back here.
- **I want to understand the full stack**: read
  [REFERENCE_STACK.md](./REFERENCE_STACK.md).
- **I want to try a first lab**: follow [GETTING_STARTED.md](./GETTING_STARTED.md).
- **Something is not behaving correctly**: use
  [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).
- **I need the hardware shape first**: read
  [HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md).
- **The words are unfamiliar**: skim [GLOSSARY.md](./GLOSSARY.md).
- **I am deciding whether LSH fits my project**: read [FAQ.md](./FAQ.md).

## Public Repositories

| Repository                                                                             | Use it for                                                                 |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| [`lsh-core`](https://github.com/labodj/lsh-core)                                       | Controller firmware, field I/O, local logic and static device topology     |
| [`lsh-bridge`](https://github.com/labodj/lsh-bridge)                                   | ESP32 serial-to-MQTT bridge, Homie exposure and bridge diagnostics         |
| [`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator) | Headless orchestration, startup recovery, watchdogs and CLI/library use    |
| [`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)   | The same orchestration runtime inside Node-RED                             |
| [`lsh-protocol`](https://github.com/labodj/lsh-protocol)                               | Shared command IDs, compact payload keys, generators and protocol fixtures |

Support forks are maintained separately and are not the main entry point:
[`homie-esp8266`](https://github.com/labodj/homie-esp8266) and
[`async-mqtt-client`](https://github.com/labodj/async-mqtt-client).

## First Lab Path

For a first end-to-end evaluation, keep the public examples close to stock and change
one layer at a time.

1. Read the [README](./README.md) for the project shape.
2. Read [REFERENCE_STACK.md](./REFERENCE_STACK.md) for the MQTT/Homie/runtime model.
3. Follow [GETTING_STARTED.md](./GETTING_STARTED.md) for the bring-up sequence.
4. Use the controller example in
   [`lsh-core`](https://github.com/labodj/lsh-core/tree/main/examples/multi-device-project).
5. Use the bridge example in
   [`lsh-bridge`](https://github.com/labodj/lsh-bridge/tree/main/examples/basic-homie-bridge).
6. Add either the headless coordinator or the Node-RED wrapper.
7. Keep [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) open once real traffic starts.

## Exact Details

- Topic layout, bootstrap, `PING`, `BOOT` and network-click semantics:
  [REFERENCE_STACK.md](./REFERENCE_STACK.md)
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
- Canonical wire contract:
  [`lsh-protocol/shared/lsh_protocol.md`](https://github.com/labodj/lsh-protocol/blob/main/shared/lsh_protocol.md)
- Role semantics for profiles and immediate peers:
  [`lsh-protocol/docs/profiles-and-roles.md`](https://github.com/labodj/lsh-protocol/blob/main/docs/profiles-and-roles.md)
