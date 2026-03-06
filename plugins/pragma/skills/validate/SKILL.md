---
name: validate
description: Run all validators against recent code changes
allowed-tools: Task, Bash
---

# Validation Orchestrator

Run all applicable validators against recent code changes.

## Step 1: Determine which validators to run

Check what files have changed:
```bash
git diff HEAD~1 --name-only --diff-filter=ACMRT 2>/dev/null || git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || git diff --name-only --diff-filter=ACMRT
```

Based on file extensions, select validators:
- `.go` files → run `go-effective`, `go-proverbs`
- `.py` files → run `python-style`
- `.ts` or `.tsx` files → run `typescript-style`
- All files → run `security`
- All files → run `state-machine`
- All files → run `error-handling`

## Step 2: Run validators in parallel

Use the Task tool to spawn validators in parallel. For each applicable validator, create a Task with:
- subagent_type: "general-purpose"
- prompt: Use the Skill tool to invoke the validator. The prompt must explicitly require skill invocation and verbatim JSON output.

**Example Task prompt for each validator:**
```text
Invoke the `go-effective` skill using the Skill tool (skill: "go-effective"). Return its JSON output verbatim — do not summarize, reformat, or re-implement the validation logic.
```

**Go files changed:**
1. Task: Invoke `go-effective` skill and return JSON output verbatim.
2. Task: Invoke `go-proverbs` skill and return JSON output verbatim.
3. Task: Invoke `security` skill and return JSON output verbatim.
4. Task: Invoke `state-machine` skill and return JSON output verbatim.
5. Task: Invoke `error-handling` skill and return JSON output verbatim.

**Python files changed:**
1. Task: Invoke `python-style` skill and return JSON output verbatim.
2. Task: Invoke `security` skill and return JSON output verbatim.
3. Task: Invoke `state-machine` skill and return JSON output verbatim.
4. Task: Invoke `error-handling` skill and return JSON output verbatim.

**TypeScript files changed:**
1. Task: Invoke `typescript-style` skill and return JSON output verbatim.
2. Task: Invoke `security` skill and return JSON output verbatim.
3. Task: Invoke `state-machine` skill and return JSON output verbatim.
4. Task: Invoke `error-handling` skill and return JSON output verbatim.

**Mixed languages:** Combine all applicable validators. Security, state-machine, and error-handling always run exactly once regardless of how many languages are detected.

Run all applicable Tasks in parallel (multiple Task calls in one response).

## Step 3: Aggregate and present results

Collect all validator outputs and present a human-readable summary. Do NOT display raw validator JSON to the user — interpret and summarise the results.

```markdown
# Validation Results

| Validator | Result | HARD | SHOULD | WARN |
|-----------|--------|------|--------|------|
| {validator} | {✓ pass / ✗ fail} | {count} | {count} | {count} |

## HARD violations (must fix)
- **{validator}** `{file}:{line}` — {rule description}

## SHOULD violations (fix or justify)
- **{validator}** `{file}:{line}` — {rule description}
  - *Accepted:* {reason — e.g., pre-existing code outside diff scope, justified trade-off}

## Warnings
- {count} advisory warnings from {validator} ({brief context})

## Verdict
**PASS / PASS with warnings / FAIL** — {1-2 sentence summary with reasoning}
```

**Important formatting rules:**
- One line per validator in the summary table.
- List HARD violations with file location and rule.
- For each SHOULD violation, explain why it was accepted or flag it for fixing.
- Group warnings concisely — don't list every warning individually unless actionable.
- The verdict must explain the reasoning (e.g., "all violations are in pre-existing code outside the diff scope").
- Omit empty sections (e.g., if no HARD violations, don't include the HARD violations heading).

## Step 4: Verdict

If any HARD violations or unjustified SHOULD violations:
- **FAIL** - list what must be fixed

If only warnings:
- **PASS with warnings** - note them but don't block

If clean:
- **PASS** - ready for commit
