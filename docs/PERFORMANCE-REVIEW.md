# Performance and provider integration review

Reviewed 2026-09-15. Read-only investigation of the implementation and retained trial records; no new model trial. Runtime changes are not part of this review.

## Observed results

| Trial | Outcome | Model operation wall time |
|---|---|---:|
| Household alternatives, three ~5 KB artifacts | Succeeded | 184.9 s |
| Initial pinball exploration | Timeout | 300.0 s |
| Pinball exploration retry, three ~5–6 KB artifacts | Succeeded | 140.7 s |
| Integrated multi-screen pinball exploration | Timeout | 600.1 s |
| One working machine-hub refinement, 26 KB | Succeeded | 216.2 s |
| Flip Log visual refinement | Timeout | 600.0 s |
| Flip Log finalization attempt, 17 KB | Submitted, but functionality regressed | 125.3 s |

Source: operation seconds_used in examples/generated/*/state/possibly.sqlite3. These are whole-operation timings, not individual model-call times. Provider read errors/retries appeared in runner logs, but logs do not reliably attribute their duration to a phase. There is no basis for blaming a specific model or assigning percentages of latency yet.

## Findings, in priority order

1. **Small edits require full model output.** CandidateTools exposes write_candidate with an entire HTML string, no patch/reuse operation. The base HTML is in the prompt; even validation-only recovery asks the model to reproduce it. Larger multi-screen artifacts magnify output cost and regression risk. Seed the base deterministically; provide bounded exact-match edits with content hashes, plus explicit unchanged reuse.
2. **Visual review forces another agent execution.** inspect_candidate returns text but withholds screenshot image blocks. After the first session.execute finishes, the host injects screenshots and runs up to three further executions when HTML changes. Each execution can itself contain multiple model/tool rounds. submit_result only stores a result; it does not stop the agent loop. Feed images through the supported tool/event path, or make one explicit, bounded review phase with completion semantics. Verify the Agent API before choosing the integration.
3. **No recoverable validation checkpoint.** Candidate HTML, review evidence, and structured submission live in memory/temporary storage. Failure retains at most three HTML files, discarding review evidence and assigning partials a new direction ID. Persist versioned artifact hashes, structured metadata, validated interaction assertions, and visual-review status atomically. A deterministic finalize function should publish only if all required evidence is already valid; otherwise return exact missing checks or repairs. It cannot reconstruct a missing semantic judgment automatically.
4. **Checks do not protect the central task.** Any nonempty click/fill sequence without a JS error counts as verified interaction. There are no visible-result assertions. A theme toggle or Add toast can pass while score entry disappears. Add named, reusable central-flow assertions; preserve them across style-only changes. Reject missing functionality before expensive visual iteration.
5. **Instrumentation is insufficient.** Hooks are cleared, engine reply usage is discarded, and only whole-operation seconds are retained. Measure preparation, provider mount, each model request/retry, artifact writing, browser inspection, visual review and finalization. Retain model IDs, token/cache usage, call counts, artifact bytes/hashes and retry summaries, never credentials. Agent main's integration docs describe usage on submit_turn; verify aggregation for our custom handler and pinned version before relying on it.
6. **Repeated secondary work.** Each browser inspection launches Chromium and rebuilds context; every refinement starts a fresh engine/session. Inspection results return up to 16 KB of page text and cumulatively repeat prior interaction text. Reuse a browser per operation with isolated/reset contexts, return compact deltas, cache unchanged-artifact checks. Measure before optimizing bundle/engine startup; preparation already uses a cache.
7. **Limits hide internal work.** max_turns counts outer run_operation executions, not every provider request or visual-review pass. Add explicit call/review/retry budgets with stage progress. Raising wall-clock limits concealed overhead rather than fixing it.
8. **Exploration scope grew substantially.** Three navigable full-fidelity concepts involve more work than three compact storyboards. Keep full-size, navigable previews but bound representative screens; don't implement three complete apps during comparison. Preserve the requested fidelity rather than reverting to tiny mocks.

## Recommended implementation order

1. Add stage/usage diagnostics and durable checkpoints together.
2. Add deterministic reuse/finalize plus exact edits against seeded base artifacts.
3. Replace post-hoc repeated review with one bounded image-aware review path.
4. Add central-flow assertions and preserve them across refinements.
5. Benchmark unchanged finalization, a theme-only patch, one interaction repair, and initial comparison with fixed provider/model/effort. Separate cold startup from warm execution; compare behavior as well as elapsed time.
6. Then complete provider configuration and dashboard settings. Do not launch more open-ended design trials to measure performance.

## Provider configuration: follow Amplifier Agent

Possibly pins amplifier-agent v0.12.0, commit 421379ad1f4aa8344ee97206ad10c136fb2391e2. The installed helper catalog lists anthropic, openai, azure-openai, ollama, github-copilot. Current upstream main documents nine providers, adding openai-chatgpt, chat-completions, gemini and vllm. Possibly's separate preflight incorrectly accepts Gemini despite its pinned helper not listing it, excludes ChatGPT, and restricts Copilot to GITHUB_TOKEN despite the provider supporting a richer token chain.

Authoritative integration guidance:
- https://github.com/microsoft/amplifier-agent/blob/main/docs/INTEGRATION.md
- https://github.com/microsoft/amplifier-agent/blob/main/docs/spec/providers-and-models.md
- https://github.com/microsoft/amplifier-agent/blob/main/docs/CONFIGURATION.md

Use Agent's provider catalog/mount contracts and provider-owned config, not another hard-coded credential registry. Upgrade to a verified release supporting required providers, or explicitly mount supported modules through the existing library API. Main documentation must not be assumed to describe v0.12.0.

Proposed Possibly environment interface (not implemented): POSSIBLY_PROVIDER (default openai), POSSIBLY_MODEL, POSSIBLY_REASONING_EFFORT, and an optional JSON POSSIBLY_PROVIDER_CONFIG for provider-specific non-secret settings. Provider-native credential environment variables remain native. Per-call library overrides take precedence. Assemble configuration in memory and pass it to Agent injection; don't write a settings file or silently choose another provider when OpenAI credentials are missing. Audit Agent's credential-file fallback if strict env-only behavior is required.

Copilot supports COPILOT_AGENT_TOKEN, COPILOT_GITHUB_TOKEN, GH_TOKEN, GITHUB_TOKEN in that order according to its installed README. ChatGPT is distinct from OpenAI API auth: the installed provider uses OAuth/device login and persists/refreshes a token file. No native env-only token interface is documented. Supporting ChatGPT while prohibiting all credential disk storage requires a provider credential-store extension; simply renaming an API-key variable is not sufficient. Disable interactive login inside background operations and report setup requirements clearly.

Dashboard settings can show redacted effective configuration, supported providers/models and credential presence. Environment defaults are host-controlled; browser changes can be explicitly session-only in-memory overrides. A local configuration check must be deterministic. A separate user-triggered connection test can make a minimal bounded provider call and report latency and resolved model. No secrets in browser snapshots, logs or SQLite. Theme control should use accessible sun/moon/system icon buttons/menu, not the current large appearance dropdown. These changes are planned, not implemented by this review.

## Implemented follow-up

Completed the first performance pass: persistent per-operation checkpoints, deterministic
`finalize_operation`, exact-match patching of preloaded base artifacts, reusable browser
process with inspection caching, screenshot delivery on the next provider request,
terminal submission, asserted outcomes with inherited regression flows, per-submission
model-call budgets, and sanitized stage/usage diagnostics. Full accumulated browser
review text is omitted from subsequent refinement prompts.

See VALIDATION.md for measured deterministic finalization and the offline real-Engine
probe. Live-model follow-up is now recorded in VALIDATION.md: three concepts completed in 411.66 s, interactive reuse in 25.04 s, style refinements in 145.86 s and 127.51 s. Provider request time dominates; exploration still generates oversized artifacts. Provider configuration, OAuth/Copilot setup, dashboard connection tests and theme-icon UI have since been implemented; see src/possibly/docs/providers.md for configuration and live validation.
