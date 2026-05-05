# Stack Config

`lsh_stack.toml` is the deployment layer for Labo Smart Home. It keeps the controller
profile clean while still giving users one command that generates a finished bridge,
coordinator and Node-RED configuration.

The split is intentional:

- `lsh_devices.toml` belongs to `lsh-core` and describes the controller firmware;
- `lsh_stack.toml` belongs to the installation and describes how the controllers are
  wired into MQTT, `lsh-bridge`, the coordinator and Node-RED.

## Quick Start

From a checkout of this repository, prefix commands with `uv run`. After installing the
package, use the same commands without that prefix.

Create a template:

```bash
uv run lsh-stack init
```

The template includes a `#:schema` hint. Editors with TOML schema support can use
[`schemas/lsh_stack.schema.json`](./schemas/lsh_stack.schema.json) for completions and
early validation.

Generate all stack artifacts:

```bash
uv run lsh-stack generate lsh_stack.toml --output-dir generated
```

The output directory contains:

- `lsh-stack-config.json`: complete machine-readable export;
- `system-config.json`: coordinator `systemConfig`;
- `node-red-lsh-logic.json`: fields for the `lsh-logic` Node-RED node;
- `bridge-platformio-flags/<device>.txt`: build flags for each bridge environment.

Use `uv run lsh-stack check lsh_stack.toml` in CI or before a firmware build. It
validates the TOML, asks `lsh-core` for the controller contract, verifies names and
prints a compact bring-up report.

## File Shape

```toml
schema_version = 1

[core]
devices = "lsh_devices.toml"

[transport]
mode = "serial_bridge"

[mqtt]
codec = "json"
lsh_base_path = "LSH/"
homie_base_path = "homie/5/"
service_topic = "LSH/Node-RED/SRV"
```

`core.devices` points to the controller TOML. If the `lsh-core` generator is not next to
your project, set `core.tool` or the `LSH_CORE_TOOL` environment variable.

`transport.mode = "serial_bridge"` is the supported public stack today. The schema
reserves `onboard_ethernet` for a future bridgeless controller profile, but the composer
fails clearly until that firmware path exists.

`mqtt.codec` controls the MQTT-facing payload codec. This is where heterogeneous mode
lives: the controller can use serial MsgPack while MQTT, the coordinator and Node-RED
stay on JSON.

## Examples

Use the smallest file that matches where you are in the bring-up:

- [`examples/lsh_stack.minimal.toml`](./examples/lsh_stack.minimal.toml) only points to
  the controller profile and chooses MQTT JSON. It is enough to generate bridge flags,
  coordinator devices and Node-RED basics.
- [`examples/lsh_stack.network-clicks.toml`](./examples/lsh_stack.network-clicks.toml)
  adds one distributed long-click action and one external actor.
- [`examples/lsh_stack.complete.toml`](./examples/lsh_stack.complete.toml) shows the
  full shape: selected devices, MQTT paths, coordinator timing, Node-RED context
  exports, an external actor topic and multiple network-click mappings.

The older [`examples/lsh_stack.toml`](./examples/lsh_stack.toml) stays as a guided
template with the common fields and commented network-click block.

## Network Clicks

Network-click actions are declared with readable names:

```toml
[[network_clicks]]
source = "j2.salaTavolo"
type = "long"
actors = [
  { device = "j1", actuators = "all" },
  { device = "garage", actuators = ["ceiling"] },
]
other_actors = ["zigbee_table_lamp"]
```

The composer checks that `source` is a `network = true` click in `lsh_devices.toml`. It
also resolves actuator names to the numeric ids required by the coordinator JSON. If a
name is wrong, generation fails before the configuration reaches Node-RED.

`other_actors` stay protocol-neutral. LSH emits the intended boolean state and your
Node-RED flow, CLI adapter or custom integration decides how to route it to Zigbee,
Tasmota, Home Assistant or another system.

## Coordinator and Node-RED

Coordinator timing and Node-RED context exports live in the stack file:

```toml
[coordinator]
click_timeout = "2s"
watchdog_interval = "60s"
other_devices_prefix = "other_devices"

[node_red]
export_topics = "flow"
export_topics_key = "lsh_topics"
other_actors_context = "global"
```

Durations accept seconds as numbers or strings such as `250ms`, `2s`, `1m` and `1h`.
Topic bases must end with `/`; concrete publish topics such as `service_topic` must not.

## Design Rule

The stack composer only owns LSH integration. It produces a complete LSH configuration,
but it does not become a universal automation language. Home Assistant entities,
Zigbee2MQTT topics, dashboards and presentation details remain in their own integration
layer.
