#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive="${1:-$repo_root/dist/lsh-stack.pyz}"
cd "$repo_root"

mkdir -p "$(dirname "$archive")"
python -m zipapp src \
  -m 'lsh_stack_config.cli:entrypoint' \
  -o "$archive" \
  -p '/usr/bin/env python3'
chmod +x "$archive"

python "$archive" --version
python "$archive" --help
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
python "$archive" new "$tmpdir/installation"
grep -F "lsh-stack.pyz setup" "$tmpdir/installation/README.md"
if python "$archive" new "$tmpdir/legacy.toml"; then
  echo "legacy single-file new target unexpectedly succeeded"
  exit 1
fi
python "$archive" setup --config "$tmpdir/installation/lsh_stack.toml"
python "$archive" check --config "$tmpdir/installation/lsh_stack.toml"
python "$archive" status --config "$tmpdir/installation/lsh_stack.toml"
python "$archive" new-core "$tmpdir/core-only"
test -s "$tmpdir/core-only/lsh_devices.toml"
test -s "$tmpdir/core-only/platformio.ini"
grep -F "platformio run -e core_panel" "$tmpdir/core-only/README.md"
