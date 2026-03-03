# Council Protocol Specification v0.1

This document specifies the portable council deliberation protocol — the invocation modes, prompt templates, response parsing, consensus classification, and output format that any orchestrator can implement independently.

The orchestrator-specific implementation for Claude Code lives in [`plugins/pragma/skills/star-chamber/PROTOCOL.md`](../../plugins/pragma/skills/star-chamber/PROTOCOL.md). That document handles Bash subprocess isolation, `uv run` invocation, temp file management, and other runtime concerns. This spec covers only the portable protocol logic.

**Status:** Draft (v0.1). Breaking changes may occur before v1.0.

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. Invocation Modes](#2-invocation-modes)
- [3. Provider Configuration](#3-provider-configuration)
- [4. Review Request](#4-review-request)
- [5. Prompt Templates](#5-prompt-templates)
- [6. Execution](#6-execution)
- [7. Anonymous Synthesis](#7-anonymous-synthesis)
- [8. Response Parsing](#8-response-parsing)
- [9. Consensus Classification](#9-consensus-classification)
- [10. Output Format](#10-output-format)
- [11. Security](#11-security)
- [12. Error Handling](#12-error-handling)

## 1. Introduction

The council protocol defines how multiple LLM providers are queried in parallel, how their responses are parsed and compared, and how the results are classified by agreement level. It is designed so that any orchestrator — CI pipelines, GitHub Actions, editor plugins, SDKs — can implement the protocol without coupling to a specific runtime.

### Versioning

This spec follows [Semantic Versioning](https://semver.org/). The current version is **0.1** (pre-stable). The version will advance to 1.0 when the schema and algorithm definitions are considered stable.

### Terminology

| Term | Definition |
|------|-----------|
| **Provider** | An LLM service (e.g., OpenAI, Anthropic, Gemini) or a local model endpoint. |
| **Council** | The set of providers consulted for a single review or question. |
| **Round** | One fan-out/fan-in cycle across all providers. |
| **Consensus** | An issue or recommendation flagged by all successful providers. |
| **Majority** | An issue or recommendation flagged by more than one but not all providers. |

## 2. Invocation Modes

The protocol supports two invocation modes. The mode determines the prompt template and aggregation strategy.

| Mode | Trigger | Prompt Template | Aggregation |
|------|---------|----------------|-------------|
| **Code Review** | Default. Files provided, no design question. | [5.1 Code Review Prompt](#51-code-review-prompt) | Group by file location, classify by agreement. |
| **Design Question** | User asks an architecture/design question. | [5.2 Design Question Prompt](#52-design-question-prompt) | Group by approach recommendation. |

**Code review** is the default mode. It reviews files for craftsmanship, architecture, correctness, invariants, and maintainability.

**Design question** mode is triggered when the user asks about architecture, design trade-offs, or approach (e.g., "should we use event sourcing or CRUD?"). No files are reviewed — providers give advisory recommendations.

## 3. Provider Configuration

Provider configuration defines which LLM providers the council consults and how to reach them.

**Schemas:**
- Single provider entry: [`schemas/provider-config.schema.json`](schemas/provider-config.schema.json)
- Full config file: [`schemas/council-config.schema.json`](schemas/council-config.schema.json)

### Provider Fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | Yes | Provider name (e.g., `openai`, `anthropic`, `llamafile`, `ollama`). |
| `model` | Yes | Model identifier (e.g., `gpt-4o`, `claude-sonnet-4-20250514`). |
| `api_key` | No | API key or `${ENV_VAR}` reference. Omit for platform mode or keyless local providers. |
| `max_tokens` | No | Max response tokens. Default: 16384. |
| `api_base` | No | Custom base URL. Use for local/self-hosted LLMs. Omit for cloud providers — SDKs use built-in defaults. |
| `local` | No | Set to `true` for local/self-hosted providers. Default: `false`. |

### API Key Resolution

Keys are resolved in this order:

1. `api_key` field in the provider config (literal value or `${ENV_VAR}` reference).
2. Environment variable matching the provider convention (e.g., `OPENAI_API_KEY`).
3. Platform key fetch (when `platform` is configured).

### Platform Mode

When `platform` is set (e.g., `"any-llm"`), the orchestrator fetches API keys from the platform service for each provider. Providers marked `local: true` get special treatment:

- **Key fetch tolerant:** If the platform has no key for a local provider, the council proceeds with an empty key instead of failing.
- **Network fault tolerant:** If the platform is unreachable, local providers still proceed. Non-local providers fail.
- **Auth error guidance:** If a local provider returns an auth error, the error message should suggest adding the key to the platform or setting `api_key` directly.

### Local Provider Semantics

Local providers (`local: true`) use `api_base` to reach a local or self-hosted endpoint. They can still use keys — if the platform has a key stored, it will be fetched and used normally. The `local` flag only affects the failure path (tolerant vs fail-fast).

## 4. Review Request

A review request captures everything an orchestrator needs to execute a council round.

**Schema:** [`schemas/review-request.schema.json`](schemas/review-request.schema.json)

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `mode` | Yes | `"code-review"` or `"design-question"`. |
| `files` | Code review only | Array of file objects with `path` and `content`. |
| `prompt` | Design question only | The user's design question. |
| `context` | No | Project rules and architecture context. |
| `providers` | No | Override which providers to consult (defaults to all configured). |

## 5. Prompt Templates

### 5.1 Code Review Prompt

The code review prompt instructs providers to review code for five focus areas and return structured JSON.

```
You are a senior software craftsman reviewing code for quality, idioms, and architectural soundness.

## Project Context
{Injected project rules, if any}
{Architecture context, if available}

## Code to Review
{For each file: ### {path}\n{content}}

## Review Focus
1. Craftsmanship: Is this idiomatic, clean, well-structured?
2. Architecture: Does this fit the project's patterns? Any design concerns?
3. Correctness: Any logical issues, edge cases, or bugs?
4. Invariants: Do classifications (terminal, final, immutable) match runtime reality?
   Are there states where cleanup or cancellation is assumed but not enforced?
   Does the code's model of the system match what actually happens?
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
```

**Response schema:** [`schemas/code-review-result.schema.json`](schemas/code-review-result.schema.json)

### 5.2 Design Question Prompt

The design question prompt instructs providers to advise on architecture/design decisions.

```
You are a senior software architect advising on design decisions.

## Project Context
{Injected project rules, if any}
{Architecture context, if available}

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

**Response schema:** [`schemas/design-advice-result.schema.json`](schemas/design-advice-result.schema.json)

## 6. Execution

### 6.1 Parallel Mode (default)

All providers are queried simultaneously in a single round. Responses are collected and passed to the parsing and classification stages.

```
Prompt → [Provider A] → Response A
      → [Provider B] → Response B    (all at once, independent)
      → [Provider C] → Response C
```

### 6.2 Debate Mode

Debate mode runs multiple rounds where providers see anonymised summaries of prior responses.

**State machine:**

```
INIT → ROUND_1 → SYNTHESIZE → ROUND_2 → SYNTHESIZE → ... → ROUND_N → FINAL
```

**Round flow:**

1. Fan out the prompt to all providers in parallel.
2. Collect responses.
3. Synthesize responses anonymously (see [section 7](#7-anonymous-synthesis)).
4. Augment the original prompt with the synthesis.
5. Repeat from step 1 for the next round.
6. After the final round, pass last-round responses to parsing and classification.

**Convergence detection:** If responses in round N are substantively identical to round N-1 (providers agree with no new points), the orchestrator MAY stop early. Completing all requested rounds is also acceptable.

**Error handling during rounds:** If a provider fails during a round, continue with remaining providers. Note failed providers in the output. Failed providers are excluded from convergence detection.

## 7. Anonymous Synthesis

Between debate rounds, the orchestrator creates a single anonymous summary of all responses from the previous round.

### Rules

1. Synthesize by content theme — never attribute points to individual providers.
2. Group similar concerns together.
3. Highlight areas of agreement and disagreement.
4. Ask providers to engage with the ideas, not the sources.

### Synthesis Template

```
## Other council members' feedback (round {N}):

**Issues raised:**
- {Grouped concern 1}
- {Grouped concern 2}

**Points of agreement:**
- {Shared observation 1}

**Points of disagreement:**
- {Divergent view 1}

Please provide your perspective on these points. Note where you agree, disagree, or have additional insights.
```

This approach follows [Chatham House rules](https://www.chathamhouse.org/about-us/chatham-house-rule): information can be used freely, but the identity of the source is not revealed.

## 8. Response Parsing

### Algorithm

For each provider response:

1. **Try extracting JSON from a markdown code block.** Look for `` ```json `` followed by a JSON object and closed by `` ``` ``. Extract and parse the JSON object.
2. **Fallback: try parsing the entire response as JSON.** If step 1 finds no code block, attempt to parse the full response text as JSON.
3. **Malformed response:** If both steps fail, mark the provider as failed with a "malformed response" error. Continue processing other providers.

### Validation

After extraction, validate the parsed JSON against the appropriate schema:
- Code review mode: [`schemas/code-review-result.schema.json`](schemas/code-review-result.schema.json)
- Design question mode: [`schemas/design-advice-result.schema.json`](schemas/design-advice-result.schema.json)

If validation fails, the orchestrator SHOULD still attempt to use the response (best-effort parsing) but MAY mark it as degraded.

## 9. Consensus Classification

### 9.1 Issue Grouping (Code Review)

Issues from different providers are grouped when they refer to the same underlying concern:

- **Same file** AND **same line range** (within ±5 lines tolerance) AND **same category** = same issue.
- Orchestrators MAY supply a custom semantic similarity function for more sophisticated grouping.

### 9.2 Approach Grouping (Design Question)

The approaches array includes all approaches mentioned by any provider — both recommended and discussed-but-rejected alternatives. An approach with `recommended_by: 0` was considered by one or more providers but not recommended by any.

Approaches from different providers are grouped when they refer to the same approach (by name match or semantic similarity). The `recommended_by` count reflects how many providers selected that approach as their primary recommendation.

### 9.3 Classification Buckets

Issues/recommendations fall into mutually exclusive buckets:

| Bucket | Definition | Confidence |
|--------|-----------|------------|
| **Consensus** | All successful providers flagged it. | Highest |
| **Majority** | More than one but not all providers. | High |
| **Individual** | Exactly one provider. | Lower |

**Design question consensus:** For design questions, `consensus_recommendation` captures high-level directional agreement (e.g., "use CRUD, not event sourcing") even when providers recommend different specific variants. It is not populated when providers disagree on direction. Per-approach `recommended_by` counts track the specific variant each provider chose.

### 9.4 Confidence Ordering

Results are ordered: consensus first, then majority, then individual. Within each bucket, order by severity (high → medium → low) for code review, or by provider count for design questions.

Orchestrators MAY apply per-provider calibration weights to adjust confidence, but the default is equal weighting.

## 10. Output Format

**Schema:** [`schemas/council-output.schema.json`](schemas/council-output.schema.json)

### 10.1 Code Review Output

The structured output includes:

- `mode`: `"code-review"`
- `files_reviewed[]`: List of reviewed file paths.
- `providers_used[]`: List of all providers consulted.
- `failed_providers[]`: Providers that failed or returned malformed responses.
- `consensus_issues[]`: Issues flagged by all successful providers.
- `majority_issues[]`: Issues flagged by more than one provider. Each item includes `provider_count` and `flagged_by` (array of provider names) to identify which providers raised it.
- `individual_issues{}`: Issues keyed by provider name.
- `quality_ratings{}`: Per-provider quality rating.
- `summary{}`: Counts (`total_issues`, `consensus_count`, `majority_count`) and `synthesis` (1-2 sentence overall assessment).
- `debate{}` (optional): Debate metadata (rounds_completed, converged).

**Markdown presentation** (for human consumption):

```markdown
## Council Review

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

Issues raised by a single provider. May be valid specialised insights.

- **{Provider}:** `{location}` - {observation}

### Summary

| Provider | Quality Rating | Issues Found |
|----------|---------------|--------------|
| {name}   | {rating}      | {count}      |

**Overall:** {1-2 sentence synthesis of the review}
```

### 10.2 Design Question Output

The structured output includes:

- `mode`: `"design-question"`
- `prompt`: The original design question (enables rendering the markdown template without external context).
- `providers_used[]`: List of all providers consulted.
- `failed_providers[]`: Providers that failed or returned malformed responses.
- `consensus_recommendation` (optional): High-level directional agreement when all providers agree, even if they differ on specifics.
- `approaches[]`: All approaches mentioned by any provider, with `recommended_by` count, merged pros/cons, `risk_level`, and optional `fit_rating`.
- `summary{}`: Contains `synthesis` (1-2 sentence overall assessment).
- `debate{}` (optional): Debate metadata (rounds_completed, converged).

**Markdown presentation:**

```markdown
## Council Advisory

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

## 11. Security

### Key Handling

- **Never log, echo, or print API key values.** Only check presence (e.g., "key is set" vs "key is missing").
- Avoid shell expansions (`${VAR:-...}`, `${VAR:+...}`) on key variables in log/print statements — these can leak values when the variable is set.
- Use `${ENV_VAR}` references in config files rather than hardcoding keys.
- Never commit config files containing actual API keys to version control.

### Redaction

Error messages MUST redact API key values. Recommended redaction patterns:
- `sk-*` → `sk-***`
- `ANY.v1.*` → `ANY.v1.***`
- Any string matching a known key prefix → first 6 characters + `***`

### Config File Permissions

Orchestrators SHOULD set restrictive permissions on config files containing key references (e.g., `chmod 600`).

## 12. Error Handling

### Provider Failure

If a provider fails (network error, auth error, timeout), continue with remaining providers. Record the failure in `failed_providers[]` with the error message.

### All Providers Fail

If all providers fail, report the error with all failure details. Do not produce partial output — there is no consensus to classify.

### Timeout

Each provider MAY have a configurable timeout (`timeout_seconds` in the council config). The default is 60 seconds. On timeout, mark the provider as failed and continue.

### Malformed Response

If a provider returns a response that cannot be parsed (see [section 8](#8-response-parsing)), mark it as failed and continue with other providers.

---

## Examples

See the [`examples/`](examples/) directory for complete worked examples:

- [`examples/code-review/`](examples/code-review/) — A 3-provider code review with consensus, majority, and individual findings.
- [`examples/design-question/`](examples/design-question/) — A 2-provider design advisory with different recommendations.
