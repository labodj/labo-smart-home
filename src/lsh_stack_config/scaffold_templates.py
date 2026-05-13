"""Starter project templates used by the lsh-stack CLI."""

from __future__ import annotations

TEMPLATE_VERSION = 1

STACK_TEMPLATE = """#:schema https://raw.githubusercontent.com/labodj/labo-smart-home/main/schemas/lsh_stack.schema.json

schema_version = 1

[core]
# Core topology lives in the controller PlatformIO project. lsh-stack reads it
# from here, then writes generated PlatformIO fragments under ./generated.
devices = "core/lsh_devices.toml"
# For local lsh-core development, uncomment this and point it at the checkout.
# tool = "../lsh-core/tools/generate_lsh_static_config.py"

[transport]
mode = "serial_bridge"

[mqtt]
codec = "json"
lsh_base_path = "LSH/"
homie_base_path = "homie/5/"
service_topic = "LSH/Node-RED/SRV"

[coordinator]
click_timeout = "2s"
click_cleanup_interval = "30s"
watchdog_interval = "60s"
interrogate_threshold = "120s"
ping_timeout = "3s"
initial_state_timeout = "2s"
other_devices_prefix = "other_devices"
# other_actors_topic = "home/lsh/other-actors"

[node_red]
expose_state_context = "global"
expose_state_key = "lsh_state"
export_topics = "flow"
export_topics_key = "lsh_topics"
expose_config_context = "global"
expose_config_key = "lsh_config"
other_actors_context = "global"

[platformio]
core_project = "core"
bridge_project = "bridge"
core_env_prefix = "core"
bridge_env_prefix = "bridge"
# Uncomment only when local core compiler flags need a system AVR toolchain.
# core_prefer_system_tools = true

[[platformio.core_profiles]]
name = "release"
extends = "common_release"
default = true

[[platformio.core_profiles]]
name = "debug"
extends = "common_debug"

[[platformio.bridge_profiles]]
name = "release"
extends = "lsh_bridge_release"

[[platformio.bridge_profiles]]
name = "debug"
extends = "lsh_bridge_debug"

[[platformio.bridge_profiles]]
name = "littlefs"
extends = "lsh_bridge_littlefs"
default = true

[[platformio.bridge_profiles]]
name = "littlefs_migration"
extends = "lsh_bridge_littlefs_migration"

[[platformio.bridge_profiles]]
name = "littlefs_debug"
extends = "lsh_bridge_littlefs_debug"

[[platformio.bridge_profiles]]
name = "littlefs_migration_debug"
extends = "lsh_bridge_littlefs_migration_debug"

[deploy.bridge]
# Use "ota" after the first USB flash and Homie/Wi-Fi setup are working.
default_method = "usb"

# [deploy.bridge.ota]
# broker_host = "mqtt.local"
# broker_port = 1883
# broker_username = "homie"
# broker_password_env = "LSH_OTA_PASSWORD"
# homie_version = "5"
# timeout = 300

[bridge.defaults.defines]
# Typed defines replace generated -D flags with the same name.
# CONFIG_ARDCOM_SERIAL_RX_PIN = "16U"
# CONFIG_ARDCOM_SERIAL_TX_PIN = "17U"

[bridge.defaults.build_flags]
# Raw flags are appended after generated flags and typed defines.
# append = ["-Wall"]

# [[network_clicks]]
# source = "panel.wall_button"
# type = "long"
# actors = [{ device = "panel", actuators = ["light"] }]
"""

DEVICES_TEMPLATE = """#:schema https://raw.githubusercontent.com/labodj/lsh-core/main/docs/lsh_devices.schema.json

schema_version = 2
preset = "controllino-maxi/fast-msgpack"

[generator]
output_dir = "include"
config_dir = "lsh_configs"
user_config_header = "lsh_user_config.hpp"

[controller]
debug_serial = "Serial"
bridge_serial = "Serial2"

[devices.panel]
name = "panel"

[devices.panel.actuators.light]
id = 1
pin = "R0"

[devices.panel.buttons.wall_button]
id = 1
pin = "A0"
short = "light"
# Uncomment together with [[network_clicks]] in ../lsh_stack.toml.
# long = { network = true, fallback = "do_nothing" }
"""

CORE_PLATFORMIO_TEMPLATE = f"""[lsh_stack_template]
kind = core-controllino-maxi
version = {TEMPLATE_VERSION}

[platformio]
default_envs = core_panel
; Optional stack overlay. If this generated file is missing, the standalone
; environment declared below still builds from lsh_devices.toml.
extra_configs = ../generated/platformio-core.ini
build_cache_dir = ./.build_cache

[common_base]
platform = atmelavr
framework = arduino
board = controllino_maxi
monitor_speed = 500000
lib_deps =
    labodj/lsh-core @ ^3
    controllino-plc/CONTROLLINO
lib_ldf_mode = deep+
lib_compat_mode = strict
build_unflags = -std=gnu++11 -std=c++11
build_flags =
    -I include
    -std=gnu++17

    ; lsh_devices.toml generated lsh-core flags.
    ; Edit lsh_devices.toml first. Uncomment these only for deliberate local
    ; PlatformIO experiments or while testing a new lsh-core option.
    ; -D LSH_ETL_PROFILE_OVERRIDE_HEADER=\\\"lsh_etl_profile_override.h\\\"
    ; -D CONFIG_MSG_PACK
    ; -D CONFIG_USE_FAST_CLICKABLES
    ; -D CONFIG_USE_FAST_ACTUATORS
    ; -D CONFIG_USE_FAST_INDICATORS
    ; -D CONFIG_ACTUATOR_DEBOUNCE_TIME_MS=100U
    ; -D CONFIG_CLICKABLE_DEBOUNCE_TIME_MS=20U
    ; -D CONFIG_CLICKABLE_SCAN_INTERVAL_MS=1U
    ; -D CONFIG_CLICKABLE_LONG_CLICK_TIME_MS=400U
    ; -D CONFIG_CLICKABLE_SUPER_LONG_CLICK_TIME_MS=1000U
    ; -D CONFIG_LCNB_TIMEOUT_MS=1000U
    ; -D CONFIG_NETWORK_CLICK_ACK_TIMEOUT_MS=1000U
    ; -D CONFIG_NETWORK_CLICK_CONFIRM_RETRY_TIMEOUT_MS=1000U
    ; -D CONFIG_PING_INTERVAL_MS=10000U
    ; -D CONFIG_CONNECTION_TIMEOUT_MS=10200U
    ; -D CONFIG_BRIDGE_BOOT_RETRY_INTERVAL_MS=250U
    ; -D CONFIG_BRIDGE_AWAIT_STATE_TIMEOUT_MS=1500U
    ; -D CONFIG_DEBUG_SERIAL_BAUD=115200U
    ; -D CONFIG_COM_SERIAL_BAUD=250000U
    ; -D CONFIG_COM_SERIAL_TIMEOUT_MS=5U
    ; -D CONFIG_COM_SERIAL_MSGPACK_FRAME_IDLE_TIMEOUT_MS=5U
    ; -D CONFIG_COM_SERIAL_MAX_RX_PAYLOADS_PER_LOOP=4U
    ; -D CONFIG_COM_SERIAL_MAX_RX_BYTES_PER_LOOP=32U
    ; -D CONFIG_COM_SERIAL_FLUSH_AFTER_SEND=1
    ; -D CONFIG_DELAY_AFTER_RECEIVE_MS=50U
    ; -D CONFIG_NETWORK_CLICK_CHECK_INTERVAL_MS=50U
    ; -D CONFIG_ACTUATORS_AUTO_OFF_CHECK_INTERVAL_MS=1000U
    ; -D CONFIG_LSH_BENCH
    ; -D CONFIG_BENCH_ITERATIONS=1000000U
    ; -D LSH_STATIC_CONFIG_RUNTIME_CHECKS

    ; Arduino core serial buffer overrides. These are not lsh-core settings.
    ; -D SERIAL_RX_BUFFER_SIZE=256U
    ; -D SERIAL_TX_BUFFER_SIZE=128U

[common_release]
extends = common_base
build_type = release
build_flags =
    ${{common_base.build_flags}}
    -D NDEBUG

[common_debug]
extends = common_base
build_type = debug
build_flags =
    ${{common_base.build_flags}}
    -D LSH_DEBUG

[env:core_panel]
extends = common_release
extra_scripts = pre:scripts/lsh_core_bootstrap.py
custom_lsh_config = lsh_devices.toml
custom_lsh_device = panel
"""

BRIDGE_PLATFORMIO_TEMPLATE = f"""[lsh_stack_template]
kind = bridge-esp32-homie
version = {TEMPLATE_VERSION}

[platformio]
default_envs = bridge_littlefs
; Optional stack overlay. If this generated file is missing, the standalone
; environments declared below still build from the local wide bridge profile.
extra_configs = ../generated/platformio-bridge.ini
build_cache_dir = ./.build_cache

[env]
platform = https://github.com/pioarduino/platform-espressif32/releases/download/stable/platform-espressif32.zip
framework = arduino
board = esp32dev
board_build.partitions = min_spiffs.csv
monitor_speed = 500000
lib_ldf_mode = deep
lib_compat_mode = strict
lib_deps =
    labodj/lsh-bridge @ ^1
build_unflags =
    -std=gnu++11 -std=gnu++17 -std=gnu++20 -std=gnu++23
build_flags =
    -I include

[lsh_bridge_common]
build_flags =
    ${{env.build_flags}}
    -D ARDUINOJSON_DEBUG=0
    -D CORE_DEBUG_LEVEL=0
    -D HOMIE_CONVENTION_VERSION=5

    ; Additional bridge-side knobs. Keep them here as a local reference and
    ; uncomment only when intentionally overriding the standalone or stack
    ; contract below.
    ; -D CONFIG_MAX_ACTUATORS=12U
    ; -D CONFIG_MAX_BUTTONS=12U
    ; -D CONFIG_MAX_NAME_LENGTH=4U
    ; -D CONFIG_MSG_PACK_ARDUINO
    ; -D CONFIG_MSG_PACK_MQTT
    ; -D CONFIG_MQTT_TOPIC_BASE=\\\"LSH\\\"
    ; -D CONFIG_MQTT_TOPIC_INPUT=\\\"IN\\\"
    ; -D CONFIG_MQTT_TOPIC_STATE=\\\"state\\\"
    ; -D CONFIG_MQTT_TOPIC_CONF=\\\"conf\\\"
    ; -D CONFIG_MQTT_TOPIC_EVENTS=\\\"events\\\"
    ; -D CONFIG_MQTT_TOPIC_BRIDGE=\\\"bridge\\\"
    ; -D CONFIG_MQTT_TOPIC_SERVICE=\\\"LSH/Node-RED/SRV\\\"
    ; -D CONFIG_MQTT_QOS_DEVICE_COMMANDS=2U
    ; -D CONFIG_MQTT_QOS_SERVICE_COMMANDS=1U
    ; -D CONFIG_MQTT_QOS_CONF=1U
    ; -D CONFIG_MQTT_QOS_STATE=1U
    ; -D CONFIG_MQTT_QOS_EVENTS=2U
    ; -D CONFIG_MQTT_QOS_BRIDGE=1U
    ; -D CONFIG_ARDCOM_SERIAL_RX_PIN=16U
    ; -D CONFIG_ARDCOM_SERIAL_TX_PIN=17U
    ; -D CONFIG_ARDCOM_SERIAL_BAUD=250000U
    ; -D CONFIG_ARDCOM_SERIAL_TIMEOUT_MS=5U
    ; -D CONFIG_ARDCOM_SERIAL_MSGPACK_FRAME_IDLE_TIMEOUT_MS=5U
    ; -D CONFIG_ARDCOM_SERIAL_MAX_RX_BYTES_PER_LOOP=32U
    ; -D CONFIG_BOOTSTRAP_REQUEST_INTERVAL_MS=500U
    ; -D CONFIG_TOPOLOGY_SAVE_RETRY_INTERVAL_MS=500U
    ; -D CONFIG_TOPOLOGY_REBOOT_GRACE_MS=500U
    ; -D CONFIG_STATE_PUBLISH_SETTLE_INTERVAL_MS=40U
    ; -D CONFIG_MQTT_COMMAND_QUEUE_CAPACITY=8U
    ; -D CONFIG_MQTT_MAX_COMMANDS_PER_LOOP=8U
    ; -D CONFIG_ACTUATOR_COMMAND_SETTLE_INTERVAL_MS=50U
    ; -D CONFIG_ACTUATOR_COMMAND_MAX_PENDING_MS=1000U
    ; -D CONFIG_ACTUATOR_COMMAND_MAX_MUTATION_COUNT=32U
    ; -D CONFIG_LSH_BRIDGE_DISABLE_RESET_TRIGGER=1
    ; -D CONFIG_LSH_BRIDGE_IMPL_STORAGE_SIZE=3072U
    ; -D CONFIG_HOMIE_FIRMWARE_NAME=\\\"lsh-homie\\\"
    ; -D CONFIG_HOMIE_FIRMWARE_VERSION=\\\"1.5.0\\\"
    ; -D CONFIG_HOMIE_BRAND=\\\"LaboSmartHome\\\"
    ; -D HOMIE_RESET

[lsh_bridge_standalone_contract]
build_flags =
    ; These defaults keep this repo buildable before or without lsh-stack.
    ; Stack-generated environments use topology-derived values instead.
    -D CONFIG_MAX_ACTUATORS=1U
    -D CONFIG_MAX_BUTTONS=1U
    -D CONFIG_MAX_NAME_LENGTH=5U
    -D CONFIG_MQTT_TOPIC_BASE=\\\"LSH\\\"
    -D CONFIG_MQTT_TOPIC_INPUT=\\\"IN\\\"
    -D CONFIG_MQTT_TOPIC_STATE=\\\"state\\\"
    -D CONFIG_MQTT_TOPIC_CONF=\\\"conf\\\"
    -D CONFIG_MQTT_TOPIC_EVENTS=\\\"events\\\"
    -D CONFIG_MQTT_TOPIC_BRIDGE=\\\"bridge\\\"
    -D CONFIG_MQTT_TOPIC_SERVICE=\\\"LSH/Node-RED/SRV\\\"
    -D CONFIG_ARDCOM_SERIAL_BAUD=250000U
    -D CONFIG_ARDCOM_SERIAL_TIMEOUT_MS=5U
    -D CONFIG_BOOTSTRAP_REQUEST_INTERVAL_MS=250U
    -D CONFIG_MSG_PACK_ARDUINO

[lsh_bridge_release]
build_flags =
    ${{lsh_bridge_common.build_flags}}

[lsh_bridge_debug]
build_type = debug
build_unflags =
    ${{env.build_unflags}}
    -D CORE_DEBUG_LEVEL=0
build_flags =
    ${{lsh_bridge_common.build_flags}}
    -D LSH_DEBUG
    -D CORE_DEBUG_LEVEL=2
    -g3
    -ggdb3

[lsh_bridge_littlefs_flags]
build_flags =
    -D HOMIE_USE_LITTLEFS=1

[lsh_bridge_littlefs_migration_flags]
build_flags =
    -D HOMIE_MIGRATE_SPIFFS_TO_LITTLEFS=1

[lsh_bridge_littlefs]
board_build.filesystem = littlefs
build_flags =
    ${{lsh_bridge_release.build_flags}}
    ${{lsh_bridge_littlefs_flags.build_flags}}

[lsh_bridge_littlefs_migration]
board_build.filesystem = littlefs
build_flags =
    ${{lsh_bridge_littlefs.build_flags}}
    ${{lsh_bridge_littlefs_migration_flags.build_flags}}

[lsh_bridge_littlefs_debug]
board_build.filesystem = littlefs
build_type = debug
build_unflags =
    ${{lsh_bridge_debug.build_unflags}}
build_flags =
    ${{lsh_bridge_debug.build_flags}}
    ${{lsh_bridge_littlefs_flags.build_flags}}

[lsh_bridge_littlefs_migration_debug]
board_build.filesystem = littlefs
build_type = debug
build_unflags =
    ${{lsh_bridge_debug.build_unflags}}
build_flags =
    ${{lsh_bridge_littlefs_debug.build_flags}}
    ${{lsh_bridge_littlefs_migration_flags.build_flags}}

[env:bridge_release]
extends = lsh_bridge_release
build_flags =
    ${{lsh_bridge_release.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}

[env:bridge_debug]
extends = lsh_bridge_debug
build_flags =
    ${{lsh_bridge_debug.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}

[env:bridge_littlefs]
extends = lsh_bridge_littlefs
build_flags =
    ${{lsh_bridge_littlefs.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}

[env:bridge_littlefs_migration]
extends = lsh_bridge_littlefs_migration
build_flags =
    ${{lsh_bridge_littlefs_migration.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}

[env:bridge_littlefs_debug]
extends = lsh_bridge_littlefs_debug
build_flags =
    ${{lsh_bridge_littlefs_debug.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}

[env:bridge_littlefs_migration_debug]
extends = lsh_bridge_littlefs_migration_debug
build_flags =
    ${{lsh_bridge_littlefs_migration_debug.build_flags}}
    ${{lsh_bridge_standalone_contract.build_flags}}
"""

BOOTSTRAP_CORE_INI = """; Bootstrap file created by lsh-stack new.
; It exists so PlatformIO can install dependencies before the first full generate.
; Run the generate command shown in README.md to replace it.

[env:core_panel]
extends = common_release
extra_scripts = pre:scripts/lsh_core_bootstrap.py
custom_lsh_config = lsh_devices.toml
custom_lsh_device = panel
"""

CORE_BOOTSTRAP_SCRIPT_TEMPLATE = """\
\"\"\"Bootstrap lsh-core's TOML pre-build hook before the first stack generation.\"\"\"

from __future__ import annotations

from pathlib import Path

Import(\"env\")


def _candidate_scripts() -> list[Path]:
    project_dir = Path(env.subst(\"$PROJECT_DIR\"))
    pioenv = env.subst(\"$PIOENV\")
    libdeps = project_dir / \".pio\" / \"libdeps\"
    exact = libdeps / pioenv / \"lsh-core\" / \"tools\" / \"platformio_lsh_static_config.py\"
    candidates = [exact]
    if libdeps.is_dir():
        candidates.extend(
            sorted(libdeps.glob(\"*/lsh-core/tools/platformio_lsh_static_config.py\"))
        )
    return candidates


for script in _candidate_scripts():
    if script.is_file():
        exec(compile(script.read_text(encoding=\"utf-8\"), str(script), \"exec\"), globals())
        break
else:
    raise RuntimeError(
        \"lsh-core is not installed yet. Build this core project once with PlatformIO \"
        \"IDE or run `platformio run -e core_panel` from core/, then run the \"
        \"stack setup/generate command shown in the installation README.\"
    )
"""

BOOTSTRAP_BRIDGE_INI = """; Bootstrap file created by lsh-stack new.
; It exists so PlatformIO can install dependencies before the first full generate.
; Run the generate command shown in README.md to replace it.

[lsh_stack_bridge_wide]
build_flags =
    -DCONFIG_MAX_ACTUATORS=1U
    -DCONFIG_MAX_BUTTONS=1U
    -DCONFIG_MAX_NAME_LENGTH=5U
    -DCONFIG_MQTT_TOPIC_BASE=\\\"LSH\\\"
    -DCONFIG_MQTT_TOPIC_INPUT=\\\"IN\\\"
    -DCONFIG_MQTT_TOPIC_STATE=\\\"state\\\"
    -DCONFIG_MQTT_TOPIC_CONF=\\\"conf\\\"
    -DCONFIG_MQTT_TOPIC_EVENTS=\\\"events\\\"
    -DCONFIG_MQTT_TOPIC_BRIDGE=\\\"bridge\\\"
    -DCONFIG_MQTT_TOPIC_SERVICE=\\\"LSH/Node-RED/SRV\\\"
    -DCONFIG_ARDCOM_SERIAL_BAUD=250000U
    -DCONFIG_ARDCOM_SERIAL_TIMEOUT_MS=5U
    -DCONFIG_BOOTSTRAP_REQUEST_INTERVAL_MS=250U
    -DCONFIG_MSG_PACK_ARDUINO

[env:bridge_littlefs]
extends = lsh_bridge_littlefs
build_flags =
    ${lsh_bridge_littlefs.build_flags}
    ${lsh_stack_bridge_wide.build_flags}
"""

CORE_MAIN_TEMPLATE = """#include <lsh.hpp>

void setup()
{
    lsh::core::setup();
}

void loop()
{
    lsh::core::loop();
}
"""

ETL_PROFILE_OVERRIDE_TEMPLATE = """#pragma once

#ifndef ETL_VERBOSE_ERRORS
#define ETL_VERBOSE_ERRORS
#endif

#ifndef ETL_NO_STL
#define ETL_NO_STL
#endif
"""

BRIDGE_MAIN_TEMPLATE = """#include <Arduino.h>
#include <lsh_bridge.hpp>

namespace
{

lsh::bridge::BridgeOptions makeBridgeOptions()
{
    lsh::bridge::BridgeOptions options;
    options.serial = &Serial2;
    options.disableLedFeedback = true;
    return options;
}

lsh::bridge::LSHBridge bridge(makeBridgeOptions());

}  // namespace

void setup()
{
    bridge.begin();
}

void loop()
{
    bridge.loop();
}
"""

PROJECT_README_TEMPLATE = """# LSH Installation

## Files You Edit

- `core/lsh_devices.toml`: controller topology, pins, local actions and core timing.
- `lsh_stack.toml`: MQTT, bridge profiles, Node-RED settings and distributed clicks.
- `core/platformio.ini` and `bridge/platformio.ini`: local PlatformIO overrides.

Do not edit files under `generated/`; they are recreated from the TOML files.

## First Setup

Run the guided setup from this folder:

```bash
{lsh_stack_command} setup
```

It generates `generated/`, checks the stack, creates missing core/bridge project files,
and, when the PlatformIO CLI is available, builds the starter core project once if
`lsh-core` has not been installed yet.

If PlatformIO is only available inside VSCode, open `core/` with the PlatformIO
extension and run `core_panel` -> Build once, then run the same setup command again.

When you are unsure what is already done, ask for the next action:

```bash
{lsh_stack_command} status
```

Use the doctor whenever an edit or generated file feels inconsistent:

```bash
{lsh_stack_command} doctor
```

When you intentionally want separated steps after setup has succeeded or after
the core project has been built once:

```bash
{lsh_stack_command} generate
{lsh_stack_command} check
```

Build the default bridge firmware:

```bash
platformio run -d bridge -e bridge_littlefs
```

In VSCode, open `core/` or `bridge/` and use the same environments from PlatformIO
Project Tasks. The local projects stay buildable without `generated/`; stack files are
an overlay for richer fleet workflows.

On Windows, use `py` instead of `python` in the commands above if that is how Python is
installed.
"""

CORE_PROJECT_README_TEMPLATE = """# LSH Core Project

## Files You Edit

- `lsh_devices.toml`: controller topology, pins, local actions and core timing.
- `platformio.ini`: local PlatformIO overrides.

Do not edit files under `generated/`; they are bootstrap files and can be replaced by
stack-generated files later.

## First Build

Run the default controller firmware build:

```bash
platformio run -e core_panel
```

If PlatformIO is only available inside VSCode, open this folder with the PlatformIO
extension and run `core_panel` -> Build from Project Tasks.

This project is standalone. If you later adopt the full stack, create a stack project
with `{lsh_stack_command} new` and point `[core].devices` at this `lsh_devices.toml`.
"""

OVERRIDES_README = """# Persistent Overrides

Files in `generated/` are disposable. Keep local PlatformIO extensions, deployment notes
and hand-written integration glue here or in the PlatformIO project files under
`core/` and `bridge/`.

Use `lsh_stack.toml` for typed bridge `defines` first. Extend generated PlatformIO
environments manually only when you need an escape hatch that the stack should not own.
"""
