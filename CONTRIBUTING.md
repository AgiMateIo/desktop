# Contributing to AgiMate Desktop

Thanks for taking the time. Issues and pull requests are welcome.

## Setup

The project uses [uv](https://docs.astral.sh/uv/). The Python version is pinned in
`.python-version` (3.12); 3.11 is the minimum.

```bash
uv sync          # creates .venv from pyproject.toml + uv.lock
uv run main.py   # runs the tray agent
```

## Before you open a pull request

```bash
uv run pytest
uv run pytest --cov=core --cov=ui --cov=plugins --cov-report=term-missing
```

New behaviour comes with tests. Core components sit at ~97% coverage, and a change
that drops it needs one more commit, not an exception.

## Adding a trigger or a tool

That is a plugin, not a change to the core — [PLUGINS.md](PLUGINS.md) is the guide, and
`tests/` shows the testing patterns the existing plugins follow.

## Commits

A concise subject in the imperative mood, capitalised, with no type prefix:

```
Upload binary tool results as files instead of base64
```

A body only when the *why* is not obvious from the subject; wrap it at ~72 characters.

## Contributor License Agreement

Contributors sign the
[CLA](https://github.com/AgiMateIo/agimate-backend/blob/master/CLA.md) once, on their
first pull request, by replying to a bot comment. One signature covers every AgiMate
repository.

## Security

Found a security problem? Do not open an issue — follow the
[security policy](https://github.com/AgiMateIo/.github/blob/main/SECURITY.md).
