# Possibly

**Choose before you build.**

When a coding agent builds the first interpretation of your app idea, that
result often becomes the experience you spend the rest of the conversation
adjusting. What if you could explore the possibilities before committing?

Possibly is an early-stage project exploring an Amplifier-powered smart tool
that brings intentional experience exploration into the agent app you already use.

## Explore, choose, try

The intended flow starts with what you already have: conversation context,
pointers to materials describing an app idea, or both. UI preferences, images
and brand references are welcome, but not required.

- **Explore** lightweight visual directions showing different ways people could
  accomplish their tasks—not just different colors on the same screen.
- **Choose and refine** a direction, including its branding and theme.
  “I like this one, but make it more like X” should preserve what you chose
  while changing what you asked to change.
- **Try** the selected direction as a rough clickable prototype and refine it
  through feedback before committing to detailed implementation.
- **Carry the choices forward** into a separate process that develops the real
  app and backend, with mocked behavior and open assumptions clearly identified.

Speed matters more than pixel-perfect polish at this stage. The aim is to make
exploring alternatives easy enough that people actually do it, instead of
settling into repeated corrections of the first generated result. Visual review
also checks whether the tool understood the idea: people can correct missing or
misinterpreted intent, not just choose or restyle a direction. Detail fits the
question—lean for flow review, richer when judging branding or visual expression.

For the initial POC, the delivered mockup is one self-contained `.html` file
that opens directly in a browser: no network, server, build or companion files
are needed to try the central task. Optional explainers and decision materials
may accompany it. Broader mockup formats are deferred. This delivery boundary
does not require the smart tool or its authorized presentation adapter to be
offline or single-file.

Amplifier is intended to power the work underneath. Possibly is intended to be a
library-first smart tool: every capability is callable through its public
library, and the default CLI is only a thin adapter with no exclusive
capability. Other agent apps and their own adapters can use that library
without adopting an Amplifier bundle or shelling out to the Possibly CLI.
The caller supplies context and explicitly chooses built-in dashboard,
host-provided UI, or headless presentation. The selected built-in dashboard
automatically starts or updates when material is ready; host UI resources remain
host owned. Service startup, opening a viewer and taking focus follow the host's
explicit permissions. Trying a downloaded mockup does not itself submit
decisions to the caller.
The handoff includes corrected intent and important choices, not just the artifact.
The caller decides how to adopt them into its own vision or contracts; Possibly
does not rewrite or approve those documents. The handoff preserves the selected
experience without dictating how the production app is engineered.

## Project status

Possibly is at the direction-setting stage. This repository contains a draft
vision, four draft behavioral contracts and a draft public API contract; there is no runnable implementation
or installation procedure yet. The flow above describes the intended experience,
not verified capabilities.

- [Vision](docs/VISION.md)
- [Context to Visual Choice contract](contracts/exploration.v1.md)
- [Selected Experience Continuity contract](contracts/selection-continuity.v1.md)
- [Calling Agent Interaction contract](contracts/caller-interaction.v1.md)
- [Dashboard Lifecycle and Human Actions contract](contracts/dashboard-lifecycle.v1.md)
- [Public Interaction API contract — provisional types and caller round trip](contracts/interaction-api.v1.md)

## Help shape it

Bring an app idea and challenge whether the choices are useful. Help distinguish
meaningful experience alternatives, make the prototype loop fast, or connect the
handoff to agentic development. There is room for ideas from UX, frontend
generation and AI tooling.