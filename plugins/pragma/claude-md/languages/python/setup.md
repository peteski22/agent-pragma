# Python Project Setup

## Lint Config Detection

Check for an existing linter or formatter configuration:

- `.pre-commit-config.yaml` (pre-commit — runs ruff, formatters, and other hooks)
- `ruff.toml` or `.ruff.toml` (ruff standalone config)
- `[tool.ruff]` section in `pyproject.toml` (ruff config embedded in project metadata)

Any of these indicate the project already has lint tooling configured.

## Reference Config

If no lint config is found, offer to copy from `reference/python/pre-commit-config.yaml` as `.pre-commit-config.yaml`.

For monorepos (Python detected in a subdirectory rather than root), use `reference/python/pre-commit-config-monorepo.yaml` instead and mention the difference to the user.

The reference config uses pre-commit with ruff for linting and formatting, which matches the validation command in the Python language rules (`uv run pre-commit run --all-files`).
