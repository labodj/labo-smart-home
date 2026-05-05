# Quality Gate

Every public LSH repository should expose one local command that matches the default CI
quality gate:

```bash
npm run check
```

CI jobs that need Node.js should request `lts/*`, so the default gate follows the
current active Node.js LTS line without hard-coding a major release.

The exact checks depend on the languages used by the repository, but the contract is the
same: formatting, linting, type checks, tests and package or build smoke tests should be
available from that command whenever they are relevant.

## Shared Baseline

All public repositories should include:

- `format`: rewrite supported files in the repository style;
- `format:check`: fail when supported files are not formatted;
- `lint:md`: lint Markdown documentation;
- `fix`: apply the safe automatic fixes supported by that repository;
- `check`: run the full local quality gate used by CI.

Markdown and structured metadata should use Prettier. Markdown prose should also pass
`markdownlint-cli2`. Workflow files should be included in Prettier checks, because CI is
now part of the product surface.

## Python Tooling

Repositories with Python tools should add:

- `ruff format --check`;
- `ruff check`;
- `mypy --strict`;
- `pytest`;
- any extra type checker already adopted by the repository, such as `pyrefly`.

Use `uv` to keep the Python toolchain locked and reproducible.

## TypeScript Packages

Runtime packages should keep the stricter Node.js gate:

- TypeScript type checking;
- ESLint with `--max-warnings=0`;
- Prettier;
- Markdown linting;
- `knip --strict`;
- build, tests with coverage and production dependency audit;
- package verification before publish.

## C++ and PlatformIO

Firmware repositories should include:

- `clang-format --dry-run --Werror` for tracked C/C++ sources;
- PlatformIO builds for public examples;
- PlatformIO static analysis where the signal is stable enough for CI.

Generated protocol headers may be excluded from clang-format when their layout is owned
by a generator. The exclusion should be explicit in the repository, not hidden in CI.

## Rule of Thumb

`npm run check` should be boring. If a maintainer runs it locally and it passes, the
normal CI quality job should not discover a different class of style, lint or type
failure later.
