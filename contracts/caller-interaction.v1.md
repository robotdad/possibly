# Calling Agent Interaction Contract — v1 (DRAFT)

**Who builds against this:** Calling agent applications and their adapters,
and people continuing an exploration through those agents.
No reference implementation or approved conformance kit exists yet.

## What it looks like

The calling agent owns the conversation and invokes the public Possibly library
directly or through an adapter. It supplies context, chooses an authorized
presentation policy, learns the person's recorded decision from the public
observation contract, and continues that same exploration. Internal Amplifier
Agent sessions, a Possibly CLI session, and shared files are not caller
prerequisites or implied context.

```text
Caller → request + supplied context + explicit authority → public Possibly library
Caller ← exploration identity + typed result/question/error + artifacts
Caller ↔ authorized presentation adapter → durable decision/feedback
Caller ← correlated observation → next explicit instruction or stop
```

## Purpose

A tool is usable by other agents only when they can tell what to call, what
happened, and what remains under their control. An authorized presentation
adapter must not become a second conversation whose decisions are invisible to
the caller. If someone selects direction B through that adapter, the caller can
name that exact revision in the next refinement request; proceeding with A from
an old chat summary is the wrong outcome.

## Library boundary, authority and ownership

Possibly is a library first. Every public capability, including exploration,
artifact access, decisions, observations, refinement, export, and stop, is
callable through its public library. The CLI ships by default as a thin adapter
for that same surface; it adds command-line parsing and I/O conventions, not
exclusive capability or different decision, stale-input, cancellation, or
failure semantics. Other adapters, including caller-owned host adapters, use
the same public library.

The public contract describes typed request inputs, results, human questions or
waiting states, errors, correlation and ordered observations, and cancellation
outcomes. Concrete names, fields, and transport schemas are deliberately not
frozen here. Importing the library and using deterministic operations neither
require model credentials nor initialize intelligence. A model-backed operation obtains model configuration
and access only from explicit host-supplied authority or from an explicitly
opted-in, documented configuration source; configuring one such source does
not require credentials on every call. It never silently inherits a CLI session
configuration, caller conversation, shared filesystem, or ambient model access.

Each exploration identifies the ownership of its storage, model configuration,
background tasks, and presenter resources. The library owns only resources it
created or was explicitly assigned. Caller conversation, caller storage,
host-provided services, and host UI resources remain caller or host owned.
Stopping releases library-owned live resources and reports terminal cleanup,
while preserving retained artifacts and decisions. It must not close, delete,
cancel, or otherwise seize caller-shared resources.

## Core (the teeth)

1. **The public capability surface is explicit and independent of the caller.**
   Every capability is reachable through the public library without the CLI or
   a presentation adapter. Library interfaces and agent-facing help document supported operations,
   typed inputs/results/questions/errors, model-backed requirements or costs,
   correlation, observations and cancellation semantics. Presentation and
   decision capabilities are not available only through undocumented browser
   actions.
2. **Context and authority cross the boundary explicitly.**
   The tool accepts supplied content and declared material references; it assumes
   neither access to the caller's conversation nor a shared filesystem. Model
   access, configuration sources, storage, background work, and presentation
   permissions are host-supplied or explicitly opted in and documented. Retrieval
   scope and inaccessible materials are reported. Reference content grants no
   execution permission.
3. **Results and subsequent instructions identify the same exploration.**
   Requests, operation outcomes, directions and artifact revisions are correlated.
   Referring to an older revision never silently targets a newer one. Invalid or
   ambiguous references produce an actionable result rather than a guessed choice.
   An exploration ID spans the experience and later continuation. Operation IDs
   identify individual work and outcomes; question IDs identify answer targets;
   revision IDs identify reviewed or changed material. Callers and presenters
   carry these identities without requiring manual human bookkeeping.
4. **The caller has a documented way to observe changes since its last reading.**
   Presentation availability, meaningful activity, accepted human decisions,
   accepted intent corrections and terminal outcomes are receivable or
   retrievable without screen scraping.
   Observations carry identity and order information; a delivery gap or expired
   history is explicit. Refreshing or replacing an authorized presentation
   adapter cannot erase accepted decisions.
   Current operation status and outstanding questions are durably retrievable
   even when the caller is no longer waiting or observation history has expired.
   Notification and client wake-up depend on supported, authorized host mechanisms;
   neither is guaranteed. Recording a need, delivering an observation, waking
   an agent and reaching a person are distinct outcomes.
5. **Decision acknowledgement is distinct from event delivery, execution and
   caller adoption.** A receipt identifies the accepted action, resulting state
   revision, and any corrected intent or important change; an event reports that
   fact, not a new instruction each time it is read. Repeated delivery cannot
   itself authorize duplicate generation. A presentation selection does not
   authorize production development or imply the caller has already acted on it.
   Accepting an intent correction records the revised brief and supersedes
   affected material; regeneration follows the request's existing execution
   authority. If further authorization is needed, the caller receives corrected
   state and the pending regeneration request, not a claim of regenerated output.
   The caller may grant bounded continuation authority up front, such as making
   one interactive mockup after selection and then waiting for feedback. The
   matching action may continue without a second human approval; without that
   authority, return the decision receipt and proposed next action to the caller.
   Repeating the same identified submission returns its original receipt, not
   duplicate work; conflicting resubmissions are reported rather than acknowledged
   as the original action. Retry identifiers and retention limits remain explicit
   API design details, not an unbounded retry guarantee.
6. **The caller can continue or stop without an inaccessible prompt.**
   Missing human input is returned as an identified question or waiting state.
   Stop requests and cancellation produce correlated outcomes, distinguishing
   accepted/stopping from terminal completion and cleanup failure. The caller can
   await that terminal outcome. Failure is explicit; partial completion is
   identified, not presented as complete success.
   A delayed need identifies the blocking question, why it matters, and its
   operation; the blocked work pauses. An accepted answer continues that same
   pending operation within valid authority and access. A later refinement is a
   new operation in the same exploration, not a replay of the answered question.
7. **Public state survives internal intelligence boundaries.**
   Internal prompts, model choices and Agent session identifiers are not required
   to interpret artifacts, retrieve decisions or resume an exploration. Tool
   execution approval is never represented as human design approval.
   Possibly may persist internal work items and checkpoints for execution and
   recovery. They are not the caller's queue, do not require caller knowledge of
   their format, and do not themselves authorize resumed work.
8. **Caller-owned governing materials remain caller-owned.** The tool does not
   implicitly edit or approve a caller's vision, contracts, or equivalent
   governing materials. The caller decides whether and how to adopt visible
   accepted corrections, important changes, selections and handoff information
   under its own process.
9. **Adapter parity preserves capability semantics.** The default CLI, a
   built-in dashboard when selected, and host-owned adapters may vary in medium
   and exposed subset, but not in the semantics of capabilities they expose.
   Host adapters may intentionally offer a narrower surface. No capability lives
   only in an adapter; decisions, stale-input handling, outcomes, questions,
   failures, observations, export and stop remain library-accessible.
10. **Embedding does not require ambient model access or surrender host resources.**
   Library imports and deterministic operations are provider-free and do not
   initialize intelligence. Model configuration and access follow explicitly
   supplied or opted-in sources. Resource ownership and cleanup are documented;
   stop preserves retained results and leaves caller-shared resources alone.
   Durable storage is explicitly supplied or selected by the host. Finish/stop
   retains the exploration record described in `selection-continuity.v1.md`,
   independently of exported HTML. Later continuation requires a new explicit
   request and appropriate authority; previous spending permission does not
   silently restart work.
11. **Adapter presentation parity is not capability-only parity.** An adapter
    that presents the built-in dashboard (including an MCP App) reuses the
    canonical native dashboard rendering and workflow rather than offering a
    reduced or redesigned control surface. The adapter binds its controls only to
    documented public-library operations, retains their identity/version/retry
    semantics, and may expose unavailable capabilities as the native dashboard's
    truthful state rather than inventing a host-only alternative. A host's
    resolved theme is presentation context, not authority to overwrite a
    person's native appearance choice.

## What v1 deliberately does NOT freeze

- CLI/MCP/HTTP transport, polling versus push and adapter packaging — promote when
  a real calling-agent round trip establishes the required integration behavior.
- Exact schemas, event retention, acknowledgement and retry keys — promote after
  disconnect, repeated-request and stale-feedback trials expose needed guarantees.
- Multi-caller conflict resolution and authentication mechanisms — promote when
  a supported concurrent or remote caller requires them.

## Conformance kit asserts

No executable kit or approved fixtures exist; these are proposed assertions.
Each currently reads **Can't check**, not passed.

- An independent caller discovers capabilities and correlates a request and result.
- A selection through any authorized presentation adapter is observed by the
  caller with its actual target revision.
- A direct-library round trip starts an exploration, receives results, records a
  human choice through a host presentation adapter, observes that choice, refines
  the same revision, exports one HTML mockup and handoff, then stops and awaits
  terminal cleanup without the caller using the Possibly CLI or operating internal
  Agent machinery.
- An accepted visual-review intent correction and its important affected changes
  are visible to the caller with the resulting revision.
- Re-reading an event does not repeat its effect; stale input is not silently retargeted.
- A missed-history condition is explicit and current accepted decisions are retrievable.
- Closed-stdin invocation returns an outcome/question; stop distinguishes request from completion.
- Replacing internal Agent session machinery does not require caller transcript reconstruction.
- Library import and deterministic operations run without model credentials or intelligence
  initialization; a model-backed operation uses only explicit host-supplied or
  explicitly opted-in documented configuration authority.
- CLI and host-adapter paths preserve decision, stale-input, failure, observation,
  export and cancellation semantics for the capabilities they expose; none are
  available only through an adapter.
- Stop releases library-owned live resources while preserving retained artifacts
  and decisions and leaving caller and host-owned
  storage, services, UI, and other shared resources untouched.
- Tool activity neither edits nor approves caller-owned governing materials; the
  caller's adoption is distinguishable from tool acknowledgement.
- A delayed question remains retrievable without notifications, identifies its
  operation, and an accepted answer continues that operation rather than creating
  unrelated work; a history gap does not hide outstanding needs.
- Selection with a valid bounded continuation grant triggers only its allowed
  follow-up; without one it returns the receipt and proposed next action.
- A repeated identified submission returns the original receipt without duplicate
  work; conflicting resubmission is not reported as accepted.
- Internal work items survive interruption without becoming caller prerequisites
  or reviving expired/closed execution authority.
- A standard MCP Apps host renders the canonical dashboard's native controls and
  workflow while exercising only public-library operations; desktop/narrow and
  light/dark/system comparisons do not accept a styling approximation.

## Reserved / open questions (NOT frozen)

- Which caller adapter demonstrates the first complete round trip?
- What observation cadence makes the caller sufficiently informed without flooding it?
- How are bounded continuation scopes, limits and expiry expressed and enforced?
- What identifies duplicate requests, and how are conflicting caller/dashboard writes resolved?

Dashboard lifecycle and action meanings belong to `dashboard-lifecycle.v1.md`.
Experience quality and preservation belong to the exploration and continuity contracts.
Proposed concrete public types and methods live in `interaction-api.v1.md`.

## Changelog

- **2026-09-19** — Added the authorized exact native-dashboard parity direction:
  a dashboard-presenting MCP App must retain the canonical rendering/workflow and
  use only a narrow public-library transport adapter. The rendered comparison
  exposed a materially different MCP surface despite capability overlap. This
  amendment remains DRAFT; it does not freeze MCP schemas or require a particular
  host.