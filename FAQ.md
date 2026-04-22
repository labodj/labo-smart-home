# LSH FAQ

This page answers the most common "should I use this?" and "how should I
approach it?" questions about the public LSH stack.

If you want the concrete runtime profile first, read
[REFERENCE_STACK.md](./REFERENCE_STACK.md). If you want the first practical lab
path, read [GETTING_STARTED.md](./GETTING_STARTED.md).

## What is LSH in one sentence?

LSH is a wired, local-first home automation stack that keeps physical control
fast and deterministic while exposing the system cleanly over MQTT, Node-RED
and Home Assistant.

## Do I need all four public repositories?

No.

They are split by responsibility:

- `lsh-core` is the controller-side runtime.
- `lsh-bridge` exposes that runtime over MQTT and Homie.
- `node-red-contrib-lsh-logic` adds central orchestration, startup recovery and
  distributed click logic.
- `lsh-protocol` keeps the shared payload contract aligned across the stack.

If you only want to study or reuse one layer, you can start there. If you want
the full public reference behavior, you eventually need all four.

## Why is LSH split across four repositories?

Because each layer has a different job, different constraints and a different
audience.

The split keeps the public stack easier to understand and easier to adopt:

- controller runtime stays focused on deterministic field behavior
- bridge runtime stays focused on serial, MQTT and Homie
- orchestration stays focused on policy and distributed logic
- protocol ownership stays explicit instead of being duplicated by hand

That separation is one of the reasons the stack is easier to study than a big
monolithic automation repo.

## Do I need Node-RED?

Not for the lowest layer.

`lsh-core` plus `lsh-bridge` already gives you a controller + MQTT path. You
add `node-red-contrib-lsh-logic` when you want the public orchestration model:

- startup recovery
- distributed network clicks
- device registry state
- Home Assistant discovery shaping
- central watchdog behavior

## Do I need Home Assistant?

No.

Home Assistant is an optional consumer of the MQTT/Homie side of the stack. The
core public runtime story is controller, bridge, broker and orchestration.

## Can I adopt LSH incrementally?

Yes, and that is usually the smartest way to start.

A practical adoption order is:

1. controller and bridge first
2. MQTT visibility second
3. Node-RED orchestration third
4. Home Assistant shaping last

That order keeps each layer testable before you add another one on top.

## What if I am not an embedded developer?

You do not need to start by reading firmware internals.

The lowest-friction path is:

1. [README.md](./README.md)
2. [REFERENCE_STACK.md](./REFERENCE_STACK.md)
3. [FAQ.md](./FAQ.md)
4. [GETTING_STARTED.md](./GETTING_STARTED.md)

Then only dive into the repo that matches your immediate goal:

- `lsh-core` for controller firmware
- `lsh-bridge` for ESP32 bridge integration
- `node-red-contrib-lsh-logic` for orchestration
- `lsh-protocol` for exact contract details

## What still works when Wi-Fi, MQTT or Node-RED is down?

Controller-local behavior.

That is one of the main design goals of LSH. Physical inputs, relays,
indicators and local fallback logic stay on the `lsh-core` side instead of
depending on a server round-trip for every action.

## What does "authoritative" mean in LSH?

It means "this component is the source of truth for this class of state".

In the public reference stack:

- `lsh-core` is authoritative for controller topology and actuator state
- retained MQTT snapshots are the last known authoritative state, not proof of
  current reachability
- bridge-local diagnostics are useful, but they are not the same thing as a
  live controller-backed state confirmation

If you are unsure how this plays out at runtime, read
[REFERENCE_STACK.md](./REFERENCE_STACK.md).

## Is LSH only for Controllino?

The current public controller-side implementation is centered on Controllino and
the live installation uses Controllino Maxi boards. That is the most documented
and battle-tested hardware path today.

The higher layers are intentionally cleaner than that:

- `lsh-protocol` is role-oriented, not Controllino-specific
- `lsh-bridge` is an ESP32 bridge runtime
- `node-red-contrib-lsh-logic` depends on the public MQTT/payload contract, not
  on Controllino itself

## Should I start with JSON or MsgPack?

For the first evaluation, keep the public examples as close to stock as
possible.

That usually means:

- keep the bundled serial codec choice unchanged
- prefer readable MQTT payloads first
- only add MQTT MsgPack after the end-to-end path is already healthy

The important rule is not "JSON good, MsgPack bad" or the reverse. The
important rule is that both sides of each hop must agree on the active codec.

## Can I rename topics?

Yes, but do not do it on day one unless you need to.

The public examples and docs consistently use:

- `LSH/<device>/conf`
- `LSH/<device>/state`
- `LSH/<device>/events`
- `LSH/<device>/bridge`
- `LSH/<device>/IN`
- `LSH/Node-RED/SRV`

Keeping that layout for the first bring-up removes a whole class of avoidable
errors.

## Do I need to copy the public examples exactly?

Not forever, but close enough for the first bring-up.

The public examples exist to remove ambiguity. The fastest way to get a wrong
result is to change codec, topics, device names and timing assumptions before
the stock path works once end to end.

## What is the fastest honest way to evaluate LSH?

Use this order:

1. Read [README.md](./README.md).
2. Read [REFERENCE_STACK.md](./REFERENCE_STACK.md).
3. Read [GETTING_STARTED.md](./GETTING_STARTED.md).
4. Open the public examples in `lsh-core`, `lsh-bridge` and
   `node-red-contrib-lsh-logic`.

That path tells you very quickly whether the stack fits your hardware,
automation style and tooling preferences.

## Where should I look if something does not work?

Start with [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

It maps common symptoms to the most likely mismatches across controller, bridge,
MQTT and Node-RED.

## Where do I find the exact settings and contract details?

- System-level picture: [REFERENCE_STACK.md](./REFERENCE_STACK.md)
- First lab path: [GETTING_STARTED.md](./GETTING_STARTED.md)
- Hardware pattern: [HARDWARE_OVERVIEW.md](./HARDWARE_OVERVIEW.md)
- Controller configuration and flags:
  [`lsh-core` README](https://github.com/labodj/lsh-core)
- Bridge runtime behavior:
  [`lsh-bridge/docs/runtime-behavior.md`](https://github.com/labodj/lsh-bridge/blob/main/docs/runtime-behavior.md)
- Bridge compile-time knobs:
  [`lsh-bridge/docs/compile-time-configuration.md`](https://github.com/labodj/lsh-bridge/blob/main/docs/compile-time-configuration.md)
- Node-RED config and examples:
  [`node-red-contrib-lsh-logic` README](https://github.com/labodj/node-red-contrib-lsh-logic)
- Exact wire contract:
  [`lsh-protocol/shared/lsh_protocol.md`](https://github.com/labodj/lsh-protocol/blob/main/shared/lsh_protocol.md)

## Is LSH production-proven or just a demo?

The public repositories are the extracted, cleaned up and documented form of a
stack that has already been used in a real installation for years.

That does not mean every possible hardware combination is documented. It does
mean the architecture, timing assumptions and cross-repo behaviors were shaped
by real use rather than by a purely synthetic demo.

## Read Next

- For the full public stack story: [REFERENCE_STACK.md](./REFERENCE_STACK.md)
- For the practical bring-up path: [GETTING_STARTED.md](./GETTING_STARTED.md)
- For shared terms: [GLOSSARY.md](./GLOSSARY.md)
- For symptom-based diagnosis: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
