# Dashboard Lifecycle and Human Actions Contract — v1 (DRAFT)

**Who builds against this:** People inspecting and selecting generated experiences,
dashboard adapters, and calling agents observing or controlling those explorations.
No reference implementation or approved conformance kit exists yet.

## What it looks like

Possibly makes the dashboard available when there is something meaningful to
inspect. The person can try a prototype and explicitly select or respond to a
direction there. Those actions become exploration state visible to the calling
agent, which remains the conversation host.

```text
Presentable result → dashboard available → inspect / select / give feedback
Selection → recorded decision → caller-visible observation
Caller stop or exploration done → dashboard stopped + retained-state receipt
```

## Purpose

The visual surface and the calling agent share one exploration, not competing
versions of it. Selecting a direction in the dashboard leaves an acknowledged,
identifiable decision the caller can use. Highlighting a card only in browser
memory, while the caller continues with another direction, violates that promise.
Finishing the exploration releases its live presentation resources without
silently deleting the results.

## Core (the teeth)

1. **Presentable material makes the dashboard available automatically.**
   Once material satisfies the applicable exploration/continuity presentation
   requirements, the tool starts or updates the dashboard and announces its
   location and readiness through the caller contract. It does not require a
   separate manual dashboard-start call. Unready portions remain labeled as such.
2. **Availability and actually showing a browser are distinguished.**
   The tool initiates presentation through the supported environment's mechanism.
   If it cannot open a viewer, it returns a usable access route or an explicit
   access failure; it never claims the person saw a page merely because a server
   started. An updated result reuses the exploration rather than creating confusion.
3. **The visible artifact and decision target are identifiable.**
   The dashboard identifies the exploration, direction and revision being shown.
   Inspection and prototype interactions are distinguished from explicit selection,
   rejection and feedback. Stale views cannot silently change a different revision.
4. **Explicit dashboard decisions are durable, acknowledged actions.**
   Selection, rejection and feedback accepted by the tool update exploration state
   and produce an observation through `caller-interaction.v1.md`. The dashboard
   shows success only after acceptance; failed submission or disconnection is
   visible. Refreshing the page preserves accepted actions and their receipts.
5. **Meaningful activity is observable without exposing private reasoning.**
   The dashboard and caller can distinguish preparation, available material,
   waiting for input, refinement and terminal outcomes. Viewing activity, when
   reported, is distinct from selection. This promises neither every pointer
   movement nor internal model scratch work.
6. **Stop and done end the live dashboard session explicitly.**
   The caller can request stop; the tool also stops when the exploration reaches
   its declared done condition. Finishing one generation call is not exploration
   completion while human review remains pending. Terminal status identifies
   retained artifacts/decisions and any resources whose cleanup failed.
7. **Shutdown does not erase choices or seize unrelated resources.**
   After stopping, dashboard writes are refused visibly; accepted decisions remain
   available through the caller contract. The tool releases only resources it
   owns, does not close unrelated browser tabs, and does not report stopped while
   its interactive service continues accepting writes.
8. **Prototype content does not inherit dashboard control authority.**
   Generated prototype code cannot silently submit selections, access unrelated
   exploration data or gain the caller's credentials. Rendering/access failures
   remain distinguishable from a human decision.

## What v1 deliberately does NOT freeze

- Presentability predicate and progressive reveal layout — promote after concrete
  examples distinguish a useful preview from misleading or broken output.
- Browser opening/focus, local versus hosted serving and read-only post-stop views —
  promote when a supported host demonstrates presentation and shutdown end to end.
- Event transport and exact state names — promote through the caller contract
  after an adapter demonstrates observation, reconnect and stop.
- Shutdown deadline, interrupted artifacts and orphan recovery — promote after
  cancellation/crash trials establish honest cleanup behavior.

## Conformance kit asserts

No executable kit or approved fixtures exist; these are proposed assertions.
Each currently reads **Can't check**, not passed.

- Presentable output starts/updates a dashboard without an extra start request.
- A viewer-opening failure is reported rather than described as successful display.
- Selection is acknowledged, survives refresh and reaches the caller with the shown revision.
- Prototype clicks alone create no design-selection or downstream-development authorization.
- Call completion while awaiting review leaves the exploration available, not falsely done.
- Caller stop and declared done stop writes, release owned resources and preserve receipts.
- Prototype content cannot exercise dashboard decision controls without an explicit human action.

## Reserved / open questions (NOT frozen)

- What exactly declares an exploration done, and does the person request it in either surface?
- Does closing the browser mean stop, disconnect, or merely hiding the dashboard?
- What remains viewable after shutdown, and for how long is decision history retained?
- Which viewing activity matters to the caller, and how is it summarized?