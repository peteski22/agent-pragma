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
- [Step 2: Inject Context](#step-2-inject-context)
- [Step 3: Construct Review Prompt](#step-3-construct-review-prompt)
- [Step 4: Fan Out to Star-Chamber](#step-4-fan-out-to-star-chamber)
- [Step 5: Parse and Aggregate Results](#step-5-parse-and-aggregate-results)
- [Step 6: Present Results to User](#step-6-present-results-to-user)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Cost Warning](#cost-warning)
- [Specification](#specification)

## Runtime Constraint

**Each Bash tool invocation in Claude Code runs in a separate subprocess.** Shell variables do not persist between invocations. `$STAR_CHAMBER_PATH` must be set at the top of every bash block that references it. **Use `;` (not `&&`) to chain the assignment with subsequent commands** — `&&` breaks variable propagation in `bash -c` contexts.

`$STAR_CHAMBER_PATH` is set by the caller:
- **Skill invocation:** The skill loader provides the base directory in the header. The skill sets `STAR_CHAMBER_PATH` to that directory.
- **Agent invocation:** The agent discovers the path via Glob and sets `STAR_CHAMBER_PATH` to the directory containing PROTOCOL.md.

**Avoid pipelines (`|`) when shell variables are involved.** Some AI coding tool runtimes (including Claude Code as of March 2026) silently empty all `$VAR` expansions when a `|` appears in the command. The `--input-file` flag on `llm_council.py` exists specifically to avoid `cat "$FILE" | uv run ...` patterns. Use `--input-file` instead of piping.

`$PLUGIN_ROOT` can be derived from `$STAR_CHAMBER_PATH` as `$STAR_CHAMBER_PATH/../..` when needed (e.g., to access reference configs). Validate the derivation by checking that `$PLUGIN_ROOT/.claude-plugin/plugin.json` exists before using it.

## Step 0: Check Prerequisites

Before running, verify uv is available and configuration exists:

```bash
command -v uv >/dev/null 2>&1 && echo "uv:ok" || echo "uv:missing"
CONFIG_PATH="${STAR_CHAMBER_CONFIG:-$HOME/.config/star-chamber/providers.json}"
[[ -f "$CONFIG_PATH" ]] && echo "config:exists:$CONFIG_PATH" || echo "config:missing"
```

**NEVER echo, log, or print API key values.** Only check presence:
```bash
[ -n "$ANY_LLM_KEY" ] && echo "key:set" || echo "key:unset"
```
Do not use shell expansions like `${VAR:-default}` on key variables — these can leak the value when the variable is set.

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

Star-chamber supports two invocation modes. Determine which applies based on how it was invoked:

**Code review** (default): Invoked with no question, or with `--file` flags pointing to code. Follow Steps 1-6 as written below.

**Design question**: The user asked a question about architecture, design trade-offs, or approach (e.g., "should we use event sourcing or CRUD?", "what's the best way to structure auth?"). Skip Step 1 (no files to identify). In Step 2, still inject context. In Step 3, construct a design question prompt instead:

```
You are a senior software architect advising on design decisions.

## Project Context
{Injected project rules}
{Architecture context if available}

## Design Question
{The user's question}

## Advisory Focus
1. Trade-offs: What are the pros and cons of each approach?
2. Fit: Which approach best fits this project's existing patterns and constraints?
3. Risk: What are the risks of each option? What could go wrong?
4. Recommendation: What would you recommend and why?

## Output Format
Provide your advice as structured JSON:
{
  "provider": "your-name",
  "recommendation": "Your recommended approach",
  "approaches": [
    {
      "name": "Approach name",
      "pros": ["..."],
      "cons": ["..."],
      "risk_level": "low|medium|high",
      "fit_rating": "excellent|good|fair|poor"
    }
  ],
  "summary": "One paragraph overall recommendation with reasoning"
}
```

For design questions, Step 5 aggregation groups by approach recommendation rather than by file location. Step 6 output uses this format:

```markdown
## Star-Chamber Advisory

**Question:** {the design question}
**Providers:** {list of providers consulted}

### Consensus Recommendation

{If all providers agree on an approach, state it here}

### Approaches Considered

**{Approach name}** - Recommended by {N}/{M} providers
- **Pros:** {merged pros}
- **Cons:** {merged cons}
- **Risk:** {risk level}

### Dissenting Views

{Any provider that recommended a different approach, with their reasoning}

### Summary

| Provider | Recommendation | Fit Rating |
|----------|---------------|------------|
| {name}   | {approach}    | {rating}   |

**Overall:** {1-2 sentence synthesis}
```

## Step 1: Identify Review Targets

Determine what code to review:

**If `--file` arguments provided**, use those files as the review targets.

**Otherwise, use recent changes:**
```bash
# Get recently changed files (committed, then staged, then unstaged).
# Filter out generated/vendor files.
( git diff HEAD~1 --name-only --diff-filter=ACMRT 2>/dev/null || git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || git diff --name-only --diff-filter=ACMRT ) | grep -v -E '(node_modules|vendor|\.min\.|\.generated\.|__pycache__|\.pyc$)'
```

Save the output as the file list for subsequent steps. Since each Bash tool invocation is isolated, you must re-derive or re-read file lists in each block that needs them (e.g., write to a temp file and read it back, or re-run the discovery command).

## Step 2: Inject Context

Gather context to include with the review prompt:

**Project rules (if they exist):**

Load project rules, filtering path-scoped rules to only those relevant to the review target files (from Step 1). Rule file locations vary by agent platform:
- Claude Code: `.claude/rules/*.md`
- OpenCode: files listed in `opencode.json` `instructions` array
- Other agents: check agent documentation for project rule conventions

Always include universal and local-supplements rule files. For files with `paths:` frontmatter, include only if at least one declared path pattern matches a file in the review target list. Files without `paths:` frontmatter are treated as global and always included.

If no project rules directory exists, skip rule injection — star-chamber will review without project-specific context.

The following Bash example assumes the Claude Code layout (`.claude/rules/`). OpenCode and other agents auto-load rules at the platform level — the skill does not need to parse `opencode.json` directly.

For parallel (non-debate) mode, create `SC_TMPDIR` here so rules can be persisted for Step 3: `SC_TMPDIR="$(mktemp -d)"`. In debate mode, `SC_TMPDIR` is created in Step 4 — set it there instead.

```bash
# Re-derive the review target file list (each Bash invocation is isolated).
STAR_CHAMBER_PATH="<set by caller>"; SC_TMPDIR="$(mktemp -d)"
RULES_FILE="$SC_TMPDIR/rules.txt"
: > "$RULES_FILE"

FILES="$(
  ( git diff HEAD~1 --name-only --diff-filter=ACMRT 2>/dev/null \
    || git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null \
    || git diff --name-only --diff-filter=ACMRT ) \
  | grep -v -E '(node_modules|vendor|\.min\.|\.generated\.|__pycache__|\.pyc$)'
)"

# Load project rules, filtering by path scope, and persist for Step 3.
RULE_DIR=".claude/rules"
if [[ -d "$RULE_DIR" ]]; then
  for f in "$RULE_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    basename="$(basename "$f")"

    # Always include universal and local-supplements (not path-scoped).
    if [[ "$basename" == "universal.md" ]] || [[ "$basename" == "local-supplements.md" ]]; then
      cat "$f" >> "$RULES_FILE"
      continue
    fi

    # If no paths: frontmatter, treat as global — always include.
    if ! grep -q '^paths:' "$f"; then
      cat "$f" >> "$RULES_FILE"
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
      cat "$f" >> "$RULES_FILE"
    fi
  done
else
  echo "No project rules directory found — reviewing without project-specific context." >&2
fi
```

**Architecture context (if exists):**
```bash
[[ -f ARCHITECTURE.md ]] && cat ARCHITECTURE.md
```

## Step 3: Construct Review Prompt

Build a structured prompt for Star-Chamber. Use the example template pattern below and adapt or extend its sections as needed when constructing the prompt.

The JSON output formats expected from providers are defined in `spec/council-protocol/SPEC.md`. Relevant schemas:
- `spec/council-protocol/schemas/code-review-result.schema.json`
- `spec/council-protocol/schemas/design-advice-result.schema.json`

**Prompt construction:** Write the prompt to a temp file using `cat >` with a single-quoted heredoc for the static template, then append dynamic content (file contents, rules) with `cat >>`. Single-quoted heredocs (`<< 'EOF'`) prevent shell expansion, which is what you want for the template — but it also means `$VARIABLE` references inside the heredoc are passed as literal text, not expanded. Append dynamic content separately.

`SC_TMPDIR` was created in Step 2 (parallel mode) or Step 4 (debate mode). Re-set it at the top of each bash block since variables do not persist between invocations.

Example:
```bash
STAR_CHAMBER_PATH="<set by caller>"; SC_TMPDIR="<set by caller>"; PROMPT_FILE="$SC_TMPDIR/prompt.txt"; cat > "$PROMPT_FILE" << 'EOF'
You are a senior software craftsman reviewing code for quality, idioms, and architectural soundness.

## Project Context
EOF
# Append project rules collected in Step 2 (if any).
cat "$SC_TMPDIR/rules.txt" >> "$PROMPT_FILE" 2>/dev/null
cat "ARCHITECTURE.md" >> "$PROMPT_FILE" 2>/dev/null
printf '\n## Code to Review\n' >> "$PROMPT_FILE"
for f in file1.py file2.py; do printf '\n### %s\n' "$f"; cat "$f"; done >> "$PROMPT_FILE"
cat >> "$PROMPT_FILE" << 'EOF'

## Review Focus
1. Craftsmanship: Is this idiomatic, clean, well-structured?
2. Architecture: Does this fit the project's patterns? Any design concerns?
3. Correctness: Any logical issues, edge cases, or bugs?
4. Invariants: Do classifications (terminal, final, immutable) match runtime reality? Are there states where cleanup or cancellation is assumed but not enforced? Does the code's model of the system match what actually happens?
5. Maintainability: Will this be easy to understand and modify later?

## Output Format
Provide your review as structured JSON:
{
  "provider": "your-name",
  "quality_rating": "excellent|good|fair|needs-work",
  "issues": [
    {
      "severity": "high|medium|low",
      "location": "file:line",
      "category": "craftsmanship|architecture|correctness|invariants|maintainability",
      "description": "What is wrong",
      "suggestion": "How to fix it"
    }
  ],
  "praise": ["What is done well"],
  "summary": "One paragraph overall assessment"
}
EOF
```

Then pass the assembled file to `llm_council.py` in Step 4:
```bash
STAR_CHAMBER_PATH="<set by caller>"; SC_TMPDIR="<set by caller>"; uv run --project "$STAR_CHAMBER_PATH" --isolated [--with <sdk>...] "$STAR_CHAMBER_PATH/llm_council.py" --input-file "$SC_TMPDIR/prompt.txt" [--provider <name>...] [--file <path>...]
```

## Step 4: Fan Out to Star-Chamber

Use `uv run --project "$STAR_CHAMBER_PATH" --isolated` to execute scripts with dependencies pinned in the star-chamber `pyproject.toml`, fully isolated from the host project's environment. The `--project` flag points `uv` at the star-chamber directory's `pyproject.toml` (not the host project's). The `--isolated` flag prevents `uv` from reusing an active virtual environment (via `VIRTUAL_ENV`) or a `.venv` directory found in the current or parent directories — without it, host project packages leak into `sys.path`. Do not use `uvx` — it runs CLI tools from PyPI (similar to `npx`), not project scripts with local file paths.

First, determine which SDK packages are needed:

```bash
STAR_CHAMBER_PATH="<set by caller>"; uv run --project "$STAR_CHAMBER_PATH" --isolated "$STAR_CHAMBER_PATH/llm_council.py" --list-sdks
```

This outputs JSON with `required_sdks` array listing needed packages (e.g., `["anthropic", "google-genai"]`).

**Execution modes:**

| Mode     | Invocation            | Flow                                        | Use Case                          |
|----------|-----------------------|---------------------------------------------|-----------------------------------|
| Parallel | (default)             | All providers review independently at once  | Fast consensus gathering          |
| Debate   | `--debate --rounds N` | Multiple rounds with summarization between  | Deep deliberation, refining ideas |

### Parallel Mode (default)

The simplest approach: all providers review independently in a single round.

Execute a single parallel review. Pass the prompt file (built in Step 3) to `llm_council.py`:

```bash
STAR_CHAMBER_PATH="<set by caller>"; SC_TMPDIR="<set by caller>"; uv run --project "$STAR_CHAMBER_PATH" --isolated [--with <sdk>...] "$STAR_CHAMBER_PATH/llm_council.py" --input-file "$SC_TMPDIR/prompt.txt" [--provider <name>...] [--file <path>...]
```

**Important:** The `uv run` command and all its arguments must be on a **single line**. Do NOT use `\` line continuations — they break under Claude Code's Bash tool. The core `any-llm-sdk` is pinned via `pyproject.toml`. Provider-specific SDKs (from `--list-sdks` output's `required_sdks` array) are added as `--with <sdk>` flags (e.g., `--with anthropic --with google-genai`).

**Important:** Do NOT redirect stderr into the output file (no `2>&1`). `uv` prints install messages to stderr (e.g., `Installed 22 packages in 27ms`) which would corrupt the JSON output. Only redirect stdout.

```text
Prompt → [Provider A] ──→ Response A
      → [Provider B] ──→ Response B    (all at once, independent)
      → [Provider C] ──→ Response C
```

### Debate Mode

For deeper deliberation, debate mode runs multiple rounds where providers respond to each other's feedback.

You orchestrate the debate loop. The Python script handles parallel fan-out/fan-in for each round; you handle summarization between rounds.

**Note:** Debate mode involves multiple rounds of LLM calls, increasing both cost and response time compared to parallel mode.

**Debate flow:**

```text
Round 1: Fan out original prompt to all providers (parallel)
         ↓
         Collect responses: R1_A, R1_B, R1_C, ...
         ↓
For each subsequent round (2 to N):
         ↓
    Create ONE anonymous summary of ALL responses from the previous round
         ↓
    Build new prompt: original + "Other council members said: {summary}"
         ↓
    Fan out to all providers in parallel (single llm_council.py call)
         ↓
    Collect responses: RN_A, RN_B, RN_C, ...
         ↓
Final: Use last round responses for consensus building
```

**Persisting round results:**

Context compaction can fire between rounds and destroy previous round responses. To prevent data loss, persist each round's results to a per-run temp directory.

Before the first round, create the fixed parent directory and a unique run subdirectory, then inform the user:
```bash
SC_PARENT="${TMPDIR:-/tmp}/star-chamber"; mkdir -p "$SC_PARENT"; chmod 700 "$SC_PARENT"; SC_TMPDIR=$(mktemp -d "$SC_PARENT/run-XXXXXX"); echo "$SC_TMPDIR"
```

**Capture the echoed path** (e.g. `/tmp/star-chamber/run-KdkPeA`) — you must re-set `SC_TMPDIR` to this literal value in every subsequent bash block, since shell variables do not persist between Bash tool invocations.

Tell the user: _"Debate mode will read and write round results in `<resolved SC_PARENT path>`. Approve access to this directory to avoid repeated prompts."_ Use the resolved value of `$SC_PARENT` (e.g. `/tmp/star-chamber`) so the path the user sees matches the actual permission prompt.

The fixed parent path lets the user grant blanket Bash permission once, while the unique `run-XXXXXX` subdirectory keeps concurrent star-chamber sessions isolated from each other. The `chmod 700` ensures only the current user can access the directory.

For each round, redirect `llm_council.py` stdout directly to a round file instead of capturing in a shell variable. **Re-set both `STAR_CHAMBER_PATH` and `SC_TMPDIR`** at the top of every bash block — they do not persist between invocations:
```bash
STAR_CHAMBER_PATH="<set by caller>"; SC_TMPDIR="<literal path from mktemp output>"; uv run --project "$STAR_CHAMBER_PATH" --isolated [--with <sdk>...] "$STAR_CHAMBER_PATH/llm_council.py" --input-file "$SC_TMPDIR/prompt.txt" > "$SC_TMPDIR/round-1.json"
```

Do NOT redirect stderr into the round file (no `2>&1`) — `uv` prints install messages to stderr which would corrupt the JSON.

Before starting round N+1, read back round N results from the temp file rather than relying on conversation context:
```bash
SC_TMPDIR="<literal path from mktemp output>"; cat "$SC_TMPDIR/round-1.json"
```

This ensures the anonymous synthesis step has access to the actual provider responses even if compaction occurred between rounds.

Clean up the temp directory after the final round is complete and results have been presented:
```bash
SC_TMPDIR="<literal path from mktemp output>"; rm -rf "$SC_TMPDIR"
```

**Round 1:** Call llm_council.py with the original prompt (all providers, parallel).

**Round 2+:** Create ONE anonymous summary of all responses from the previous round, then call llm_council.py again with the augmented prompt. All providers receive the same summary - this maintains parallel execution and aligns with the anonymous synthesis approach.

**Summarization (anonymous synthesis):** When summarizing for the next round, synthesize feedback by content themes WITHOUT attributing specific points to individual providers. Present the collective feedback anonymously, focusing on consolidating similar concerns and highlighting areas of agreement or disagreement. This encourages providers to engage with ideas rather than sources. Example:

```text
"## Other council members' feedback (round 1):

**Issues raised:**
- The config loader silently ignores missing env vars, risking runtime errors
- Linear search in get_resource_definition may be slow for large configs
- Consider adding a strict mode for env var validation

**Points of agreement:**
- Type hints are solid
- Overall code structure is clean

Please provide your perspective on these points. Note where you agree, disagree, or have additional insights."
```

**Error handling:** If a provider fails during a round, continue with the remaining providers. Note failed providers in the final output but do not block the debate.

**Convergence check:** If responses in round N are substantively the same as round N-1 (providers just agree with no new points), you may stop early. This is optional - completing all requested rounds is also acceptable.

**Prompt construction:** Build the prompt as a temp file (see Step 3), then pass it via `--input-file "$SC_TMPDIR/prompt.txt"`. Never store the prompt in a shell variable — file contents and special characters will break expansion.

**Important:** Keep the entire `uv run` command on one line. The core `any-llm-sdk` is resolved from `pyproject.toml`; provider SDKs are added via `--with` flags from the `--list-sdks` output. Each `--with` must be a separate argument.

## Step 5: Parse and Aggregate Results

The response parsing algorithm and consensus classification rules are formally specified in `spec/council-protocol/SPEC.md` (sections *Response Parsing* and *Consensus Classification*). The steps below summarize the implementation.

For each successful provider response:

1. **Extract JSON** from the response. Providers often wrap JSON in markdown code blocks like ` ```json {...} ``` `. Extract the JSON object. If parsing fails, note the provider as having a malformed response.

2. **Normalize issues** by location and category to enable grouping.

3. **Group issues by similarity**:
   - Same file + same line range + same category = likely same issue
   - Similar descriptions across providers = same underlying concern

4. **Classify by agreement** (mutually exclusive buckets):
   - **Consensus** (all providers flagged it): Highest confidence
   - **Majority** (2+ providers, but not all): High confidence
   - **Individual** (1 provider only): Note but lower confidence

## Step 6: Present Results to User

Present the aggregated results using this format. Always show consensus issues first. The output schema and markdown presentation templates are defined in `spec/council-protocol/SPEC.md` (section *Output Format*).

```markdown
## Star-Chamber Review

**Files:** {list of files reviewed}
**Providers:** {list of providers used}

### Consensus Issues (All Providers Agree)

These issues were flagged by every council member. Address these first.

1. `{file}:{line}` **[{SEVERITY}]** - {description}
   - **Suggestion:** {how to fix}

### Majority Issues ({N}/{M} Providers)

These issues were flagged by most council members.

1. `{file}:{line}` **[{SEVERITY}]** ({which providers}) - {description}
   - **Suggestion:** {how to fix}

### Individual Observations

Issues raised by a single provider. May be valid specialized insights.

- **{Provider}:** `{location}` - {observation}

### Summary

| Provider | Quality Rating | Issues Found |
|----------|---------------|--------------|
| {name}   | {rating}      | {count}      |

**Overall:** {1-2 sentence synthesis of the review}
```

**Important:**
- Always lead with consensus issues - these are the most actionable
- Include the suggestion/fix from providers when available
- Note which providers flagged majority issues for context
- Keep the summary concise - users want to know what to fix
- Do NOT include raw JSON output in the terminal summary - the markdown format above is for human consumption

## Usage Examples

```bash
# Basic - review recent changes with default providers (parallel, single round).
/star-chamber

# Specific files and providers.
/star-chamber --file backend/app/auth.py --provider openai --provider anthropic

# Debate mode - 2 rounds (default) where each provider sees others' responses.
/star-chamber --debate

# Debate mode - 3 rounds of deliberation.
/star-chamber --debate --rounds 3

# Debate with specific files.
/star-chamber --debate --rounds 2 --file auth.py --provider openai --provider gemini
```

## Configuration

The provider configuration schema is formally specified in `spec/council-protocol/SPEC.md` (section *Provider Configuration*). Relevant schemas:
- `spec/council-protocol/schemas/provider-config.schema.json`
- `spec/council-protocol/schemas/council-config.schema.json`

Provider configuration is read from `~/.config/star-chamber/providers.json`.

The reference configuration with current models is maintained at `reference/star-chamber/providers.json` in the pragma plugin. Update models there and re-run `generate_config.py` with `--platform` or `--direct` to propagate changes to your local config.

Override config path with `STAR_CHAMBER_CONFIG` environment variable.

### Provider fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | Provider name (e.g., `openai`, `anthropic`, `llamafile`, `ollama`) |
| `model` | yes | Model identifier |
| `api_key` | no | API key or `${ENV_VAR}` reference. Omit for platform mode or keyless local providers. |
| `max_tokens` | no | Max response tokens (default: 16384) |
| `api_base` | no | Custom base URL. Use for local/self-hosted LLMs (llamafile, ollama, vLLM, LocalAI, lmstudio). Omit for cloud providers — the SDK uses built-in defaults. |
| `local` | no | Set to `true` for local/self-hosted providers (default: `false`). See [Platform mode and local providers](#platform-mode-and-local-providers) for behavioral details. |

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

- **Key fetch tolerant:** If the platform has no key for a local provider, the council proceeds with an empty key instead of failing. A warning is logged to stderr.
- **Network fault tolerant:** If the platform is unreachable or returns an unexpected error, local providers still proceed. Non-local providers fail fast.
- **Auth error guidance:** If a local provider returns an auth error at call time, the error message suggests adding the key to the any-llm platform project or setting `api_key` directly in `providers.json`.
- **Diagnostic output:** `--list-sdks` reports local providers under `providers_local`, not `providers_missing_key`.

Local providers can still use keys: if the platform has a key stored for a local provider (e.g., llamafile behind a reverse proxy with auth), it will be fetched and used normally. The `local` flag only affects the *failure* path.

## Using any-llm.ai Managed Platform (Optional)

Instead of setting individual API keys, you can use the [any-llm.ai](https://any-llm.ai) managed platform for:
- **Centralized key management** - Store provider keys securely (encrypted client-side)
- **Usage tracking** - Automatic cost and token tracking across all providers
- **Single authentication** - One `ANY_LLM_KEY` instead of multiple provider keys

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
- Provider and model used
- Token counts (input/output)
- Request timestamps
- Cost estimates

### Platform Config Example

Same as the reference config but with `"platform": "any-llm"` added and `api_key` fields removed — the library fetches keys from the platform automatically. The setup flow handles this transformation.

Note: `api_key` fields are omitted - the library fetches them from the platform automatically.

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
- The `--list-sdks` command shows whether keys are set, not their values.

## Troubleshooting

### Common Errors

**Authentication failed for {provider}:**
```json
{"provider": "openai", "success": false, "error": "Authentication failed for openai. Check OPENAI_API_KEY is set and valid."}
```
- Verify the environment variable is set: `[ -n "$OPENAI_API_KEY" ] && echo "set" || echo "not set"`
- Check if the key is valid (not expired or revoked)
- For platform mode, verify `ANY_LLM_KEY` is set: `[ -n "$ANY_LLM_KEY" ] && echo "set" || echo "not set"`

**Request timed out:**
```json
{"provider": "gemini", "success": false, "error": "Request timed out after 60s"}
```
- Increase timeout via `--timeout 120` or in config `timeout_seconds`
- Check network connectivity to the provider

**Missing SDK:**
```json
{"provider": "anthropic", "success": false, "error": "Missing SDK for anthropic. Install with: pip install anthropic (or add '--with anthropic' to uv run)"}
```
- Run `--list-sdks` to see required packages
- Add the missing SDK as a `--with <sdk>` flag to the `uv run` command

**Provider not in sdk_map:**
```text
[star-chamber] Provider custom-llm not in sdk_map, assuming OpenAI-compatible
```
- This is a warning, not an error. Unknown providers are assumed to use the OpenAI-compatible API.
- If your provider needs a specific SDK, add it to `sdk_map.json`

### Partial Failures

When some providers succeed and others fail, the output includes both:

```json
{
  "reviews": [
    {"provider": "openai", "model": "gpt-4o", "success": true, "content": "..."}
  ],
  "failed_reviews": [
    {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "success": false, "error": "Request timed out after 60s"}
  ],
  "providers_used": ["openai", "anthropic"]
}
```

The review continues with available providers. Check `failed_reviews` for details on failures.

### Debate Convergence

In debate mode, the council may exit early if responses stabilize:
```text
[star-chamber] Debate converged after round 3
```

This means all successful providers gave the same responses in consecutive rounds. Providers that failed or timed out are excluded from convergence detection and listed under `failed_reviews`. The output will include `"converged": true`.

## Cost Warning

Each invocation calls all configured providers. With 3 providers reviewing ~2000 tokens:
- ~$0.02-0.10 per invocation depending on models
- Basic mode (no debate) is used when auto-invoked to keep costs predictable.

## Specification

The portable council protocol (invocation modes, prompt templates, response parsing, consensus classification, and output format) is formally specified in `spec/council-protocol/SPEC.md` with JSON schemas and worked examples. This PROTOCOL.md contains the Claude Code-specific orchestration implementation — Bash subprocess isolation, `uv run` invocation, temp file management, and setup wizard flow. As a rule of thumb: if it affects interoperability or wire format, it belongs in the spec; if it concerns Claude Code runtime or tooling constraints, it belongs here.
