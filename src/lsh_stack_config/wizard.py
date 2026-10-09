"""Small optional prompts that produce ordinary, editable TOML, without guessing wiring."""

from __future__ import annotations

import json
import re
import sys

from .errors import StackConfigError
from .scaffold_templates import DEVICES_TEMPLATE, STACK_TEMPLATE

MAX_PORT = 65535


def interactive_config() -> tuple[str, str]:
    """Collect only supported hardware, controller names and non-secret MQTT settings."""
    sys.stdout.write("Supported stack: Controllino Maxi controllers + ESP32 DevKit bridges.\n")
    if input("Use this hardware? [Y/n]: ").strip().lower() not in ("", "y", "yes"):
        raise StackConfigError("other hardware needs a manually configured PlatformIO project")
    names = _device_names()
    while True:
        codec = input("MQTT payload codec [json/msgpack, default json]: ").strip() or "json"
        if codec in ("json", "msgpack"):
            break
        sys.stdout.write("Choose json or msgpack.\n")
    host = input("MQTT broker host/IP (blank: configure OTA later): ").strip()
    stack = STACK_TEMPLATE.replace('codec = "json"', f'codec = "{codec}"')
    if host:
        while True:
            port = input("MQTT port [1883]: ").strip() or "1883"
            if (
                port.isascii()
                and port.isdecimal()
                and len(port) <= len(str(MAX_PORT))
                and 1 <= int(port) <= MAX_PORT
            ):
                break
            sys.stdout.write("Enter a port from 1 to 65535.\n")
        username = input("MQTT username (blank: anonymous): ").strip()
        stack += "\n[deploy.bridge.ota]\n"
        stack += (
            f"broker_host = {json.dumps(host, ensure_ascii=False)}\nbroker_port = {int(port)}\n"
        )
        if username:
            # TOML accepts Unicode scalars, not JSON's surrogate-pair escapes.
            stack += f"broker_username = {json.dumps(username, ensure_ascii=False)}\n"
            stack += 'broker_password_env = "LSH_OTA_PASSWORD"\n'
    devices = DEVICES_TEMPLATE.split("[devices.panel]", 1)[0]
    devices += "# Add your real actuator/button pins before flashing; no wiring is assumed.\n"
    for name in names:
        devices += f'\n[devices.{name}]\nname = "{name}"\n'
    sys.stdout.write(
        "No passwords saved and no I/O wiring assumed. Configure actual pins before flashing.\n"
    )
    return stack, devices


def _device_names() -> list[str]:
    while True:
        names = [
            value.strip()
            for value in (
                input("Device names, comma-separated [panel]: ").strip() or "panel"
            ).split(",")
        ]
        if len(set(names)) == len(names) and all(
            re.fullmatch(r"[a-z][a-z0-9]{0,31}", n) for n in names
        ):
            return names
        sys.stdout.write(
            "Use distinct names: a lowercase letter followed by lowercase letters/digits, max 32.\n"
        )
