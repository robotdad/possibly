# Food for thought: Smart Tools as interactive experiences

Draft for discussion, 2026-09-16. Prepared before implementing Possibly's A2UI
integration. Proposals below are not current Smart Tools requirements.

## The observation

Possibly packages expertise in exploring an application's experience before
implementation. A calling agent starts an exploration, a person compares and
tries concepts, and both continue from the same retained decisions and revisions.
The visual workspace is a primary place where the person does the work.

The library remains the tool. A primary human interface is compatible with that
architecture: it presents and manipulates capabilities owned by the library.
“Optional adapter” describes deployment, not how important the experience is.

Could the spec explicitly recognize this shape: a smart tool may deliver an
ongoing domain experience, with coordinated agent and human participation, as
well as a one-call result?

## What the current spec already says

Reviewed `microsoft/amplifier-smart-tools` main at commit
`0f89dd9263338918d9b27bb48670c688c3e9bac1`. Links below pin that source revision.

| Source | Existing position | Discussion opportunity |
|---|---|---|
| [Structure](https://github.com/microsoft/amplifier-smart-tools/blob/0f89dd9263338918d9b27bb48670c688c3e9bac1/spec/structure.md) | Every capability lives in the library; UI/service adapters are optional, may be the right way to drive a tool, and must not start unless requested. | Clarify that an optional shipped UI can still be the primary human experience. Distinguish capability access from equivalent human usability. |
| [Invocation](https://github.com/microsoft/amplifier-smart-tools/blob/0f89dd9263338918d9b27bb48670c688c3e9bac1/spec/invocation.md) | Normal calls return results; output shapes belong to each capability; noninteractive callers must not hang on unavailable input. | Document accepted operations, pending questions, observation, and continuation without holding a CLI call open indefinitely. |
| [Manifest](https://github.com/microsoft/amplifier-smart-tools/blob/0f89dd9263338918d9b27bb48670c688c3e9bac1/spec/manifest.md) | Selection metadata and operational guidance are separate; frontmatter fields form a closed set. | Hosts may eventually need to discover presentation options. Experiment in documented library capabilities before proposing new manifest fields. |
| [Roadmap](https://github.com/microsoft/amplifier-smart-tools/blob/0f89dd9263338918d9b27bb48670c688c3e9bac1/ROADMAP.md) | Long-running calls, product integration, and continuing a smart call are open decisions. | Interactive experiences provide one concrete case connecting those three questions. |
| [Scope](https://github.com/microsoft/amplifier-smart-tools/blob/0f89dd9263338918d9b27bb48670c688c3e9bac1/spec/README.md) | The spec describes a construction shape, not a cross-vendor wire protocol. | Keep interaction semantics protocol-neutral; use A2UI as an optional adapter example. |

This is an extension of the existing direction, not evidence that the spec
prohibits rich UI today. Possibly's contracts are local drafts and experience
reports, not normative interpretations of the upstream specification.

## Proposal 1: clarify primary experiences and optional adapters

Suggested discussion wording for Structure:

> A tool-provided UI may be the primary human-facing experience. Optional means
> callers can use the library's capabilities without that particular adapter;
> it does not imply that every medium offers an equivalent human experience.
> Domain state, decisions, and workflow transitions remain library capabilities.
> Rendering and medium-specific interaction mechanics belong to adapters.
> Starting a service or opening a viewer requires an explicit caller choice.

A comparison workspace can be substantially better than terminal output for a
person choosing a design. The library and CLI can still expose the artifacts,
decisions, and observations needed to complete the workflow through another host.
Headless access does not mean that human review has occurred.

The boundary needs examples: grid layout and focus are presentation; selecting
an exact revision and recording feedback are domain operations. A reusable
presenter may turn library state into UI descriptions without owning a second
copy of the workflow.

## Proposal 2: explore an optional interaction profile

Start as guidance and a reference example for tools that span calls and human
actions. Do not impose a session runtime on simple tools or prescribe universal
method names yet. A participating tool would document:

- **Identity:** how a caller identifies the exploration, operation, and exact
  artifact revision being reviewed.
- **Observation:** how callers obtain a snapshot, subsequent changes, meaningful
  progress, partial outcomes, and terminal state. Internal reasoning is not
  required progress data.
- **Human input:** how questions, drafts, submitted decisions, and continuation
  differ, and how accepted actions become visible to every authorized participant.
- **Consistency:** retry behavior, acknowledgments, stale actions, and how a host
  recovers after disconnecting. Do not prescribe SQLite, event sourcing, or one
  concurrency mechanism.
- **Authority:** which actions merely record intent and which may initiate more
  model work, under what prior or fresh authorization and bounds.
- **Lifecycle:** who owns execution and presentation resources; what stop,
  finish, disconnect, and resume mean; what remains available afterward.

A start call could return an accepted operation and observation handle; a
waiting-for-input state could be returned as data with a documented answer
capability. Neither requires prompting on closed stdin or pretending that an
accepted operation has completed.

Possibly already supplies much of this through `get_exploration`, `read_changes`,
`review_snapshot`, `save_review_state`, `record_decision`, and operation/lifecycle
methods. These are examples to learn from, not names to standardize prematurely.

## Proposal 3: distinguish presentation, transport, and execution

A2UI is useful because it describes UI structure, bound data, and actions over
a registered catalog. It does not replace the tool's domain API or decide who
may execute an action. A library-backed presenter can emit descriptions without
using a model; model-authored UI is a separate option.

For Possibly, the proposed flow is:

```text
Possibly library → review presenter → A2UI → dashboard or embedded host
Possibly library ← validated domain actions ← either host
```

Keep three decisions independent:

1. Which surface presents the experience: built-in viewer, host UI, or headless.
2. How messages travel: direct integration, HTTP, or another host transport.
3. Who runs and bounds the work: calling process, owned worker, or host execution.

The library is Python today. A2UI helps the frontend consume presentation data;
it does not make Python directly importable into a JavaScript or native host.
That host still needs an execution bridge.

An exploratory presentation capability could report supported protocol versions,
catalog identities, required custom components, fallback behavior, and how to
route actions. These are proposed capability semantics, not new descriptor or
manifest fields. Capability discovery must not start a viewer or a model call.

Custom components are a real integration cost. Possibly needs a trusted
`PrototypePreview` implementation that displays immutable generated HTML with
the existing sandbox and network restrictions. A2UI does not itself make that
HTML safe. Hosts must implement the component or explicitly offer a reduced
experience, such as thumbnails and artifact access. Installing a generic A2UI
renderer alone is insufficient.

## Proposal 4: make human actions visible without implicit orchestration

A person submitting feedback in a workspace and an agent continuing in chat
must not create competing versions of the task. The accepted decision should
be retrievable through the library, including its exact reviewed target.

Distinguish four facts: input exists, it was accepted, a caller was notified,
and additional work was authorized. None automatically proves the next.
Possibly currently retains feedback without waking the caller. An integrated
application may choose a notification or subscription mechanism, and may have
preauthorized continuations, but those policies should be explicit.

Draft text is useful context but not a submitted instruction. Viewing or trying
a prototype is not selecting it. Closing a view is not cancelling execution.
These distinctions are useful across design, editing, approval, and planning tools.

## How to explore this without enlarging the core spec too early

1. Add the primary-surface clarification and a roadmap question about coordinated
   human/agent interaction.
2. Publish a non-normative example or short interaction guide connecting the
   existing roadmap questions. Demonstrate library, CLI, and a primary UI over
   the same state.
3. Build Possibly's narrow review flow in two hosts using one presenter. Test
   ordinary selection, feedback, revision changes, and recovery after refresh.
4. Compare against another tool's interaction needs before choosing common
   metadata or APIs. A document review or media editing tool could reveal
   requirements that a design explorer misses.
5. Consider an opt-in conformance profile only after the behavior is repeatable.

Candidate behavioral checks: accepted decisions survive reconnect; exact-revision
actions cannot silently target a newer artifact; an exact retry does not duplicate
a decision; draft saving does not spend model budget; waiting input returns a
usable handle; closing a view does not imply stop; surface disposal does not destroy
retained work; unsupported catalogs yield an explicit fallback or error.

The current conformance kit checks packaging and invocation properties. Its
passing verdict does not establish interaction quality or multi-host consistency.
UI usability, task diversity, and visual fidelity also need separate evaluation.

## What this changes for Possibly before we build

- Treat the existing dashboard as the first full review workspace, with a
  reusable presenter underneath it. Preserve its important human affordances.
- Separate domain state, persisted review drafts, and transient view state.
  Avoid remounting a running prototype when progress data changes.
- Project only appropriate review data into a surface. Do not copy the full
  backend snapshot, viewer credentials, or provider configuration into UI data.
- Keep artifact delivery/cache separate from routine progress and state updates.
- Start with deterministic A2UI review descriptions and validate the same flow
  in the dashboard and one embedded host. Keep model generation unchanged for
  this experiment.
- Later explore [A2UI prototype generation](a2ui-prototype-mode.md) as a separate
  mode with an explicit target catalog and mock action environment.

## Questions to take to the authors

1. Does the primary-human-surface clarification capture the intended library-first
   boundary, or should “optional means works completely without it” be refined?
2. Would a concrete interactive reference example help resolve roadmap items 1,
   3, and 5 together without adding a general session protocol?
3. Which facts about interactive presentation matter before installation, versus
   at runtime? Should any eventually become selection metadata?
4. Where should shared presentation semantics end and host orchestration begin,
   especially for waking callers and authorizing follow-up model work?
5. What second tool would make a useful counterexample to Possibly before any
   interaction profile becomes normative?

## A2UI references

- [Current 0.9.1 specification](https://a2ui.org/specification/v0.9.1-a2ui/)
- [Renderer support matrix](https://a2ui.org/reference/renderers/)
- [Custom catalogs](https://a2ui.org/guides/defining-your-own-catalog/)
- [Custom component authoring](https://a2ui.org/guides/authoring-components/)

The reviewed docs identify 0.9.1 as current production and 1.0 as candidate.
Pin and test an actual renderer/catalog combination for the experiment rather
than treating spec availability as implementation support.
