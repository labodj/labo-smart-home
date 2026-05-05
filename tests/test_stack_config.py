"""Tests for the public LSH stack composer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lsh_stack_config.composer import compose_stack
from lsh_stack_config.errors import StackConfigError
from lsh_stack_config.parser import load_stack_config


def test_stack_config_generates_end_to_end_node_red_and_bridge_config(tmp_path: Path) -> None:
    """Friendly TOML names become validated coordinator and Node-RED JSON."""
    config_path = _write_stack_config(
        tmp_path,
        """
        schema_version = 1

        [core]
        devices = "lsh_devices.toml"

        [mqtt]
        codec = "json"

        [coordinator]
        click_timeout = "2500ms"

        [[network_clicks]]
        source = "panel.logic_button"
        type = "long"
        actors = [{ device = "lights", actuators = ["ceiling"] }]
        other_actors = ["zigbee_table_lamp"]
        """,
    )

    stack = compose_stack(load_stack_config(config_path), _core_export())
    panel = _device_entry(stack, "panel")
    action = panel["longClickButtons"][0]

    assert stack["protocol"] == "json"
    assert (
        "-DCONFIG_MSG_PACK_ARDUINO" in stack["bridge"]["devices"]["panel"]["platformioBuildFlags"]
    )
    assert (
        "-DCONFIG_MSG_PACK_MQTT" not in stack["bridge"]["devices"]["panel"]["platformioBuildFlags"]
    )
    assert stack["coordinator"]["options"]["clickTimeout"] == 2.5
    assert action == {
        "id": 7,
        "actors": [{"name": "lights", "allActuators": False, "actuators": [3]}],
        "otherActors": ["zigbee_table_lamp"],
    }
    assert (
        json.loads(stack["nodeRed"]["lshLogic"]["systemConfigJson"])
        == stack["coordinator"]["systemConfig"]
    )


def test_stack_config_rejects_clicks_not_declared_as_network_clicks(tmp_path: Path) -> None:
    """The stack cannot invent coordinator actions for local-only firmware clicks."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.local_only"
        actors = [{ device = "lights", actuators = "all" }]
        """,
    )

    with pytest.raises(StackConfigError, match="not declared as network=true"):
        compose_stack(load_stack_config(config_path), _core_export())


def test_stack_config_rejects_unknown_actuator_names(tmp_path: Path) -> None:
    """Actor targets are checked against the controller contract before output."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [{ device = "lights", actuators = ["missing"] }]
        """,
    )

    with pytest.raises(StackConfigError, match="unknown actuator 'missing'"):
        compose_stack(load_stack_config(config_path), _core_export())


def test_stack_config_reserves_bridgeless_mode_until_core_support_exists(tmp_path: Path) -> None:
    """Future transport names are explicit but cannot silently generate wrong output."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [transport]
        mode = "onboard_ethernet"
        """,
    )

    with pytest.raises(StackConfigError, match="reserved for future bridgeless firmware"):
        compose_stack(load_stack_config(config_path), _core_export())


def _write_stack_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "lsh_stack.toml"
    path.write_text(content, encoding="utf-8")
    return path


def _device_entry(stack: dict[str, object], name: str) -> dict[str, object]:
    devices = stack["coordinator"]["systemConfig"]["devices"]
    return next(device for device in devices if device["name"] == name)


def _core_export() -> dict[str, object]:
    return {
        "schema": "lsh-stack-config/v1",
        "source": "lsh_devices.toml",
        "lshBasePath": "LSH/",
        "homieBasePath": "homie/5/",
        "serviceTopic": "LSH/Node-RED/SRV",
        "protocol": "msgpack",
        "qosPolicy": {
            "coordinatorSubscriptions": {
                "bridge": 2,
                "conf": 2,
                "events": 2,
                "homieState": 1,
                "state": 2,
            }
        },
        "bridge": {
            "devices": {
                "panel": {
                    "deviceName": "panel",
                    "platformioBuildFlags": [
                        "-DCONFIG_MAX_ACTUATORS=1U",
                        '-DCONFIG_MQTT_TOPIC_BASE=\\"LSH\\"',
                        '-DCONFIG_MQTT_TOPIC_SERVICE=\\"LSH/Node-RED/SRV\\"',
                        "-DCONFIG_MSG_PACK_ARDUINO",
                        "-DCONFIG_MSG_PACK_MQTT",
                    ],
                    "topics": {},
                },
                "lights": {
                    "deviceName": "lights",
                    "platformioBuildFlags": [],
                    "topics": {},
                },
            }
        },
        "controllers": {
            "panel": {
                "deviceName": "panel",
                "actuators": [],
                "buttons": [{"name": "logic_button", "id": 7}],
                "indicators": [],
            },
            "lights": {
                "deviceName": "lights",
                "actuators": [{"name": "ceiling", "id": 3}],
                "buttons": [],
                "indicators": [],
            },
        },
        "coordinator": {
            "options": {
                "lshBasePath": "LSH/",
                "homieBasePath": "homie/5/",
                "serviceTopic": "LSH/Node-RED/SRV",
                "protocol": "msgpack",
                "subscriptionQos": {
                    "bridge": 2,
                    "conf": 2,
                    "events": 2,
                    "homieState": 1,
                    "state": 2,
                },
            },
            "systemConfig": {"devices": [{"name": "panel"}, {"name": "lights"}]},
            "subscriptions": {},
            "unmappedNetworkClicks": [
                {
                    "device": "panel",
                    "buttonId": 7,
                    "button": "logic_button",
                    "clickType": "long",
                }
            ],
        },
        "nodeRed": {"lshLogic": {"protocol": "msgpack", "systemConfigJson": "{}"}},
        "footprint": {},
    }
