# Public Interaction API Contract — v1 (DRAFT)

**Who builds against this:** Library callers, CLI and presentation adapter authors,
and implementers of Possibly's operation and retained-state boundaries.

This is the provisional public API contract, not a locked interface or an executable
example. Method names, schemas and mechanisms remain proposals; no reference
implementation or approved executable conformance kit exists.

It elaborates the [Calling Agent Interaction contract](caller-interaction.v1.md)
and [Dashboard Lifecycle contract](dashboard-lifecycle.v1.md), alongside
[Context to Visual Choice](exploration.v1.md) and
[Selected Experience Continuity](selection-continuity.v1.md).
The related behavioral drafts carry the intended interaction requirements.
The concrete schemas, method names, runner modes and recovery mechanisms here
remain provisional elaborations, not amendments to or replacements for those promises.

## 1. What this preserves

- Library-first; the default CLI and presentation adapters use the same capabilities.
- Lightweight intake from supplied context; consequential questions rather than a form.
- Durable decisions distinct from execution permission and notification delivery.
- Bounded preauthorized continuation, without a second human approval.
- Feedback targets what was reviewed; retries do not cause duplicate work.
- Finish now, continue later from retained work; export is not an exploration backup.
- Public exploration state survives internal Agent sessions and internal work items.
- The host owns its conversation, access grants, shared services and presentation.

## 2. Objects and identity

| Object | Meaning |
|---|---|
| Exploration | Durable container for the brief, alternatives, decisions, revisions and operations; same identity when returning later. |
| Operation | One requested piece of work: initial exploration, click-through, refinement, export or lifecycle cleanup. |
| Question | An identified need blocking a particular operation; its answer belongs to that operation. |
| Revision | Immutable snapshot of brief/design/artifact references with explicit parentage and supersession. |
| Direction | A named alternative within an exploration, with its own identified revisions. |
| Receipt | A durable acknowledgement of an accepted mutation, not a claim that model work completed. |
| Observation | An ordered report of an already-recorded change; reading it has no execution effect. |

Use opaque IDs, not caller conversation or internal Agent session IDs. Each operation,
question, receipt and artifact reference carries its exploration identity.
An exploration's `state_version` changes for accepted mutations; it is distinct
from a design `revision_id`. Recording a selection need not rewrite an artifact.

```text
Target = { exploration_id, revision_id, direction_id? }
Mutation = { request_id, expected_state_version? }

MutationResult<T> =
    Accepted { receipt: T }
  | Replayed { receipt: T }
  | Conflict { code, current_state_version, target, resolution_options }
  | Rejected { code, message, required_action? }

OperationReceipt = { receipt_id, exploration_id, operation_id, state_version }
DecisionReceipt = {
  receipt_id, exploration_id, decision_id, target, state_version,
  changes, follow_up: OperationRef | PendingAction | None
}

OperationSnapshot = {
  exploration_id, operation_id, kind, target?,
  state: queued | running | waiting_input | waiting_access | interrupted
       | succeeded | failed | cancelled,
  questions, partial_artifacts, result?, failure?,
  active_period_id, interruption_cause?,
  execution_status: { mode: in_process | host_runner | owned_runner,
                      availability: available | unavailable | recovery_required }
}
Question = {
  question_id, exploration_id, operation_id, target?,
  kind, prompt, why_needed, answer_schema,
  state: pending | answered | superseded | cancelled | suspended,
  predecessor_question_id?
}

CleanupOutcome = {
  exploration_id, operation_id, lifecycle: finished | stopped | cleanup_failed,
  write_fence_active, retained_revision_ids, retained_artifact_ids,
  retained_decision_ids, retained_question_ids,
  released_resources, failed_resources: [{ resource_id, cause, retry_action }]
}
```

`execution_status` distinguishes an available runner from work awaiting one; queued
is never advertised as running. Error/cleanup details are public, private reasoning
is not. A partial artifact is not a successful completed result.

## 3. Explicit host binding, not hidden infrastructure

Proposed construction:

```text
p = Possibly(
  storage = host_selected_durable_store,
  material_resolver = explicitly_scoped_host_resolver?,
  model_access = host_access_handle_or_opted_in_source?,
  execution = host_runner_or_explicit_owned_runner?,
  notifier = optional_host_notification_adapter?
)
```

Construction/import, reads, decision recording and other deterministic operations
must not initialize a model or require model credentials. Binding an opted-in model
source once does not require passing credentials on every operation.

Keep raw credentials, credential-bearing URLs and runtime objects out of exploration
records, internal work items, artifacts and events. Persist nonsecret configuration
references and authorization records; reacquire access from the host when needed.
An answer supplying access is an access handle through an authorized host path, not
secret text saved in a question response.

**A saved operation is not a background worker.** Background execution requires a
declared runner with a lifetime beyond the calling method. It may be host owned
or explicitly authorized and library owned. Without one, the library must use an
explicit in-process execution mode or report execution unavailable, not promise
that a CLI exit leaves work running.

`start()` returns `Rejected(execution_unavailable)` before accepting executable work
if its requested runner mode is unavailable. For in-process mode the host must keep
the library execution context alive; for a bound host/owned runner its declared
lifetime governs. Availability can change after acceptance: snapshots then report
unavailable/recovery_required, not ongoing execution. `wait_operation()` returns
that blocked/interrupted snapshot, an input/access need, a terminal snapshot, or
`WaitTimedOut(last_snapshot)`; none of these outcomes provisions a runner.

Waiting is separate from driving execution. A wait deadline never cancels work or
extends its budget. Losing the process may interrupt an in-process runner; retained
checkpoints allow explicit recovery, not proof that it kept running.

Presentation per exploration:

```text
PresentationPolicy = {
  mode: builtin | host | headless,
  service_scope, viewer_scope, focus_scope
}
ExecutionGrant = {
  allowed_actions, bounded_limits, expires_at?,
  continuation_rules: [
    { trigger: selected, action: make_interactive, maximum_uses: 1 }
  ]
}
```

Exact limit units/enforcement are unresolved, not an unlimited default. No grant
means no model work. A valid grant is still insufficient if model access or the
runner is unavailable. Report the missing requirement.
For builtin presentation, automatic startup/update occurs when authorized material
is presentable. Host/headless modes never require builtin startup. Failure of optional
presentation leaves public artifacts and controls accessible. Starting a service is
not evidence the human saw it. Generated HTML cannot invoke decision controls or
inherit model/host credentials.

## 4. Proposed public surface

Pseudocode: signatures describe semantics, not a selected implementation language.
All mutations take `Mutation`; each returns a typed result, never a hidden prompt.

| Method | Main inputs | Result / effect |
|---|---|---|
| `capabilities()` | None | Versioned capability descriptions, types, model requirements and help; basis for CLI/agent help. |
| `start()` | Supplied context/materials, presentation, execution grant | Exploration and initial operation receipt; return IDs after durable acceptance. |
| `get_exploration()` | Exploration ID | Current state version, revisions, decisions, pending needs, lifecycle and resources. |
| `get_operation()` | Exploration and operation IDs | Current operation snapshot, including result or question. |
| `wait_operation()` | IDs, deadline, desired condition | Snapshot when input/access is needed or terminal; otherwise explicit wait timeout and last snapshot. |
| `read_changes()` | Exploration ID, cursor, page limit | Ordered observations, next cursor and explicit history-gap result. |
| `get_revision()` / `read_artifact()` | Exact target / artifact ID | Revision metadata or authorized content access; no assumed shared path. |
| `record_decision()` | Target, select/reject/feedback/brief-correction payload | Durable decision receipt; optional identified follow-up under existing authority. |
| `answer()` | Exploration, operation, question IDs, typed answer | Accepted/replayed answer receipt or explicit conflict/rejection; continues the same operation if authority/access permit. |
| `refine()` | Exact base target, instruction or accepted feedback ID, grant | New operation, producing descendant revisions without overwriting the base. |
| `export()` | Exact target, HTML-and-handoff request | Export operation; packages existing artifacts deterministically, does not generate missing material implicitly. |
| `finish()` | Exploration ID, chosen revision, expected state version | Cleanup operation; final revision retained, no further ordinary writes after the finish fence. |
| `stop()` | Exploration ID, reason | Interruption and cleanup operation; report partial output and cleanup failures. |
| `reopen()` | Exploration ID, retained base, new authority/presentation | Explicit new active period; no generation until a request or new continuation rule authorizes it. |
| `resume_operation()` | Interrupted operation ID, fresh/revalidated authority | Explicit recovery from an eligible checkpoint in the same operation; does not revive succeeded/cancelled work. |

Questions are available from snapshots even if notification/history delivery fails.
Deletion is a separate future explicit storage-management capability, not overloaded
onto finish/stop. No delete API or retention deadline is selected by this draft.

### Mutation, revision and retry rules

1. Scope request IDs to the authorized caller and store. Same ID and same payload
   returns the original receipt; changed payload with that ID conflicts. Publish
   the retention/dedup horizon before promising retries across arbitrary time.
2. A receipt can reference an operation whose current state has changed. Retrieve
   current state separately; replaying the receipt does not restart the operation.
3. Commit a decision, any continuation reservation and follow-up operation identity
   atomically (or with equivalent recoverable guarantees). Schedule from that record,
   never from event delivery. One-use grants cannot be consumed again by new request IDs.
4. This prevents duplicate logical work; it does not magically make external model
   calls exactly once across crashes. Indeterminate provider outcomes need recovery
   handling before replay/spending; that mechanism is still open.
5. Feedback always retains its reviewed target. If applying it conflicts with newer
   choices, record the feedback and create an identified pending application operation
   with a question. Do not silently change its target or pause an unrelated operation.
6. An invalid/stale answer returns `Conflict` with the actual question state. Seeing
   `answered` in that state is not acknowledgement that this submission was accepted.
7. Structured brief correction records a new brief revision and marks affected work
   superseded immediately. Ambiguous free-text interpretation may need an authorized
   operation/question first; do not claim the corrected brief exists before it does.
8. Publication checks the revision/state against which generation began. A late
   result cannot overwrite a newer accepted correction; retain it as superseded
   or pending conflict resolution, visibly.

### Finish, stop and return

Proposed safety choice: `finish()` conflicts if generation or an unresolved
application operation remains in flight; it does not silently discard it. The caller
can await/resolve it or explicitly choose stop. Waiting for design review alone does
not block an explicit finish. An export-and-finish convenience composes the two:
export failure leaves the exploration open; finish failure leaves the export valid.

Finish/stop establishes a write fence and invalidates old continuation authority.
Cleanup operations distinguish acceptance from terminal cleanup success/failure,
listing retained results and each remaining owned resource. A cleanup failure is
never described as stopped successfully. Retrying cleanup must not regenerate.

Pending questions and their context are retained as suspended at stop; explicitly
rejected needs remain cancelled. Ordinary
decision writes from an old viewer fail visibly. `reopen()` requires an explicit
retained base and creates a new active period, with fresh state version/authority.
It does not revive old viewer write contexts or cancelled questions. Suspended needs
are presented for explicit reactivation under the new authority; a still-pending
question retains its question and operation identities when that operation is
continued. Reactivation must validate relevance and bind the operation to the new
active period before accepting an answer. Cancelled/completed operations are not
reactivated; a new refinement has a new operation identity. Nothing is silently
discarded or executed against the closed period. Reads/export
of retained material do not themselves reopen the exploration.

`resume_operation()` is limited to runner/process interruption within the same
still-active period, with authority revalidated and no finish/stop fence. It rejects
finished/stopped periods and cancelled/succeeded operations. Returning after closure
requires explicit reopen and renewed authority. It may explicitly reactivate
suspended pending work or accept a new refinement operation; public history retains
the earlier work and needs. The reactivation method and state-transition details
remain provisional; `resume_operation()` cannot bypass reopen.
Lifecycle operation terminal snapshots carry `CleanupOutcome` on both success and
failure, not an unstructured success message.

## 5. Worked caller round trip

Illustrative successful path with one delayed question, not executed evidence.
Names below are synthetic identifiers. The host supplies an authorized runner
that remains available across calls; no automatic caller wake is assumed.

```text
1. capabilities()
   -> library operations/help; host learns notification is optional

2. start(context, materials, presentation=host,
         grant=explore + one make_interactive after selection, request_id=A)
   -> Accepted(E1, O1, state_version=1)

3. wait_operation(E1, O1, bounded_deadline)
   -> WaitTimedOut(snapshot=running)
   # Wait ending does not cancel O1. Host runner is still executing.

4. Later: get_operation(E1, O1)
   -> waiting_input, Q1: "Which of these two conflicting task requirements governs?"
   # Durable snapshot is authoritative whether or not a notifier ran.

5. answer(E1, O1, Q1, chosen_requirement, request_id=B)
   -> answer receipt; same O1 becomes runnable
   # Duplicate B returns the same receipt; changed answer with B conflicts.

6. read_changes(E1, cursor=C0)
   -> O1 succeeded; interpreted brief B1; alternatives D1/R1, D2/R2, D3/R3
   # Host UI shows exact targets and comparable visual directions.

7. record_decision(target=E1/D2/R2, select, request_id=C)
   -> DecisionReceipt(target=R2, follow_up=O2)
   # O2 consumes the one authorized make_interactive continuation.
   # Duplicate C returns the same receipt/O2. Event rereads cause no generation.

8. get_operation(E1, O2)
   -> succeeded, interactive revision R4(parent=R2)
   # Exploration stays active for review.

9. refine(target=E1/D2/R4,
          instruction="Keep the layout; simplify navigation",
          grant=one refinement, request_id=D)
   -> O3
   get_operation(E1, O3) -> succeeded, R5(parent=R4)

10. export(target=E1/D2/R5, HTML-and-handoff, request_id=E)
    -> O4; later succeeded with standalone HTML artifact and separate handoff
    # Handoff includes decisions, corrected brief, important changes, mocks,
    # assumptions and preserved intent. It does not edit caller governing docs.

11. finish(E1, chosen_revision=R5, expected_state_version=current, request_id=F)
    -> cleanup operation O5; wait_operation(E1,O5) -> succeeded
    # Retained exploration remains readable. Host UI/service remain host owned.

12. Later: reopen(E1, base=R5, fresh_authority, presentation=host, request_id=G)
    -> new active-period receipt, no generation
    refine(target=E1/D2/R5, new_instruction, new_grant, request_id=H)
    -> O6; eventually R6(parent=R5); R5 remains unchanged
```

If the host notification adapter is supported and authorized, it may signal steps
4, 6 or 8. Saved state, event delivery, waking an agent and reaching a person remain
distinct. An expired event cursor returns `HistoryGap` plus a way to fetch a current
snapshot and restart from a matching cursor; it must not imply complete replay.

## 6. Traceability and unfinished decisions

| Basis | How this draft addresses it |
|---|---|
| Caller contract Core 1–2, 9–10 | Public methods, help, explicit host dependencies, provider-free deterministic paths, adapter parity. |
| Caller Core 3–5 | IDs, target revisions, state versions, receipts, retries, ordered changes, bounded continuation. |
| Caller Core 6–8 | Identified needs and cleanup outcomes, no hidden prompts/internal-session dependencies, no edits to caller governance. |
| Dashboard Core 1–6, 9 | Presentation policy, separate authority, identifiable actions, public activity, prototype isolation. |
| Dashboard Core 7–8 | Cleanup/write fence, retained state, no seizure of host resources. |
| Exploration and continuity contracts | Brief/directions, deliberate selection, refinement preservation and HTML/handoff outputs; this API does not prove their quality. |
| Interaction requirements | Finish-now/continue-later, internal work items, revision feedback, delayed questions and identity model. |

All related contracts remain DRAFT. The behavioral drafts reflect bounded
continuation, delayed questions, retained work and finish-now/continue-later.
Concrete API details here remain proposals, not evidence of conformance; source/API
compatibility and executable checks are still outstanding.

Still proposed or unverified:

- Host runner ownership, durable execution/recovery and first supported caller adapter.
- Agent source/API compatibility with bounded operations, questions and checkpoints;
  no import, model trial or runtime compatibility test has been run.
- Storage format, atomic mutation mechanism, access scope, deletion/retention policy,
  dedup horizon, observation cursor/snapshot consistency and crash recovery.
- Concrete grant limit units and enforcement, provider-call uncertainty on recovery.
- Artifact serving, generated-content isolation and builtin presentation implementation.
- Exact schemas/language/method names, and state/write-fence details for reopen.
- Scenario correctness criteria and executable conformance fixtures.

Compatibility must distinguish Possibly-owned state/control from Agent-owned
intelligence and host-owned execution/notification. Source inspection can inform
that boundary but cannot establish runtime conformance.

## Changelog

- v1 draft: provisional library surface, identity model, host dependencies,
  revision-safe decisions, bounded continuation, delayed questions, lifecycle
  outcomes and an illustrative caller round trip. No interface lock or runtime
  verification is implied.