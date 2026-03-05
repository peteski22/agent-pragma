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

**Each Bash tool invocation in Claude Code runs in a separate subprocess.** Shell variables do not persist between invocations. **Use `;` (not `&&`) to chain variable assignments with subsequent commands** — `&&` breaks variable propagation in `bash -c` contexts.

**Avoid pipelines (`|`) when shell variables are involved.** Some AI coding tool runtimes (including Claude Code as of March 2026) silently empty all `$VAR` expansions when a `|` appears in the command. Use temp files instead of pipes.

`$STAR_CHAMBER_PATH` is set by the caller:
- **Skill invocation:** The skill loader provides the base directory in the header. The skill sets `STAR_CHAMBER_PATH` to that directory.
- **Agent invocation:** The agent discovers the path via Glob and sets `STAR_CHAMBER_PATH` to the directory containing PROTOCOL.md.

`$PLUGIN_ROOT` can be derived from `$STAR_CHAMBER_PATH` as `$STAR_CHAMBER_PATH/../..` when needed (e.g., to access reference configs). Validate the derivation by checking that `$PLUGIN_ROOT/.claude-plugin/plugin.json` exists before using it.

**CLI invocation:** Star-chamber is a PyPI package with a CLI entry point. Use `uvx` to run it in an isolated environment:

```bash
uvx star-chamber <command> [options] [arguments]
```

`uvx` installs `star-chamber` from PyPI (cached after first run) and executes in isolation — no interference with the host project's environment.

**Platform mode requires extra packages.** The any-llm routing layer needs each provider's SDK installed in the same environment. When using platform mode (`"platform": "any-llm"` in config), add `--with` flags for the platform client and each provider SDK:

```bash
uvx --with any-llm-platform-client --with anthropic --with google-genai star-chamber <command> [options] [arguments]
```

Direct key mode (no platform) still requires provider SDKs but they are pulled in transitively by `any-llm`. Only platform mode needs the explicit `--with` flags.

## Step 0: Check Prerequisites

Before running, verify uv is available and configuration exists:

```bash
command -v uv >/dev/null 2>&1 && echo "uv:ok" || echo "uv:missing"
CONFIG_PATH="${STAR_CHAMBER_CONFIG:-$HOME/.config/star-chamber/providers.json}"
[[ -f "$CONFIG_PATH" ]] && echo "config:exists:$CONFIG_PATH" || echo "config:missing"
```

**Verify star-chamber is accessible:**
```bash
uvx star-chamber list-providers
```

If this fails with a package resolution error, star-chamber may not be published or uv's cache may be stale. Try `uvx --reinstall star-chamber list-providers`.

**If uv is missing**, stop and show:
```
uv is required but not installed.

Install uv:
  curl -LsSf https://astral.sh/uv/install.sh | sh

See: https://docs.astral.sh/uv/getting-started/installation/
```

**STOP if uv is missing. Do not proceed.**

**If config is missing**, ask how to manage API keys:

```
Star-Chamber requires provider configuration.

How would you like to manage API keys?

[any-llm.ai platform] - Single ANY_LLM_KEY, centralized key vault, usage tracking
[Direct provider keys] - Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY individually
[Skip] - I'll set it up manually later
```

**If user chooses "any-llm.ai platform":**

```bash
STAR_CHAMBER_PATH="<set by caller>"
PLUGIN_ROOT="$STAR_CHAMBER_PATH/../.."; uv run --no-project --isolated "$PLUGIN_ROOT/reference/star-chamber/generate_config.py" --platform
```

Then show:
```
Created ~/.config/star-chamber/providers.json (platform mode)

Setup:
  1. Create account at https://any-llm.ai
  2. Create a project and add your provider API keys
  3. Copy your project key and set:
     export ANY_LLM_KEY="ANY.v1...."
```

**If user chooses "Direct provider keys":**

```bash
STAR_CHAMBER_PATH="<set by caller>"
PLUGIN_ROOT="$STAR_CHAMBER_PATH/../.."; uv run --no-project --isolated "$PLUGIN_ROOT/reference/star-chamber/generate_config.py" --direct
```

Then show:
```
Created ~/.config/star-chamber/providers.json (direct keys mode)

Set these environment variables:
  export OPENAI_API_KEY="sk-..."
  export ANTHROPIC_API_KEY="sk-ant-..."
  export GEMINI_API_KEY="..."

Edit the config to remove providers you don't have keys for.
```

**If user chooses "Skip":**

```
To set up manually later, see the Configuration section below or run /star-chamber again.
```

**STOP if config is missing. Do not proceed without configuration.**

## Invocation Modes: Code Review vs Design Question

Star-chamber supports two modes, each with its own CLI command:

**Code review** (default): Invoked with no question, or with `--file` flags pointing to code. Uses `uvx star-chamber review`. Follow all steps below.

**Design question**: The user asked a question about architecture, design trade-offs, or approach (e.g., "should we use event sourcing or CRUD?", "what's the best way to structure auth?"). Uses `uvx star-chamber ask`. Skip Step 1 (no files to identify). In Step 2, still gather context.

The SDK handles prompt construction, fan-out to providers, response parsing, and consensus classification for both modes. This protocol handles target identification, context gathering, invocation, and result presentation.

## Step 1: Identify Review Targets

*(Code review mode only. Skip for design questions.)*

Determine what code to review:

**If `--file` arguments provided**, use those files as the review targets.

**Otherwise, use recent changes:**
```bash
# Get recently changed files (committed, then staged, then unstaged).
# Filter out generated/vendor files.
( git diff HEAD~1 --name-only --diff-filter=ACMRT 2>/dev/null || git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || git diff --name-only --diff-filter=ACMRT ) | grep -v -E '(node_modules|vendor|\.min\.|\.generated\.|__pycache__|\.pyc$)'
```

Save the output as the file list for subsequent steps. Since each Bash tool invocation is isolated, you must re-derive or re-read file lists in each block that needs them (e.g., write to a temp file and read it back, or re-run the discovery command).

## Step 2: Gather Context

Gather project context into a temp file that will be passed to `star-chamber` via `--context-file`. The SDK injects this into the `## Project Context` section of its prompt template.

Create a temp directory and context file:
```bash
SC_TMPDIR="$(mktemp -d)"; CONTEXT_FILE="$SC_TMPDIR/context.txt"; : > "$CONTEXT_FILE"; echo "$SC_TMPDIR"
```

**Capture the echoed path** — you must re-set `SC_TMPDIR` to this literal value in every subsequent bash block.

**Project rules (if they exist):**

Load project rules, filtering path-scoped rules to only those relevant to the review target files (from Step 1). Rule file locations vary by agent platform:
- Claude Code: `.claude/rules/*.md`
- OpenCode: files listed in `opencode.json` `instructions` array
- Other agents: check agent documentation for project rule conventions

Always include universal and local-supplements rule files. For files with `paths:` frontmatter, include only if at least one declared path pattern matches a file in the review target list. Files without `paths:` frontmatter are treated as global and always included.

If no project rules directory exists, skip rule injection — star-chamber will review without project-specific context.

The following Bash example assumes the Claude Code layout (`.claude/rules/`). OpenCode and other agents auto-load rules at the platform level — the skill does not need to parse `opencode.json` directly.

```bash
SC_TMPDIR="<literal path from mktemp output>"; CONTEXT_FILE="$SC_TMPDIR/context.txt"

FILES="$(
  ( git diff HEAD~1 --name-only --diff-filter=ACMRT 2>/dev/null \
    || git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null \
    || git diff --name-only --diff-filter=ACMRT ) \
  | grep -v -E '(node_modules|vendor|\.min\.|\.generated\.|__pycache__|\.pyc$)'
)"

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
      done <<< "$FILES"
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
SC_TMPDIR="<literal path from mktemp output>"; uvx star-chamber review --context-file "$SC_TMPDIR/context.txt" --format json [--provider <name>...] [--timeout <seconds>] file1.py file2.py
```

**Design question:**
```bash
SC_TMPDIR="<literal path from mktemp output>"; uvx star-chamber ask --context-file "$SC_TMPDIR/context.txt" --format json [--provider <name>...] [--timeout <seconds>] "Should we use Redis or Memcached?"
```

**Important:** Keep the `uvx` command on a **single line**. Do NOT use `\` line continuations — they break under Claude Code's Bash tool.

**Important:** Do NOT redirect stderr into the output file (no `2>&1`). `uv` prints install messages to stderr which would corrupt the JSON output. Only redirect stdout when saving to a file.

### JSON Output Structure

**Code review** (`mode: "code-review"`) output fields:
- `consensus_issues` — issues all providers agree on (address first).
- `majority_issues` — issues flagged by 2+ providers (includes `flagged_by` list).
- `individual_issues` — issues from single providers, keyed by provider name.
- `quality_ratings` — per-provider quality assessment (keyed by provider name).
- `reviews` — full individual provider reviews with `raw_content`.
- `failed_providers` — providers that errored (with error messages).
- `summary` — aggregated summary.

**Design question** (`mode: "design-question"`) output fields:
- `prompt` — the original question.
- `approaches` — aggregated approaches with `name`, `pros`, `cons`, `risk_level`, `fit_rating`, `recommended_by` count.
- `consensus_recommendation` — recommendation all providers agreed on (if any).
- `failed_providers` — providers that errored.
- `summary` — aggregated summary.

For full schema details: `uvx star-chamber schema code-review-result` or `uvx star-chamber schema design-advice-result`. List all schemas with `uvx star-chamber schema list`.

### Clean Up

After results are presented, remove the temp directory:
```bash
SC_TMPDIR="<literal path from mktemp output>"; rm -rf "$SC_TMPDIR"
```

## Step 4: Present Results to User

Parse the JSON output from Step 3 and present using the appropriate format below. Do NOT include raw JSON in the terminal summary — the markdown formats below are for human consumption.

### Code Review Format

```markdown
## Star-Chamber Review

**Files:** {list of files reviewed}
**Providers:** {providers_used from JSON}

### Consensus Issues (All Providers Agree)

These issues were flagged by every council member. Address these first.

1. `{location}` **[{severity}]** ({category}) - {description}
   - **Suggestion:** {suggestion}

### Majority Issues ({N}/{M} Providers)

These issues were flagged by most council members.

1. `{location}` **[{severity}]** ({category}) — flagged by {flagged_by} - {description}
   - **Suggestion:** {suggestion}

### Individual Observations

Issues raised by a single provider. May be valid specialized insights.

- **{Provider}:** `{location}` - {description}

### Summary

| Provider | Quality Rating | Issues Found |
|----------|---------------|--------------|
| {name}   | {rating}      | {count}      |

**Overall:** {summary from JSON}
```

### Design Question Format

```markdown
## Star-Chamber Advisory

**Question:** {prompt from JSON}
**Providers:** {providers_used from JSON}

### Consensus Recommendation

{consensus_recommendation from JSON, if present}

### Approaches Considered

**{name}** — Recommended by {recommended_by} provider(s)
- **Pros:** {pros}
- **Cons:** {cons}
- **Risk:** {risk_level}
- **Fit:** {fit_rating}

### Summary

**Overall:** {summary from JSON}
```

**Presentation guidelines:**
- Always lead with consensus issues — these are the most actionable.
- Include the suggestion from providers when available.
- Note which providers flagged majority issues for context.
- Keep the summary concise — users want to know what to fix.
- If `failed_providers` is non-empty, note which providers failed and why.

## Debate Mode

For deeper deliberation, debate mode runs multiple rounds where providers respond to each other's feedback. The caller orchestrates the debate loop; the SDK handles single-round execution.

**Note:** Debate mode involves multiple rounds of LLM calls, increasing both cost and response time.

### Persisting Round Results

Context compaction can fire between rounds and destroy previous responses. Persist each round's results to a per-run temp directory.

Before the first round, create the fixed parent directory and a unique run subdirectory:
```bash
SC_PARENT="${TMPDIR:-/tmp}/star-chamber"; mkdir -p "$SC_PARENT"; chmod 700 "$SC_PARENT"; SC_TMPDIR=$(mktemp -d "$SC_PARENT/run-XXXXXX"); echo "$SC_TMPDIR"
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
Round 1: uvx star-chamber review --context-file $SC_TMPDIR/context.txt --format json <files> > $SC_TMPDIR/round-1.json
         ↓
         Read round-1.json, create anonymous synthesis
         ↓
For each subsequent round (2 to N):
         ↓
    Write synthesis to $SC_TMPDIR/council-context.txt
         ↓
    uvx star-chamber review --context-file $SC_TMPDIR/context.txt --council-context $SC_TMPDIR/council-context.txt --format json <files> > $SC_TMPDIR/round-N.json
         ↓
Final: Use last round's JSON for presentation (Step 4)
```

### Round Execution

For each round, redirect stdout to a round file:
```bash
SC_TMPDIR="<literal path>"; uvx star-chamber review --context-file "$SC_TMPDIR/context.txt" --format json [--provider ...] file1.py > "$SC_TMPDIR/round-1.json"
```

Do NOT redirect stderr into the round file (no `2>&1`) — `uv` prints install messages to stderr which would corrupt the JSON.

Before starting round N+1, read back round N results from the temp file rather than relying on conversation context:
```bash
SC_TMPDIR="<literal path>"; cat "$SC_TMPDIR/round-1.json"
```

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

Write the synthesis to `$SC_TMPDIR/council-context.txt` for the next round.

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

The reference configuration with current models is maintained at `reference/star-chamber/providers.json` in the pragma plugin. Update models there and re-run `generate_config.py` with `--platform` or `--direct` to propagate changes to your local config.

### Schemas

The SDK ships the council protocol schemas as package data:

```bash
# List available schemas.
uvx star-chamber schema list

# Print a specific schema.
uvx star-chamber schema council-config
uvx star-chamber schema code-review-result
```

### Provider fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | Provider name (e.g., `openai`, `anthropic`, `llamafile`, `ollama`). |
| `model` | yes | Model identifier. |
| `api_key` | no | API key or `${ENV_VAR}` reference. Omit for platform mode or keyless local providers. |
| `max_tokens` | no | Max response tokens (default: 16384). |
| `api_base` | no | Custom base URL for local/self-hosted LLMs. Omit for cloud providers — the SDK uses built-in defaults. |
| `local` | no | Set to `true` for local/self-hosted providers (default: `false`). See [Platform mode and local providers](#platform-mode-and-local-providers). |

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

### Platform mode and local providers

When `platform: "any-llm"` is configured, the council fetches API keys from the any-llm platform for each provider. Providers marked `local: true` get special treatment:

- **Key fetch tolerant:** If the platform has no key for a local provider, the council proceeds with an empty key instead of failing.
- **Network fault tolerant:** If the platform is unreachable, local providers still proceed. Non-local providers fail fast.
- **Auth error guidance:** If a local provider returns an auth error, the error message suggests adding the key to the any-llm platform or setting `api_key` directly in `providers.json`.

Local providers can still use keys: if the platform has a key stored for a local provider, it will be fetched and used normally. The `local` flag only affects the *failure* path.

## Using any-llm.ai Managed Platform (Optional)

Instead of setting individual API keys, you can use the [any-llm.ai](https://any-llm.ai) managed platform for:
- **Centralized key management** — Store provider keys securely (encrypted client-side).
- **Usage tracking** — Automatic cost and token tracking across all providers.
- **Single authentication** — One `ANY_LLM_KEY` instead of multiple provider keys.

### Platform Setup

1. Create account at https://any-llm.ai
2. Create a project and add your provider API keys (OpenAI, Anthropic, Gemini, etc.)
3. Copy your project key
4. Set environment variable:
   ```bash
   export ANY_LLM_KEY="ANY.v1.abc123..."
   ```
5. Enable platform mode in your config (`~/.config/star-chamber/providers.json`):
   ```json
   {
     "platform": "any-llm",
     ...
   }
   ```

### What Gets Tracked

The platform tracks **metadata only** (never prompts/responses):
- Provider and model used.
- Token counts (input/output).
- Request timestamps.
- Cost estimates.

## Security Considerations

**API Key Storage:**
- **Prefer environment variables** over hardcoding keys in the config file.
- Use `${ENV_VAR}` syntax in config to reference environment variables.
- Never commit `providers.json` with actual API keys to version control.
- The any-llm.ai platform mode is recommended for team environments.

**Key Handling:**
- **Never echo, log, or print API key values** in shell commands or debug output.
- Only check key *presence* (e.g., `[ -n "$VAR" ]`), never key *contents*.
- Avoid shell expansions (`${VAR:-...}`, `${VAR:+...}`) on key variables in echo/print statements — these can leak values.

**Error Output:**
- API keys are automatically redacted from error messages (patterns: `sk-*`, `ANY.v1.*`, etc.).

## Troubleshooting

### Common Errors

**Authentication failed for {provider}:**
```json
{"provider": "openai", "error": "Authentication failed for openai. Check OPENAI_API_KEY is set and valid."}
```
- Verify the environment variable is set: `[ -n "$OPENAI_API_KEY" ] && echo "set" || echo "not set"`
- Check if the key is valid (not expired or revoked).
- For platform mode, verify `ANY_LLM_KEY` is set: `[ -n "$ANY_LLM_KEY" ] && echo "set" || echo "not set"`

**Request timed out:**
```json
{"provider": "gemini", "error": "Request timed out after 60s"}
```
- Increase timeout via `--timeout 120` or in config `timeout_seconds`.
- Check network connectivity to the provider.

**Star-chamber not found:**
```
error: No executables are provided by package `star-chamber`
```
- Verify the package exists on PyPI: `pip index versions star-chamber`
- Try `uvx --reinstall star-chamber list-providers` to clear the cache.

### Partial Failures

When some providers succeed and others fail, the JSON output includes `failed_providers` alongside successful results. The review continues with available providers. Check `failed_providers` for details.

### Checking Provider Status

```bash
uvx star-chamber list-providers
```

This shows all configured providers, their models, and connection status (direct, platform, or local).

## Cost Warning

Each invocation calls all configured providers. With 3 providers reviewing ~2000 tokens:
- ~$0.02-0.10 per invocation depending on models.
- Basic mode (no debate) is used when auto-invoked to keep costs predictable.
- Debate mode multiplies cost by the number of rounds.
