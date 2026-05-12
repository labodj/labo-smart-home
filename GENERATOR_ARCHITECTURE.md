# Stack Generator Architecture

This note is for maintainers of the `lsh-stack` generator. User-facing bring-up lives in
[`GETTING_STARTED.md`](./GETTING_STARTED.md) and [`STACK_CONFIG.md`](./STACK_CONFIG.md);
this page explains how the generator is put together so future changes stay small and
predictable.

## Data Flow

The generator has one main pipeline:

1. `parser.py` reads `lsh_stack.toml` into typed dataclasses from `models.py`.
2. `core_export.py` asks `lsh-core` for the controller contract described by
   `lsh_devices.toml`.
3. `composer.py` merges the stack TOML and the controller contract into one stack JSON
   document.
4. `render.py` writes human and machine artifacts under `generated/`.
5. `deploy.py` derives exact build, USB upload and MQTT OTA commands.

Keep that direction one-way. Parsing should not render files, rendering should not parse
TOML, and deployment command building should not know how controller topology is
computed.

## Module Ownership

| Module                       | Owns                                                        |
| ---------------------------- | ----------------------------------------------------------- |
| `cli.py`                     | command dispatch and user-visible command output            |
| `models.py`                  | typed configuration shape                                   |
| `parser.py`                  | TOML validation and friendly errors                         |
| `core_export.py`             | the boundary with `lsh-core`                                |
| `composer.py`                | stack JSON semantics and cross-component values             |
| `render.py`                  | generated files and generated guides                        |
| `deploy.py`                  | PlatformIO, USB and MQTT OTA command strings                |
| `render_common.py`           | tiny shared helpers used by CLI/render/deploy               |
| `bridge_ota_script.py`       | source text for the generated bridge OTA wrapper            |
| `platformio_batch_script.py` | source text for generated PlatformIO batch targets          |
| `platformio_utils.py`        | PlatformIO ini parsing and path formatting                  |
| `doctor.py`                  | plain-language diagnostics                                  |
| `scaffold.py`                | starter project file writing                                |

If a change needs logic from another module, prefer moving a small helper to
`render_common.py` or `platformio_utils.py` over copy-pasting it.

## Explicit Behavior Rules

- Generated files are disposable outputs. The source of truth is TOML plus the
  controller contract exported by `lsh-core`.
- Generated commands must show the config files they consume. Bridge OTA commands pass
  `--config generated/bridge-ota.json` explicitly.
- Bridge firmware OTA is MQTT/Homie only. Do not add `espota` paths for bridge
  firmware.
- User-facing examples use plain `python` or installed commands. Development-only gates
  may use `uv`.
- The generator must not copy protocol or OTA implementations from other projects. It
  should call stable entry points such as `homie-esp8266/scripts/homie_ota.py`.
- Defaults are allowed only when they are documented. For example, when no bridge
  profiles are configured, one default bridge profile is derived from
  `platformio.bridge_base_env`.

## Test Rules

When changing generator behavior, update or add focused tests in `tests/test_stack_config.py`.
The minimum gate before handing work back is:

```bash
npm run check
```

When bridge OTA behavior changes, also smoke-test a generated personal stack command and
run the OTA updater tests in `homie-esp8266`.
