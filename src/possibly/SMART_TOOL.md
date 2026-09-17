---
smart_tool_format: 1
name: possibly
version: 0.1.0
description: Explore visual alternatives for an app, choose an experience, and refine a standalone prototype before production development.
use_cases:
  - Compare meaningful task flows before committing to an app design
  - Refine a selected experience while preserving deliberate choices
  - Hand a self-contained interactive prototype and decision record to a development agent
platforms:
  - macos
requires:
  - name: model-provider
    purpose: Generation runs through embedded Amplifier Agent and requires explicitly authorized provider credentials. Deterministic state and help operations work without them.
    optional: true
    install: docs/caller-guide.md
  - name: chromium
    purpose: Model-backed artifact review uses an offline Chromium browser. State and help operations do not need it.
    optional: true
    install: docs/caller-guide.md
---
# Possibly

Choose before you build. Reach for Possibly when someone has an app idea and needs
useful visual alternatives before investing in implementation. It produces a bounded,
mocked prototype; it does not build a production backend or edit caller-owned plans.

The library is the tool: `possibly.Possibly` exposes every operation. The CLI is a
thin JSON adapter. Compose capabilities using library values where possible.

## Install and prerequisites

Install the CLI without a checkout with `uv tool install --python 3.12 'possibly @ git+https://github.com/robotdad/possibly'`.
Install its browser with `uv tool run --from 'possibly @ git+https://github.com/robotdad/possibly' playwright install chromium`.
Run `possibly --help` from any working directory. If needed, run `uv tool update-shell` and open a new terminal.
The standard install includes the OpenAI, Anthropic, and Google GenAI SDKs. Do not rely on runtime provider loading to install missing SDKs. Amplifier may still download provider modules on first use, requiring network access.
For development in a checkout, run `uv sync --extra dev`, then `uv run playwright install chromium`.
Generation embeds Amplifier Agent v0.17.0 in-process;
there is no Possibly-owned model credential store. `--model-env` explicitly opts into
environment credentials, e.g. ANTHROPIC_API_KEY or OPENAI_API_KEY. Pass `--provider`
and optionally `--model` / `--reasoning-effort` to choose them. OpenAI is the default;
`POSSIBLY_PROVIDER`, `POSSIBLY_MODEL`, `POSSIBLY_REASONING_EFFORT`, and non-secret JSON
`POSSIBLY_PROVIDER_CONFIG` supply environment defaults. No model is loaded for help or state reads.

Run `possibly provider-settings` for redacted configuration and supported providers.
`possibly --model-env test-provider` sends one small connection test. `provider-login`
helps with ChatGPT device OAuth or GitHub CLI/Copilot setup. These need no store.
The dashboard gear opens process-only provider settings, connection tests and login help.
No settings file is saved; provider-owned OAuth caches are allowed.
See [provider setup and examples](docs/providers.md).

## Caller round trip

Global host options precede the capability. Capability arguments are a JSON object
matching its library signature. `--input @file.json` reads a file; `--input -` reads
stdin. Closed stdin fails immediately. Request IDs identify submissions, not operations.

1. Run `possibly capabilities`, then `possibly start --help`.
2. Create an input JSON file with context, request_id, grant, and presentation:

```json
{
  "context": "A community garden needs to coordinate watering shifts.",
  "request_id": "garden-explore-1",
  "grant": {"actions": ["explore"], "max_turns": 4, "timeout_seconds": 300,
            "max_tool_calls": 20, "prototype_after_selection": true},
  "presentation": {"mode": "builtin", "service": true, "open_viewer": false}
}
```

3. Run `possibly --store /absolute/state/path --model-env --provider anthropic --execution owned_runner start --input @request.json`.
4. Retain the exploration/operation IDs. Use `get-operation`, `wait-operation`, or
   `read-changes` with `--store` and JSON identifiers. The builtin dashboard URL appears
   in `get-exploration` when material or a question becomes available. Open it only
   with host/user permission; keep its access URL private.
Before responding to a conversational follow-up, call `review-snapshot` to read saved
view/revision context, submitted feedback, and unsent drafts with their save times.
Treat drafts as context, not generation authorization. Use `save-review-state` for
custom host UIs. Overall feedback can target `revision_id: null`.

5. Questions are durable. Ask the person, then call `answer` with exploration_id,
   operation_id, question_id, text, and a new request_id. This continues the same operation.
6. Select the exact revision through the dashboard or `record-decision`. A granted
   one-use continuation queues a prototype automatically. Without one, call
   `make-interactive` with an explicit grant. Dashboard feedback records a proposed
   refinement; the caller chooses the base and authorizes `refine`.
7. Call `export` with the exact interactive revision and `--output-dir /chosen/new/path`.
   HTML opens offline; handoff.json carries the intent, choices, mocks and assumptions.
8. Call `finish` with the revision and expected_state_version, or `stop` to interrupt.
   Check cleanup status. Export alone leaves the exploration open.
9. `reopen` explicitly chooses a retained base and grants no spending. Follow it with
   a newly authorized `refine`. Old viewer submissions cannot write into the new period.

For host UI/headless use, choose that presentation mode. Default execution is in_process:
the invocation runs until output/question/failure, and no worker survives CLI exit.
`run-operation` explicitly drives queued work when no runner exists. Waiting never drives it.

## Performance and recovery

Before retrying failed generation, read `operation-diagnostics`. If completed validation
was retained, call `finalize-operation`: it is deterministic and requires no model.
It refuses incomplete or stale checkpoints and identifies missing evidence. Do not call
`refine` merely to reproduce an already-generated artifact. Refinement is explicitly
new model work. Old HTML-only partials cannot be silently promoted to completed work.

## Sharp edges

- Supply actual context and material contents. References are resolved by the caller;
  Possibly never assumes access to unsupplied conversations, URLs, or shared files.
- Same caller + request_id + payload returns the original receipt. Changed payload
  conflicts. Replayed receipts do not restart work. Receipts/history are retained for
  the lifetime of this store; no deletion or history expiry is implemented.
- A receipt is acceptance, not completion. Inspect operation state. A successful
  generation is also not a human-approved design.
- Generated previews run in sandboxed frames. Clicking a mockup does not record choices.
- An interrupted provider call may have consumed tokens. Recovery is explicit and
  requires a fresh grant; it cannot guarantee exactly-once provider spending.
- max_turns bounds engine submissions; timeout_seconds bounds cumulative running time;
  max_tool_calls bounds tool executions per submission. These are not dollar/token caps.
- This first release supports local single-host stores. Do not expose its loopback
  dashboard to a network or share a store between unrelated trust domains.
- Visual quality and preservation require human evaluation. Mechanical checks do not
  establish that alternatives are useful or that the handoff preserves the experience.

See `docs/caller-guide.md` for library usage and execution limitations.

## Task-diverse exploration across models

The goal is to reveal different ways to accomplish the same job, not three colors
or three incomplete feature slices. Before generating, propose distinct user
questions, organizing objects, first actions and completion conditions. Keep the
original requirements shared. Label new workflow ideas as hypotheses.

`plan-exploration` resolves a bounded plan without model calls. Pass its complete
result as `start.exploration_plan`, or use `"exploration_plan": "auto"`. Automatic
planning uses up to three configured providers (OpenAI, Gemini, Anthropic first),
cycling providers when necessary; it uses provider defaults, not a quality ranking.
It does not authenticate providers or silently fall back after a failure.
For better task diversity supply domain-specific lenses:

```json
{
  "concurrency": 2,
  "candidates": [
    {"provider": "openai", "model": "YOUR_DISCOVERED_MODEL",
     "lens": {"id": "session", "question": "What did I play tonight?",
              "instruction": "Organize around a venue session with rapid score confirmation."}},
    {"provider": "gemini", "model": "YOUR_DISCOVERED_MODEL",
     "lens": {"id": "mastery", "question": "Which personal best could I beat next?",
              "instruction": "Organize around goals and attempts; retain the same machine and score logging scope."}}
  ]
}
```

Use `possibly --model-env provider-models --input '{"provider":"github-copilot"}'`
to discover model IDs from a provider. A catalog entry is not proof of account
access or tool/vision compatibility; test the chosen model. A single Copilot
provider can populate all candidate slots with distinct model IDs and lenses.
Provider settings in the dashboard also offer model discovery.

Fan-out runs 2–3 isolated Agent worker processes with concurrency 1–3. The grant's
wall-clock timeout covers the **whole batch including queued work**. Model/tool
call allowances are divided across candidates; at least two model calls and three
tool calls per candidate are required. For three candidates, a reasonable starting
experiment is 18 model calls, 30 tool calls, and 240 seconds. These are ceilings,
not an expected wait or a performance guarantee. There are no silent retries or
unbounded reviewer loops. Narrow/refine a selected concept rather than regenerating
the batch to change its styling.

The builtin dashboard appears immediately for planned exploration. Completed
candidates become available as they finish. `candidate_ready` events and
`operation-diagnostics` expose progress; a successful operation can have
`result.partial: true` when only some workers complete. Inspect candidate statuses
and failures. A brief correction during generation changes the design epoch; later work
is retained as superseded. Selection alone does not invalidate other alternatives.
Do not replay `start` to recover failed workers. A batch with zero completions
fails; completed alternatives remain retained. `finalize-operation` handles normal
single-operation checkpoints, not incomplete fan-out worker submissions.

Each concept carries `task_model` (six fields), actual provider/model provenance,
call counts/usage, and a host-generated embedded thumbnail. Its central interaction
must pass an offline assertion and receive model visual review before publication.
These checks do not prove full feature coverage or product quality. Review task
semantics, scope, numeric consistency, and mobile/dark presentation yourself.

The gallery uses static images; choose up to two **Compare live** slots to load
sandboxed interactive previews. Clear comparison to unload them. Each can expand
for full-size multi-screen navigation. Selection opens its own refinement workspace;
**Focus prototype** collapses the feedback margin. New batch results do not reset
an active comparison. The caller should still retrieve `review-snapshot` before
acting on conversational feedback. Export remains the exact selected HTML plus
handoff, with embedded assets and no model call. Refinements follow the selected
concept's provider/model unless the caller explicitly overrides the provider.

Concept thumbnails open a large interactive preview without recording a selection.
Previews retain the captured viewport and color scheme, with fit-to-panel or actual-size
viewing. Mark two concepts and open the separate side-by-side comparison to compare;
choose a direction only when ready to create its refinement workspace. Overall
feedback is separate from feedback on a specific concept.

## Embed the review experience

The built-in dashboard uses a shared A2UI v0.9.1 review presenter. Use `review-catalog`
(no store/provider) to discover its component schemas, `review-surface` to obtain a
replayable description, and `review-action` to route review input through the library.
The shipped browser renderer accepts injected host IO callbacks; it needs no CDN or
Node runtime. See [shared review workspace integration](docs/caller-guide.md#shared-a2ui-review-workspace).
Generated prototypes remain self-contained HTML in isolated previews. A host must
support the custom preview component, keep provider/viewer credentials outside the
surface, and own its execution and notification policies. Rendering a surface costs
no model calls. Answering an existing question may continue its authorized operation.

Embedded hosts can request `review_surface(..., profile="comparison")` for a
comparison-first review with local shortlisting and an `onDiscuss` callback. The
default `workspace` profile retains dashboard feedback. Both use the same library
decisions and exact HTML exports. A typed npm renderer artifact can be built from
`web/`; hosts pin its integrity with the compatible library commit.
