#!/usr/bin/env python3
"""
Multi-LLM council for star-chamber skill.

Features:
- Fan out prompts to multiple LLM providers in parallel
- Fan in responses for aggregation
- Target specific files or recent changes
- Select providers or use default config

Note: Debate mode (multi-round deliberation) is orchestrated by Claude Code
in SKILL.md, not by this script. This script handles single-round parallel calls.
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, TypedDict


# API key patterns to redact from error messages.
API_KEY_PATTERNS = [
    r"sk-(?:proj-)?[a-zA-Z0-9]{20,}",  # OpenAI keys (classic and project-scoped).
    r"sk-ant-[a-zA-Z0-9-]{20,}",  # Anthropic keys.
    r"ANY\.v1\.[a-zA-Z0-9]+",  # any-llm.ai platform keys.
    r"AIza[a-zA-Z0-9_-]{35}",  # Google API keys.
    r"gsk_[a-zA-Z0-9]{20,}",  # Groq keys.
]


# Fallback when provider config omits max_tokens.
DEFAULT_MAX_TOKENS = 16384


class ProviderConfig(TypedDict, total=False):
    """Configuration for a single LLM provider."""

    provider: str
    model: str
    api_key: str
    max_tokens: int
    api_base: str
    local: bool


class ReviewResult(TypedDict, total=False):
    """Result from a single provider review."""

    provider: str
    model: str
    success: bool
    content: str
    parsed_json: dict[str, Any] | list[Any] | None
    error: str


def extract_json(content: str) -> dict[str, Any] | list[Any] | None:
    """Extract JSON from LLM response, handling markdown code blocks.

    LLMs often wrap JSON responses in markdown code blocks like:
        ```json
        {"key": "value"}
        ```

    This function tries to parse JSON directly first, then falls back to
    extracting from code blocks.
    """
    if not content:
        return None

    # Try direct parse first.
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` or ``` ... ``` blocks.
    # Patterns use \s* to handle optional whitespace/newlines.
    patterns = [
        r"```json\s*(.*?)\s*```",  # ```json ... ```
        r"```\s*([\{\[].*?[\}\]])\s*```",  # ``` {/[ ... ]/} ```
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    print("[star-chamber] Could not extract JSON from response", file=sys.stderr)
    return None


def sanitize_error(message: str) -> str:
    """Redact API keys and sensitive patterns from error messages."""
    result = message
    for pattern in API_KEY_PATTERNS:
        result = re.sub(pattern, "[REDACTED]", result)
    return result


def load_sdk_map() -> dict[str, str | None]:
    """Load provider-to-SDK mapping."""
    sdk_map_path = Path(__file__).resolve().parent / "sdk_map.json"
    if not sdk_map_path.exists():
        print(
            json.dumps({
                "error": f"SDK map not found: {sdk_map_path}",
                "hint": "Ensure star-chamber skill is set up correctly.",
            }),
        )
        sys.exit(1)

    try:
        with open(sdk_map_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(
            json.dumps({
                "error": f"Invalid JSON in SDK map: {sdk_map_path}",
                "details": str(e),
                "hint": "Check the file for syntax errors.",
            }),
        )
        sys.exit(1)

    # Validate structure: should be dict with string keys and string/None values.
    if not isinstance(data, dict):
        print(
            json.dumps({
                "error": "SDK map must be a JSON object",
                "got": type(data).__name__,
            }),
        )
        sys.exit(1)

    data.pop("_comment", None)
    return data


def get_required_sdks(provider_names: list[str]) -> list[str]:
    """Return list of SDK packages needed for the given providers."""
    sdk_map = load_sdk_map()
    sdks = []
    for name in provider_names:
        sdk = sdk_map.get(name.lower())
        if sdk:
            sdks.append(sdk)
        elif name.lower() != "openai":  # openai is the base case, no SDK needed
            print(
                f"[star-chamber] Provider {name} not in sdk_map, assuming OpenAI-compatible",
                file=sys.stderr,
            )
    return sorted(set(sdks))


async def _get_review_internal(
    config: ProviderConfig, prompt: str,
) -> ReviewResult:
    """Send prompt to a single provider and return structured response.

    If api_key is empty and ANY_LLM_KEY is set, the SDK auto-detects platform mode.
    If api_base is set, it overrides the provider's default endpoint URL.
    """
    provider = config["provider"]
    model = config["model"]
    api_key = config.get("api_key", "")
    max_tokens = config.get("max_tokens", DEFAULT_MAX_TOKENS)
    api_base = config.get("api_base", "")
    local = config.get("local", False)

    try:
        # Import here to allow uv run --with to install the dependency.
        from any_llm import acompletion

        kwargs: dict[str, Any] = {
            "model": model,
            "provider": provider,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        # OpenAI gpt-5.x and o-series models require max_completion_tokens
        # instead of max_tokens. any-llm-sdk doesn't map this automatically
        # (see https://github.com/mozilla-ai/any-llm/issues/862).
        if provider.lower() == "openai":
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        if api_key:
            kwargs["api_key"] = api_key
        # If no api_key, SDK checks ANY_LLM_KEY and auto-routes through platform.
        if api_base:
            kwargs["api_base"] = api_base

        response = await acompletion(**kwargs)
        if not response.choices:
            return ReviewResult(
                provider=provider,
                model=model,
                success=False,
                error="No response choices returned from provider",
            )
        content = response.choices[0].message.content
        return ReviewResult(
            provider=provider,
            model=model,
            success=True,
            content=content,
            parsed_json=extract_json(content),
        )
    except ImportError:
        sdk_map = load_sdk_map()
        sdk = sdk_map.get(provider.lower())
        if sdk:
            hint = f"Install with: pip install {sdk} (or add '--with {sdk}' to uv run)"
        else:
            hint = "This provider may use the OpenAI-compatible API (no extra SDK needed)"
        return ReviewResult(
            provider=provider,
            model=model,
            success=False,
            error=f"Missing SDK for {provider}. {hint}",
        )
    except Exception as e:
        error_msg = str(e).lower()
        # Map providers to their env var names for helpful errors.
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "google": "GEMINI_API_KEY",
            "cohere": "COHERE_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "groq": "GROQ_API_KEY",
        }
        env_var = env_var_map.get(provider.lower(), f"{provider.upper()}_API_KEY")

        # Detect common API key issues (error_msg is already lowercased above).
        is_auth_error = (
            "api_key" in error_msg
            or "unauthorized" in error_msg
            or "401" in error_msg
            or "api key" in error_msg
            or "apikey" in error_msg
        )
        if is_auth_error:
            if local:
                return ReviewResult(
                    provider=provider,
                    model=model,
                    success=False,
                    error=(
                        f"Local provider {provider} returned auth error. "
                        "If authentication is required, add the key to your any-llm platform "
                        "project or set api_key in providers.json."
                    ),
                )
            return ReviewResult(
                provider=provider,
                model=model,
                success=False,
                error=f"Authentication failed for {provider}. Check {env_var} is set and valid.",
            )
        return ReviewResult(
            provider=provider,
            model=model,
            success=False,
            error=sanitize_error(str(e)),
        )


async def get_review(
    config: ProviderConfig, prompt: str, timeout: float | None = None,
) -> ReviewResult:
    """Get review with optional timeout.

    Wraps _get_review_internal with asyncio.wait_for for timeout handling.
    """
    if timeout is None:
        return await _get_review_internal(config, prompt)

    try:
        return await asyncio.wait_for(
            _get_review_internal(config, prompt),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ReviewResult(
            provider=config["provider"],
            model=config["model"],
            success=False,
            error=f"Request timed out after {timeout}s",
        )


async def resolve_api_keys(
    providers: list[dict[str, Any]],
    use_platform: bool,
    any_llm_key: str = "",
) -> list[dict[str, Any]]:
    """Resolve API keys for all providers, returning new provider dicts.

    In platform mode, fetches keys from the any-llm platform. Local providers
    tolerate platform failures gracefully (proceed with empty key).

    In direct mode, expands ${ENV_VAR} references from the environment.
    """
    if use_platform:
        ignored = [p["provider"] for p in providers if p.get("api_key")]
        if ignored:
            print(
                f"[star-chamber] Using platform mode, ignoring api_key for: {', '.join(ignored)}",
                file=sys.stderr,
            )
        return await _resolve_platform_keys(providers, any_llm_key)

    # Direct mode: resolve from environment variables.
    resolved = []
    for p in providers:
        p = {**p}
        api_key = p.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            p["api_key"] = os.environ.get(env_var, "")
        resolved.append(p)
    return resolved


async def _resolve_platform_keys(
    providers: list[dict[str, Any]], any_llm_key: str,
) -> list[dict[str, Any]]:
    """Fetch provider keys from any-llm platform, returning new provider dicts.

    Tolerates failures for local providers: ProviderKeyFetchError and network/
    transport errors result in an empty key with a warning, not a crash.
    """
    from any_llm_platform_client import (
        AnyLLMPlatformClient,
        ProviderKeyFetchError,
    )

    # Match the env var and default used by any-llm-sdk's platform provider.
    platform_base = os.environ.get("ANY_LLM_PLATFORM_URL", "https://platform-api.any-llm.ai").rstrip("/")
    platform_url = platform_base if platform_base.endswith("/api/v1") else f"{platform_base}/api/v1"
    client = AnyLLMPlatformClient(any_llm_platform_url=platform_url)
    resolved = []
    for p in providers:
        p = {**p}
        try:
            result = await client.aget_decrypted_provider_key(any_llm_key, p["provider"])
            p["api_key"] = result.api_key
        except ProviderKeyFetchError:
            if p.get("local"):
                print(
                    f"[star-chamber] No platform key for local provider {p['provider']}, proceeding without",
                    file=sys.stderr,
                )
                p["api_key"] = ""
            else:
                raise
        except Exception as e:
            if p.get("local"):
                print(
                    f"[star-chamber] Platform error for local provider {p['provider']}: {e}, proceeding without",
                    file=sys.stderr,
                )
                p["api_key"] = ""
            else:
                raise
        resolved.append(p)
    return resolved


def get_changed_files() -> list[str]:
    """Fallback if no --file args provided: get recent changes."""
    try:
        output = subprocess.check_output(
            ["git", "diff", "HEAD~1", "--name-only", "--diff-filter=ACMRT"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return [f.strip() for f in output.splitlines() if f.strip()]
    except Exception:
        # Try staged files as fallback.
        try:
            output = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return [f.strip() for f in output.splitlines() if f.strip()]
        except Exception:
            return []


async def run_council(
    prompt: str,
    providers: list[ProviderConfig],
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run multi-LLM council review.

    Fans out the prompt to all providers in parallel and returns their responses.
    Debate mode (multi-round deliberation) is handled by Claude Code in SKILL.md.
    """
    tasks = [get_review(p, prompt, timeout=timeout) for p in providers]
    results = list(await asyncio.gather(*tasks))
    return {"reviews": results}


def main() -> None:
    """Entry point for the LLM council script."""
    parser = argparse.ArgumentParser(description="Star-Chamber Multi-LLM Review")
    parser.add_argument(
        "--file", "-f", action="append", help="Target file(s) to review"
    )
    parser.add_argument(
        "--provider", "-p", action="append", help="LLM providers to use"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Timeout in seconds for each provider request (overrides config)",
    )
    parser.add_argument(
        "--list-sdks",
        action="store_true",
        help="Output required SDK packages for configured/specified providers and exit",
    )
    parser.add_argument(
        "--input-file", "-I",
        help="Read prompt from file instead of stdin",
    )
    args = parser.parse_args()

    # Load provider config.
    config_path = os.environ.get(
        "STAR_CHAMBER_CONFIG",
        os.path.expanduser("~/.config/star-chamber/providers.json"),
    )

    if not os.path.exists(config_path):
        print(
            json.dumps(
                {
                    "error": f"Config file not found: {config_path}",
                    "hint": "Run /star-chamber to set up configuration, or create manually.",
                },
                indent=2,
            )
        )
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    platform = config.get("platform")
    any_llm_key = ""

    # Validate platform mode prerequisites.
    if platform == "any-llm":
        any_llm_key = os.environ.get("ANY_LLM_KEY", "")
        if not any_llm_key:
            print(
                json.dumps(
                    {
                        "error": "Platform mode enabled but ANY_LLM_KEY not set",
                        "setup": {
                            "step1": "Create project at https://any-llm.ai",
                            "step2": "Add your provider API keys to the project",
                            "step3": "Copy your project key and set: export ANY_LLM_KEY='...'",
                        },
                        "docs": "https://any-llm.ai/docs",
                    },
                    indent=2,
                )
            )
            sys.exit(1)

    providers = config.get("providers", [])

    # Filter to requested providers if specified.
    if args.provider:
        requested = [x.lower() for x in args.provider]
        providers = [p for p in providers if p["provider"].lower() in requested]
        if not providers:
            print(
                json.dumps(
                    {
                        "error": "No matching providers found.",
                        "requested": args.provider,
                        "available": [p["provider"] for p in config.get("providers", [])],
                    },
                    indent=2,
                )
            )
            sys.exit(1)

    # Handle --list-sdks: output diagnostic info and exit.
    if args.list_sdks:
        provider_names = [p["provider"] for p in providers]
        sdks = get_required_sdks(provider_names)

        # In platform mode, add platform SDK.
        if platform == "any-llm":
            sdk_map = load_sdk_map()
            platform_sdk = sdk_map.get("platform")
            if platform_sdk:
                sdks = sorted(set(sdks + [platform_sdk]))

        # Check which providers have API keys set.
        # For direct mode, resolve env vars to check readiness.
        ready = []
        missing_key = []
        platform_provided = []
        local_providers = []
        for p in providers:
            if p.get("local"):
                local_providers.append(p["provider"])
            elif platform == "any-llm":
                platform_provided.append(p["provider"])
            else:
                # Direct mode: resolve env var to check if key is available.
                api_key = p.get("api_key", "")
                if api_key.startswith("${") and api_key.endswith("}"):
                    api_key = os.environ.get(api_key[2:-1], "")
                if api_key:
                    ready.append(p["provider"])
                else:
                    missing_key.append(p["provider"])

        output = {
            "providers_configured": provider_names,
            "providers_ready": ready,
            "providers_missing_key": missing_key,
            "providers_local": local_providers,
            "required_sdks": sdks,
            "uv_with_flags": " ".join(f"--with {sdk}" for sdk in sdks),
            "platform": platform,
        }
        if platform == "any-llm":
            output["providers_platform_provided"] = platform_provided
            output["platform_key_set"] = bool(os.environ.get("ANY_LLM_KEY"))

        print(json.dumps(output, indent=2))
        sys.exit(0)

    # Read prompt from file or stdin.
    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(
                json.dumps({"error": f"Input file not found: {args.input_file}"}),
            )
            sys.exit(1)
        prompt = input_path.read_text()
    else:
        prompt = sys.stdin.read()

    # Determine files to review.
    files_to_review = args.file if args.file else get_changed_files()

    # Build combined prompt with file list.
    combined_prompt = prompt
    if files_to_review:
        combined_prompt += "\n\nFiles to review:\n" + "\n".join(
            f"- {f}" for f in files_to_review
        )

    # Determine timeout: CLI flag > config > None.
    timeout: float | None = args.timeout
    if timeout is None:
        raw_timeout = config.get("timeout_seconds")
        if raw_timeout is not None:
            try:
                timeout = float(raw_timeout)
                if timeout <= 0:
                    raise ValueError("must be positive")
            except (TypeError, ValueError):
                print(
                    json.dumps({
                        "error": "Invalid timeout_seconds in config",
                        "value": raw_timeout,
                        "hint": "timeout_seconds must be a positive number",
                    }),
                )
                sys.exit(1)

    # Resolve API keys and run the council.
    async def _run() -> dict[str, Any]:
        resolved = await resolve_api_keys(
            providers, platform == "any-llm", any_llm_key=any_llm_key,
        )
        return await run_council(combined_prompt, resolved, timeout=timeout)

    result = asyncio.run(_run())

    # Separate successful and failed reviews.
    all_reviews = result.get("reviews", [])
    successful = [r for r in all_reviews if r.get("success")]
    failed = [r for r in all_reviews if not r.get("success")]

    # Build final output.
    output: dict[str, Any] = {
        "reviews": successful,
        "files_reviewed": files_to_review,
        "providers_used": [p["provider"] for p in providers],
    }

    if failed:
        output["failed_reviews"] = failed

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
