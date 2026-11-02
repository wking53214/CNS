#!/usr/bin/env python3
"""Explicitly authorized, single-request Anthropic/CNS integration test."""

import argparse
import getpass
import sys

try:
    import anthropic
except ImportError:
    print('Anthropic SDK missing. Install with: python3 -m pip install ".[anthropic]"')
    sys.exit(1)

from cns_composition.providers.protocol import ModelRequest
from cns_composition.providers.anthropic import (
    AnthropicProvider,
    AnthropicProviderError,
)

def main():
    parser = argparse.ArgumentParser(
        description="One explicitly authorized Anthropic API request through CNS."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Authorize the interactive one-request test.")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = parser.parse_args()

    expected_response = "CNS CONNECTION VERIFIED"
    request = ModelRequest(
        model=args.model,
        system_instruction="You are participating in a technical integration test.",
        user_messages=(
            f"Reply with exactly this text and nothing else: {expected_response}",
        ),
        max_output_tokens=32,
        generation_settings={},
    )

    if not args.execute:
        print("SAFE MODE: No API request made.")
        print("To authorize one request, run:")
        print("python3 scripts/anthropic_smoke_test.py --execute")
        return 0

    print("\nCNS / ANTHROPIC LIVE SMOKE TEST")
    print("This test sends exactly one short request.")
    print("Automatic SDK retries are disabled.")
    print("The API key will not be saved or displayed.")

    approval = input('\nType SEND ONE REQUEST to continue: ')
    if approval != "SEND ONE REQUEST":
        print("Cancelled. No API request made.")
        return 0

    api_key = getpass.getpass("\nEnter your Anthropic API key (hidden): ")
    if not api_key.strip():
        print("No key supplied. Cancelled.")
        return 1

    client = anthropic.Anthropic(
        api_key=api_key,
        max_retries=0,
        timeout=30.0,
    )
    del api_key

    provider = AnthropicProvider(client)


    print("\nSending one request...")
    try:
        result = provider.generate(request)
    except AnthropicProviderError as error:
        print("\nPROVIDER REQUEST FAILED")
        print("Category:", error.category)
        print("Request ID:", error.request_id or "not supplied")
        print("No automatic retry was attempted.")
        return 2
    except Exception as error:
        print("\nUNEXPECTED LOCAL ERROR")
        print("Error type:", type(error).__name__)
        print("Error details suppressed.")
        return 3

    print("\nREQUEST SUCCEEDED")
    print("Provider:", result.provider)
    print("Returned model:", result.model)
    print("Completion status:", result.completion_status.value)
    print("Request ID:", result.request_id or "not supplied")

    if result.usage:
        print("Input tokens:", result.usage.input_tokens)
        print("Output tokens:", result.usage.output_tokens)
    else:
        print("Token usage: not supplied")

    print("Response:", repr(result.content))
    print("Native response retained:", result.native_response is not None)
    matched = result.content.strip() == expected_response
    print("Expected response matched:", "YES" if matched else "NO")
    print("\nOne-request API smoke test complete.")
    return 0 if matched else 4


if __name__ == "__main__":
    sys.exit(main())
