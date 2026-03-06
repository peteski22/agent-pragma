---
name: review
description: Review recent changes - run all validators and report status
allowed-tools: Bash, Read, Glob, Grep, Task
---

# Review Changes

Run all applicable validators against recent changes and report findings.

**Step 2 (rule injection) runs before validation.** If no project rules are found, validation continues with validator built-in rulesets. Run `/setup-project` to configure project-specific rules.

## Step 1: Identify what changed

Get changed files. Try in order until one succeeds:

```bash
# 1. Committed changes (most common)
git diff HEAD~1 --name-only --diff-filter=ACMRT

# 2. Staged changes (pre-commit)
git diff --cached --name-only --diff-filter=ACMRT

# 3. Unstaged changes (working directory)
git diff --name-only --diff-filter=ACMRT
```

The `--diff-filter=ACMRT` includes Added, Copied, Modified, Renamed, Type-changed (excludes Deleted).

Collect the list of changed files and their directories.

## Step 2: Inject applicable rules

Collect project rules from the project's rule directory. Rule file locations vary by agent platform:
- Claude Code: `.claude/rules/*.md`
- OpenCode: files listed in `opencode.json` `instructions` array
- Other agents: check agent documentation for project rule conventions

For Claude Code, use the Glob tool to discover `.claude/rules/*.md` files, then the Read tool to load them. OpenCode auto-loads rules from `opencode.json` at the platform level.

**Path-scoped filtering:** Always include universal and local-supplements rule files. For files with `paths:` frontmatter, include only if at least one declared path pattern matches a changed file from Step 1. Files without `paths:` frontmatter are treated as global and always included. This prevents unrelated language rules from being applied (e.g., Go rules on a Python-only change).

De-duplicate (a rule file only needs to be read once even if multiple files share it).

**If no rule files are found:** Log "No project rules found — using validator built-in rulesets." and skip to Step 3. Validators have built-in rules and do not require project-specific rule files to function.

**Precedence:** Most specific (path-scoped) rules override more general (universal) rules. Local supplements have highest priority.

If two rules conflict and precedence is unclear, prefer the more specific rule and note the conflict in the report.

Record which rule files were loaded.

## Step 2a: Check for local supplements

Check for a local supplements file (e.g., `CLAUDE.local.md` for Claude Code) at the project root and read it if present. This is a per-user, unversioned file for machine-specific overrides (e.g., custom validation commands).

If it exists, read it. Pay particular attention to any "Validation Commands" section, which overrides defaults.

## Step 3: Run deterministic checks

**Check rules for custom validation commands first:**
Look for a "Validation Commands" section in loaded project rules, in precedence order:
1. Local supplements (from Step 2a — highest priority)
2. Path-scoped rule files (from Step 2)
3. Universal rule file (from Step 2)

Use the highest-precedence match.

If no custom commands found, use these defaults based on file types:

**Go:**
```bash
golangci-lint run -v 2>&1 | tail -50
```

**Python:**
```bash
uv run pre-commit run --all-files 2>&1 | tail -50
```

**TypeScript:**
```bash
pnpm run lint 2>&1 | tail -50
# or: npx biome check . 2>&1 | tail -50
```

Report linter results. If linters fail, report and stop - fix these first.

## Step 4: Run semantic validators

Use the Task tool to spawn validators in parallel based on what changed:

**Always run:**
- `security`
- `state-machine`
- `error-handling`

**If Go files changed (.go):**
- `go-effective`
- `go-proverbs`

**If Python files changed (.py):**
- `python-style`

**If TypeScript files changed (.ts, .tsx):**
- `typescript-style`

Collect all results.

## Step 5: Aggregate and report

```
## Review Results

### Rules Applied
- python rules (scoped to backend/**)
- universal rules

### Files Changed
- cmd/main.go
- internal/service/handler.go
- internal/service/handler_test.go

### Linting
✓ golangci-lint passed

### Security Validation
✓ passed (no HARD, no unexplained SHOULD)

### State Machine Validation
✓ passed (no HARD, no SHOULD)

### Go Effective Validation
✗ FAILED (1 HARD, 1 SHOULD unexplained)

**HARD violations (must fix):**
1. handler.go:45 - Exported function `ProcessRequest` missing doc comment

**SHOULD violations (fix or justify):**
1. handler.go:78 - Function has 6 parameters (>5 requires justification)

**Warnings:**
1. handler.go:120 - Complex function, consider breaking up

### Summary
- Rules applied: 2
- Hard violations: 1
- Should violations: 1 (0 justified)
- Warnings: 1

### Recommended Actions
1. Add doc comment to ProcessRequest
2. Consider using options pattern for ProcessRequest parameters
```

## Rules

- Step 2 (rule injection) must be attempted. If no project rules exist, proceed with validator built-in rulesets.
- Report ALL findings, don't summarize away details.
- Be specific with file:line locations.
- Clearly separate HARD/SHOULD/WARN severity.
- Note any rule conflicts encountered.
- If everything passes, say so clearly.
