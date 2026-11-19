# Getting Started With LSH

A wall button and a relay can work locally on the controller. The ESP32 bridge makes
their state visible over MQTT. A coordinator is useful when a button should also control
something on another device.

## Build your first project

Follow the [Quick Start](./README.md#quick-start) with Python 3.11+ and PlatformIO Core.
Downloads need an internet connection. You can complete this part at your desk with the
boards unplugged. The rest of this guide assumes you are inside `my-lsh-installation/`
with its local `lsh-stack.pyz`. On Windows, substitute `py` for `python` if needed. From
a source checkout you can use the absolute path to `lsh-stack.py` instead; an installed
package provides the `lsh-stack` command.

After `new`, `status` lists the two source TOMLs and may say that generated files are
incomplete. Its next action is `setup`. Setup installs the core generator, generates and
validates the installation, then builds the selected controllers and default bridge.
With the default device `panel`, look for:

| Artifact                                  | Location                                         |
| ----------------------------------------- | ------------------------------------------------ |
| Controller firmware                       | `core/.pio/build/core_panel/firmware.hex`        |
| Bridge firmware                           | `bridge/.pio/build/bridge_littlefs/firmware.bin` |
| Deployment instructions for these devices | `generated/README.generated.md`                  |

The stack starter currently requests `labodj/lsh-core @ ^4.0.2`. PlatformIO can also use
the installation managed by VS Code. If a build fails, correct the first reported error
and rerun `python lsh-stack.pyz setup`.

## Match the example to your wiring

Edit `core/lsh_devices.toml` for pins, names and local button actions. Edit
`lsh_stack.toml` for MQTT settings, bridge profiles and cross-device actions. For
example, in the default starter, change the existing relay's pin from `R0` to `R1`
**only if the relay on your bench is wired to R1**. Its name stays `light`, so the
button still targets it:

```toml
[devices.panel.actuators.light]
id = 1
pin = "R1"

[devices.panel.buttons.wall_button]
id = 1
pin = "A0"
short = "light"
```

The normal starter already has these tables. If you used `new --interactive`, it created
the named controllers with empty I/O lists. Add the tables under your own device name. A
broker entered in the wizard configures the **OTA updater**. Provision the ESP32's own
Wi-Fi and MQTT connection when setting up the physical bridge.

Run `python lsh-stack.pyz setup` again after editing. Use
`python lsh-stack.pyz explain panel` for the generated device summary and
`core/lsh_devices.toml` for its pin assignments. Keep hand edits outside `generated/`.

## Connect one controller and bridge

1. Check the board, pin assignments and UART levels against the
   [hardware overview](./HARDWARE_OVERVIEW.md#controller-to-bridge-interface). The
   reference pair uses a Controllino Maxi and an ESP32 DevKit.
2. Follow the USB instructions in `generated/README.generated.md` for the chosen device
   and port. Provision the bridge's Wi-Fi and broker settings using the
   [bridge setup guide](https://github.com/labodj/lsh-bridge). The first physical
   milestone is the bridge joining your broker.
3. Observe the default topics below in an MQTT client. Use the device ID configured for
   Homie and the LSH device name for the respective topics. In this example both are
   `panel`. The root is `homie/`, the Homie version is 5 and the composer's
   `mqtt.homie_base_path` is **`homie/5/`**.

| What to observe                        | Expected evidence                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `homie/5/panel/$state`                 | A fresh `ready` transition indicates that the bridge has completed Homie startup.                                  |
| `LSH/panel/bridge`                     | A live service ping reply reports `controller_connected=true` and `runtime_synchronized=true`.                     |
| `LSH/panel/conf` and `LSH/panel/state` | The announced topology and packed state agree. Retained snapshots can be read even when the controller is offline. |

To get a fresh reply, follow
[Send a service ping](./TROUBLESHOOTING.md#send-a-service-ping). If only the bridge is
reachable, check the UART path, baud and serial codec at both ends. With MQTT MsgPack,
configure your viewer to decode binary payloads. See
[the one-minute triage](./TROUBLESHOOTING.md#first-60-second-triage). Once USB
provisioning and the live checks pass, use
[Bridge Uploads](./STACK_CONFIG.md#bridge-uploads) for subsequent OTA updates.

## Choose one orchestration runtime

- **Headless service.** Use the coordinator command from `generated/README.generated.md`
  with `generated/system-config.json` and your broker settings. Verify the configured
  device appears in the coordinator's diagnostics.
  [Coordinator guide](https://github.com/labodj/labo-smart-home-coordinator)
- **Node-RED.** Install `node-red-contrib-lsh-logic` and import
  `generated/node-red-flow.json`. Select your broker in both MQTT nodes, review the
  initially disabled tab, enable it and deploy. Use a Debug node on the Configuration
  output to inspect the subscriptions. Follow `generated/node-red-setup.md`. Run one
  coordinator for this set of devices.

## Other starting points

For a controller on its own, use `new-core`. For hand-maintained projects, use the
[controller example](https://github.com/labodj/lsh-core/tree/main/examples/multi-device-project)
and
[bridge example](https://github.com/labodj/lsh-bridge/tree/main/examples/basic-homie-bridge).
The [reference profile](./REFERENCE_STACK.md) explains topics, recovery and network
clicks. The [stack reference](./STACK_CONFIG.md) covers daily operations, override
files, advanced firmware profiles and migration of existing installations.
