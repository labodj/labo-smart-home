"""Run lsh-stack from a source checkout without installing the package."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

main = import_module("lsh_stack_config.cli").main
raise SystemExit(main())
