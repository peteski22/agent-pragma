# TypeScript Project Setup

## Lint Config Detection

Check for an existing linter or formatter configuration:

- `biome.json` or `biome.jsonc` (Biome — combined linter and formatter)
- `.eslintrc.*` or `eslint.config.*` (ESLint — traditional JS/TS linter)
- `prettier.config.*` or `.prettierrc*` (Prettier — formatter, often paired with ESLint)

Any of these indicate the project already has lint tooling configured.

## Reference Config

If no lint config is found, offer to copy from `reference/typescript/biome.json` as `biome.json`.

The reference config uses Biome for combined linting and formatting, which matches the TypeScript language rules.
