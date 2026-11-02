# Contributing

```bash
uv sync
ln -sf ../../scripts/git-hooks/pre-push .git/hooks/pre-push   # lint + tests before each push
uv run pytest -q
uv run --with ruff ruff check src tests scripts
```

- One branch per change, opened as a PR against `main`. CI (lint, tests) must pass.
- Keep diffs small; delete code your change makes obsolete.
- A bug fix comes with a test that fails without it.
- Update the README and `docs/` in the same PR as the behavior they describe.
- Project status and open work: [docs/implementation-status.md](docs/implementation-status.md).

By contributing you agree your work is licensed under Apache 2.0.
