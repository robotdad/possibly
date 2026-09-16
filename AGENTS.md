# Working with Possibly

Possibly is a library-first Amplifier Smart Tool for exploring app experiences before
implementation. Read the human overview in `README.md`. Treat `possibly --help`
(or `uv run possibly --help` in this checkout) as the current tool-owned caller skill.

## Using the tool for a person

1. Read the installed help, then `<capability> --help` for exact signatures. Do not
   invent CLI flags or use private database writes as an integration API.
2. Check `provider-settings`. Generation requires explicitly authorized environment
   access (`--model-env` or `AmplifierIntelligence(allow_environment=True)`). Native
   credentials and provider-owned OAuth caches stay outside exploration records.
   `test-provider` spends one small request; model discovery does not generate a design.
3. Preserve the person's requirements. Propose distinct task questions and organizing
   objects, not cosmetic variants or separate feature slices masquerading as products.
   Use domain-specific lenses with `plan-exploration` when helpful. Provider diversity
   complements task diversity; it does not guarantee it. Label inferred choices.
4. Start with an explicit retained-state directory, request ID, bounded grant and
   presentation choice. Use `owned_runner` for asynchronous CLI/dashboard work;
   use the public library for embedding. Service permission and opening a browser
   are separate choices. Keep the authenticated loopback viewer URL private.
5. Retain exploration, operation and revision IDs. Poll `wait-operation` or read
   changes/diagnostics; do not resubmit `start` to check progress. Successful fan-out
   can be partial. Inspect worker statuses and keep completed alternatives useful.
6. Before acting on a conversational follow-up, call `review-snapshot`: the person
   may have submitted feedback or left an unsent draft. Drafts provide context, not
   automatic generation authority. The dashboard does not trigger the caller.
7. Ask the person to choose unless they already delegated selection. Record the exact
   revision. Make it interactive or refine with explicit authority and a bounded
   grant. Preserve central behavior, test inherited flows, and prefer small patches.
8. Review task semantics as well as appearance: scope, numeric consistency, useful
   state changes, responsive layouts, theme contrast, and honestly labeled mocks.
9. Export the exact reviewed interactive revision. Carry its JSON handoff into the
   production build without silently rewriting the person's plans or architecture.
   Finish/stop and verify cleanup; closing a tab does not stop the runner.

Use new request IDs for new intent; reuse the same ID only for an exact retry.
Deterministic reads, decisions, export and cleanup must not call a model.
`finalize-operation` publishes only complete retained evidence; it is not a model
repair call and cannot invent missing checks. Recovery that may spend tokens needs
an explicit fresh grant. See `src/possibly/docs/caller-guide.md` and `providers.md`.

## Develop from this checkout

```sh
uv sync --extra dev --extra openai --extra anthropic
uv run playwright install chromium
uv run possibly --help
uv run pytest -q
uv run ruff check src tests examples
uv run ruff format --check src tests examples
```

Python 3.12+ is required. `uv.lock` pins the environment; Amplifier Agent is pinned
in `pyproject.toml`. Review compatibility deliberately when changing that dependency.
Do not run live examples as ordinary unit tests: they use real provider credentials
and spend tokens. Tests use isolated providers; Chromium is needed for browser tests.

For integration changes, `uv run python examples/performance_probe.py` exercises the
real Agent loop with a scripted provider, screenshot review and terminal submission.
It makes no model request but may prepare/download runtime modules on its first run.
Run the current conformance kit from `microsoft/amplifier-smart-tools` against this
repository (`python <spec-checkout>/conformance/run.py <possibly-checkout>`). The
root `smart-tool.json` points at `.venv/bin/possibly`, so sync this checkout first.
Conformance checks packaging/help; they do not certify model output quality.

When live evaluation is authorized, use a fresh store and a bounded trial. Examples
include `provider_smoke.py`, `diversity_trial.py`, `diversity_continue.py` and
`diversity_verify.py`. Read each script first: some assume earlier retained trial
artifacts. Compare task diversity, scope and correctness separately from visual
quality and latency. Record failures as well as successes. Close every trial runner.

## Code map and boundaries

| Area | Responsibility |
|---|---|
| `src/possibly/lib.py`, `models.py` | Public operations, grants, lifecycle, revisions and idempotent receipts |
| `store.py`, `checkpoints.py` | Durable state, evidence and deterministic recovery |
| `intelligence.py`, `runtime.py` | Embedded Agent, narrow candidate tools, bounded calls and visual review |
| `fanout.py`, `fanout_worker.py` | Process-isolated candidates under shared budgets |
| `providers.py` | Environment/runtime configuration, model discovery, provider-owned authentication |
| `artifacts.py` | Self-contained HTML, isolation and offline browser inspection |
| `runner.py`, `dashboard.html` | Owned execution and authenticated local review UI |
| `cli.py`, `help.py`, `SMART_TOOL.md` | Thin JSON CLI and library-owned help/skill |

Keep every externally useful capability available through the library. CLI and
browser adapters must not own exclusive business logic. The internal designer gets
artifact write/read/patch/inspect/submit tools, not shell, host filesystem or delegation.
Keep prototypes sandboxed and offline; never put provider keys or viewer tokens in
page content. Asset validation must distinguish actual CSS references from JavaScript.
Gallery thumbnails are host-generated bytes, not base64 authored by a model.

Preserve atomic receipts, immutable revision bytes, epoch-based stale-result fences,
finite grants, cancellation and cleanup. Fan-out must not multiply the grant; queued
workers share its deadline. Agent runtime has process-global state, so independent
model workers use processes rather than sharing one threaded engine. An implicit
provider default must not override the selected revision's provenance during refinement.

## Change and review workflow

- Read the relevant draft contracts in `contracts/` and implementation notes before
  changing public behavior. Explain any contract/implementation discrepancy.
- Keep changes scoped; preserve unrelated working-tree edits. Do not commit generated
  stores, screenshots from private trials, credentials, caches or local viewer URLs.
  `examples/generated/` is ignored. Deliberately published README artwork belongs in
  `docs/images/` with its prompt/provenance notes.
- Update `SMART_TOOL.md`, public capability help, and caller/provider docs in the same
  change as API behavior. The small `skills/possibly/SKILL.md` delegates to live help;
  avoid a second drifting copy of the API. Keep README focused on humans getting started.
- Run checks appropriate to the change. For behavior changes, cover meaningful failure
  paths and invariants. For UI changes, inspect the rendered result and verify feedback,
  selection, preview isolation and export still work.
- Report what changed, validation, live-test costs/limits when known, and remaining gaps.
  Publish commits or PRs when requested. Catalog contributions add only
  `tools/possibly/source.json`; the catalog owns generated manifest/provenance snapshots.
