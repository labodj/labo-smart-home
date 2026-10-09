#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive="${1:-$repo_root/dist/lsh-stack.pyz}"
cd "$repo_root"

mkdir -p "$(dirname "$archive")"
python - "$archive" <<'PY'
import sys
import zipapp

zipapp.create_archive(
    "src",
    target=sys.argv[1],
    main="lsh_stack_config.cli:entrypoint",
    interpreter="/usr/bin/env python3",
    filter=lambda path: "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"),
)
PY
chmod +x "$archive"

python "$archive" --version
python "$archive" --help
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
printf 'y\nsalotto,cucina\njson\n\n' | python "$archive" new "$tmpdir/installation" --interactive
grep -F "lsh-stack.pyz setup" "$tmpdir/installation/README.md"
if python "$archive" new "$tmpdir/legacy.toml"; then
  echo "legacy single-file new target unexpectedly succeeded"
  exit 1
fi
# Use the copied launcher: moving/deleting the downloaded archive must not break setup.
launcher="$tmpdir/installation/lsh-stack.pyz"
python "$launcher" setup --config "$tmpdir/installation/lsh_stack.toml"
test -s "$tmpdir/installation/core/.pio/build/core_salotto/firmware.hex"
test -s "$tmpdir/installation/core/.pio/build/core_cucina/firmware.hex"
test -s "$tmpdir/installation/bridge/.pio/build/bridge_littlefs/firmware.bin"
test -s "$tmpdir/installation/generated/node-red-flow.json"
python "$launcher" check --config "$tmpdir/installation/lsh_stack.toml"
python "$launcher" doctor --strict --config "$tmpdir/installation/lsh_stack.toml"
# The IDE/default CLI build must follow renamed devices too, not the bootstrap panel.
# PlatformIO may clean other build artifacts after the first generated headers appear.
platformio run -d "$tmpdir/installation/core"
test -s "$tmpdir/installation/core/.pio/build/core_salotto/firmware.hex"
(
  cd "$tmpdir/installation/core"
  python ../lsh-stack.pyz status
  python ../lsh-stack.pyz core build --all --debug --dry-run
  python ../lsh-stack.pyz bridge build --debug --dry-run
)
python "$launcher" templates check --config "$tmpdir/installation/lsh_stack.toml"
python "$archive" new-core "$tmpdir/core-only"
test -s "$tmpdir/core-only/lsh_devices.toml"
test -s "$tmpdir/core-only/platformio.ini"
grep -F "platformio run -e core_panel" "$tmpdir/core-only/README.md"
