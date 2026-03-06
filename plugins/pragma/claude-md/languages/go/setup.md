# Go Project Setup

## Lint Config Detection

Check for an existing linter configuration:

- `.golangci.yml`
- `.golangci.yaml`

These are config files for golangci-lint, the standard Go linter aggregator.

## Reference Config

If no lint config is found, offer to copy from `reference/go/golangci-lint.yml` as `.golangci.yml`.

The reference config uses golangci-lint v2 format and includes template variables `{org}` and `{repo}` — replace these with the project's actual org and repo name from Step 1.
