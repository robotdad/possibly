# Possibly — Vision (DRAFT)

*Choose before you build.*

*Written for people shaping apps and the agent applications helping them.
The specific behavioral promises live in `../contracts/`.*

## What Possibly is

Possibly makes choosing an app experience a natural part of agentic development,
before the first generated implementation becomes the design by default. A person
sees different ways their app can work, recognizes the tradeoffs, and chooses what
is worth trying rather than repeatedly correcting an experience they never chose.

The starting point is the context they already have: a conversation, pointers to
materials describing the idea, or both. Screenshots, branding and UI preferences
are welcome but not required. Possibly separates what is known from what is open,
then derives experience directions—visually expressed alternatives for how people
accomplish their tasks. It does not require someone to invent those alternatives
or fit their idea into a fixed app catalog.

The person compares lightweight mockups before investing in a click-through,
a rough interactive approximation of a selected direction. Look and feel belong
in the exploration too: “this one, but more like that reference” is a useful
instruction. The person can refine an approach without losing what they liked,
or return to another direction when trying it changes their mind. Visual review
also tests the tool's interpreted brief. When it reveals omitted or misunderstood
intent and the correction is accepted, the identified brief revision and all
affected current directions or artifacts are updated or visibly superseded.

Possibly is an Amplifier-powered smart tool: a capability another agent application
can call without requiring its users to adopt an Amplifier app or load its internal
agents. The calling app supplies context and presents results; the person chooses
the experience; a separate development process builds the real app and backend.
The tool makes accepted corrections and important changes visible to that caller
and to handoff consumers, but neither edits nor approves the caller's own vision
or contracts. The caller decides adoption through its own process.

The initial POC delivers one self-contained HTML mockup file that opens directly
in a browser, with no network, server, build or companion files needed to try it.
Optional explainers and decision materials may accompany it. Broader mockup
formats are deferred. This is the delivered mockup, not a requirement that the
smart tool or live dashboard be single-file or offline. Trying the standalone
mockup does not itself submit decisions to the caller.

The selected experience and its decision record connect exploration to development.
They distinguish intended interaction from fake behavior and unresolved assumptions,
so a fresh development agent can continue without the person repeating the design
conversation. The chosen experience—not incidental prototype code—is the shared
reference that guides both the person and the development process.

## Principles

### 1. **Choice precedes commitment.**

Useful visual alternatives come before default investment in a clickable prototype.
Selection focuses effort without making rejected directions unreachable.

### 2. **Alternatives change something that matters.**

Experience exploration reveals different ways to accomplish a task, not only
different colors on the same screen. Branding exploration is valuable in its own
right and is distinguishable from a change in task approach.

### 3. **Existing context is enough to begin.**

People do not rewrite their ideas into a special form merely to use the tool.
Absent UI guidance leaves room to explore; it does not become a fabricated requirement.

### 4. **Refinement preserves deliberate choices.**

References and feedback identify what to change and what to retain. A restyling
does not silently replace the selected interaction, and an interaction change
does not silently discard the chosen visual direction.

### 5. **Approximation serves learning.**

Mockups are detailed enough for the question being asked and cheap enough to
revise. A lean flow review and a legitimate visual or branding review call for
different representations and fidelity; neither requires wireframes everywhere.
Fake data and behavior are visible as such; visual polish is not evidence of
functioning software.

### 6. **The experience survives its rendering and its handoff.**

For the initial POC, a standalone self-contained HTML file is the delivered
mockup, not the product boundary. A downstream process receives the current,
corrected intent, important changes, choices and uncertainties it needs, without
inheriting a mandated production architecture or pretending prototype code is
production-ready.

## What this deliberately resists

- A fixed catalog of app templates that limits what someone may describe.
- Several fully interactive apps built before the person chooses a direction.
- A full visual editor or pixel-matching engine as a prerequisite to exploration.
- A replacement for the production app/backend development process.
- Claims of universal coverage or time savings based on an attractive demo alone.

## How you can tell it is working

- A person identifies a useful experience choice they had not already specified.
- A person understands the alternatives from their visuals, not a sales explanation.
- A person spots omitted or misunderstood intent in a visual, corrects it, and
  recognizes that correction in the revised brief and experience.
- A person says “more like this” and recognizes both the requested change and
  the important parts that stayed intact.
- A person learns something from trying the selected interaction and can revise it
  without an interruption that defeats the purpose of exploring.
- A fresh development agent preserves selected interactions without asking the
  person to explain the experience again.
- A caller uses the same method on unrelated ideas without bespoke art direction.

For example, someone describing a community-garden watering-shift app can see the
difference between people claiming calendar slots and supplying availability for
proposed assignments, without having prescribed either interface. The screens
help them choose between direct choice and coordinated matching. Differently
colored versions of the same calendar offer a useful branding choice, but do not
reveal another way to accomplish the task. Possibly makes that distinction clear
rather than presenting cosmetic variety as experience exploration.

## Changelog

- **2026-09-14** — First draft from the captured working direction; not ratified.
- **2026-09-14** — Clarified that visual review can correct a revisioned
  interpreted brief; representation fidelity follows the review question; caller
  adoption remains caller-owned; and the initial POC mockup is one standalone
  self-contained HTML file, while broader formats are deferred.