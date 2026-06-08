"""Generate star-chamber provider config from reference file.

Two modes derive from a single direct-keys reference (providers.json):

- ``--direct``  Per-provider API keys via ``${ENV_VAR}`` references (the
                reference as-is). Non-OpenAI providers need their SDK at run
                time (``uvx --with anthropic --with google-genai ...``).
- ``--otari``   Route every provider through an Otari gateway: strip per-provider
                keys, add a top-level ``otari`` block resolved from
                ``OTARI_API_BASE``/``OTARI_API_KEY``, and prefix each model with
                its provider label (``openai:gpt-4o``) per Otari's naming
                convention.

NOTE: the ``provider:model`` prefix follows Otari's documented convention; verify
it against your gateway's docs if a provider rejects the model name.
"""

import argparse
import json
import pathlib
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate star-chamber config.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--otari", action="store_true", help="Otari gateway mode (routes all providers through Otari).")
    group.add_argument("--direct", action="store_true", help="Direct keys mode (per-provider API keys).")
    args = parser.parse_args()

    ref_path = pathlib.Path(__file__).parent / "providers.json"
    if not ref_path.exists():
        print(f"Reference file not found: {ref_path}", file=sys.stderr)
        sys.exit(1)

    try:
        ref = json.loads(ref_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in reference file {ref_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.otari:
        ref["providers"] = [
            {
                **{k: v for k, v in p.items() if k != "api_key"},
                "model": f"{p['provider']}:{p['model']}",
            }
            for p in ref["providers"]
        ]
        # Resolved from OTARI_API_BASE/OTARI_API_KEY at runtime; omit either to
        # fall back to the environment, or set OTARI_PLATFORM_TOKEN for a hosted
        # platform that uses Bearer-token auth.
        ref["otari"] = {"api_base": "${OTARI_API_BASE}", "api_key": "${OTARI_API_KEY}"}

    dest = pathlib.Path.home() / ".config" / "star-chamber" / "providers.json"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(ref, indent=2) + "\n")
    except OSError as exc:
        print(f"Failed to write config to {dest}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
