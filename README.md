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
settling into repeated corrections of the first generated result. Mockup delivery
is not limited to HTML, and the method is not a fixed catalog of app templates.

Amplifier is intended to power the work underneath. Smart-tool packaging is
intended to let other agent apps use the capability without adopting an Amplifier
bundle. The handoff should preserve the selected experience without dictating
how the production app is engineered.

## Project status

Possibly is at the direction-setting stage. This repository contains a draft
vision and two draft behavioral contracts; there is no runnable implementation
or installation procedure yet. The flow above describes the intended experience,
not verified capabilities.

- [Vision](docs/VISION.md)
- [Context to Visual Choice contract](contracts/exploration.v1.md)
- [Selected Experience Continuity contract](contracts/selection-continuity.v1.md)

## Help shape it

Bring an app idea and challenge whether the choices are useful. Help distinguish
meaningful experience alternatives, make the prototype loop fast, or connect the
handoff to agentic development. There is room for ideas from UX, frontend
generation and AI tooling.