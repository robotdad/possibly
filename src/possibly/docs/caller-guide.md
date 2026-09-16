# Caller guide

```python
from possibly import Possibly, Grant
from possibly.intelligence import AmplifierIntelligence

p = Possibly(
    "/absolute/host-selected/store",
    intelligence=AmplifierIntelligence(provider="anthropic", allow_environment=True),
)
result = p.start("Coordinate watering shifts for a community garden.", request_id="start-1", grant=Grant())
eid = result["receipt"]["exploration_id"]
snapshot = p.get_exploration(eid)
# Present snapshot revisions; read_artifact(eid, rid) supplies HTML.
# Ask the person before recording a selection.
```

All methods return JSON-compatible values. Mutations return `{status: accepted|replayed,
receipt: {...}}`. Foreground model operations additionally return an operation snapshot.
Errors raise `PossiblyError`; `to_dict()` is the CLI error envelope. CLI exits 1 for
operation failures and named rejections, 2 for malformed input. stdout contains only
results; diagnostic output belongs on stderr. Reference-only calls are supported: omit context and supply `materials=[{"name": "Brief", "content": "..."}]`.
Library hosts may instead bind `material_resolver(reference) -> str` and pass declared references
with an optional `required` flag. Required failures reject; optional failures remain visible.
No resolver means no implicit URL/file access.

Use `capabilities()` and capability help
for exact signatures. Library calls are synchronous; async hosts can use a worker thread.

## Model access and browser setup

Provider requests and login require explicit `allow_environment=True` / `--model-env`; settings reads expose presence only.
OpenAI is the default. See [providers and settings](providers.md) for all nine providers, environment variables, process-only overrides, connection tests and OAuth/GitHub login.
Install the corresponding extra. No credential values are serialized into records.
For an installed tool, install Chromium with `uv tool run --from 'possibly @ git+https://github.com/robotdad/possibly' playwright install chromium`.
Developers in a checkout can use `uv run playwright install chromium`.
The generation adapter mounts only write_candidate, patch_candidate, read_candidate, inspect_candidate and submit_result. Chromium
runs with network disabled. It does not receive the store, presenter token or provider keys
in page content. No shell, arbitrary host filesystem tool, or delegation tool is mounted.

## Authority and execution

`Grant.actions` contains explore, make_interactive or refine. Defaults allow four engine
submissions, 300 cumulative running seconds, and twenty internal tool executions per
submission. Questions consume an engine submission; their answers continue the operation.
A grant may expire. Stop/finish invalidates continuation and fences publication.
The first version uses cancellation-aware embedded calls; unexpected process death leaves
an uncertain operation requiring explicit recovery. `resume_operation` requires a fresh
grant, retaining the same operation ID; it does not replay cancelled/succeeded operations.

The owned runner is a local subprocess. It receives the explicitly opted-in environment,
keeps a heartbeat, and polls queued operations. Selecting builtin presentation also requires
service permission. The service starts automatically once material/questions are ready.
`open_viewer` is a separate opt-in. There is no focus-taking operation.

Presentation failures leave artifacts readable through the library. Closing a browser tab
does not stop a runner. Finish/stop and check cleanup. No automatic idle shutdown is promised.

## State and continuity

SQLite commits receipts, decisions, continuation reservations and observations atomically.
Snapshots include a cursor from the same read. Events are retained without expiration;
invalid cursors return history_gap. Immutable revision content is stored in the database.
Supersession and selection are metadata, not destructive edits to content.

Feedback records a reviewed revision and proposes refinement. Applying it requires an
explicit refine request naming the chosen base; this version does not interpret feedback
as implicit permission. Brief correction text is an explicit accepted correction attached
to a new brief revision; all earlier visuals are conservatively superseded. Regeneration
requires a new grant. Reopening retains suspended questions. `reactivate_operation` requires a fresh grant,
current state version and explicit relevance confirmation; it preserves question/operation
identities. Answering then continues that same operation in the new active period.

This release is a local POC. Multi-caller authentication, remote storage, deletion/retention
controls, token/dollar accounting, and recovery from partially completed browser actions
are not implemented. Package conformance and runtime tests do not ratify the draft
experience-quality contracts.

### Review context across chat and dashboard

Before responding to a user continuing an exploration, call `review_snapshot`.
It includes submitted decisions and per-reviewer dashboard views, revision IDs,
draft text, and save timestamps. Drafts are context, never authorization to generate.
The browser autosaves feedback as the user types; text whose save failed or is still
in flight is unavailable. `save_review_state` is also public for custom host UIs;
use a stable reviewer ID and increasing sequence to prevent reordered writes.
Overall submitted feedback uses `record_decision` with `revision_id: null` and
`action: feedback`; it applies across directions. Revision feedback stays scoped.

Concepts and prototypes may contain multiple locally navigable screens within one
self-contained HTML artifact. The dashboard exposes a full-size expanded preview;
local mock navigation is isolated from dashboard selections and decisions.


## Performance and deterministic finalization

`finalize_operation(exploration_id, operation_id, request_id=...)` can finish a failed,
inactive operation with a complete durable checkpoint. It calls neither a provider nor
Chromium. It checks artifact hashes, submitted metadata, successful browser checks,
asserted task outcomes, visual-review delivery and unchanged design intent. Missing
checks produce `checkpoint_incomplete` with explicit `missing` details. No synthesis
or repair is hidden inside finalization. Closed sessions must remain closed; this
operation does not bypass lifecycle fences. Old HTML-only partials lack this evidence.

`operation_diagnostics(exploration_id, operation_id)` reports live stage timings and
provider-boundary call records, model names when exposed, numeric usage, artifact
sizes, and cache hits. It contains no raw prompts or credential values. Provider-internal
HTTP retries are included in call duration, not counted separately. Usage is available
only when the provider returns it; missing usage is not zero consumption.

Refinements preload `base` and support exact-match `patch_candidate` edits guarded by
a SHA-256 hash. Unchanged writes preserve checks; changed bytes invalidate them.
Browser assertions (`assert_text`, `assert_value`, `assert_visible`) verify outcomes;
a click alone is insufficient. Existing asserted flows run again after edits. Assertions
still need to describe the real task: passing a weak assertion is not semantic proof.
A single Chromium process is reused per operation, with isolated contexts per check.
Screenshots enter the next provider request in the same agent execution. Accepted
submission short-circuits further calls. `Grant.max_model_calls` defaults to 12 per
submission; the overall timeout still bounds provider retries.

Checkpoints live in `STORE/operations/OPERATION_ID/TURN/`, alongside sanitized diagnostics.
They are retained with the rest of the exploration. No automatic cleanup/expiry is added.

Concept thumbnails open a large interactive preview without recording a selection.
Previews retain the captured viewport and color scheme, with fit-to-panel or actual-size
viewing. Mark two concepts and open the separate side-by-side comparison to compare;
choose a direction only when ready to create its refinement workspace. Overall
feedback is separate from feedback on a specific concept.
