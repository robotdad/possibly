# Selected Experience Continuity Contract — v1 (DRAFT)

**Who builds against this:** People refining a chosen direction, calling agent apps,
mockup renderers and separate app/backend development agents consuming the handoff.
No reference implementation or approved conformance kit exists yet.

## What it looks like

Someone chooses a direction, asks for it to feel more like a reference, tries the
selected interaction and changes it. The initial POC delivers that mockup as one
self-contained HTML file. The next development agent receives both the result
and the decisions needed to preserve it.

```text
Selected direction → reference/feedback refinement → one click-through
Handoff: selected experience + decisions + mocked behavior + open assumptions
```

## Purpose

Exploration loses its value if refinement quietly erases the choice or development
replaces it with a conventional layout. This promise keeps the selected experience
recognizable while allowing intentional changes. It does not freeze prototype code
or dictate how the real app is engineered.

For example, someone choosing a calendar-first watering-shift app may ask for the
typography and imagery of a supplied reference while keeping direct shift claiming.
A useful refinement adopts that visual treatment and still lets people browse
slots and claim their chosen shift. One that silently replaces claiming with
automatic assignments loses the selected experience, however closely it matches
the reference's appearance. The distinction is between a requested change and an
unrequested replacement, not a prohibition on changing the interaction.

## Core (the teeth)

1. **Reference-driven refinement separates change from preservation.** “This one,
   more like X” identifies the requested visual or interaction transfer, the
   referenced material and revision, and what should remain. Material ambiguity
   is exposed rather than silently resolved into a different experience.
2. **The result preserves choices outside the requested change and follows the
   current interpreted intent.** A theme change does not silently replace the task
   flow; an interaction change does not silently discard the selected branding.
   Accepted intent corrections from visual review update the identified brief
   revision and affected directions/artifacts, while superseded versions remain
   distinguishable from current ones.
   Intentional departures remain distinguishable from accidental drift.
3. **A selected direction becomes a bounded interactive approximation.**
   The default is one click-through for trying the central task and forming feedback.
   A second is reserved for a specific comparison, never required by default.
4. **Selection does not erase alternatives.**
   Rejected directions remain available so feedback can return to exploration.
   Choosing a direction is not an irreversible deletion of the other choices.
5. **The initial POC delivers one self-contained HTML mockup.** The delivered
   mockup is one `.html` file that opens directly in a supported browser and
   embeds its CSS, JavaScript, and required images, fonts, and data (or uses
   system fonts). Inspecting or trying the bounded central task requires no
   external assets, CDN, runtime service, build, install, server, or required
   companion-assets folder. Supporting explainers or decision materials may be
   separate optional files but are never runtime dependencies. Broader mockup
   formats are deferred and are not required for this initial POC.
6. **Handoff preserves corrected intent and exposes approximation.** The package
   includes the selected prototype, current identified brief revision, accepted
   intent corrections, important interaction and visual changes, mocked behavior
   and unresolved assumptions. A fresh development agent can continue a bounded
   piece without the original conversation. Prototype-code reuse and production
   architecture are not mandatory. Required handoff information may be embedded
   in the HTML or included in the caller-facing result; separate documents are
   optional, not a condition of complete delivery.
7. **A downloaded initial-POC HTML file is an independent mockup, not a dashboard
   control channel.** Its offline interactions do not silently create durable
   caller decisions. The live-dashboard decision and observation obligations in
   `dashboard-lifecycle.v1.md` and `caller-interaction.v1.md` remain in force.
   Submitting selections, feedback or corrections to the exploration uses the
   live dashboard or calling agent, not the standalone export.

## What v1 deliberately does NOT freeze

- Broader mockup formats beyond the initial standalone HTML file — promote when a
  real consumer needs a stable format.
- Branding controls and image-generation tools — promote when tested refinement
  failures require a specific guarantee, not merely a preferred implementation.
- Handoff schema and downstream integration — promote when an actual consumer
  depends on stable fields or behavior.
- State coverage beyond the central task — promote when a missing state prevents
  an approved experience judgment or causes a demonstrated handoff failure.

## Conformance kit asserts

No assertions below have executable checks or approved fixtures yet: **Can't check**.
Human judgments require an approved rubric and a recorded review, not model assent.

- A reference-driven change is recognizable while agreed invariants stay intact;
  an ambiguous reference transfer is not silently treated as settled, and an
  accepted intent correction updates the current brief/directions/artifacts rather
  than leaving contrary material current (1–2).
- A selected central task can be tried and a requested interaction revised,
  without requiring multiple click-throughs (3).
- Selection leaves earlier directions accessible (4).
- The one delivered initial-POC `.html` file opens directly in a supported browser
  and supports inspection and trying the bounded central task with networking
  disabled and no companion files, build, install, or server (5).
- A fresh development agent implements an approved bounded piece from the handoff,
  preserving chosen interactions, corrected intent and important changes, and
  distinguishing mocks from requirements (6).
- Interacting with a downloaded HTML file offline creates no silent durable caller
  decision; such decisions use the live dashboard/caller path (7).

## Reserved / open questions (NOT frozen)

- Which broader mockup format, if any, should follow the initial self-contained
  HTML POC when a real consumer needs it?
- What constitutes a meaningful reference match and a preserved choice?
- Which downstream piece and handoff consumer test continuity without requiring
  production engineering inside the exploration loop?