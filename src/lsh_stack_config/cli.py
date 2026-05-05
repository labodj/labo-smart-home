"""Command-line interface for the end-to-end LSH stack composer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .composer import compose_stack
from .core_export import load_core_export
from .errors import StackConfigError
from .models import JsonObject, StackConfig
from .parser import load_stack_config
from .render import render_report, stack_json, write_output_tree

if TYPE_CHECKING:
    from collections.abc import Sequence

_TEMPLATE = """#:schema ./schemas/lsh_stack.schema.json

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
expose_state_context = "none"
expose_state_key = "lsh_state"
export_topics = "flow"
export_topics_key = "lsh_topics"
expose_config_context = "none"
expose_config_key = "lsh_config"
other_actors_context = "global"

# [[network_clicks]]
# source = "panel.logic_button"
# type = "long"
# actors = [{ device = "lights", actuators = "all" }]
# other_actors = ["zigbee_table_lamp"]
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``lsh-stack`` command."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _init(args)
        if args.command == "generate":
            return _generate(args)
        if args.command == "check":
            return _check(args)
        if args.command == "report":
            return _report(args)
    except StackConfigError as exc:
        sys.stderr.write(f"lsh-stack error: {exc}\n")
        return 2
    parser.print_help(sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lsh-stack",
        description="Compose bridge, coordinator and Node-RED config from LSH TOML files.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="write a guided lsh_stack.toml template")
    init.add_argument("path", nargs="?", type=Path, default=Path("lsh_stack.toml"))
    init.add_argument("--force", action="store_true", help="overwrite an existing file")

    for command in ("generate", "check", "report"):
        child = subparsers.add_parser(command, help=f"{command} an lsh_stack.toml file")
        child.add_argument("config", type=Path, help="path to lsh_stack.toml")
        child.add_argument("--core-tool", type=Path, help="override lsh-core generator path")
        if command == "generate":
            child.add_argument(
                "--output-dir",
                type=Path,
                help="write generated files instead of printing one JSON document",
            )
    return parser


def _init(args: argparse.Namespace) -> int:
    path = args.path.resolve()
    if path.exists() and not args.force:
        raise StackConfigError(f"{path} already exists; pass --force to overwrite it.")
    path.write_text(_TEMPLATE, encoding="utf-8")
    sys.stdout.write(f"wrote {path}\n")
    return 0


def _generate(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    if args.output_dir is None:
        sys.stdout.write(stack_json(stack))
        return 0

    written = write_output_tree(args.output_dir.resolve(), stack)
    sys.stdout.write(render_report(config, stack))
    sys.stdout.write("written files:\n")
    for path in written:
        sys.stdout.write(f"- {path}\n")
    return 0


def _check(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    sys.stdout.write(render_report(config, stack))
    return 0


def _report(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    sys.stdout.write(render_report(config, stack))
    return 0


def _compose(config_path: Path, core_tool: Path | None) -> tuple[StackConfig, JsonObject]:
    config = load_stack_config(config_path)
    core_export = load_core_export(config.core, override_tool=core_tool)
    stack = compose_stack(config, core_export)
    return config, stack
