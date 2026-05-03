# LSH FAQ

This page answers the common "should I use this?" and "how should I approach it?"
questions that come up when evaluating LSH.

For the full documentation map, use [DOCS.md](./DOCS.md).

## What is LSH in one sentence?

LSH is a wired, local-first home automation stack that keeps physical control responsive
and deterministic while exposing controller state and commands cleanly over MQTT/Homie
and Node-RED orchestration.

## Do I need every public repository?

No. The repositories are split by responsibility:

- `lsh-core` is the controller-side runtime.
- `lsh-bridge` exposes that runtime over MQTT and Homie.
- `labo-smart-home-coordinator` adds central orchestration, startup recovery, and
  distributed click logic as a standalone CLI/library package.
- `node-red-contrib-lsh-logic` wraps that coordinator for Node-RED users.
- `lsh-protocol` keeps the shared payload contract aligned across the stack.

If you only want to inspect or reuse one layer, start there. For a working deployment,
you usually combine the controller, bridge, and one orchestration surface. The protocol
repository is the shared source of truth behind the generated contract; most adopters
read it when they need exact wire details rather than editing it on day one.

If you also want Home Assistant MQTT discovery, that sits outside LSH. Use
[`homie-home-assistant-discovery`](https://github.com/labodj/homie-home-assistant-discovery)
as a standalone daemon or embeddable Node.js core, or
[`node-red-contrib-homie-home-assistant-discovery`](https://github.com/labodj/node-red-contrib-homie-home-assistant-discovery)
when you want the same Homie-to-Home-Assistant mapping inside Node-RED.

## Why is LSH split across several repositories?

Because each layer has a different job, different constraints, and a different audience.

The split makes the system easier to understand and adopt:

- controller runtime stays focused on deterministic field behavior
- bridge runtime stays focused on serial, MQTT, and Homie
- orchestration stays focused on policy and distributed logic
- protocol ownership stays explicit instead of being duplicated by hand

That separation keeps each repository easier to understand, test, and adopt in stages.

## Do I need Node-RED?

Not for the lowest layer.

`lsh-core` plus `lsh-bridge` already gives you a controller + MQTT path. You add
orchestration when you want the public distributed runtime model:

- startup recovery
- distributed network clicks
- device registry state
- central watchdog behavior

Use
[`labo-smart-home-coordinator`](https://github.com/labodj/labo-smart-home-coordinator)
when you want that runtime as a headless CLI process or embedded Node.js library. Use
[`node-red-contrib-lsh-logic`](https://github.com/labodj/node-red-contrib-lsh-logic)
when you want the same runtime inside Node-RED.

## Do I need Home Assistant?

No.

Home Assistant is an optional consumer of the MQTT/Homie side of the stack. The core
runtime path is controller, bridge, broker, and orchestration.

Home Assistant entity discovery is not part of LSH itself. If you want it, attach one of
the generic Homie discovery projects to the Homie topics published by `lsh-bridge`.

## Can I adopt LSH incrementally?

Yes, and it is usually a low-risk way to avoid confusion.

A practical adoption order is:

1. controller and bridge first
2. MQTT visibility second
3. coordinator or Node-RED orchestration third
4. optional external Homie-to-Home-Assistant discovery last, if you need Home Assistant
   entities

That order keeps each layer testable before you add another one on top.

## What if I am not an embedded developer?

You do not need to start by reading firmware internals.

The smoothest path is:

1. [README.md](./README.md)
2. [REFERENCE_STACK.md](./REFERENCE_STACK.md)
3. this FAQ
4. [GETTING_STARTED.md](./GETTING_STARTED.md)

Then dive only into the repository that matches your immediate goal:

- `lsh-core` for controller firmware
- `lsh-bridge` for ESP32 bridge integration
- `labo-smart-home-coordinator` for headless orchestration
- `node-red-contrib-lsh-logic` for Node-RED orchestration
- `lsh-protocol` for exact contract details
- external Homie discovery projects for optional Home Assistant MQTT discovery

For the controller side, current `lsh-core` profiles are configured from TOML. You
describe relays, buttons, indicators, IDs, pins, and click behavior in
`lsh_devices.toml`; the generator emits the C++ profile. You still need to understand
your hardware and build environment, but you should not need to write device topology
code by hand for a typical controller.

## What still works when Wi-Fi, MQTT, or Node-RED is down?

Controller-local behavior.

That is one of the main design goals of LSH. Physical inputs, relays, indicators, and
local fallback logic stay on the `lsh-core` side instead of depending on a server
round-trip for every action.

## What does "authoritative" mean in LSH?

It means "this component is the source of truth for this class of state".

In the public reference stack:

- `lsh-core` is authoritative for controller topology and actuator state
- retained MQTT snapshots are the last known authoritative state, not proof of current
  reachability
- bridge-local diagnostics are useful, but they are not the same thing as a live
  controller-backed state confirmation

If you are unsure how this plays out at runtime, read
[REFERENCE_STACK.md](./REFERENCE_STACK.md).

## Is LSH only for Controllino?

The current controller-side implementation is centered on Controllino, and the live
installation uses Controllino Maxi boards. That is the hardware path documented in the
most detail today.

The higher layers are less tied to that choice:

- `lsh-protocol` is role-oriented, not Controllino-specific
- `lsh-bridge` is an ESP32 bridge runtime
- `labo-smart-home-coordinator` and `node-red-contrib-lsh-logic` depend on the public
  MQTT/payload contract, not on Controllino itself

## Should I start with JSON or MsgPack?

For the first evaluation, keep the public examples as close to stock as possible.

That usually means:

- keep the bundled serial codec choice unchanged
- prefer readable MQTT payloads first
- only add MQTT MsgPack after the end-to-end path is already healthy

The important rule is not "JSON good, MsgPack bad" or the reverse. What matters is that
both sides of each hop agree on the active codec.

## Can I rename topics?

Yes, but do not do it on day one unless you need to.

The public examples and docs use this layout consistently:

- `LSH/<device>/conf`
- `LSH/<device>/state`
- `LSH/<device>/events`
- `LSH/<device>/bridge`
- `LSH/<device>/IN`
- `LSH/Node-RED/SRV`

Keeping that layout for the first bring-up removes a whole class of avoidable errors.

## Do I need to copy the public examples exactly?

Not forever, but close enough for the first bring-up.

The public examples exist to remove ambiguity. A common way to get a misleading result
is to change codec, topics, device names, and timing assumptions before the stock path
works once end to end.

The intended workflow is: make the example build, make one real device work, then
customize names, topology, and distributed logic in small steps.

## What is a practical way to evaluate LSH?

Use this order:

1. Read [README.md](./README.md).
2. Read [REFERENCE_STACK.md](./REFERENCE_STACK.md).
3. Read [GETTING_STARTED.md](./GETTING_STARTED.md).
4. Open the public examples in `lsh-core`, `lsh-bridge`, `labo-smart-home-coordinator`,
   and `node-red-contrib-lsh-logic`.

That path quickly shows whether the stack fits your hardware, automation style, and
tooling preferences.

## Where should I look if something does not work?

Start with [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

It maps common symptoms to the most likely mismatches across controller, bridge, MQTT,
and Node-RED.

## Where do I find the exact settings and contract details?

Use [DOCS.md](./DOCS.md). It keeps the detailed links to the stack profile, repository
READMEs, bridge runtime docs, Node-RED examples, and protocol contract in one place.

## Has LSH been used in a real installation?

Yes. The public repositories come from a stack that has been used in a real installation
for years.

That does not mean every possible hardware combination is documented. It means the
architecture, timing assumptions, and cross-repo behaviors were shaped by real use, not
by a purely synthetic demo.
