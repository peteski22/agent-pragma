---
name: implement
description: Implement a feature or fix with automatic validation
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Task, WebFetch, WebSearch
---

# Implement with Validation

Implement the requested feature/fix, then validate before completing.

**Phase 0 is mandatory and must complete successfully before any other phase.**

## Task

$ARGUMENTS

## Phase 0: Inject Applicable Rules

Before starting work, collect and read all applicable project rules.

### Step 1: Identify target directories

Based on the task, identify which directories will contain files to be created or modified.

If uncertain, err on the side of including more directories rather than fewer. Extra rules being applied is safe; missing rules is not.

### Step 2: Collect project rules

Collect project rules from the project's rule directory. Rule file locations vary by agent platform:
- Claude Code: `.claude/rules/*.md`
- OpenCode: `AGENTS.md` (auto-loaded natively)
- Other agents: check agent documentation for project rule conventions

For Claude Code, use the Glob tool to discover `.claude/rules/*.md` files, then the Read tool to load them. OpenCode auto-loads rules from `AGENTS.md` at the platform level. Collect those that exist and are readable. A file is considered "found" only if it exists and can be successfully read.

**Note:** Path-scoped rules (those with `paths:` frontmatter) may be auto-loaded by the agent platform only for matching files. When collecting rules manually, read the frontmatter and apply path-scoped rules only to the target directories they match.

### Step 2a: Check for local supplements

Check for a local supplements file (e.g., `CLAUDE.local.md` for Claude Code) at the project root and read it if present. This is a per-user, unversioned file for machine-specific overrides (e.g., custom validation commands).

If it exists, read it. Pay particular attention to any "Validation Commands" section, which overrides defaults.

### Step 3: Read and apply rules

Read each discovered rule file.
Apply rules in order of precedence (most specific first):

```text
1. Path-scoped language rules with matching paths (highest precedence)
2. Universal rules
```

Earlier rules override later rules where they conflict.

If two rules conflict and precedence is unclear, prefer the more specific rule and note the conflict in the final report.

### Step 3a: Fallback baseline (conditional)

**This step only applies if NO project rule files were found in Step 2.**

If project-specific rules were found and loaded, skip this step entirely and note in report: "Project rules: loaded (N files)"

If no project-specific rules were found, attempt to load the universal baseline from the plugin:

1. **Resolve plugin root:** The skill loader provides the base directory in the header: `Base directory for this skill: <path>`. Derive `PLUGIN_ROOT` as `<base directory>/../..` (skills live at `<plugin-root>/skills/<name>/`, so two levels up).

2. **Validate plugin root:** Check that `$PLUGIN_ROOT/.claude-plugin/plugin.json` exists.
   - If missing → skip fallback, note in report: "Project rules: none found. Plugin baseline unavailable. Proceeding with built-in validator rulesets. Run /setup-project to configure project-specific rules."

3. **Validate baseline file:** Does `$PLUGIN_ROOT/claude-md/universal/base.md` exist and is it readable?
   - If file missing or unreadable → skip fallback, note in report: "Project rules: none found. Plugin baseline unavailable. Proceeding with built-in validator rulesets. Run /setup-project to configure project-specific rules."

4. **Load baseline:** If both checks pass, read `$PLUGIN_ROOT/claude-md/universal/base.md` as the baseline rules.
   - Note in report: "Fallback baseline: loaded from pragma plugin"

This fallback ensures projects without `/setup-project` still get essential rules (branch creation, scope verification, etc.).

### Step 4: Record applied rules

Track which rule files were loaded for the final report, including:
- Which project-specific rule files were loaded (if any)
- Fallback baseline status: not needed, loaded, skipped, or failed (with reason)
- Local supplements status (loaded or not found)

### Step 5: Execute pre-implementation setup

The "Pre-Implementation Setup" section of the loaded rules contains **actions to execute**, not just guidance to follow. The rules file is the single source of truth; this step is the executor.

**If no "Pre-Implementation Setup" section exists** in any loaded rules, skip this step and note in the final report that no pre-implementation setup was defined.

**How to execute:**

1. **Locate the section:** Find the "Pre-Implementation Setup" section in the loaded rules.

2. **Identify actionable items:** Look for:
   - Bash code blocks (` ```bash `) - these are commands to run
   - Imperative instructions ("Check...", "Create...", "Verify...")
   - Conditional actions ("**If...**" statements)

3. **Execute in order:** For each actionable item:
   - Run bash code blocks using the Bash tool
   - Evaluate conditionals and take the action specified in the rules
   - When a conditional requires a decision, ask the user
   - Record outcomes for the final report

4. **Handle failures:** If any command fails or a situation isn't covered by the rules, ask the user for guidance before proceeding.

5. **Record for report:** Track what was executed and outcomes (e.g., branch created, steps skipped, user decisions).

---

## Phase 1: Understand

1. Clarify requirements if ambiguous.
2. **Discover existing patterns before proposing solutions:**
   - Ask "how does Y access X?" not "does X exist in Y?" - directory existence alone doesn't reveal how code flows.
   - Check dependency files (pyproject.toml, package.json, go.mod) for workspace/monorepo patterns.
   - Grep for imports to understand how code flows between components.
   - Look for build artifacts (.egg-info, .venv, dist/, node_modules/, target/) indicating local packages.
   - If the task involves sharing code, find existing shared packages first.
   - If the GitHub issue lists multiple approaches, investigate each sufficiently to make an informed decision.
   - **Architecture violation guard:** If discovered patterns violate architecture rules from the project rules or language-specific validators (e.g., models defined in route files, business logic in handlers, services that are actually repositories):
     1. Do not replicate the violations — follow documented layer responsibilities instead.
     2. Note the pre-existing deviation in the Phase 4 report.
     3. If the codebase systematically deviates (e.g., no repository layer exists, all models are in route files), follow correct architecture for new code where feasible without breaking existing imports or interfaces.
     4. If correct architecture would require creating new layers or significant refactoring, note this in the Phase 4 report and recommend a dedicated refactoring task.
   - **State model scrutiny guard:** If the task involves modifying state enums, status fields, transition logic, or terminal/final state classifications:
     1. For each state classified as terminal/final, verify that all running processes, background jobs, or external systems are actually stopped or cleaned up when entering that state.
     2. If a state is "terminal" only from one system's perspective (e.g., API/UI marks it as done) but not another's (e.g., a worker/Lambda is still running), it is not truly terminal — flag this before implementing.
     3. Check whether entering a terminal state creates a cancellation signal or cleanup action, not just a status label.
     4. If the existing codebase has states where "terminal" means "UI considers it done" but runtime processes continue, note this in the Phase 4 report and ensure new code does not compound the problem.
3. Identify files that need changes based on discovered patterns.
4. **Plan the commit units.** Split the work into logical units, where each unit is one self-contained,
   independently reviewable change. Order them by dependency: shared types and helpers before the code that
   consumes them. Record the list for Phase 2.

   A task touching one concern is one unit. Do not invent units to pad the history.
5. **Determine the commit mode.** The mode governs every committing step in Phases 2 and 3, so settle it
   here, while the plan is fresh and before any code is written. The three modes are:

   - **Green commits** → each unit is committed only once the committed tree passes the project's
     deterministic checks. Every commit passed the project's checks when it was made.
   - **Readable commits** → each unit is committed as one coherent idea without passing on its own. Only
     the branch tip has to pass. Commits read better in review, at the cost of bisect and of building an
     intermediate commit.
   - **No commits** → every unit is implemented without committing, and the planned units are reported so
     the user can split the changeset themselves.

   Settle the mode in this order, and stop at the first case that applies:

   1. **Commits are impossible.** Phase 0 reported that this is not a git repository. Use no commits,
      record the reason as "no git repository", and do not ask.
   2. **The task already states a preference.** The task text or the current session already asks for a
      particular behavior, for example "commit as you go", "atomic commits please", or "one commit only".
      Adopt the matching mode, state which mode you adopted and why, and do not ask. Re-asking a question
      the user has already answered is the defect this phase exists to prevent.
   3. **Ask.** State the planned units so the decision is informed, name the commit rules you will follow,
      and wait for the answer. Ask at most once per run; never re-ask between units.
   4. **No answer is available.** The run is non-interactive, or the user does not answer. Use green
      commits, proceed, and record the mode as "green commits (default, not confirmed)". Never default to
      no commits, because that reproduces the reported defect.

   Then re-split or re-order the remaining units for the chosen mode. Under green commits, fold a unit
   together with whatever it needs to pass its own checks, including its tests and its call sites. Under
   readable commits, keep the smaller coherent units.

   Record the mode and how it was determined for the Phase 4 report.

---

## Phase 2: Implement

Work through the commit units from Phase 1 one at a time. Each unit is implemented and checked before the
next one starts, and committed unless the mode from Phase 1 Step 5 is no commits.

**Before the first unit:** resolve the deterministic check commands once, using the precedence rules in
Phase 3 Step 1. The commit mode was settled in Phase 1 Step 5.

For each unit, in the planned order:

1. Make the code changes for that unit only.
2. Follow the rules loaded in Phase 0.
3. Keep changes focused - don't over-engineer.
4. Then take the branch for the mode settled in Phase 1 Step 5:
   - **Green commits** → stage only the files belonging to the unit, commit it, run the deterministic
     checks, and fix failures with `git commit --amend` until they pass.
   - **Readable commits** → stage only the files belonging to the unit and commit it. Leave the checks to
     Phase 3.
   - **No commits** → leave the unit's changes in the working tree, stage nothing, and move on.
5. Under green or readable commits, record the commit hash and subject for the Phase 4 report. Under no
   commits, record the unit as completed instead.

Every commit message explains the "why", not just the "what".

**Declining a new branch does not disable committing.** Phase 0 asks about branches, and a user who
continues on an existing feature branch can commit normally. Only an absent git repository makes committing
impossible, and Phase 1 Step 5 already resolves that case to no commits.

**If a commit itself fails**, stop before the next unit. A valid repository still rejects a commit for
reasons that have nothing to do with the mode, such as an unset identity, a failed signature, or a hook
that refuses the change. Report the command's error alongside the units already committed, and ask for
guidance. Do not implement further units, and do not fall back to no commits on your own.

**If a unit grows beyond its plan**, split it. Commit the finished part rather than letting the unit absorb
unrelated work.

**If the unit plan proves wrong** (a unit is not independently reviewable, or the order breaks the tree),
re-plan the remaining units and note the change in the Phase 4 report.

---

## Phase 3: Validate

After every unit is implemented, validate the complete change. Under green commits this catches problems
that only appear across units. Under readable commits it is the only deterministic gate, so the branch tip
must pass everything here before Phase 4.

**Before running validators:** Re-check whether any new directories were introduced during implementation. If so, repeat Phase 0 for those directories and include any newly discovered rules.

1. **Run linters first** (deterministic checks):

   **Check rules for custom validation commands:**
   Look for a "Validation Commands" section in loaded project rules, in precedence order:
   1. Local supplements (from Step 2a — highest priority)
   2. Path-scoped rule files (from Step 2)
   3. Universal rule file (from Step 2)

   If custom commands exist at any level, use the highest-precedence match. Otherwise, check for a Makefile with `lint`/`test` targets and use those. If no Makefile targets exist, fall back to these defaults:
   - Go: `golangci-lint run --fix -v`
   - Python: `uv run pre-commit run --all-files`
   - TypeScript: `pnpm run lint` or `npx biome check .`

   **Priority order:** Local supplements > path-scoped language rules > universal rules > built-in defaults. Local supplements have the highest priority to allow per-machine customization without modifying version-controlled rules.

   Fix any issues before proceeding.

2. **Run semantic validators** (LLM checks):
   - Use the Task tool to spawn validators in parallel. For each validator, create a Task with `subagent_type: "general-purpose"` and a prompt instructing the subagent to invoke the validator skill via the Skill tool (e.g., `skill: "security"`) and return the JSON result verbatim.
   - Do NOT use validator names as the `subagent_type` — most validators are skills, not agents. Always use `general-purpose` as the subagent type.
   - **Collect all validator JSON results internally.** Do NOT display raw validator JSON to the user — you will aggregate these results into the Phase 4 summary.
   - Note: This duplicates the dispatch logic in `validate` intentionally — implement needs inline control for the fix-and-re-validate loop. Keep both in sync.
     - `security` (always)
     - `state-machine` (always)
     - `error-handling` (always)
     - `go-effective` (if Go files changed)
     - `go-proverbs` (if Go files changed)
     - `python-style` (if Python files changed)
     - `typescript-style` (if TypeScript files changed)

3. **Fix violations**:
   - HARD violations: must fix.
   - SHOULD violations: fix or justify.
   - WARN: note but don't block.
   - Commit each round of fixes under the mode from Phase 1 Step 5:
     - **Green commits** → amend the unit commit the fix belongs to, or make the fix its own commit when it
       belongs to no single unit. Re-run the deterministic checks against the rewritten commit.
     - **Readable commits** → use `git commit --fixup=<that commit>` where the fix corrects one Phase 2
       commit, and an ordinary commit otherwise. Run `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash`
       before Phase 4, so the history reported is the history that gets reviewed.
     - **No commits** → leave the fixes in the working tree.
   - Record every commit this phase creates, and every rewritten hash, alongside the Phase 2 ledger.

4. **Re-validate** if fixes were made.

5. **After all validators pass, proceed to Phase 4.** Do not stop here — the final output must be the Phase 4 summary, not raw validator output.

---

## Phase 4: Complete

Only after validation passes:

1. Summarize what was implemented.
2. List files changed.
3. List the commits made, in order, and the commit mode in effect with how it was determined: asked,
   stated in the task, or defaulted.
4. List rules that were applied (from Phase 0).
5. Note any warnings or justified SHOULD violations.
6. Note any rule conflicts encountered.
7. Note any change to the Phase 1 unit plan, and any reason commits were skipped.

## Output Format

```
## Implementation Complete

**Task:** [what was requested]

**Branch:** `branch-name` (created | existing | continued | skipped)

**Rules Applied:**
- python rules (scoped to backend/**)
- universal rules
- local supplements

**Changes:**
- file.go: [what changed]
- file_test.go: [what changed]

**Commits:** green commits | readable commits | no commits (user choice) | none (no git repository)
[suffix "(default, not confirmed)" where the mode was defaulted; list the planned units where nothing was
committed]
- `abc1234` feat(scope): first logical unit
- `def5678` feat(scope): second logical unit

**Validation:**
- Linting: ✓ passed
- Security: ✓ passed (no HARD, no unexplained SHOULD)
- Go Effective: ✓ passed (no HARD, 1 SHOULD justified, 1 WARN noted)

**Justified SHOULD items:**
- security:42 - Deferred input sanitization (handled by upstream middleware)
- go-effective:78 - 6-parameter function (options pattern would over-complicate here)

**Warnings:**
- [any WARN items to be aware of]

Ready for review.
```

## Rules

- Phase 0 is mandatory. Do NOT skip rule injection.
- Plan commit units in Phase 1 and settle the commit mode there. Under green or readable commits, commit
  every unit. Under no commits, commit nothing. Do NOT batch agreed work into a single commit, do NOT
  re-ask per unit, and do NOT commit anything once the user has chosen no commits.
- Under readable commits, do NOT report completion while the branch tip fails.
- Do NOT skip validation.
- Do NOT say "done" until validation passes.
- Do NOT ignore HARD or SHOULD violations.
- If stuck in a validation loop (3+ attempts), report the issue and ask for guidance.
