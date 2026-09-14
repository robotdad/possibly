# Context to Visual Choice Contract — v1 (DRAFT)

**Who builds against this:** People describing an app, calling agent applications,
and consumers rendering or comparing the generated directions.
No reference implementation or approved conformance kit exists yet.

## What it looks like

A calling agent supplies a conversation and/or references to app-description
materials. The person receives visually comparable alternatives, with enough
of the central task shown to understand why one approach differs from another.

```text
Context/materials → known intent + open choices → visual directions
Each direction: task approach + representative states + practical tradeoff
```

## Purpose

The person should not have to write a polished prompt or design every alternative.
Without this promise, generation can invent requirements or present decorative
variations as meaningful choice. The output makes exploration inspectable.

For a watering-shift app, choosing between claiming calendar slots and supplying
availability for proposed assignments changes how people accomplish the task.
The visual sequences make that tradeoff visible. Choosing between differently
styled calendars explores branding instead. Both can be useful, but presenting
the latter as different task approaches obscures the choice rather than helping
someone make it.

## Core (the teeth)

1. **Conversation context and material references are valid inputs.**
   Either may be supplied alone or together; UI references and assets are optional.
   An otherwise usable app description is not rejected merely for lacking a mockup.
2. **Requirements are distinguished from inferred possibilities.**
   The interpreted brief identifies supplied intent, explicit UI guidance and open
   choices. Inaccessible sources are reported, not represented as having been read.
3. **Alternatives are derived from the app's users and tasks.**
   The person need not specify each design in advance or choose an app template.
   Clarifying questions address missing intent rather than outsource all exploration.
4. **Experience directions offer task-relevant differences.**
   A set presented as alternative experiences differs in how the task is accomplished.
   Theme-only variants are identified as visual exploration, not falsely counted as
   different task approaches.
5. **Visuals carry the comparison.**
   Each direction shows representative states or screens for the central task and
   its practical tradeoff. Prose alone is not a delivered visual direction.
6. **Selection precedes default click-through investment.**
   The person can select or redirect from lightweight directions before a working
   click-through is generated. The normal flow does not require trying several apps.

## What v1 deliberately does NOT freeze

- Direction count, storyboard screen count and comparison-page layout — promote
  constraints when observed comparison failures justify them.
- Rendering technology or intermediate schema — promote a stable interface when
  an actual renderer or caller depends on it.
- Models, prompts and image-generation policy — promote only if a behavioral
  guarantee cannot otherwise be preserved across implementations.
- Numerical speed targets — promote after approved trials establish a useful bar.

## Conformance kit asserts

No assertions below have executable checks or approved fixtures yet: **Can't check**.
The test proposal must include good/bad cases and explicit false-positive risks.

- Context-only, references-only and mixed inputs work without mandatory UI assets (1).
- An inaccessible reference is named, and an inferred UI preference is not stated
  as a supplied requirement (2).
- The same method handles unrelated approved scenarios without bespoke design
  instructions or fixed-template admission restrictions (3).
- An approved human rubric distinguishes task alternatives from cosmetic variants
  and checks that their visual sequences support the stated differences (4–5).
- The observable sequence reaches a selection/redirect point before default
  click-through generation (6).

## Reserved / open questions (NOT frozen)

- Which real conversation/material scenarios and visual-comparison rubric are
  sufficient for the first experiment?
- How do callers supply context and references, and how are access failures surfaced?
- Which ambiguities require a question instead of an explicitly labeled assumption?