# Star-Chamber Protocol

<!-- Single source of truth for the star-chamber review protocol.
     Referenced by both skills/star-chamber/SKILL.md (explicit /star-chamber)
     and agents/star-chamber.md (auto-invocation).
     Both consumers set $STAR_CHAMBER_PATH before following this protocol. -->

## Table of Contents

- [Runtime Constraint](#runtime-constraint)
- [Step 0: Check Prerequisites](#step-0-check-prerequisites)
- [Invocation Modes: Code Review vs Design Question](#invocation-modes-code-review-vs-design-question)
- [Step 1: Identify Review Targets](#step-1-identify-review-targets)
- [Step 2: Gather Context](#step-2-gather-context)
- [Step 3: Invoke Star-Chamber](#step-3-invoke-star-chamber)
- [Step 4: Present Results to User](#step-4-present-results-to-user)
- [Debate Mode](#debate-mode)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Cost Warning](#cost-warning)

## Runtime Constraint

**Each Bash tool invocation in Claude Code runs in a separate subprocess.** Shell variables do not persist between invocations. **Use `;` (not `&&`) to chain variable assignments with subsequent commands in single-line invocations** — `&&` breaks variable propagation in `bash -c` contexts. Multi-line code blocks within a single Bash tool invocation naturally preserve variables.

**Avoid pipelines (`|`) when shell variables are involved.** Some AI coding tool runtimes (including Claude Code as of March 2026) silently empty all `$VAR` expansions when a `|` appears in the command. Use temp files instead of pipes.

**Cross-invocation file access rules:**
- **Reading** artifacts from prior Bash invocations (result JSON, synthesis files): Use the **Read tool** with a literal path. Do NOT use `cat`, `python3 -c`, or shell commands — these trigger permission prompts.
- **Writing** to the temp directory: Use **Bash** (`cat > file << 'EOF'`, redirection). The user has already approved the temp directory. Do NOT use the Write tool — it triggers a file-creation permission prompt for paths outside the project.
- **Within a single invocation:** Shell file manipulation (`cat`, `grep`, `awk`) is fine — the restriction applies to cross-invocation references only.

`$STAR_CHAMBER_PATH` is set by the caller:
- **Skill invocation:** The skill loader provides the base directory in the header. The skill sets `STAR_CHAMBER_PATH` to that directory.
- **Agent invocation:** The agent discovers the path via Glob and sets `STAR_CHAMBER_PATH` to the directory containing PROTOCOL.md.

`$PLUGIN_ROOT` can be derived from `$STAR_CHAMBER_PATH` as `$STAR_CHAMBER_PATH/../..` when needed (e.g., to access reference configs). Validate the derivation by checking that `$PLUGIN_ROOT/.claude-plugin/plugin.json` exists before using it.

**CLI invocation:** Star-chamber is a PyPI package with a CLI entry point. Use `uvx` to run it in an isolated environment:

```bash
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber <command> [options] [arguments]
```

`uvx` installs `star-chamber` from PyPI (cached after first run) and executes in isolation — no interference with the host project's environment.

**Version:** This protocol targets star-chamber **0.11.0 or later**, whose config routes gateway traffic through a top-level `otari` object. A pre-0.2 `"platform": "any-llm"` config is rejected by the loader; regenerate it (see Step 0) if you hit that error.

The package version and the protocol version it reports are different numbers that happen to read alike here. 0.11.0 reports a `spec_version` of 0.11, while 0.10.0 reported 0.9, because the spec is versioned separately and its 0.7, 0.8 and 0.10 revisions were merged without ever shipping in a release. Read the reported value rather than inferring it from the package version.

0.11.0 is the floor for eight reasons. The first two fail late rather than at install time, the next four do not fail at all, and the last two change what the council reports. 0.9.0 is not one of them, because it only opens the published schema so that a consumer validating against an older copy of it is not rejected on a field that copy predates, and this protocol never validates output against a schema. The reasons, in order:

- 0.4.2 is the first release to declare the `otari` extra used below. Asking an earlier 0.4.x for that extra is not an error — uv warns on stderr, installs nothing, and exits 0 — so the council starts and then fails at its first provider call.
- 0.4.3 is the first release whose extra requires an Otari client that speaks the `/api/v1` API root. The hosted otari.ai gateway and self-hosted Otari 0.6.0 or later serve only that root, so an older client, which calls `/v1`, fails every gateway call as not found. The reverse also holds: a self-hosted gateway older than 0.6.0 serves only `/v1`, so this protocol needs that gateway upgraded first.
- 0.5.0 is the first release to report the roster that answered, and the first to group issues by line span. An earlier release reports only the roster asked, so a report built from it describes agreement between the members that answered as agreement across every member consulted. It also parses a cited line range as a file path of its own, so one defect cited as `file.py:203-207` by one member and `file.py:205` by another is reported as two unrelated findings rather than one the council agreed on. Neither is an error, so the council succeeds and the report is wrong.
- 0.6.0 is the first release whose `summary` separates the issue counts from the prose, and the first whose serialized output carries only the fields the shipped schema declares. An earlier release joins every member's prose into one string, so a report reading `summary.synthesis` finds nothing there and prints an empty line. Earlier output also carries an undeclared `reviews` field and omits a required `files_reviewed`, so its shape and the schema beside it disagree.
- 0.7.0 is the first release to merge design approaches and the first to derive `recommended_by`. An earlier release concatenates each member's own approaches, so one approach that three members named arrives as three entries with its pros and cons split across them, and the per-member reply has no field for the count, so every approach reports a count of zero. `consensus_recommendation` there also requires byte-identical recommendation prose, so it almost never fires. A report built from an earlier release has to merge the approaches itself and cannot report the counts at all.
- 0.8.0 is the first release whose `summary.synthesis` is a synthesis. An earlier release joins each answering member's own summary, so the one field that claims to read across the council carries no reading, and a single-member session hides the defect because one member's summary passes for an assessment. 0.8.0 also names the member asked in `summary.synthesized_by` and records a failed attempt in `summary.synthesis_error`, so a report can say whose assessment it is instead of presenting one member's judgment as the council's.
- 0.10.0 is the first release to refuse a member's value outside a closed set, and the first to require the fields that explain a failure. Five fields name a closed set, and an earlier release copies an unrecognized value straight through, so a member answering in its own vocabulary is reported as a success while the document it produces fails validation against the schema the same package ships. Refusing that member instead costs it its vote, which lowers `providers_responded` and can promote a concern it did not share from a majority one to a consensus one. 0.10.0 also requires `model` and `raw_content` on a failure, so a report can name the model asked where several members share one provider and quote the reply rather than guess at it, and it requires `synthesis_error` and `synthesized_by` on the summary, so an assessment that is absent is told apart from one the output does not record.
- 0.11.0 is the first release to group issues on the place alone and to keep every member's account of a group, and the first whose `consensus_recommendation` reports a majority. An earlier release groups on the category as well as the place, so one defect three members read as `correctness`, `invariants` and `architecture` is reported as three unrelated single-member findings. It also keeps one member's account per group and discards the rest, so two members describing different defects at one place are reported as one agreed finding carrying one description. An earlier `consensus_recommendation` requires every answering member to name exactly one approach and all of them to name the same one, so it is null in nearly every real session while the per-approach counts beside it show clear agreement. A report built from an earlier release understates agreement, overstates it, and reads an empty recommendation as disagreement.

Every command below therefore requests `star-chamber[otari]>=0.11.0` rather than the bare extra. The constraint is what makes the floor binding: an unconstrained request can be served from a cached older environment that lacks the extra or holds an outdated client, and it reports nothing when it is. With the constraint, an environment that cannot satisfy the floor fails as an unsatisfiable-requirements error instead of producing a council that dies at its first provider call, one that reports more agreement than it found, one whose report is missing its summary, or one that passes off a member's unrecognized rating as a success.

**The Otari gateway client is part of the invocation, not an optional addition.** In **Otari** mode every non-local provider is dispatched through the OpenAI-compatible Otari gateway. The gateway client is absent from the base install, so without the `otari` extra the first gateway call fails, reporting that the Otari packages are not installed. The failure lands at call time, not install time, so a command that resolves cleanly can still fail on use.

**Every star-chamber invocation in this protocol already requests the extra. Copy the commands as written and do not strip it.** The extra is harmless outside Otari mode — it installs a gateway client that goes unused — so it is safe to leave in place whatever the configured mode is. Do not retype an invocation from memory: an invocation that drops `--from 'star-chamber[otari]>=0.11.0'` resolves and runs, then fails at the first provider call.

**Provider SDKs are not all included by default.** Only the OpenAI SDK is a base dependency of `any-llm-sdk`. In **direct** mode, each non-OpenAI provider (Anthropic, Gemini, Cohere, etc.) needs its own SDK added as a further `--with` flag:

```bash
uvx --from 'star-chamber[otari]>=0.11.0' --with anthropic --with google-genai star-chamber <command> [options] [arguments]
```

In Otari mode those *per-provider* SDK flags are not needed, because the gateway holds the upstream credentials:

```bash
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber <command> [options] [arguments]
```

## Step 0: Check Prerequisites

Before running, verify uv is available and configuration exists:

```bash
command -v uv >/dev/null 2>&1 && echo "uv:ok" || echo "uv:missing"
CONFIG_PATH="${STAR_CHAMBER_CONFIG:-$HOME/.config/star-chamber/providers.json}"
[[ -f "$CONFIG_PATH" ]] && echo "config:exists:$CONFIG_PATH" || echo "config:missing"
```

**Verify star-chamber is accessible:**
```bash
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber list-providers
```

If this fails with a package resolution error or missing module import, star-chamber may not be published or uv's cache may be stale. Try `uvx --reinstall --from 'star-chamber[otari]>=0.11.0' star-chamber list-providers` to refresh the cached environment.

**If `list-providers` fails because the Otari API base "ends in an API path"**, the base URL still carries an API path such as `/v1` from an older setup. The error names the setting that supplied the base and the corrected value. Show the error to the user and offer to apply the fix. Change nothing until the user agrees.

- **`'otari.api_base' in the config`:** Offer to set `otari.api_base` in `$CONFIG_PATH` to the corrected value.
- **`OTARI_API_BASE` or `GATEWAY_API_BASE`:** Find where the user sets the variable, for example with `grep -n -e OTARI_API_BASE -e GATEWAY_API_BASE ~/.zshrc ~/.zprofile ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null`. Offer to change that line to the corrected value. If the variable is set somewhere you cannot edit, give the user the corrected value to set there. The current shell and agent session keep the old value, so tell the user to restart them before the fix takes effect.

After a fix to the config, run `list-providers` again to confirm it passes.

**If uv is missing**, stop and show:
```
uv is required but not installed.

Install uv:
  curl -LsSf https://astral.sh/uv/install.sh | sh

See: https://docs.astral.sh/uv/getting-started/installation/
```

**STOP if uv is missing. Do not proceed.**

**If config is missing**, ask how to manage API keys:

```text
Star-Chamber requires provider configuration.

How would you like to manage API keys?

[Otari gateway] - Route all providers through an Otari gateway (credentials auto-detected by the SDK)
[Direct provider keys] - Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY individually
[Skip] - I'll set it up manually later
```

**If user chooses "Otari gateway":**

```bash
STAR_CHAMBER_PATH="<set by caller>"
PLUGIN_ROOT="$STAR_CHAMBER_PATH/../.."; uv run --no-project --isolated "$PLUGIN_ROOT/reference/star-chamber/generate_config.py" --otari
```

Then show:
```text
Created ~/.config/star-chamber/providers.json (Otari gateway mode)

Setup (the SDK auto-detects the credential from these env vars):
  # Hosted otari.ai platform:
  export OTARI_API_BASE="https://api.otari.ai"
  export OTARI_API_KEY="..."      # tk_... token, sent as Authorization: Bearer

  # — or — self-hosted gateway:
  export OTARI_API_BASE="https://your-gateway.example"
  export GATEWAY_API_KEY="..."    # sent via the Otari-Key header

OTARI_API_BASE is the gateway origin with no path. The SDK adds the API path.

The generated config prefixes each model as provider:model (Otari's naming
convention). Verify the prefixes against your gateway's docs.
```

**If user chooses "Direct provider keys":**

```bash
STAR_CHAMBER_PATH="<set by caller>"
PLUGIN_ROOT="$STAR_CHAMBER_PATH/../.."; uv run --no-project --isolated "$PLUGIN_ROOT/reference/star-chamber/generate_config.py" --direct
```

Then show:
```text
Created ~/.config/star-chamber/providers.json (direct keys mode)

Set these environment variables:
  export OPENAI_API_KEY="sk-..."
  export ANTHROPIC_API_KEY="sk-ant-..."
  export GEMINI_API_KEY="..."

Edit the config to remove providers you don't have keys for.
```

**If user chooses "Skip":**

```text
To set up manually later, see the Configuration section below or run /star-chamber again.
```

**STOP if config is missing. Do not proceed without configuration.**

## Invocation Modes: Code Review vs Design Question

Star-chamber supports two modes, each with its own CLI command:

**Code review** (default): Invoked with no question, or with `--file` flags pointing to code. Uses the `star-chamber review` command. Follow all steps below.

**Design question**: The user asked a question about architecture, design trade-offs, or approach (e.g., "should we use event sourcing or CRUD?", "what's the best way to structure auth?"). Uses the `star-chamber ask` command. Skip Step 1 (no files to identify). In Step 2, still gather context.

The SDK handles prompt construction, fan-out to providers, response parsing, and consensus classification for both modes. This protocol handles target identification, context gathering, invocation, and result presentation.

## Step 1: Identify Review Targets

*(Code review mode only. Skip for design questions.)*

Every review records two sets. The **changed set** is every file this branch and this working tree touch. The **target set** is the files the council reads. Step 4 reports one against the other, so a review that covered part of a change cannot read like one that covered all of it.

Shell variables do not persist between Bash tool invocations, so each set is written to a temp file that later blocks read back. Use separate blocks to avoid the pipe-breaks-variable-expansion runtime constraint.

Create the temp directory first, whether or not `--file` was given. Step 2 and Step 4 both read artifacts from it.

```bash
SC_TMPDIR="$(mktemp -d)"; echo "$SC_TMPDIR"
```

**Capture the echoed path** and re-set `SC_TMPDIR` in every subsequent block.

### Resolve the base of the committed range

Take the committed range from the branch point rather than from the last commit. A range of `HEAD~1 HEAD` reviews the tip commit and says nothing about the commits before it, which is how a defect in an earlier commit reaches a clean verdict. Try the remote's default branch, then a local `main` or `master`. Do not use `@{upstream}`: a feature branch's upstream is its own remote copy, so the branch point against it is the branch's own tip on an up-to-date branch, not an integration point. A candidate that resolves to `HEAD` is rejected and the next one is tried. This block echoes its result rather than passing it on, for the same reason the temp path is echoed.

```bash
SC_BASE=""; SC_SEEN=""; SC_HEAD="$(git rev-parse HEAD)"; for SC_REF in "$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)" main master; do if [ -z "$SC_REF" ]; then continue; fi; SC_TRY="$(git merge-base HEAD "$SC_REF" 2>/dev/null)"; if [ -z "$SC_TRY" ]; then continue; fi; SC_SEEN="yes"; if [ "$SC_TRY" = "$SC_HEAD" ]; then continue; fi; SC_BASE="$SC_TRY"; break; done; if [ -n "$SC_BASE" ]; then echo "base:$SC_BASE scope:branch"; else if [ -n "$SC_SEEN" ]; then echo "base:HEAD~1 scope:tip-commit-only reason:on-integration-branch"; else echo "base:HEAD~1 scope:tip-commit-only reason:no-integration-ref"; fi; fi
```

**Capture the echoed base and scope word.** Re-set `SC_BASE` literally in the blocks below, and carry the scope word into the Step 4 scope line.

- `scope:branch` means the range covers the branch from its branch point.
- `scope:tip-commit-only` means no usable branch point was found, so the range is the last commit alone and the review does not cover the branch. Report that in Step 4 rather than letting it pass as full coverage. The silence is the original defect, not the narrow range.

The two reasons are not the same problem. `reason:on-integration-branch` means a candidate resolved and its branch point is `HEAD`, which is the expected result of reviewing the default branch itself, where the last commit is the unit of work. `reason:no-integration-ref` means no candidate ref resolved at all, so the integration point is unknown and a feature branch's earlier commits are being left out. Name the reason in the scope line, because the second is a coverage gap and the first is not.

A branch point is unusable when no candidate ref resolves, and when every candidate's branch point is `HEAD` itself, which is what happens on the default branch. Without the second case the committed range is empty there and only the staged, unstaged, and untracked changes reach the council.

### Collect the changed set

This is the reporting universe, so it keeps deletions and untracked files. A file the branch deleted is still a changed file, and an untracked file often holds the newest code.

```bash
SC_TMPDIR="<literal path from mktemp output>"; SC_BASE="<literal base from the echoed line>"; ( git diff "$SC_BASE" HEAD --name-only 2>/dev/null; git diff --cached --name-only 2>/dev/null; git diff --name-only 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null ) > "$SC_TMPDIR/raw-changed.txt"
```

```bash
SC_TMPDIR="<literal path from mktemp output>"; sort -u "$SC_TMPDIR/raw-changed.txt" > "$SC_TMPDIR/changed.txt"
```

### Collect the target set

**If `--file` arguments were provided**, those paths are the targets. Write them straight to `filtered.txt` and skip the filter below, because the caller named them deliberately:

```bash
SC_TMPDIR="<literal path from mktemp output>"; cat > "$SC_TMPDIR/filtered.txt" << 'EOF'
<one --file path per line>
EOF
```

**Otherwise collect the reviewable changed files.** This set filters to `ACMRT`, because a deleted file has no content for the council to read:

```bash
SC_TMPDIR="<literal path from mktemp output>"; SC_BASE="<literal base from the echoed line>"; ( git diff "$SC_BASE" HEAD --name-only --diff-filter=ACMRT 2>/dev/null; git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null; git diff --name-only --diff-filter=ACMRT 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null ) > "$SC_TMPDIR/raw-files.txt"
```

Then filter and deduplicate in separate commands (avoids pipelines — see [Runtime Constraint](#runtime-constraint)):
```bash
SC_TMPDIR="<literal path from mktemp output>"; grep -v -E '(node_modules|vendor|\.min\.|\.generated\.|__pycache__|\.pyc$)' "$SC_TMPDIR/raw-files.txt" > "$SC_TMPDIR/filtered.txt" || true
```

```bash
SC_TMPDIR="<literal path from mktemp output>"; sort -u "$SC_TMPDIR/filtered.txt" > "$SC_TMPDIR/files.txt"
```

### Narrowing the target set

**When the list is narrowed by hand, keep every file that carries new production code**, however few lines changed in it. A small diff in a composition root, in dependency wiring, or in a shared module is where a pattern break hides, because those few lines decide how the new code joins the existing structure. The size of a file's diff is a poor measure of how much of the design it settles. Drop generated, vendored, and lock files. Do not drop a file for being large.

`files.txt` is the authoritative target list, and Step 3 reviews exactly what it holds. Write any narrowing back to it before the counts below are taken:

```bash
SC_TMPDIR="<literal path from mktemp output>"; cat > "$SC_TMPDIR/kept.txt" << 'EOF'
<the kept paths, one per line>
EOF
sort -u "$SC_TMPDIR/kept.txt" > "$SC_TMPDIR/files.txt"
```

Narrowing only the Step 3 argument list leaves `files.txt` overstating what was reviewed, and the scope line then reports coverage the council never had. That is the original defect in a second form.

### Record what was left out

Take these after any narrowing. `comm` needs sorted inputs, which `sort -u` guarantees on both sides.

Label every excluded path with why it went: `deleted` where the changed set holds a path the tree no longer does, `generated` or `vendored` where the filter dropped it, and `narrowed` where it was removed by hand. A bare count tells a reader nothing about whether the omission mattered.

```bash
SC_TMPDIR="<literal path from mktemp output>"; comm -23 "$SC_TMPDIR/changed.txt" "$SC_TMPDIR/files.txt" > "$SC_TMPDIR/excluded.txt"
```

```bash
SC_TMPDIR="<literal path from mktemp output>"; echo "changed:$(wc -l < "$SC_TMPDIR/changed.txt")"; echo "reviewed:$(wc -l < "$SC_TMPDIR/files.txt")"; echo "excluded:$(wc -l < "$SC_TMPDIR/excluded.txt")"
```

**Capture the three counts** for the Step 4 scope line, and read `excluded.txt` with the Read tool for the excluded list. A review that covered part of the change reads exactly like one that covered all of it unless the two sets are reported against each other.

The file list at `$SC_TMPDIR/files.txt` is used by Step 2 for path-scoped rule matching and by Step 3 as review targets.

## Step 2: Gather Context

Gather project context into a temp file that will be passed to `star-chamber` via `--context-file`. The SDK injects this into the `## Project Context` section of its prompt template. Use the `$SC_TMPDIR` created in Step 1.

Create the context file:
```bash
SC_TMPDIR="<literal path from mktemp output>"; CONTEXT_FILE="$SC_TMPDIR/context.txt"; : > "$CONTEXT_FILE"
```

**Project rules (if they exist):**

Load project rules, filtering path-scoped rules to only those relevant to the review target files (from Step 1). Rule file locations vary by agent platform:
- Claude Code: `.claude/rules/*.md`
- OpenCode: `AGENTS.md` (auto-loaded natively)
- Other agents: check agent documentation for project rule conventions

Always include universal and local-supplements rule files. For files with `paths:` frontmatter, include only if at least one declared path pattern matches a file in the review target list. Files without `paths:` frontmatter are treated as global and always included.

If no project rules directory exists, skip rule injection — star-chamber will review without project-specific context.

The following Bash example assumes the Claude Code layout (`.claude/rules/`). OpenCode and other agents auto-load rules from `AGENTS.md` at the platform level.

```bash
SC_TMPDIR="<literal path from mktemp output>"; CONTEXT_FILE="$SC_TMPDIR/context.txt"; FILES_LIST="$SC_TMPDIR/files.txt"

RULE_DIR=".claude/rules"
if [[ -d "$RULE_DIR" ]]; then
  for f in "$RULE_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    basename="$(basename "$f")"

    # Always include universal and local-supplements (not path-scoped).
    if [[ "$basename" == "universal.md" ]] || [[ "$basename" == "local-supplements.md" ]]; then
      cat "$f" >> "$CONTEXT_FILE"
      continue
    fi

    # If no paths: frontmatter, treat as global — always include.
    if ! grep -q '^paths:' "$f"; then
      cat "$f" >> "$CONTEXT_FILE"
      continue
    fi

    # For path-scoped rules, include only if a target file matches a declared pattern.
    matched=false
    while IFS= read -r pattern; do
      [[ -z "$pattern" ]] && continue
      pattern="${pattern#- }"
      pattern="${pattern%\"}"
      pattern="${pattern#\"}"
      # When pattern starts with **/, also try without the prefix.
      # Bash [[ == ]] treats **/ as requiring a path separator,
      # so **/*.py won't match root-level files like main.py.
      alt_pattern=""
      if [[ "$pattern" == \*\*/* ]]; then
        alt_pattern="${pattern#\*\*/}"
      fi
      while IFS= read -r file_path; do
        [[ -z "$file_path" ]] && continue
        # shellcheck disable=SC2254
        if [[ "$file_path" == $pattern ]] || [[ -n "$alt_pattern" && "$file_path" == $alt_pattern ]]; then
          matched=true
          break
        fi
      done < "$FILES_LIST"
      $matched && break
    done < <(awk '/^paths:[[:space:]]*$/{p=1;next} p&&/^[[:space:]]*-[[:space:]]/{gsub(/^[[:space:]]*-[[:space:]]*/,"",$0);print;next} p{exit}' "$f")

    if $matched; then
      cat "$f" >> "$CONTEXT_FILE"
    fi
  done
else
  echo "No project rules directory found — reviewing without project-specific context." >&2
fi
```

**Architecture context (if exists):**
```bash
SC_TMPDIR="<literal path from mktemp output>"; CONTEXT_FILE="$SC_TMPDIR/context.txt"
[[ -f ARCHITECTURE.md ]] && cat ARCHITECTURE.md >> "$CONTEXT_FILE"
```

## Step 3: Invoke Star-Chamber

The SDK handles prompt construction, fan-out to all configured providers, response parsing, and consensus classification. Pass the context file from Step 2 and request JSON output.

**Code review:**
```bash
SC_TMPDIR="<literal path from mktemp output>"; uvx --from 'star-chamber[otari]>=0.11.0' star-chamber review --context-file "$SC_TMPDIR/context.txt" --format json [--provider <name>...] [--timeout <seconds>] file1.py file2.py
```

**Design question:**
```bash
SC_TMPDIR="<literal path from mktemp output>"; uvx --from 'star-chamber[otari]>=0.11.0' star-chamber ask --context-file "$SC_TMPDIR/context.txt" --format json [--provider <name>...] [--timeout <seconds>] "Should we use Redis or Memcached?"
```

The council asks one member to write the session assessment after the rounds finish, so a session makes one provider call more than it has members, and a session where two calls time out is the worst case rather than one. `--no-synthesis` on either command skips it and spends no extra call, leaving `summary.synthesis` empty, and the config key `"synthesis"` sets the default.

**Non-debate mode:** Do NOT redirect stdout to a file — the JSON is consumed directly from the Bash tool response in Step 4.

**Important:** Keep the `uvx` command on a **single line**. Do NOT use `\` line continuations — they break under Claude Code's Bash tool.

**Important:** Do NOT redirect stderr into the output file (no `2>&1`). `uv` prints install messages to stderr which would corrupt the JSON output. Only redirect stdout when saving to a file.

### JSON Output Structure

**Code review** (`mode: "code-review"`) output fields:
- `spec_version` — the protocol version that produced the document, which is not the package version: 0.10.0 reports 0.9.
- `providers_used` — every provider asked, including any that then failed.
- `providers_responded` — the providers that returned a usable answer, and the denominator the groupings below were computed over.
- `consensus_issues` — the places every provider that answered cited (address first).
- `majority_issues` — the places more than one provider that answered cited, but not all of them.
- `individual_issues` — the places one provider cited, keyed by provider name, the keys A-Z.

**All three hold groups, not issues.** A group is one place the council cited, and it carries a `findings` entry for every account a member gave of that place. A `finding` has the `provider` that raised it and that member's own `severity`, `location`, `category`, `description` and `suggestion`. The group's own `location`, `severity`, `categories` and `flagged_by` are derived from its findings and belong to the group, not to any member: `location` is the citation that opened the group and a finding may cite a narrower or wider place, `severity` is the most urgent any finding carries, and `categories` is every category its findings carry, A-Z and without repeats. Read `findings` for what the members said. There is no `description` on a group to read instead.
- `quality_ratings` — per-provider quality assessment (keyed by provider name).
- `reviews` — full individual provider reviews with `raw_content`.
- `failed_providers` — the members that produced nothing usable, each carrying `provider`, `model`, `error` and `raw_content`. `model` names the model that was asked, which the display name does not give where several members share one provider. `raw_content` holds the reply whole, and distinguishes two cases a reader needs apart: it is null where no reply arrived at all, such as a timeout, which points at the network or the gateway, and empty where a reply arrived carrying no content, which points at the model or the prompt.
- `summary` — an object, not prose. `total_issues` counts the groups across the three buckets above, and `consensus_count` and `majority_count` count the first two of them. All three count groups rather than findings, so a group several members described counts once. `synthesis` holds one member's assessment of the session in one or two sentences, written without seeing which member said what, and is empty where no member wrote one. `synthesized_by` names the member asked, whether or not it answered, and is null where none could be asked. `synthesis_error` carries the provider and the error where a member was asked and produced nothing usable. `synthesized_by` and `synthesis_error` are always present, so a null reports an absence and is told apart from a key the output never wrote. Three rules stop a summary contradicting itself. A recorded error requires a named author. An assessment requires a named author and no recorded error. An author named beside an empty assessment requires a recorded error, which is what tells a member that was asked and wrote nothing from one that was never asked. An author is never an empty name.

**Design question** (`mode: "design-question"`) output fields:
- `spec_version` — the protocol version that produced the document, which is not the package version: 0.10.0 reports 0.9.
- `providers_used` — every provider asked, including any that then failed.
- `providers_responded` — the providers that returned a usable answer, and the denominator for `consensus_recommendation`.
- `prompt` — the original question.
- `approaches` — every approach any provider named, merged by name across providers, with `name`, `pros`, `cons`, `risk_level`, `fit_rating` and a `recommended_by` count. One entry is one approach the council weighed: the names are matched ignoring case, punctuation and spacing, the pros and cons are the union of what every provider naming it said, and `risk_level` and `fit_rating` take the value the most providers stated, resolving a tie toward the more cautious one. `recommended_by` counts the providers whose own recommendation names that approach, which counts mentions rather than endorsements, so an approach every member named in order to reject it carries their count. `risk_level` reads `unknown` where no member rated the approach, and `fit_rating` is null where none assessed fit. The council places both and a member may not send either, so read them as the council's own and never attribute them to a member.
- `consensus_recommendation` — the name of the approach a strict majority of the providers that answered named in their own recommendation, or null where no approach held one. The value is always a name that appears in `approaches`, so look it up there rather than reading it as prose. **It tallies names, not endorsements.** The council matches the approach names against the words of a member's recommendation and reads no polarity from them, so a recommendation that names one approach in order to reject it casts a ballot for it: two members that both write "avoid Redis" make Redis the consensus recommendation. A member casts a ballot only where its recommendation names exactly one approach and that member named the approach itself, because a recommendation naming two does not say which it meant. The configured threshold can raise the bar toward unanimity but never lower it below a majority. Absence still does not mean they disagreed: members expressing one direction in different words are tallied separately, so each wording must hold the majority on its own.
- `failed_providers` — the members that produced nothing usable, carrying the same fields, and the same null against empty distinction, as above.
- `summary` — an object, not prose, carrying `synthesis`, `synthesized_by` and `synthesis_error` with the meanings above. The count fields are code-review only and are absent here.

Both modes return the same object, so the schema for the fields above is `council-output`: `uvx --from 'star-chamber[otari]>=0.11.0' star-chamber schema council-output`. The `code-review-result` and `design-advice-result` schemas describe one provider's own reply, which is what each entry of `reviews` holds, not the aggregated output. List all schemas with `uvx --from 'star-chamber[otari]>=0.11.0' star-chamber schema list`.

**Read `spec_version` before reading the fields.** These descriptions were written against spec version 0.11. Where a document reports a higher one, present it and say that this field-level reading of it is unverified, rather than guessing at a field. Do not select behavior per field for a version above 0.11, because only versions up to it are a set this protocol documents. A document reporting 0.9 or lower predates the floor above.

**Five fields carry a value from a fixed set.** A member that answers outside its field's set is failed where its reply is parsed, so the value never reaches the output. That member is reported in `failed_providers`, and its `error` names the field and the values the field permits.

| Field | Where it sits | Values a member may send |
|---|---|---|
| `category` | an issue a member sends, and the finding made from it | `architecture`, `correctness`, `craftsmanship`, `invariants`, `maintainability` |
| `fit_rating` | an approach | `poor`, `fair`, `good`, `excellent` |
| `quality_rating` | a review | `needs-work`, `fair`, `good`, `excellent` |
| `risk_level` | an approach | `high`, `medium`, `low` |
| `severity` | an issue a member sends, and the finding made from it | `high`, `medium`, `low` |

`risk_level` and `severity` are listed most severe first, and `fit_rating` and `quality_rating` worst first, which is the declaration order of each set. Two things follow from that order: groups sort by severity in it, and where members disagree on one approach's risk or fit, a tie resolves toward the first value listed, which is the most cautious one. `category` is unranked and listed A-Z.

### Clean Up

After results are presented, remove the temp directory:
```bash
SC_TMPDIR="<literal path from mktemp output>"; rm -rf "$SC_TMPDIR"
```

## Step 4: Present Results to User

Parse the JSON output from Step 3 and present using the appropriate format below. In **non-debate mode**, the JSON is returned directly by the Bash tool response — parse it in-context. In **debate mode**, use the **Read tool** with the literal temp file path to read the final round's JSON (e.g., reading `/tmp/star-chamber/run-KdkPeA/round-2.json`). Do NOT use `python3 -c`, `cat`, or other shell commands to read result files. Do NOT include raw JSON in the terminal summary — the Markdown formats below are for human consumption.

**A group is one place, not one defect.** The council groups two citations when they name the same file and their line spans overlap or sit within five lines of each other. What a member said takes no part, so two members describing different defects at one place are grouped, and `consensus_count` counts that group once. A count of one can therefore stand for two unrelated defects both members happened to cite at one line.

**Two kinds of citation name a file rather than a place in it.** One that carries no line does, and so does one whose span is wider than fifty lines. Such a citation joins the first group already opened in that file, whatever lines that group holds, so `file.py:1-100` groups with `file.py:500`. It joins that one group and does not reach the others in the file. A group therefore does not say the citations in it are near each other, and the group's `location` can name a line far from a finding beside it.

Nothing is hidden by that. Every account is in the group's `findings`, and more than one entry in `categories` says the members read the place as different kinds of concern. Read the findings before describing a group as one defect the council agreed on, and where they describe different defects, report them separately and say the group was split by hand.

### Code Review Format

```markdown
## Star-Chamber Review

**Files:** {list of files reviewed}
**Scope:** {reviewed} of {changed} changed files reviewed; {excluded} left out. Committed range from {base}, which {covers the branch | is the tip commit only, so the branch is not covered}.
**Excluded:** {path} ({reason}), {path} ({reason}) — or `none`
**Providers asked:** {providers_used from JSON}
**Providers answered:** {providers_responded from JSON}

### Consensus Issues (Every Provider That Answered Cited)

Every council member that answered cited these places. Address these first.

1. `{group.location}` **[{group.severity}]** ({group.categories, comma separated}) — cited by {group.flagged_by}
   - **{finding.provider}** `{finding.location}` **[{finding.severity}]** ({finding.category}): {finding.description}
     - **Suggestion:** {finding.suggestion}
   - one bullet per entry in {group.findings}, in the order they appear

### Majority Issues (More Than One Provider, Not All)

More than one council member that answered cited these places, but not all of them. The bucket takes a group at two members, which is not a majority of a larger roster, so give each group's own count and do not report the bucket as the view of most of the council.

1. `{group.location}` **[{group.severity}]** ({group.categories, comma separated}) — cited by {group.flagged_by}
   - **{finding.provider}** `{finding.location}` **[{finding.severity}]** ({finding.category}): {finding.description}
     - **Suggestion:** {finding.suggestion}
   - one bullet per entry in {group.findings}, in the order they appear

### Individual Observations

Places one provider cited. May be valid specialized insights.

- **{provider}:** `{group.location}` ({group.categories, comma separated})
  - `{finding.location}` **[{finding.severity}]** ({finding.category}): {finding.description}
    - **Suggestion:** {finding.suggestion}
  - one bullet per entry in {group.findings}, in the order they appear

### Summary

**Issues:** {summary.total_issues} distinct — {summary.consensus_count} consensus, {summary.majority_count} majority, the rest individual.

| Provider | Quality Rating | Issues Found |
|----------|---------------|--------------|
| {name}   | {rating}      | {count}      |

**Overall ({summary.synthesized_by}'s assessment):** {summary.synthesis from JSON} — this shape only where both are present, and see the presentation guidelines for the line to write where there is no assessment
```

### Design Question Format

```markdown
## Star-Chamber Advisory

**Question:** {prompt from JSON}
**Providers asked:** {providers_used from JSON}
**Providers answered:** {providers_responded from JSON}

### Consensus Recommendation

{consensus_recommendation from JSON, if present — it is an approach name, so report it as the approach a majority named and not as a direction in prose, and read that approach's `cons` before calling it the council's choice. Where it is absent, state whether the approaches agree on a direction and say that this reading is yours}

### Approaches Considered

**{name}**
- **Recommended by:** {recommended_by} of the providers that answered
- **Pros:** {pros}
- **Cons:** {cons}
- **Risk:** {risk_level — or that no member rated the risk, where this reads `unknown`}
- **Fit:** {fit_rating — or that no member assessed the fit, where this is null}

### Summary

**Overall ({summary.synthesized_by}'s assessment):** {summary.synthesis from JSON} — this shape only where both are present, and see the presentation guidelines for the line to write where there is no assessment
```

**Presentation guidelines:**
- Always lead with consensus issues — these are the most actionable.
- Include the suggestion from providers when available.
- Note which providers flagged majority issues for context.
- Keep the summary concise — users want to know what to fix.
- If `failed_providers` is non-empty, note which providers failed and why.
- Report the answering roster, not only the roster asked. `consensus_issues` and `majority_issues` are computed over `providers_responded`, so agreement across two of three providers asked is consensus among the two that answered, and saying "3 providers" there overstates it.
- Report a failure beside the consensus count, not only at the end. `providers_responded` is the exact complement of `failed_providers` within `providers_used`, and the groupings are computed over it, so a failure does not only shrink the report. It raises the share of the answering members that any one concern represents, and a concern the failed member did not share can land in `consensus_issues` where a full roster would have left it a majority one. Give the reader the answering count next to the agreement, so the agreement can be read against what measured it.
- Do not report disagreement because `consensus_recommendation` is absent. The field names an approach only where a strict majority of the answering members named that one approach in their recommendation, so it stays null where members name one direction in different words, or where a member's recommendation names two approaches and casts no ballot at all. Read the approaches and their `recommended_by` counts, say whether they point the same way, and say that the reading is yours rather than the council's.
- Do not present `consensus_recommendation` or `recommended_by` as the council endorsing an approach. Both count the approach names a member's recommendation mentions, and neither reads whether that member argued for it or against it, so an approach every member named in order to reject it can hold the majority. The document keeps no member's recommendation text, so the reading cannot be settled from it. Report the field as the approach a majority named, weigh it against that approach's `cons`, and where the cons contradict the name say so and leave the field as the council produced it.
- Do not group the approaches again. The council merges them by name, so each entry already carries the pros and cons of every provider that named it, and the number of entries is the number of approaches the council weighed. Two entries can still describe one idea under different names, because the merge matches names rather than meanings. Saying so is worth reporting, but report it as a reading of the entries and leave the entries and the counts as the council produced them.
- Report `recommended_by` as the council derived it, including zero. Zero means the approach was raised and discussed and then recommended by nobody, which is a finding rather than missing data, so report it instead of omitting the line. Where every approach carries zero, no provider's recommendation named an approach the council could match to one it had raised, and saying that is more use to a reader than silence.
- Do not print the council's own placeholder as though a member chose it. `risk_level` reads `unknown`, and `fit_rating` is null, where no member rated or assessed that approach, and a member may send neither value. Write that no member rated it. An `unknown` printed as a risk level reads as a member judging the risk unknowable, which is a different claim from nobody having judged it, and a null printed as a fit reads as a defect in the report.
- Attribute the overall assessment to the member that wrote it, and never build that attribution from a null `summary.synthesized_by`. `summary.synthesis` is one member's view, written blind to which member said what, and not a position the council took, so the member's name belongs in the line that reports it.
- Where there is no assessment, report the reason the output gives and no more. A `summary.synthesized_by` that is set means a member was asked and wrote nothing usable, and `summary.synthesis_error` names that member and says why. A null means no member was asked, and the output does not say why: the caller switched the assessment off, or no member answered, or there was nothing to assess. An empty `providers_responded` settles the second of those. Otherwise report that no assessment was requested, and attribute it to the caller switching it off only where this invocation passed `--no-synthesis` or the config sets `synthesis` to false, which the caller knows and the output does not.
- Report the counts from `summary` as the council computed them. They count the groups the tool produced, before any split done by hand, so a report that splits a group holding different defects shows more issues than `total_issues` counts. Say that the split was done by hand and leave the counts alone, which keeps the two reconcilable. Adjusting them to match presents a hand-split set as the council's own result.
- Do not attribute a group's own fields to a member. `location`, `severity` and `categories` are derived from the findings and belong to the group. The location is the citation that opened it, so a finding beside it may cite a different place; the severity is the most urgent any member gave, so it can exceed what the member shown beside it said; and `categories` may hold several, which is the members disagreeing rather than one member naming several. Report them as the group's, and take a member's own severity, location and category from that member's finding.

## Debate Mode

For deeper deliberation, debate mode runs multiple rounds where providers respond to each other's feedback. The caller orchestrates the debate loop; the SDK handles single-round execution.

**Note:** Debate mode involves multiple rounds of LLM calls, increasing both cost and response time.

### Persisting Round Results

Context compaction can fire between rounds and destroy previous responses. Persist each round's results to a per-run temp directory.

Before the first round, create the fixed parent directory and a unique run subdirectory:
```bash
_tmpbase="${TMPDIR:-/tmp}"; SC_PARENT="${_tmpbase%/}/star-chamber"; mkdir -p "$SC_PARENT"; chmod 700 "$SC_PARENT"; SC_TMPDIR=$(mktemp -d "$SC_PARENT/run-XXXXXX"); echo "$SC_TMPDIR"
```

**Capture the echoed path** (e.g. `/tmp/star-chamber/run-KdkPeA`) and re-set `SC_TMPDIR` to this literal value in every subsequent bash block (see [Runtime Constraint](#runtime-constraint)).

Tell the user: _"Debate mode will read and write round results in `<resolved SC_PARENT path>`. Approve access to this directory to avoid repeated prompts."_ Use the resolved value of `$SC_PARENT` (e.g. `/tmp/star-chamber`) so the path the user sees matches the actual permission prompt.

The fixed parent path lets the user grant blanket Bash permission once, while the unique `run-XXXXXX` subdirectory keeps concurrent star-chamber sessions isolated. The `chmod 700` ensures only the current user can access the directory.

### Gathering Context for Debate

Gather context as in Step 2, but write to the debate temp directory:
```bash
SC_TMPDIR="<literal path from mktemp output>"; CONTEXT_FILE="$SC_TMPDIR/context.txt"; : > "$CONTEXT_FILE"
```

Then run the same rule-loading and architecture-context logic from Step 2, writing to `$CONTEXT_FILE`.

### Debate Flow

```text
Round 1: uvx --from 'star-chamber[otari]>=0.11.0' star-chamber review --context-file $SC_TMPDIR/context.txt --format json <files> > $SC_TMPDIR/round-1.json
         ↓
         Use Read tool on round-1.json, create anonymous synthesis
         ↓
For each subsequent round (2 to N):
         ↓
    Write synthesis to $SC_TMPDIR/council-context.txt via Bash heredoc
         ↓
    uvx --from 'star-chamber[otari]>=0.11.0' star-chamber review --context-file $SC_TMPDIR/context.txt --council-context $SC_TMPDIR/council-context.txt --format json <files> > $SC_TMPDIR/round-N.json
         ↓
Final: Use Read tool on last round's JSON for presentation (Step 4)
```

### Round Execution

For each round, redirect stdout to a round file:
```bash
SC_TMPDIR="<literal path>"; uvx --from 'star-chamber[otari]>=0.11.0' star-chamber review --context-file "$SC_TMPDIR/context.txt" --format json [--provider ...] file1.py > "$SC_TMPDIR/round-1.json"
```

Do NOT redirect stderr into the round file (no `2>&1`) — `uv` prints install messages to stderr which would corrupt the JSON.

Before starting round N+1, use the **Read tool** to read back round N results from the temp file (e.g., reading `/tmp/star-chamber/run-KdkPeA/round-1.json`), rather than relying on conversation context or shell commands.

This ensures the anonymous synthesis step has access to the actual provider responses even if compaction occurred between rounds.

### Anonymous Synthesis

When summarizing for the next round, synthesize feedback by content themes WITHOUT attributing specific points to individual providers. Present the collective feedback anonymously, focusing on consolidating similar concerns and highlighting areas of agreement or disagreement. This encourages providers to engage with ideas rather than sources. Example:

```text
## Other council members' feedback (round 1):

**Issues raised:**
- The config loader silently ignores missing env vars, risking runtime errors
- Linear search in get_resource_definition may be slow for large configs
- Consider adding a strict mode for env var validation

**Points of agreement:**
- Type hints are solid
- Overall code structure is clean

Please provide your perspective on these points. Note where you agree, disagree, or have additional insights.
```

Write the synthesis to `council-context.txt` in the run directory via **Bash** (the user has already approved the temp directory). Do NOT use the Write tool — it triggers a separate file-creation permission prompt for paths outside the project directory.

```bash
SC_TMPDIR="<literal path>"; cat > "$SC_TMPDIR/council-context.txt" << 'SYNTHESIS'
<paste the anonymous synthesis here>
SYNTHESIS
```

### Error Handling and Convergence

**Error handling:** If a provider fails during a round, continue with remaining providers. Note failed providers in the final output but do not block the debate.

**Convergence check:** If responses in round N are substantively the same as round N-1 (providers just agree with no new points), you may stop early. This is optional — completing all requested rounds is also acceptable.

### Clean Up

After presenting final results, clean up the temp directory:
```bash
SC_TMPDIR="<literal path>"; rm -rf "$SC_TMPDIR"
```

## Usage Examples

```bash
# Basic — review recent changes with all configured providers.
/star-chamber

# Specific files and providers.
/star-chamber --file backend/app/auth.py --provider openai --provider anthropic

# Design question.
/star-chamber "Should we use Redis or Memcached for session storage?"

# Debate mode — 2 rounds (default) where each provider sees others' responses.
/star-chamber --debate

# Debate mode — 3 rounds of deliberation.
/star-chamber --debate --rounds 3

# Debate with specific files.
/star-chamber --debate --rounds 2 --file auth.py --provider openai --provider gemini
```

## Configuration

Provider configuration is read from `~/.config/star-chamber/providers.json`. Override with `STAR_CHAMBER_CONFIG` environment variable.

The reference configuration with current models is maintained at `reference/star-chamber/providers.json` in the pragma plugin. Update models there and re-run `generate_config.py` with `--otari` or `--direct` to propagate changes to your local config.

### Schemas

The SDK ships the council protocol schemas as package data:

```bash
# List available schemas.
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber schema list

# Print a specific schema.
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber schema council-config
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber schema code-review-result
```

### Provider fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | Provider name (e.g., `openai`, `anthropic`, `llamafile`, `ollama`). |
| `model` | yes | Model identifier. |
| `api_key` | no | API key or `${ENV_VAR}` reference. Omit for Otari mode or keyless local providers. |
| `max_tokens` | no | Max response tokens (default: 16384). |
| `api_base` | no | Custom base URL for local/self-hosted LLMs. Omit for cloud providers — the SDK uses built-in defaults. |
| `local` | no | Set to `true` for local/self-hosted providers (default: `false`). See [Otari mode and local providers](#otari-mode-and-local-providers). |

### Local/self-hosted LLM examples

```json
{
  "provider": "llamafile",
  "model": "local-model",
  "api_base": "http://gpu-box.local:8080/v1",
  "max_tokens": 4096,
  "local": true
}
```

```json
{
  "provider": "ollama",
  "model": "llama3",
  "api_base": "http://localhost:11434",
  "max_tokens": 4096,
  "local": true
}
```

Cloud-hosted providers do not need `api_base` or `local` — omit both fields.

### Otari mode and local providers

When a top-level `otari` object is configured, every **non-local** provider is dispatched through the Otari gateway: the call uses `provider="otari"` with Otari's shared `api_base`/`api_key`, and the per-provider `provider` field becomes a label. The `model` must use Otari's `provider:model` naming (e.g. `openai:gpt-4o`).

Providers marked `local: true` are treated differently:

- **Always bypass Otari.** Local providers ignore the gateway and call their own `api_base` with their own `provider` and `api_key`, even when `otari` is set.
- **Intended for self-hosted models** (Ollama, llamafile, etc.) that should not be routed through the gateway.

Auth failures are reported per route: gateway calls report that authentication failed at the Otari gateway, while local calls name the provider and point at its key.

## Using an Otari Gateway (Optional)

Instead of setting individual provider API keys, you can route every non-local provider through [Otari](https://github.com/mozilla-ai/otari), Mozilla AI's OpenAI-compatible LLM gateway:
- **Centralized key management** — Provider keys live at the gateway, not on each developer's machine.
- **Single authentication** — One credential (`OTARI_API_KEY` or `GATEWAY_API_KEY`) instead of per-provider keys.
- **Uniform routing** — Otari selects the upstream provider; star-chamber only needs the OpenAI-compatible client.

### Otari Setup

1. Stand up or obtain access to an Otari gateway (see Otari's documentation).
2. Generate an Otari-mode config (`~/.config/star-chamber/providers.json`) via Step 0, or add a top-level `otari` block by hand:
   ```json
   {
     "providers": [
       {"provider": "openai", "model": "openai:gpt-4o"},
       {"provider": "anthropic", "model": "anthropic:claude-sonnet-4-20250514"}
     ],
     "otari": {"api_base": "${OTARI_API_BASE}"}
   }
   ```
3. Point at the gateway and authenticate:
   ```bash
   # Hosted otari.ai platform:
   export OTARI_API_BASE="https://api.otari.ai"
   export OTARI_API_KEY="..."      # tk_... token, sent as Authorization: Bearer

   # — or — self-hosted gateway:
   export OTARI_API_BASE="https://your-gateway.example"
   export GATEWAY_API_KEY="..."    # sent via the Otari-Key header
   ```

`api_base` is the gateway origin with no path. The SDK adds the gateway's `/api/v1` API root itself, so star-chamber rejects a base that ends in an API path such as `/v1` before it calls any provider. A self-hosted gateway must be Otari 0.6.0 or later, because older gateways serve only `/v1`.

`api_base` and `api_key` may be omitted from the config; when omitted, the SDK's `OtariProvider` auto-detects credentials from its own env vars (`OTARI_API_KEY` for platform mode, `GATEWAY_API_KEY` for self-hosted). Both fields also support `${ENV_VAR}` references for explicit values.

Otari expects the `model` field in `provider:model` form; consult Otari's documentation for its exact naming convention. Providers marked `local: true` always bypass the gateway.

## Security Considerations

**API Key Storage:**
- **Prefer environment variables** over hardcoding keys in the config file.
- Use `${ENV_VAR}` syntax in config to reference environment variables.
- Never commit `providers.json` with actual API keys to version control.
- Otari gateway mode is recommended for team environments — provider keys stay at the gateway rather than on developer machines.

**Key Handling:**
- **Never echo, log, or print API key values** in shell commands or debug output.
- Only check key *presence* (e.g., `[ -n "$VAR" ]`), never key *contents*.
- Avoid shell expansions (`${VAR:-...}`, `${VAR:+...}`) on key variables in echo/print statements — these can leak values.

**Error Output:**
- API keys are automatically redacted from error messages (patterns: `Bearer ...`, `sk-*`, `key-*`, `api_key=...`, etc.).

## Troubleshooting

### Common Errors

**Authentication failed for {provider}:**
```json
{"provider": "openai", "error": "Authentication failed for openai. Check OPENAI_API_KEY is set and valid."}
```
- Verify the environment variable is set: `[ -n "$OPENAI_API_KEY" ] && echo "set" || echo "not set"`
- Check if the key is valid (not expired or revoked).
- For Otari mode, verify credentials are set: `{ [ -n "$OTARI_API_KEY" ] || [ -n "$GATEWAY_API_KEY" ]; } && echo "set" || echo "not set"`

**Otari API base ends in an API path:**
```
Error: Otari API base 'https://api.otari.ai/v1' from OTARI_API_BASE ends in an API path. The gateway client adds the API path itself, so the base must be the gateway origin. Set OTARI_API_BASE to 'https://api.otari.ai'.
```
- star-chamber exits with status 2 before it calls any provider.
- Offer the fix described in [Step 0](#step-0-check-prerequisites).

**Not Found from the Otari gateway for every provider:**
```json
{"provider": "openai", "error": "[gateway] Not Found"}
```
- A self-hosted gateway must be Otari 0.6.0 or later, because older gateways serve only `/v1`.
- Check that `OTARI_API_BASE` (or `otari.api_base` in the config) points at the gateway origin.

**Request timed out:**
```json
{"provider": "gemini", "error": "Request timed out after 60s"}
```
- Increase timeout via `--timeout 120` or in config `timeout_seconds`.
- Check network connectivity to the provider.

**A member answered outside a closed set:**
```json
{"provider": "openai", "model": "openai:gpt-5.2", "error": "Field severity in an issue in openai response must be one of high, medium, low, got 'showstopper'", "raw_content": "..."}
```
- Nothing in the setup is wrong, so there is no configuration fix. The member answered and the reply was rejected where it was parsed, which puts the member in `failed_providers` rather than `providers_responded`.
- Re-running can succeed, because the member may answer inside the set next time.
- Read `raw_content` to see what it sent. Where one member fails this way on every run, drop it from the roster with `--provider` rather than paying for a call whose vote is discarded each time.
- Check the consensus counts before reporting them. The failed member's absence can promote a majority concern to a consensus one.

**Star-chamber not found:**
```
error: No executables are provided by package `star-chamber`
```
- Verify the package exists on PyPI: `pip index versions star-chamber`
- Try `uvx --reinstall --from 'star-chamber[otari]>=0.11.0' star-chamber list-providers` to clear the cache.

**Requirements are unsatisfiable:**
```
  × No solution found when resolving tool dependencies:
  ╰─▶ Because only star-chamber[otari]<=0.9.0 is available and you require
      star-chamber[otari]>=0.11.0, we can conclude that your requirements
      are unsatisfiable.
```
- Retry with a refreshed index before treating this as a real floor failure: `uvx --refresh --from 'star-chamber[otari]>=0.11.0' star-chamber list-providers`.
- A floor raised soon after the release it names can fail against a stale index. PyPI's JSON API and its `/simple/` index can report different newest versions for some minutes, in either direction, and `uv` caches its own index read until asked to refresh. The message names a newest version lower than the floor either way, so it reads like a typo in the constraint.
- Where a refreshed read still cannot resolve it, the floor is genuinely unavailable. Check what the index offers: `uvx --refresh --from 'star-chamber[otari]' star-chamber list-providers`.

### Partial Failures

When some providers succeed and others fail, the JSON output includes `failed_providers` alongside successful results. The review continues with available providers. Check `failed_providers` for details.

`providers_responded` is the exact complement of `failed_providers` within `providers_used`, and the groupings are computed over the members that answered. A failure therefore does not only shrink the report. It raises the share of the answering members that any one concern represents, which can turn a majority concern into a consensus one.

A member can also fail for answering outside a closed set. That is a reply that arrived and was rejected where it was parsed, not a call that never completed, so a member is reported as failed although it answered. Its `error` names the field and the values the field permits, and its `raw_content` holds what it sent.

### Checking Provider Status

```bash
uvx --from 'star-chamber[otari]>=0.11.0' star-chamber list-providers
```

This shows all configured providers, their models, and connection status (direct, otari, or local).

## Cost Warning

Each invocation calls all configured providers. With 3 providers reviewing ~2000 tokens:
- ~$0.02-0.10 per invocation depending on models.
- The closing assessment calls one provider again after the rounds, so an invocation makes one call more than it has providers. `--no-synthesis` removes it.
- Basic mode (no debate) is used when auto-invoked to keep costs predictable.
- Debate mode multiplies cost by the number of rounds.
