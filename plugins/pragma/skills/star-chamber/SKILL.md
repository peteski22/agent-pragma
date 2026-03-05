---
name: star-chamber
description: Multi-LLM craftsmanship council with live progress and debate mode for code review and design questions
user-invocable: true
model-invocable: false
allowed-tools: Bash, Read, Glob, Grep
---

# Star-Chamber: Multi-LLM Craftsmanship Council

This skill is for explicit `/star-chamber` invocations with live progress in the main conversation. It supports `--debate` for multi-round deliberation. For automatic invocation on architectural decisions, the `star-chamber` agent handles that separately.

Advisory skill that fans out code reviews and design questions to multiple LLM providers (Claude, OpenAI, Gemini, etc.) and aggregates their feedback into consensus recommendations.

## Arguments

| Flag | Description | Manual Only |
|------|-------------|-------------|
| `--provider <name>` | LLM provider to use (repeatable, e.g., `--provider openai --provider gemini`). Defaults to all in config. | No |
| `--file <path>` | Specify file to review (repeatable). Defaults to recent git changes. | No |
| `--timeout <seconds>` | Timeout per provider request (overrides config `timeout_seconds`). | No |
| `--debate` | Enable debate mode: multiple rounds with summarization between rounds. | **Yes** |
| `--rounds N` | Number of debate rounds (default: 2, requires --debate). | **Yes** |

**Manual-only flags** are skill invocation parameters interpreted by Claude Code, NOT flags passed to the star-chamber CLI. Debate mode is orchestrated by Claude Code (see Debate Mode in the protocol).

## Path Setup

The skill loader provides the base directory in the header: `Base directory for this skill: <path>`. Set the path variable used throughout the protocol:

```bash
STAR_CHAMBER_PATH="<base directory from header>"
# e.g., STAR_CHAMBER_PATH="$HOME/.claude/plugins/cache/pragma/skills/star-chamber"
```

## Protocol

Read and follow the full protocol from `$STAR_CHAMBER_PATH/PROTOCOL.md`. It contains Steps 0-4: prerequisite checks, invocation mode detection (code review vs design question), review target identification, context gathering, CLI invocation, and result presentation. Debate mode is documented as a separate section.

## Auto-Invocation

This skill is not auto-invoked (`model-invocable: false`). The `star-chamber` custom subagent handles auto-invocation based on its description. This skill is for explicit `/star-chamber` invocations only.
