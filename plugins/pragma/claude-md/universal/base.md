# Universal Rules

These rules apply to all projects regardless of language or framework.

Rules are organized by timing: when they should be applied during the workflow.

**Contents:**
- [Decision Order](#decision-order) - Priority for all decisions
- [Pre-Implementation Setup](#pre-implementation-setup) - Actions to execute before coding
- [Implementation Guidelines](#implementation-guidelines) - Guidance to follow while coding
- [Pre-Completion Guidelines](#pre-completion-guidelines) - Verify before marking done

---

## Decision Order

Use this priority for all work:

1. Correctness and safety
2. Maintainability and clarity
3. Developer velocity
4. Performance optimization

Never trade a higher priority for a lower one without discussing the trade-off with the user and getting explicit approval.

---

## Pre-Implementation Setup

Execute these actions before writing any code.

### Git Workflow

Check current branch:

```bash
git branch --show-current
```

**If on `main` or `master`**, create a feature branch:

```bash
# Replace <prefix> and <short-description> with actual values
git checkout -b <prefix>/<short-description>
```

**If not in a git repository**, skip git steps and note in report.

**If there are uncommitted changes**, you MUST ask the user before proceeding. Present these options:
- Stash the changes
- Commit the changes first
- Continue with uncommitted changes in the working tree

Do NOT stash, commit, or discard uncommitted changes without explicit user approval.

**If in detached HEAD state**, ask user whether to create a branch from current commit.

**If the proposed branch already exists**, ask user: switch to existing branch, or use a different name?

**If already on a feature branch**, confirm with user whether to continue on this branch or create a new one.

Use descriptive branch names with these prefixes:

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feature/` | New functionality | `feature/add-user-auth` |
| `fix/` | Bug fixes | `fix/login-redirect-loop` |
| `refactor/` | Code improvements | `refactor/api-client-types` |
| `docs/` | Documentation only | `docs/update-readme` |
| `chore/` | Maintenance tasks | `chore/upgrade-dependencies` |

### Scope Verification

Before coding:

- If the task is ambiguous, clarify requirements with the user.
- If the task involves breaking changes to public APIs, confirm impact with the user.
- If the task scope seems larger than requested, verify intent before expanding.

### Pattern Discovery

Before proposing a solution, understand how the codebase already works.

**Core principle:** Ask "how does Y access X?" not "does X exist in Y?"

Checking if a directory exists tells you nothing about how code flows. Instead, trace the actual connections: grep for imports, check dependency files, examine how components are wired together.

**When implementing a new instance of something, find existing instances first.** Adding a new API endpoint? Study existing endpoints. New CLI command? Look at similar commands. New provider/adapter? Find existing providers. Copy their patterns unless there's a specific reason to deviate.

**Concrete checks before implementing:**
- **File paths/config locations:** Search for similar paths to find existing constants or variables instead of hardcoding strings.
- **Error messages:** Check how errors are formatted elsewhere (wrapping patterns, message style).
- **API responses:** Find existing response structures before creating new ones.
- **Logging:** Match existing log levels, formats, and context fields.
- **Dependencies:** Check if a package already provides the functionality you need.

**If the task involves sharing code between components**, find existing shared packages first and follow established patterns before proposing new ones.

**If a GitHub issue lists multiple approaches**, investigate each sufficiently to make an informed decision.

### Research

- If CQ is available (as a skill, MCP server, or plugin), query it before starting work. CQ surfaces known pitfalls, integration gotchas, and undocumented quirks that training data misses.
- Do not rely on training data for facts that can be verified. Look up current documentation, API references, and library versions rather than assuming recalled knowledge is correct. Training data may be outdated, incomplete, or confidently wrong.
- Use WebSearch or WebFetch to look up current information, especially for:
  - Library/framework APIs that change frequently.
  - Cloud provider documentation (AWS, GCP, Azure).
  - Language features added recently.
  - Version-specific behavior.

---

## Implementation Guidelines

Follow these while writing code.

### Code Quality

- Never introduce security vulnerabilities (OWASP top 10).
- Avoid over-engineering. Only make changes that are directly requested or necessary.
- Do not add features, refactor code, or make "improvements" beyond what was asked.
- Keep solutions simple and focused.
- Handle error paths intentionally; do not swallow errors.
- Runtime-visible strings (error messages, log lines, wire responses) describe conditions in domain terms. Do not name libraries, schema columns, or internal classes — they couple your interface to internals.

### Scope Discipline

- Do not perform optimization, cleanup, or refactoring beyond what was requested without user approval.
- When you notice opportunities for improvement outside the requested scope, surface them — describe what you found, the benefit, and the cost. The user may choose to include it now, defer it, or ask you to create a GitHub issue for follow-up.
- The goal is high quality code, not the shortest path to task completion. Raising these opportunities is valuable; acting on them without discussion is not.
- When work is needed for correctness, safety, or to complete the requested task but falls outside the original scope, do the minimal required amount and explain why. "Minimal required amount" means minimizing the changeset while maintaining high quality — not shortcuts or hacky solutions.

### Test-First Development

- Write a failing test before implementation code where feasible.
- For bug fixes, reproduce the bug with a failing test before changing code. Confirm the test fails for the correct reason.
- Apply the minimal change required to make the failing test pass.
- Skip test-first only when the cost clearly outweighs the benefit (exploratory prototyping, pure configuration, cosmetic changes).

### Design Principles

- Prefer deep modules: simple interfaces that hide complex implementations. A module that exposes most of its complexity through its interface adds overhead without reducing cognitive load.
- Hide information behind well-defined boundaries. Internal representations, storage formats, and implementation strategies should not leak through APIs.
- Extract an abstraction when the third instance of a pattern appears — not before. Two similar cases are coincidence; three are a pattern.
- Budget complexity: every new abstraction, indirection, or layer must simplify more code than it complicates. If it doesn't pay for itself, inline it.
- Prefer narrow, specific interfaces over broad, general ones. A function that does one thing well is more useful than one that does many things approximately.

### Strong Typing

- Model a closed set of valid values as a named type with constants (an enum), not a bare primitive. Validate untrusted input into the type at the boundary, keep it typed through the code, and convert to a primitive only where an external API demands it.
- Do not over-type open-ended values. Free text or user content stays a plain string — there is no enumerable set to protect. Use language-standard path types where they exist (e.g., `pathlib.Path` in Python) but do not create custom wrappers around primitives that have no invariant to enforce.
- Keep signatures within the language's parameter norm; bundle cohesive data into a validated type rather than appending another positional argument.
- Prefer the standard library's modern idioms over hand-rolled equivalents.

### Docstrings and Comments

- Default to writing no comments. Add one only when the why is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug.
- A docstring documents the intent of the unit and the contract it offers. Do not reference callers, downstream behavior, or test code. Do not assume or describe context that exists only at the call site — the docstring must be intelligible without knowing who calls the function or why.
- Only describe this function, class, or module. Implementation details of other modules do not belong here.
- Use US English in code, docstrings, comments, and identifiers.

### Dependencies

- Do not add new dependencies without discussing with the user first.
- When proposing a dependency, research and present: maintenance activity (last release date, commit frequency), contributor count, GitHub stars, known security advisories, and license compatibility.
- Prefer standard library solutions where they exist. A dependency is justified when it saves significant complexity and has a healthy maintenance profile.
- Supply chain risk is real. A dependency with few maintainers, infrequent releases, or no recent activity is a liability — flag it explicitly.

### Communication

- Be direct and objective. Avoid sycophantic responses.
- If you made a mistake, acknowledge it specifically rather than generic agreement.
- When uncertain, investigate first and/or ask the user, rather than guessing.

---

## Pre-Completion Guidelines

Verify these before marking work as done.

### Validation

- Prefer `Makefile` targets when available (`make lint`, `make test`, `make check`).
- Fall back to language-specific commands from `.claude/rules/{lang}.md` when no Makefile target exists.
- Run linting and formatting checks before considering work complete. Do not ship changes that fail lint or format checks.
- If full-suite checks are expensive, run targeted checks and note what was skipped.

### Commits

- Follow atomic commit principles:
  - Each commit should represent one logical change.
  - Commits should be self-contained and independently reviewable.
  - Don't mix unrelated changes in a single commit.
  - Don't commit half-finished work; use stash if needed.
- Commit each logical unit of work as it is completed, not at the end. Retroactively splitting a large changeset into atomic commits is painful and error-prone (repeated stash/apply cycles across files). Committing as you go produces a clean, reviewable history naturally.
- Write clear commit messages that explain the "why", not just the "what".

### Pull Requests

- Push feature branches and create Pull Requests to merge into `main`.
- Keep PRs focused; large PRs are hard to review.
- Link PRs to issues using keywords: `Fixes #123`, `Closes #456`.
- Rebase feature branches onto `main` before merging to keep history linear.
- Squash commits if the PR contains fixup commits; preserve meaningful commit history otherwise.

---

## Rule Authority

If there is any discrepancy between CLAUDE.md guidance and validator agent behavior, the validator is authoritative. Validators encode the precise, enforceable rules.
