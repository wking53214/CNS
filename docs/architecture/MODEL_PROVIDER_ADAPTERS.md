# CNS Model Provider Adapters

## Purpose

CNS provides a provider-neutral contract for model requests and responses.
Provider adapters translate that contract into the request and response
formats of individual model providers.

The provider adapter is an implementation of the CNS composition-layer
contract. It is not a governance authority.

## Architecture boundary

The responsibilities are deliberately separated:

- `cns`: stable CNS contract and public data shapes.
- `cns_composition.providers.protocol`: provider-neutral request,
  response, usage, status, and protocol definitions.
- `cns_composition.providers.anthropic`: Anthropic-specific SDK translation.
- STACK components: retain their own policy, governance, authorization,
  orchestration, and operational responsibilities.

CNS does not select providers, route requests, authorize requests, make
policy decisions, govern model behavior, execute tools, or orchestrate
agents.

The provider adapter does not acquire those responsibilities.

## Installing the Anthropic adapter dependency

The base CNS package does not require the Anthropic SDK.

Install the optional dependency when using the Anthropic adapter:

    python -m pip install ".[anthropic]"

The optional dependency is declared in `pyproject.toml` as an extra.
The base project dependency list remains empty.

## API-key configuration

The integrating application supplies credentials to the official Anthropic
SDK client. The SDK reads `ANTHROPIC_API_KEY` from the process environment
when `anthropic.Anthropic()` is constructed without an explicit `api_key`.

For example, the host application can install the optional extra, configure
`ANTHROPIC_API_KEY` through its environment or secret manager, construct the
SDK client, and inject that client into `AnthropicProvider`.

CNS does not retrieve, store, rotate, or manage provider credentials. API keys
must not be committed to source control, written into CNS request records, or
included in logs. The adapter receives an already-configured client and makes
no credential-management decisions.

## Current Anthropic adapter behavior

The adapter:

- Uses the official Anthropic Python SDK.
- Receives an already-created SDK client through dependency injection.
- Translates supported provider-neutral requests into Anthropic Messages API
  calls.
- Normalizes text response blocks, token usage, model identity, stop status,
  and request identifiers.
- Retains the native provider response separately.
- Translates provider exceptions into adapter-level exceptions.
- Does not implement retries; the injected SDK client controls retry behavior.
- Does not load credentials or create a client automatically.

The host controls SDK retry count and timeouts. To request one attempt,
construct the SDK client with `max_retries=0`.

The adapter does not make a live API request merely by being imported.

## Current limitations

The current adapter does not implement:

- Multimodal input or output.
- Tool use.
- Streaming.
- Async requests.
- Provider-specific thinking configuration.
- Stop-sequence arrays.

The generation settings it accepts are `temperature`, `top_p` and `top_k`
(numeric; `top_k` must be an integer). Any other setting is rejected rather than silently
ignored.

> Checked against `cns_composition/providers/anthropic.py` and `pyproject.toml` on 2026-11-07: the optional extra
> pins `anthropic` at 0.116.0 or later and below 1.0, and the base dependency list is empty.

## Security and responsibility boundaries

Credentials and client construction belong to the integrating application.
The adapter receives the client; it does not decide whether a request is
authorized.

Provider-native response objects are retained for callers that need
provider-specific details. The normalized response remains the portable
contract.

A provider response, token count, request identifier, or adapter status is
not an authorization decision or governance approval.

## Testing expectations

Adapter tests should use controlled SDK clients or mocked responses.
Ordinary tests must not require a live API key or make live provider calls.

A live connectivity test is a separate operational check and must be
explicitly initiated by the operator.
