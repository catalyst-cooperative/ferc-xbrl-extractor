# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Copilot, etc.) working in this
repository. Keep it current: treat stale instructions here as a bug, since agents will
follow whatever this file says even after it stops being true.

## Project overview

This package extracts data from FERC's XBRL filings (the format FERC has used for
electronic filing since around 2021) and loads it into SQLite, DuckDB, or Parquet
outputs. It parses FERC's XBRL taxonomies to determine table structure, uses
[Arelle](https://arelle.org/arelle/) to parse individual filings against that
taxonomy, and writes the extracted facts out in a relational form.

It's a library and CLI tool (`xbrl_extract`), not a standalone application. Its
primary consumer is the [PUDL](https://github.com/catalyst-cooperative/pudl) ETL
pipeline, which depends on it to turn FERC Form 1, 2, 6, 60, and 714 XBRL filings into
the `ferc*_xbrl.sqlite` databases PUDL builds on. Changes here that alter output
schemas, table names, or CLI behavior can break PUDL's ETL, so treat those as
higher-risk than internal refactors.

## Setup commands

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and
[Hatch](https://hatch.pypa.io/) for environment and task management -- not pixi,
unlike most other Catalyst Cooperative repositories.

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it isn't
    already available.
- Run `uv tool install hatch` once to get the `hatch` CLI, then `hatch env create` to
    build the default development environment (installs the `dev`, `docs`, `tests`,
    and `types` extras -- see `[tool.hatch.envs.default]` in `pyproject.toml`).
- Run `hatch run prek install` once to install the git pre-commit hooks (run via
    [prek](https://prek.j178.dev/), a fast drop-in replacement for `pre-commit` that
    still reads `.pre-commit-config.yaml`).

## Task commands

Run everything through `hatch run` rather than calling the underlying tools directly
outside their environment, so agents use the same invocations CI does. See
`[tool.hatch.envs.*]` in `pyproject.toml` for the full definitions; the ones agents
will use most:

- `hatch run test:all` -- erase old coverage, run unit and integration tests with
    pytest, and report combined coverage.
- `hatch run test:unit` / `hatch run test:integration` -- run just one suite.
- `hatch run lint:check` -- run `ruff check` and `ruff format --check`. Doesn't modify
    files.
- `hatch run lint:format` -- reformat code and auto-fix lint issues with `ruff`.
- `hatch run types:check` -- type check with `pyrefly` (separate, non-detached env
    from `lint`; see "Gotchas" below).
- `hatch run types:coverage-check` -- enforce the 85% type-coverage floor on `src/`.
    `types:coverage-report` prints the same metric as a human-readable per-module
    table instead of raw JSON.
- `hatch run docs:build` -- build the documentation with Sphinx into
    `docs/_build/html/`. Runs `doc8` first and fails on Sphinx warnings (`-W`).
- `hatch run docs:check` -- run just the `doc8` formatting check on `docs/` and
    `README.rst`.

An agent should run `hatch run lint:check`, `hatch run types:check`,
`hatch run types:coverage-check`, and `hatch run test:all` before considering a
change complete, and `hatch run lint:format` if it touched Python code.

## Code style

- Formatting and most style rules are enforced by `ruff` (see `[tool.ruff]` in
    `pyproject.toml`) and applied automatically by `hatch run lint:format` / the
    `ruff-check` and `ruff-format` pre-commit hooks. Don't hand-format code to match a
    personal preference that conflicts with what `ruff format` produces.
- Type checking uses `pyrefly` at the `basic` preset (`[tool.pyrefly]`), blocking in
    pre-commit and CI, plus the 85% `src/` type-coverage floor above. New code should
    be typed cleanly; suppress a genuine false positive with
    `# pyrefly: ignore[rule-name]` and a short note explaining *why*, not just that
    it is one -- e.g. for `arelle-release` fields typed as plain `str` but narrower
    in our models, prefer letting `pydantic` validate the value at construction and
    note that in the suppression comment, rather than chasing it statically. Only
    raise the preset (e.g. to `strict`) as its own deliberate change, since it will
    likely surface a batch of new errors at once.
- Docstrings use the Google convention (`[tool.ruff.lint.pydocstyle]`).
- Direct runtime `dependencies` in `pyproject.toml` should stay loosely
    version-constrained (lower bounds only, no upper bounds unless there's a known
    incompatibility) since this is a library other projects depend on. The `dev`,
    `docs`, `tests`, and `types` extras are purely for local development and CI, so
    keep those current rather than loose.

## Testing instructions

- Tests live under `tests/`, split into `tests/unit/` (fast, no external
    dependencies) and `tests/integration/` (exercises the CLI entry point end to end
    against example filings under `examples/`).
- Run the full suite with `hatch run test:all`. To iterate quickly on a single test
    file or `-k` expression while debugging, `hatch run test:unit -- <args>` or a
    direct `pytest` invocation inside the `test` env works too, but always confirm
    with `hatch run test:all` before calling something done.
- New behavior needs a test. Bug fixes should add a regression test that fails
    without the fix.

## Documentation

- Documentation source lives under `docs/` as reStructuredText, built with
    [Sphinx](https://www.sphinx-doc.org/) using the `pydata-sphinx-theme` (matching
    the look of PUDL's and other Catalyst docs sites), and published to GitHub Pages
    (only the latest version, not a versioned history).
- API reference docs are generated automatically from docstrings via `sphinx-autoapi`.
- The docs build also generates `llms.txt`, `llms-full.txt`, and a Markdown twin of
    every page (via `sphinx-llm`, configured in `docs/conf.py`) to make the
    documentation more consumable by LLM agents. `docs/_templates/llms-txt-link.html`
    renders the footer link to `llms.txt` -- keep it if you touch the theme config.
- Update `docs/release_notes.rst` for user-facing changes. Add entries to a
    `1.Y.Z (Unreleased)` section at the top of the file (create it, copying the
    format of the most recent released section, if it doesn't exist yet). Reference
    the relevant PR and/or issue number using the `sphinx-issues` roles, e.g.
    `` :pr:`123` `` / `` :issue:`123` ``. Keep each bullet to one concise,
    intent-focused sentence -- describe *what changed and why*, not an enumeration
    of every file or line touched; that's what the PR diff and commit messages are
    for. This has been a recurring correction, so treat a multi-sentence bullet as a
    sign to cut it down before committing.
- Don't trust the file's existing top section number alone to know what the next
    version is -- it can lag behind reality. Run `git tag --sort=-v:refname | head -1`
    to find the actual most-recently-released version, and base the next number on
    that. This repo bumps the patch version for ordinary PRs and the minor version
    for larger or more disruptive changes (infrastructure overhauls, new features);
    only bump the major version if asked to. If the version you're about to write
    already exists as a tag, stop and reconcile the mismatch (e.g. by asking) rather
    than silently overwriting or renumbering.

## Commit / PR instructions

- Before committing, run `hatch run lint:check`, `hatch run types:check`, and
    `hatch run test:all`; CI (`.github/workflows/pytest.yml`) runs the same checks
    (across Python 3.11-3.14 for tests) and will fail the PR otherwise.
- `.github/workflows/docs.yml` builds and, on `main`, deploys the documentation;
    `.github/workflows/release.yml` builds and publishes to PyPI on `v*` tags pushed
    to `main`, and refuses to run unless the tag points at the current head of
    `origin/main`.

## Security & data handling

- This package parses filings from external sources (arbitrary user-supplied XBRL
    zip files via the CLI) using Arelle. Don't disable or weaken any input validation
    around instance/taxonomy parsing without understanding why it's there.
- Don't commit example filings or fixtures containing anything other than public FERC
    data.

## Gotchas

- Hatch environments use `installer = "uv"` and pin `python = "3.14"`, but Hatch still
    resolves *which* concrete interpreter satisfies that pin itself, by searching
    `PATH` (or falling back to its own separate, uv-independent Python distribution
    manager) -- it does not consult `[tool.uv]`'s `python-preference`. If you have
    multiple 3.14.x installs around (Homebrew, uv-managed, etc.), Hatch can silently
    pick a stale one. To force it to use a specific uv-managed interpreter, set the
    `HATCH_PYTHON` environment variable to that interpreter's path, e.g.
    `HATCH_PYTHON="$(uv python find 3.14)" hatch run test:all` -- this is what CI does
    in `.github/workflows/*.yml`, and is worth doing locally too after upgrading the
    Python version via `uv python install`/`uv python pin`. Follow with
    `hatch env prune` to drop any environments already built against the old
    interpreter.
- `hatch run lint:*` is `detached = true` (no runtime deps installed), so `ruff`
    works there but `pyrefly` can't -- it needs pandas/pydantic/duckdb/etc. installed
    to resolve imports, hence its own non-detached `[tool.hatch.envs.types]` env.
- `arelle-release` is a large, slow-to-install dependency (it's a full XBRL
    processor). Don't be surprised if `hatch env create` or CI takes a while the first
    time; this is normal, not a hang.
- The pre-commit/`prek` `pyrefly`, `pyrefly-coverage`, and `unit-tests` hooks are
    local `language: system` hooks, which pre-commit.ci can't run -- they're in its
    `ci.skip` list and enforced instead as separate steps in
    `.github/workflows/pytest.yml`.
- `PUDL_DOCS_DISABLE_INTERSPHINX=1` speeds up doc builds and avoids failures when
    external intersphinx targets (numpy, pandas, etc. doc sites) are temporarily
    unreachable. CI sets this for the `docs` workflow; set it locally too if a docs
    build seems to be hanging or failing on network lookups.
