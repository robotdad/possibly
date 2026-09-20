# Dashboard Lifecycle and Human Actions Contract — v1 (DRAFT)

**Who builds against this:** People inspecting and selecting generated experiences,
the built-in dashboard or host-provided presentation adapters, and calling agents
observing or controlling those explorations.
No reference implementation or approved conformance kit exists yet.

## What it looks like

When configuring or starting an exploration, the host explicitly chooses its
presentation policy. It may enable the built-in dashboard, provide its own UI
over the public artifacts and decision/observation controls, or stay headless
while retaining direct access to the same capabilities. With the built-in
dashboard selected, Possibly automatically starts or updates it when material
is ready; no separate dashboard-start call is required. A host-provided UI
remains host owned.

```text
Presentable result → selected presentation policy
  built-in dashboard: automatically available/updated → inspect / select / feedback
  host UI or headless: public artifacts + decision/observation controls
Human action → recorded decision → caller-visible observation
Caller stop or exploration done → terminal cleanup + retained-state receipt
```

## Purpose

An authorized presentation adapter and the calling agent share one exploration,
not competing versions of it. Selecting a direction through an authorized
adapter leaves an acknowledged, identifiable decision the caller can use.
Highlighting a card only in browser memory, while the caller continues with
another direction, violates that promise. Finishing the exploration releases
library-owned presentation resources without silently deleting results or
seizing host resources.

## Core (the teeth)

1. **Presentation policy is explicit and capability-preserving.** At
   configuration or exploration start, the host explicitly chooses built-in
   dashboard, host-provided UI, or headless presentation. All choices retain
   public access to artifacts, durable decisions, observations, refinement,
   export, and stop; a dashboard is not the only capability path.
2. **Automatic lifecycle is limited to the selected built-in dashboard.** Once
   material satisfies the applicable exploration/continuity presentation
   requirements and the needed presentation permissions are granted, the tool
   starts or updates its built-in dashboard and announces
   its location and readiness through the caller contract. It does not require a
   separate manual dashboard-start call. This clause does not start, update, or
   govern a host-provided UI. Unready portions remain labeled as such.
3. **Service, viewer, and focus authority are distinct and explicit.** Possibly
   never launches a server, opens a browser/viewer, or takes focus unless the
   host grants the corresponding scope. These permissions may be supplied
   together at configuration or start; no repeated approval ceremony is required.
   Selecting a dashboard does not implicitly grant viewer-opening or focus
   permission. Missing required permission is reported, not guessed.
   It reports unavailable or failed optional
   presentation explicitly and still returns the available public artifacts and
   controls. It never claims the person saw a page merely because a service
   started. An updated result reuses the exploration rather than creating confusion.
4. **Visible artifacts and decision targets are identifiable.** An authorized
   presenter, and results for headless access, identify the exploration,
   direction and revision being shown. Inspection and prototype interactions are
   distinguished from explicit selection, rejection and feedback. They identify
   the current interpreted-brief revision when relevant, so visual review can
   expose omitted or misunderstood intent. Stale views cannot silently change a
   different revision.
   If newer choices conflict with applying feedback from an older view, the
   person can choose the reviewed base or explicitly carry the change forward.
5. **Authorized presentation decisions are durable, acknowledged actions.**
   Selection, rejection and feedback accepted through the built-in dashboard,
   a host-provided UI, or direct public controls update exploration state and
   produce an observation through `caller-interaction.v1.md`. An accepted
   visual-review intent correction creates the identified brief revision and
   updates affected current directions/artifacts or marks them superseded. A
   presenter shows success only after acceptance; failed submission or
   disconnection is visible. Refreshing or replacing a presenter preserves
   accepted actions and their receipts.
6. **Meaningful activity is observable without exposing private reasoning.**
   The selected presenter and caller can distinguish preparation, available material,
   waiting for input, refinement and terminal outcomes. Viewing activity, when
   reported, is distinct from selection. This promises neither every pointer
   movement nor internal model scratch work.
7. **Stop and done end library-owned presentation work explicitly.** The caller
   can request stop; the tool also stops when the exploration reaches its declared
   done condition. Finishing one generation call is not exploration completion
   while human review remains pending. Terminal status identifies retained
   artifacts/decisions and any library-owned resources whose cleanup failed; the
   caller can await that terminal outcome.
   Export alone does not finish exploration; export and finish may be requested
   together. Finish ends live work successfully; stop is the interruption path,
   with partial work and cleanup failures reported explicitly.
   Closing a viewer only disconnects that viewer: it implies neither selection
   nor stop, grants no new authority, and does not extend existing work limits.
8. **Shutdown does not erase choices or seize host resources.** While stopped or
   finished, ordinary library decision writes are refused visibly; accepted decisions remain
   available through the caller contract. The tool releases only live storage
   handles, background tasks, services, viewers, and presenter resources it owns,
   without deleting retained artifacts or decisions. It does
   not close unrelated browser tabs, stop a host service or UI, delete caller
   storage, or report stopped while its owned interactive service accepts writes.
   Retained exploration state, including pending needs, remains available for an
   explicit later continuation. Returning can reuse the same exploration without
   reconstructing its context, creating new revisions while preserving the base.
   Restart only needed, authorized live resources; prior generation permission
   does not silently restart spending. Old presentation submissions must not
   bypass the closed state or target a newly continued revision without validation.
9. **Prototype content does not inherit presentation control authority.**
   Generated prototype code cannot silently submit selections, access unrelated
   exploration data or gain the caller's credentials. Rendering/access failures
   remain distinguishable from a human decision. The initial-POC standalone HTML
   mockup may open independently, but it is not an authorized presentation-control
   channel: offline interactions do not silently create durable caller decisions.
10. **An MCP App is the built-in dashboard over a different transport, not a
    second dashboard.** When an authorized MCP Apps host presents Possibly's
    dashboard, it renders the same canonical dashboard document, styles, control
    inventory, responsive geometry, preview sizing, history, feedback and export
    eligibility as the built-in dashboard. Its only substitution is a narrow
    transport adapter for the public-library operations. It preserves the native
    appearance control: system follows the host's resolved theme (falling back to
    media preference when absent), and a person's local light/dark override wins.
    Partial host-context updates must merge rather than reset appearance, drafts,
    current workspace, pending retries, or mounted previews. An empty or
    unattached MCP App may show only the truthful native-shell empty state; it does
    not replace the dashboard with an adapter-specific workflow or controls.

## What v1 deliberately does NOT freeze

- Presentability predicate and progressive reveal layout — promote after concrete
  examples distinguish a useful preview from misleading or broken output.
- Presentation-policy configuration, service/viewer/focus scopes, local versus
  hosted serving and read-only post-stop views — promote when a supported host
  demonstrates presentation and shutdown end to end.
- Event transport and exact state names — promote through the caller contract
  after an adapter demonstrates observation, reconnect and stop.
- Shutdown deadline, interrupted artifacts and orphan recovery — promote after
  cancellation/crash trials establish honest cleanup behavior.

## Conformance kit asserts

No executable kit or approved fixtures exist; these are proposed assertions.
Each currently reads **Can't check**, not passed.

- With the built-in dashboard explicitly selected and required service permission
  granted, presentable output starts or
  updates it without an extra start request.
- With a host-provided UI or headless presentation selected, no built-in service,
  browser, viewer, or focus action occurs without separately granted scope.
- With the built-in dashboard selected but service, viewer or focus permission
  withheld, the withheld action does not occur and any resulting presentation
  limitation is explicit.
- A viewer-opening or other optional presentation failure is reported rather than
  described as successful display, while public artifacts and controls remain available.
- Selection through each authorized presentation path is acknowledged, survives
  presenter refresh/replacement and reaches the caller with the shown revision.
- An accepted visual-review intent correction identifies its brief revision and
  leaves affected directions/artifacts updated or visibly superseded.
- Prototype clicks alone create no design-selection or downstream-development authorization.
- Call completion while awaiting review leaves the exploration available, not falsely done.
- Caller stop and declared done stop library writes, release only library-owned
  resources, preserve receipts, and yield a terminal cleanup outcome.
- Export alone leaves exploration open. Closing the viewer neither stops the
  exploration nor authorizes additional execution.
- Finish/stop preserves context, choices and pending needs for explicit later
  continuation; new revisions preserve the base and old viewer submissions
  cannot bypass lifecycle or revision validation.
- Prototype content cannot exercise authorized presentation decision controls
  without an explicit human action.
- Offline interaction with a downloaded initial-POC HTML mockup does not create a
  durable presentation or caller decision.
- An MCP App rendered in an independent standard host has the same native
  dashboard controls, geometry, light/dark/system behavior and preview contract
  at desktop and narrow viewports; its only adapter-specific behavior is the
  public-library transport.
- Host theme/context changes merge without remounting the dashboard or losing a
  current workspace, outgoing draft, accepted-but-unacknowledged retry, or opaque
  prototype preview.

## Reserved / open questions (NOT frozen)

- How are explicit finish and declared done conditions represented, and how are
  in-flight work or pending application conflicts resolved before completion?
- How does a presenter reconnect or reopen after finish/stop without reviving
  obsolete write contexts or execution grants?
- What remains viewable after shutdown, and for how long is decision history retained?
- Which viewing activity matters to the caller, and how is it summarized?

## Changelog

- **2026-09-19** — Added the authorized exact-parity direction after rendered
  native/MCP comparison found a separately designed MCP review surface. The
  corrective requirement is one canonical native dashboard and workflow with
  narrow built-in HTTP and MCP public-library transports, including native
  responsive geometry, preview behavior, system/light/dark appearance and
  lossless runtime host-context updates. This remains DRAFT and does not lock a
  host implementation or transport schema.