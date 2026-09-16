# Providers and settings

Possibly uses Amplifier Agent v0.17.0's provider catalog and module mounting. The
current catalog includes OpenAI, Anthropic, Azure OpenAI, Gemini, GitHub Copilot,
ChatGPT subscription OAuth, Ollama, Chat Completions compatible endpoints, and vLLM.
Provider modules own their model defaults and authentication behavior. Possibly
never silently falls back to another provider.

## Installation

The standard Possibly installation supports every provider listed above. No
provider-specific install extras are required: OpenAI, Anthropic, and Google GenAI
SDKs are installed as normal package dependencies. Runtime provider loading must
not be relied on to install missing SDKs. Amplifier may still download provider
modules on first use; allow network access and additional setup time. Credentials or
OAuth authorization are still required for the selected service.

If upgrading an older installation that lacks the SDKs, run
`uv tool upgrade possibly` before retrying.

Installation regression check (2026-09-16): installed the package without extras
into a fresh isolated uv tool environment, imported all three SDKs, and mounted
OpenAI, Anthropic, and Gemini with fresh Amplifier caches and dummy credentials.
No model requests were made; this verifies installation and mounting, not service
authorization or generation quality.

## Environment configuration

| Variable | Meaning |
|---|---|
| `POSSIBLY_PROVIDER` | Provider name; defaults to `openai` |
| `POSSIBLY_MODEL` | Model ID; omit to use the provider default |
| `POSSIBLY_REASONING_EFFORT` | Provider-supported reasoning effort; omit for its default |
| `POSSIBLY_PROVIDER_CONFIG` | Non-secret provider options as a JSON object, e.g. `{"temperature":0.2}` |

Explicit library/CLI options override environment defaults. `--provider`, `--model`,
and `--reasoning-effort` precede the capability. Native credentials remain native:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, etc. `provider-settings`
reports the accepted credential names and setup guidance without revealing values.
For API keys, Possibly requires environment credentials rather than reading saved
Agent API-key settings. Provider-owned OAuth caches and runtime/module caches are allowed.
No Possibly settings or credential file is written.

```sh
possibly provider-settings
possibly --model-env --provider openai test-provider
possibly --model-env --provider gemini test-provider --input '{"timeout_seconds":60}'
```

These commands do not need a store. A connection test sends one small request through
the same provider mount used by generation, with a 64-token output allowance and a
1–120 second overall timeout (default 60). Providers may internally retry. Results
report resolved model, startup/request time, and numeric usage when available. No
design generation or browser review occurs. A successful connection does not prove
that every model supports the image and tool capabilities Possibly needs.

OpenAI-compatible services can use `chat-completions` with
`CHAT_COMPLETIONS_BASE_URL`, optional `CHAT_COMPLETIONS_API_KEY`, and a chosen model.
vLLM uses `VLLM_BASE_URL` and optional `VLLM_API_KEY`. Ollama accepts `OLLAMA_HOST`
or `OLLAMA_BASE_URL`. These endpoints may instead be supplied as non-secret `base_url`
or `host` provider options. Azure needs its API key, endpoint and deployment/model.
Arbitrary provider configuration is passed through; unsupported values are rejected
by the provider during mounting or testing. Secret fields/headers are refused in
provider options; use native credential variables.

## Login

```sh
possibly --model-env provider-login --input '{"provider":"openai-chatgpt"}'
possibly --model-env provider-login --input '{"provider":"github-copilot"}'
```

ChatGPT login shows the provider's device verification URL and code. The user must
complete authorization. The provider stores and refreshes tokens in Agent's OAuth
cache. Possibly disables automatic interactive login while generating/testing;
expired tokens are refreshed through the provider, and failed refresh requires an
explicit login. Login has a bounded timeout (default 300 seconds, maximum 600).

Copilot first tries the existing GitHub CLI login. If absent, it runs `gh auth login
--hostname github.com --web` and relays device instructions. GitHub CLI owns its cache;
Possibly imports the resulting token only into its running process. For subsequent
CLI processes, use `export GH_TOKEN="$(gh auth token)"` before launching Possibly.
An account with Copilot access is required. The provider's environment priority is
`COPILOT_AGENT_TOKEN`, `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, then `GITHUB_TOKEN`.
Possibly does not log in automatically or change the active provider after login.

## Dashboard and library

The gear icon opens settings in an active builtin dashboard. Choose a provider,
model and reasoning effort; optionally enter non-secret provider JSON. Apply affects
subsequent operations in that runner only. Blank advanced options preserve the current
provider's options; `{}` clears them. Switching providers clears old options and model.
The browser receives option names, not their values or credential material. Settings
are neither stored in SQLite nor browser storage. The appearance icon cycles system,
light and dark; only that appearance preference is kept in browser storage.

Test connection and Sign in / setup run as background jobs so the dashboard stays
responsive. Device instructions and results are available only through the authenticated
local dashboard. Busy generation rejects settings changes/tests/login. Closing the
dialog does not cancel an ongoing login; it expires at its timeout or runner exit.
The CLI settings/setup commands work before any exploration exists.

`Possibly.provider_settings`, `configure_provider`, `test_provider` and `provider_login`
expose the same functions to library callers. Bind `AmplifierIntelligence` with
`allow_environment=True` to authorize model requests/login. `provider_login` accepts
an optional `on_progress(text)` callback for a host UI. Process-only overrides are
forwarded in the child environment when an owned runner starts. A CLI invocation of
`configure-provider` ends immediately, so its override also ends immediately; use
environment variables to configure subsequent invocations. Dashboard changes do not
modify a separate CLI caller's environment.

## Validation (2026-09-15)

The environment-configured providers passed live connection tests:

| Provider | Provider default model | Warm total | Model request |
|---|---|---:|---:|
| OpenAI | gpt-5.6-sol | 3.48 s | 2.32 s |
| Anthropic | claude-sonnet-5 | 2.92 s | 0.90 s |
| Gemini | gemini-3.7-flash | 2.61 s | 1.49 s |

A first OpenAI test including cold setup took 51.6 s. Gemini reported both native key
names present and selected GOOGLE_API_KEY. These are observations, not fixed model
choices or latency guarantees. Each also passed a live Agent integration smoke check:
inspect an existing artifact, click and assert the score, receive its screenshot,
then submit immediately (two provider calls each): OpenAI 6.07 s, Anthropic 6.67 s, Gemini 4.26 s. Run `examples/provider_smoke.py`
explicitly to repeat; it consumes provider tokens.

ChatGPT and Copilot had no environment credential/OAuth configuration for a live test.
Their login/progress and OAuth refresh paths are covered with isolated tests; actual
account authorization and subscription access remain unverified. Other unconfigured
providers were not contacted.

## Models and diverse batches

`possibly --model-env provider-models --input '{"provider":"openai"}'` reads
model IDs through Amplifier's provider. It makes no generation request and never
starts an interactive login. Catalog results may include models unsuitable for
image/tool use, or models the account cannot invoke; use `test-provider` and a
bounded artifact trial. Dashboard **Discover models** populates model suggestions.

Use `plan-exploration` and `start.exploration_plan` for 2–3 provider/model/lens
combinations. This is explicit multi-model exploration, not fallback routing.
The provider default remains OpenAI for ordinary operations. Automatic batch plans
use configured providers and upstream defaults; specific model IDs should be pinned
by callers when reproducibility matters. Model settings are not written to a user
configuration file. Non-secret model provenance and the authorized batch plan are
retained as part of the exploration's reproducibility record.
