"""Render the controller batch tasks exposed by PlatformIO IDE."""

from __future__ import annotations


def render_platformio_core_targets_script() -> str:
    """Return a helper that builds/cleans the configured profile, never uploads it."""
    return '''\
"""Generated controller batch tasks. Regenerate with lsh-stack; do not edit."""

import subprocess
import sys

Import("env")


def _run_batch(target, source, env):
    action = "clean" if str(target[0]) == "lsh_core_clean_all" else "build"
    names = env.GetProjectOption("custom_lsh_stack_core_envs", "").split()
    if not names:
        raise RuntimeError("Missing controller environments; regenerate the stack.")
    command = [sys.executable, "-m", "platformio", "run"]
    for name in names:
        command.extend(["-e", name])
    if action == "clean":
        command.extend(["-t", "clean"])
    return subprocess.call(command, cwd=env.subst("$PROJECT_DIR"))


for action in ("build", "clean"):
    env.AddCustomTarget(
        name="lsh_core_" + action + "_all",
        dependencies=None,
        actions=_run_batch,
        title="LSH " + action.title() + " All Controllers",
        description=action.title() + " every controller using this environment's profile",
        always_build=True,
    )
'''
