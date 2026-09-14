# Calling Agent Interaction Contract — v1 (DRAFT)

**Who builds against this:** Calling agent applications and their adapters,
and people continuing an exploration through those agents.
No reference implementation or approved conformance kit exists yet.

## What it looks like

The calling agent owns the conversation. It invokes Possibly, presents its
dashboard location, learns what the person selected there, and continues with
that same exploration. Internal Amplifier Agent sessions remain an implementation
detail, not something the caller must operate.

```text
Caller → request + supplied context → Possibly
Caller ← exploration identity + state + dashboard/artifact references
Caller ← recorded dashboard selection/activity → next explicit instruction
```

## Purpose

A tool is usable by other agents only when they can tell what to call, what
happened, and what remains under their control. A dashboard must not become a
second conversation whose decisions are invisible to the caller. If someone
selects direction B in the dashboard, the caller can name that exact revision
in the next refinement request; proceeding with A from an old chat summary is
the wrong outcome.

## Core (the teeth)

1. **The public capability surface is explicit and independent of the caller.**
   Library interfaces and agent-facing help document supported operations, inputs,
   outputs, model-backed costs, errors and control semantics. Dashboard/control
   capabilities are not available only through undocumented browser actions.
2. **Context and authority cross the boundary explicitly.**
   The tool accepts supplied content and declared material references; it assumes
   neither access to the caller's conversation nor a shared filesystem. Retrieval
   scope and inaccessible materials are reported. Reference content grants no
   execution permission.
3. **Results and subsequent instructions identify the same exploration.**
   Requests, operation outcomes, directions and artifact revisions are correlated.
   Referring to an older revision never silently targets a newer one. Invalid or
   ambiguous references produce an actionable result rather than a guessed choice.
4. **The caller has a documented way to observe changes since its last reading.**
   Dashboard availability, meaningful activity, accepted human decisions and
   terminal outcomes are receivable or retrievable without screen scraping.
   Observations carry identity and order information; a delivery gap or expired
   history is explicit. Refreshing the dashboard cannot erase accepted decisions.
5. **Decision acknowledgement is distinct from event delivery and execution.**
   A receipt identifies the accepted action and resulting state revision; an event
   reports that fact, not a new instruction each time it is read. Repeated delivery
   cannot itself authorize duplicate generation. Dashboard selection does not
   authorize production development or imply the caller has already acted on it.
6. **The caller can continue or stop without an inaccessible prompt.**
   Missing human input is returned as an identified question or waiting state.
   Stop requests produce a correlated outcome, distinguishing accepted/stopping
   from actually stopped. Failure is explicit; partial completion is identified,
   not presented as complete success.
7. **Public state survives internal intelligence boundaries.**
   Internal prompts, model choices and Agent session identifiers are not required
   to interpret artifacts, retrieve decisions or resume an exploration. Tool
   execution approval is never represented as human design approval.

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
- A dashboard selection is observed by the caller with its actual target revision.
- Re-reading an event does not repeat its effect; stale input is not silently retargeted.
- A missed-history condition is explicit and current accepted decisions are retrievable.
- Closed-stdin invocation returns an outcome/question; stop distinguishes request from completion.
- Replacing internal Agent session machinery does not require caller transcript reconstruction.

## Reserved / open questions (NOT frozen)

- Which caller adapter demonstrates the first complete round trip?
- What observation cadence makes the caller sufficiently informed without flooding it?
- Which actions may the tool continue autonomously after selection under the original request?
- What identifies duplicate requests, and how are conflicting caller/dashboard writes resolved?

Dashboard lifecycle and action meanings belong to `dashboard-lifecycle.v1.md`.
Experience quality and preservation belong to the exploration and continuity contracts.